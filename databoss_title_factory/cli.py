"""Non-interactive command line interface for the local trusted kernel."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from .auth import (
    AuthError,
    audit_summary,
    authenticate_session,
    bootstrap_owner,
    initialize_db,
    login,
    revoke_session,
    roles_for_user,
)
from .config import ConfigError, load_config
from .core import build_inventory, latest_run, resume_pipeline, run_ocr, start_run
from .security import SecurityError, resolve_allowed_path, verify_signature
from .workbook_audit import audit_workbook, compare_workbooks

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_INPUT_ERROR = 2
EXIT_BLOCKED = 3


def _json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _allowed_roots(values: Sequence[str] | None) -> tuple[Path, ...]:
    roots = tuple(Path(value).expanduser().resolve(strict=True) for value in (values or []))
    return roots or (Path.cwd().resolve(),)


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1024 and 65535")
    return port


def _resolve_project(args: argparse.Namespace) -> Path:
    roots = _allowed_roots(args.allow_root)
    if args.config:
        config_path = resolve_allowed_path(args.config, roots)
        config = load_config(config_path)
        return config.resolve_source_root(tuple(roots))
    if not args.root:
        raise ConfigError("--root or --config is required")
    root = resolve_allowed_path(args.root, roots)
    if not root.is_dir():
        raise SecurityError("project root must be a directory")
    return root


def _auth_database(args: argparse.Namespace, *, must_exist: bool) -> Path:
    return resolve_allowed_path(
        args.database,
        _allowed_roots(args.allow_root),
        must_exist=must_exist,
    )


def _auth_init_db(args: argparse.Namespace) -> int:
    database = _auth_database(args, must_exist=False)
    initialize_db(database)
    _json({"status": "INITIALIZED", "database": str(database)})
    return EXIT_OK


def _explicit_value(cli_value: str | None, environment_name: str | None, label: str) -> str:
    if cli_value is not None:
        return cli_value
    if environment_name and environment_name in os.environ:
        return os.environ[environment_name]
    raise AuthError(f"{label} must be explicitly supplied by argument or environment")


def _auth_bootstrap_owner(args: argparse.Namespace) -> int:
    database = _auth_database(args, must_exist=False)
    username = _explicit_value(args.username, args.username_env, "username")
    password = _explicit_value(args.password, args.password_env, "password")
    user_id = bootstrap_owner(database, username, password, args.project)
    _json(
        {
            "status": "OWNER_BOOTSTRAPPED",
            "database": str(database),
            "project": args.project,
            "username": username,
            "user_id": user_id,
        }
    )
    return EXIT_OK


def _auth_login_check(args: argparse.Namespace) -> int:
    database = _auth_database(args, must_exist=True)
    username = _explicit_value(args.username, args.username_env, "username")
    password = _explicit_value(args.password, args.password_env, "password")
    token = login(database, username, password)
    principal = authenticate_session(database, token)
    result = {
        "status": "AUTHENTICATED",
        "username": principal.username,
        "roles": roles_for_user(database, principal.user_id),
    }
    if args.show_token:
        result["token"] = token
    else:
        revoke_session(database, token)
    _json(result)
    return EXIT_OK


def _auth_audit_summary(args: argparse.Namespace) -> int:
    database = _auth_database(args, must_exist=True)
    _json({"status": "OK", **audit_summary(database, limit=args.limit)})
    return EXIT_OK


def _health(args: argparse.Namespace) -> int:
    optional = ("openpyxl", "PIL", "fitz", "pytesseract")
    result: dict[str, Any] = {
        "status": "HEALTHY",
        "python": sys.version.split()[0],
        "components": {
            name: ("AVAILABLE" if importlib.util.find_spec(name) else "UNAVAILABLE")
            for name in optional
        },
        "network_calls": "NONE",
        "production_release_default": "BLOCKED",
    }
    if args.config:
        roots = _allowed_roots(args.allow_root)
        config = load_config(resolve_allowed_path(args.config, roots))
        result["config"] = {
            "path": str(config.path),
            "external_providers_enabled": config.external_providers_enabled,
            "readiness_default": config.data.get("readiness_default", "BLOCKED"),
        }
    _json(result)
    return EXIT_OK


def _inventory(args: argparse.Namespace) -> int:
    root = _resolve_project(args)
    context = start_run(root)
    rows = build_inventory(context)
    _json(
        {
            "status": "INVENTORIED",
            "run_id": context.run_id,
            "run_dir": context.run_dir,
            "file_count": len(rows),
        }
    )
    return EXIT_OK


def _pipeline(args: argparse.Namespace) -> int:
    root = _resolve_project(args)
    if not 0 <= args.weak_threshold <= 1:
        raise ConfigError("--weak-threshold must be between 0 and 1")
    roots = _allowed_roots(args.allow_root)
    cursor_json = (
        resolve_allowed_path(args.cursor_json, roots) if args.cursor_json else None
    )
    codex_json = (
        resolve_allowed_path(args.codex_json, roots) if args.codex_json else None
    )
    context = latest_run(root) if args.resume else start_run(root)
    result = resume_pipeline(
        context,
        weak_threshold=args.weak_threshold,
        cursor_json=cursor_json,
        codex_json=codex_json,
    )
    _json(result)
    return EXIT_OK if result.get("status") != "PAUSED" else EXIT_BLOCKED


def _ocr(args: argparse.Namespace) -> int:
    root = _resolve_project(args)
    if not 0 <= args.weak_threshold <= 1:
        raise ConfigError("--weak-threshold must be between 0 and 1")
    context = latest_run(root)
    rows = run_ocr(context, weak_threshold=args.weak_threshold)
    _json(
        {
            "status": "READY_FOR_REVIEW",
            "run_id": context.run_id,
            "run_dir": context.run_dir,
            "citation_count": len(rows),
        }
    )
    return EXIT_OK


def _serve(args: argparse.Namespace) -> int:
    roots = _allowed_roots(args.allow_root)
    database_value = args.auth_database or os.environ.get("DATABOSS_AUTH_DB", "")
    if not database_value:
        raise ConfigError("--auth-database or DATABOSS_AUTH_DB is required")
    database = resolve_allowed_path(database_value, roots)
    if not database.is_file():
        raise ConfigError("authentication database does not exist")
    os.environ["DATABOSS_AUTH_DB"] = str(database)
    app_path = Path(__file__).with_name("app.py").resolve(strict=True)
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(args.port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    os.execv(sys.executable, command)
    return EXIT_RUNTIME_ERROR  # pragma: no cover - exec only returns on failure


def _template_qa(args: argparse.Namespace) -> int:
    roots = _allowed_roots(args.allow_root)
    template = resolve_allowed_path(args.template, roots)
    signature = verify_signature(template)
    if not signature.valid or signature.detected_format not in {"xlsx", "xlsm"}:
        _json(
            {
                "status": "BLOCKED",
                "reason": "template signature verification failed",
                "signature": signature,
            }
        )
        return EXIT_BLOCKED
    audit = audit_workbook(template)
    defects: list[str] = []
    if audit["package"]["external_link_parts"]:
        defects.append("external workbook links present")
    comparison = None
    if args.baseline:
        baseline = resolve_allowed_path(args.baseline, roots)
        baseline_signature = verify_signature(baseline)
        if not baseline_signature.valid:
            defects.append("baseline signature verification failed")
        else:
            comparison = compare_workbooks(audit_workbook(baseline), audit)
            if not comparison["preservation_passed"]:
                defects.append("template does not match baseline")
    _json(
        {
            "status": "PASSED" if not defects else "BLOCKED",
            "path": template,
            "sha256": audit["sha256"],
            "sheet_order": audit["sheet_order"],
            "external_links": audit["package"]["external_link_parts"],
            "defects": defects,
            "comparison": comparison,
        }
    )
    return EXIT_OK if not defects else EXIT_BLOCKED


def _add_database_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", required=True)
    parser.add_argument("--allow-root", action="append")


def _add_credential_arguments(
    parser: argparse.ArgumentParser,
    *,
    username_environment: str,
    password_environment: str,
) -> None:
    parser.add_argument("--username")
    parser.add_argument("--username-env", default=username_environment)
    parser.add_argument("--password")
    parser.add_argument("--password-env", default=password_environment)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="databoss-title-factory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health = subparsers.add_parser("health", help="report local component availability")
    health.add_argument("--config")
    health.add_argument("--allow-root", action="append")
    health.set_defaults(handler=_health)

    for name, handler in (
        ("inventory", _inventory),
        ("ocr", _ocr),
        ("pipeline", _pipeline),
    ):
        command = subparsers.add_parser(name)
        command.add_argument("--root")
        command.add_argument("--config")
        command.add_argument("--allow-root", action="append")
        command.set_defaults(handler=handler)
        if name in {"ocr", "pipeline"}:
            command.add_argument("--weak-threshold", type=float, default=0.65)
        if name == "pipeline":
            command.add_argument("--resume", action="store_true")
            command.add_argument("--cursor-json")
            command.add_argument("--codex-json")

    serve = subparsers.add_parser("serve", help="run the authenticated local web UI")
    serve.add_argument("--auth-database")
    serve.add_argument("--allow-root", action="append")
    serve.add_argument("--port", type=_port, default=8501)
    serve.set_defaults(handler=_serve)

    template = subparsers.add_parser("template-qa")
    template.add_argument("--template", required=True)
    template.add_argument("--baseline")
    template.add_argument("--allow-root", action="append")
    template.set_defaults(handler=_template_qa)

    auth = subparsers.add_parser("auth", help="manage local authentication")
    auth_commands = auth.add_subparsers(dest="auth_command", required=True)

    auth_init = auth_commands.add_parser("init-db", help="initialize the auth database")
    _add_database_arguments(auth_init)
    auth_init.set_defaults(handler=_auth_init_db)

    bootstrap = auth_commands.add_parser(
        "bootstrap-owner", help="create the first project Owner"
    )
    _add_database_arguments(bootstrap)
    bootstrap.add_argument("--project", required=True)
    _add_credential_arguments(
        bootstrap,
        username_environment="DATABOSS_OWNER_USERNAME",
        password_environment="DATABOSS_OWNER_PASSWORD",
    )
    bootstrap.set_defaults(handler=_auth_bootstrap_owner)

    login_check = auth_commands.add_parser(
        "login-check", help="validate local credentials"
    )
    _add_database_arguments(login_check)
    _add_credential_arguments(
        login_check,
        username_environment="DATABOSS_USERNAME",
        password_environment="DATABOSS_PASSWORD",
    )
    login_check.add_argument(
        "--show-token", action="store_true", help="include a reusable session token in JSON"
    )
    login_check.set_defaults(handler=_auth_login_check)

    audit = auth_commands.add_parser("audit-summary", help="summarize auth audit events")
    _add_database_arguments(audit)
    audit.add_argument("--limit", type=int, default=100)
    audit.set_defaults(handler=_auth_audit_summary)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return int(args.handler(args))
    except (
        AuthError,
        ConfigError,
        SecurityError,
        FileNotFoundError,
        NotADirectoryError,
    ) as exc:
        _json({"status": "INPUT_ERROR", "error": str(exc)})
        return EXIT_INPUT_ERROR
    except Exception as exc:
        _json({"status": "ERROR", "error": str(exc)})
        return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
