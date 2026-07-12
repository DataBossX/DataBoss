import datetime as dt
import json
import sqlite3
from pathlib import Path

import pytest

from databoss_title_factory.auth import (
    AuthenticationError,
    AuthorizationError,
    audit_summary,
    authenticate_session,
    bootstrap_owner,
    create_user,
    hash_password,
    initialize_db,
    login,
    require_permission,
    revoke_session,
    set_project_roles,
    verify_password,
)
from databoss_title_factory.cli import EXIT_OK, main


OWNER_PASSWORD = "Local-Primary-Strong-482!"
USER_PASSWORD = "Local-User-Strong-739!"


def _owner(database: Path, project: str = "project-a") -> str:
    initialize_db(database)
    bootstrap_owner(database, "owner", OWNER_PASSWORD, project)
    return login(database, "owner", OWNER_PASSWORD)


def test_password_hash_uses_random_salt_and_constant_time_verification():
    first = hash_password(OWNER_PASSWORD)
    second = hash_password(OWNER_PASSWORD)
    assert first != second
    assert OWNER_PASSWORD not in first
    assert verify_password(OWNER_PASSWORD, first)
    assert not verify_password("wrong password", first)
    assert not verify_password(OWNER_PASSWORD, "malformed")


def test_login_stores_only_token_hash_and_audits_success_and_failure(tmp_path: Path):
    database = tmp_path / "auth.sqlite3"
    _owner(database)
    with pytest.raises(AuthenticationError):
        login(database, "owner", "incorrect")

    with sqlite3.connect(database) as connection:
        password_hash = connection.execute(
            "SELECT password_hash FROM users WHERE username='owner'"
        ).fetchone()[0]
        stored_tokens = [
            row[0] for row in connection.execute("SELECT token_hash FROM sessions").fetchall()
        ]
        audit = connection.execute(
            "SELECT outcome, details FROM audit_events WHERE action='login' ORDER BY id"
        ).fetchall()
    assert OWNER_PASSWORD not in password_hash
    assert all(len(value) == 64 for value in stored_tokens)
    assert [row[0] for row in audit][-2:] == ["success", "failure"]
    assert all("password" not in json.loads(row[1]) for row in audit)


def test_session_expiry_and_revocation(tmp_path: Path):
    database = tmp_path / "auth.sqlite3"
    token = _owner(database)
    principal = authenticate_session(database, token)
    assert principal.username == "owner"
    revoke_session(database, token)
    with pytest.raises(AuthenticationError):
        authenticate_session(database, token)

    fresh = login(database, "owner", OWNER_PASSWORD)
    future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)
    with pytest.raises(AuthenticationError):
        authenticate_session(database, fresh, now=future)


def test_permissions_are_project_scoped_and_read_only_cannot_mutate(tmp_path: Path):
    database = tmp_path / "auth.sqlite3"
    owner_token = _owner(database)
    create_user(database, owner_token, "project-a", "reader", USER_PASSWORD, "Read-Only")
    reader_token = login(database, "reader", USER_PASSWORD)

    assert require_permission(database, reader_token, "project-a", "view").username == "reader"
    with pytest.raises(AuthorizationError):
        require_permission(database, reader_token, "project-a", "process")
    with pytest.raises(AuthorizationError):
        require_permission(database, reader_token, "project-b", "view")


def test_role_denial_and_only_owner_can_approve_delivery(tmp_path: Path):
    database = tmp_path / "auth.sqlite3"
    owner_token = _owner(database)
    create_user(database, owner_token, "project-a", "examiner", USER_PASSWORD, "Examiner")
    examiner_token = login(database, "examiner", USER_PASSWORD)

    require_permission(database, examiner_token, "project-a", "approve_title")
    with pytest.raises(AuthorizationError):
        require_permission(database, examiner_token, "project-a", "approve_delivery")
    require_permission(database, owner_token, "project-a", "approve_delivery")


def test_user_role_and_denial_audit_records_are_append_only(tmp_path: Path):
    database = tmp_path / "auth.sqlite3"
    owner_token = _owner(database)
    create_user(database, owner_token, "project-a", "analyst", USER_PASSWORD, "Analyst")
    set_project_roles(database, owner_token, "project-a", "analyst", ["Reviewer"])
    analyst_token = login(database, "analyst", USER_PASSWORD)
    with pytest.raises(AuthorizationError):
        require_permission(database, analyst_token, "project-a", "approve_delivery")

    summary = audit_summary(database)
    actions = {(item["action"], item["outcome"]) for item in summary["events"]}
    assert ("user_create", "success") in actions
    assert ("role_change", "success") in actions
    assert ("authorize:approve_delivery", "denied") in actions
    with sqlite3.connect(database) as connection, pytest.raises(
        sqlite3.IntegrityError, match="append-only"
    ):
        connection.execute("DELETE FROM audit_events")


def test_auth_cli_paths_are_allow_root_constrained_and_login_hides_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    database = tmp_path / "auth.sqlite3"
    monkeypatch.setenv("OWNER_NAME", "owner")
    monkeypatch.setenv("OWNER_SECRET", OWNER_PASSWORD)
    assert main(
        [
            "auth", "init-db", "--database", str(database), "--allow-root", str(tmp_path)
        ]
    ) == EXIT_OK
    assert main(
        [
            "auth", "bootstrap-owner", "--database", str(database), "--project", "project-a",
            "--username-env", "OWNER_NAME", "--password-env", "OWNER_SECRET",
            "--allow-root", str(tmp_path),
        ]
    ) == EXIT_OK
    assert main(
        [
            "auth", "login-check", "--database", str(database), "--username-env", "OWNER_NAME",
            "--password-env", "OWNER_SECRET", "--allow-root", str(tmp_path),
        ]
    ) == EXIT_OK
    output = capsys.readouterr().out
    assert '"status": "AUTHENTICATED"' in output
    assert '"token"' not in output
