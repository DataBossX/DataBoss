"""DataBossX Command Center -- stdlib-only HTTP server.

Zero heavy dependencies on purpose: this must start instantly on Ryan's
Windows box with whatever Python is already installed. Binds to
127.0.0.1 only -- never 0.0.0.0.
"""
import json
import os
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent))

import actions
import ai_router
import db
import discovery
import identity
import next_move
import workers

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = Path(os.environ.get("DATABOSSX_DB_PATH", str(BASE_DIR / "runtime" / "databossx.db")))
SERVER_PATH = Path(__file__).resolve()

_IDENTITY = None

_conn = None
_conn_lock = threading.Lock()


def get_conn():
    global _conn
    if _conn is None:
        with _conn_lock:
            if _conn is None:
                _conn = db.connect(DB_PATH)
                db.init_db(_conn)
    return _conn


def _discover_and_cache():
    conn = get_conn()
    lanes = discovery.discover_all()
    for lane, projects in lanes.items():
        discovery.cache_projects(conn, lane, projects)
    return lanes


def _write_receipt(conn, task, lane, project, action_result: "actions.ActionResult", model_tool: str):
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        """
        INSERT INTO receipts (id, job_id, task, lane, project, action, start_ts, end_ts,
            inputs_json, output_summary, files_changed_json, model_tool, tests_json, warnings_json, rollback)
        VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()), task, lane, project, task, now, now,
            json.dumps({}), action_result.summary, json.dumps(action_result.files_changed),
            model_tool, json.dumps({"acceptance": actions.REGISTRY[task].acceptance_test}),
            json.dumps(action_result.warnings), "No destructive writes; safe to delete files_changed.",
        ),
    )
    conn.commit()


class Handler(BaseHTTPRequestHandler):
    server_version = "DataBossXCommandCenter/0.1"

    def log_message(self, fmt, *args):  # quiet default access log noise
        pass

    def _send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str):
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self._send_json({"error": "not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}

    def _log_internal_error(self, exc: Exception) -> str:
        """Full traceback goes to the server's own stdout/log only. The
        browser gets a bounded message plus an ID to correlate against
        runtime\\server.log -- never a stack trace or local path dump."""
        error_id = str(uuid.uuid4())[:8]
        print(f"[error {error_id}] {exc}\n{traceback.format_exc()}", file=sys.stderr)
        return error_id

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/" or path == "/index.html":
                self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            elif path == "/static/app.css":
                self._send_file(STATIC_DIR / "app.css", "text/css; charset=utf-8")
            elif path == "/static/app.js":
                self._send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
            elif path == "/static/logo.svg":
                self._send_file(STATIC_DIR / "logo.svg", "image/svg+xml")
            elif path == "/api/health":
                self._handle_health()
            elif path == "/api/state":
                self._handle_state()
            elif path == "/api/jobs":
                self._handle_jobs()
            elif path == "/api/receipts":
                self._handle_receipts()
            elif path == "/api/workers":
                self._handle_workers()
            elif path == "/api/setup":
                self._handle_get_setup()
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: broad-except - never crash the loop
            error_id = self._log_internal_error(exc)
            self._send_json({"error": "internal_error", "error_id": error_id}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_json_body()
            if path == "/api/actions/run":
                self._handle_run_action(body)
            elif path == "/api/command":
                self._handle_command(body)
            elif path == "/api/mode":
                self._handle_set_mode(body)
            elif path == "/api/discover":
                self._send_json({"lanes": _discover_and_cache()})
            elif path == "/api/setup/confirm":
                self._handle_confirm_setup(body)
            else:
                self._send_json({"error": "not found"}, 404)
        except actions.ActionRefused as refused:
            self._send_json({"ok": False, "refused": True, "reason": str(refused)}, 403)
        except Exception as exc:  # noqa: broad-except
            error_id = self._log_internal_error(exc)
            self._send_json({"error": "internal_error", "error_id": error_id}, 500)

    # ------------------------------------------------------------------
    def _handle_health(self):
        import hashlib
        payload = {"status": "ok", "version": "0.1.0"}
        if _IDENTITY is not None:
            # Non-secret fingerprint only -- lets a caller correlate this
            # response with a specific identity.json without the raw
            # instance_id (nonce) ever appearing in an HTTP response.
            fingerprint = hashlib.sha256(_IDENTITY["instance_id"].encode()).hexdigest()[:12]
            payload.update({
                "pid": _IDENTITY["pid"],
                "port": _IDENTITY["port"],
                "instance_fingerprint": fingerprint,
                "started_at": _IDENTITY["started_at"],
            })
        self._send_json(payload)

    def _handle_state(self):
        conn = get_conn()
        lanes = _discover_and_cache()
        mode = db.get_setting(conn, "ai_mode", ai_router.DEFAULT_MODE)
        move = next_move.next_best_move(lanes)
        local_model = ai_router.detect_local_model()
        recent_receipts = [
            dict(r) for r in conn.execute(
                "SELECT * FROM receipts ORDER BY end_ts DESC LIMIT 8"
            ).fetchall()
        ]
        active_jobs = [
            dict(r) for r in conn.execute(
                "SELECT * FROM jobs WHERE status = 'running' ORDER BY started_at DESC"
            ).fetchall()
        ]
        self._send_json({
            "lanes": lanes,
            "next_best_move": move,
            "ai_mode": mode,
            "sandbox_mode": os.environ.get("DATABOSSX_SANDBOX_MODE", "0") == "1",
            "setup_confirmed": bool(db.get_setting(conn, "setup_confirmed", False)),
            "local_model": local_model,
            "recent_receipts": recent_receipts,
            "active_jobs": active_jobs,
            "actions_available": [
                {"key": k, "label": v.label, "cost_class": v.cost_class}
                for k, v in actions.REGISTRY.items()
            ],
            "server_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    def _handle_jobs(self):
        conn = get_conn()
        rows = [dict(r) for r in conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 50").fetchall()]
        self._send_json({"jobs": rows})

    def _handle_receipts(self):
        conn = get_conn()
        rows = [dict(r) for r in conn.execute("SELECT * FROM receipts ORDER BY end_ts DESC LIMIT 50").fetchall()]
        self._send_json({"receipts": rows})

    def _handle_workers(self):
        conn = get_conn()
        self._send_json({
            "owned": workers.list_databossx_workers(conn),
            "observed": workers.list_observed_processes(),
        })

    def _handle_get_setup(self):
        conn = get_conn()
        confirmed = db.get_setting(conn, "setup_confirmed", False)
        self._send_json({
            "setup_confirmed": bool(confirmed),
            "sandbox_mode": os.environ.get("DATABOSSX_SANDBOX_MODE", "0") == "1",
            "read_roots": dict(discovery.DEFAULT_ROOTS),
            "write_root_pattern": "<project>/" + discovery.WORKING_SUBDIR,
            "note": (
                "Read-only actions work before confirmation. Any action that "
                "writes to disk (e.g. Build Worklist) is refused until you "
                "confirm these roots are correct via POST /api/setup/confirm."
            ),
        })

    def _handle_confirm_setup(self, body: dict):
        conn = get_conn()
        db.set_setting(conn, "setup_confirmed", True)
        self._send_json({"ok": True, "setup_confirmed": True})

    def _handle_run_action(self, body: dict):
        task_key = body.get("task")
        project_path = body.get("project_path")
        lane = body.get("lane")
        project = body.get("project", "")
        if not task_key or not project_path:
            self._send_json({"ok": False, "error": "task and project_path are required"}, 400)
            return
        if lane not in discovery.DEFAULT_ROOTS:
            self._send_json({
                "ok": False, "refused": True,
                "reason": f"lane must be one of {sorted(discovery.DEFAULT_ROOTS)}; got {lane!r}",
            }, 403)
            return
        conn = get_conn()
        setup_confirmed = bool(db.get_setting(conn, "setup_confirmed", False))
        job_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        spec = actions.REGISTRY.get(task_key)
        cost_class = spec.cost_class if spec else "FREE"
        conn.execute(
            "INSERT INTO jobs (id, task, lane, project, status, cost_class, created_at, started_at, inputs_json, attempts, max_attempts) "
            "VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?, 1, ?)",
            (job_id, task_key, lane, project, cost_class, now, now, json.dumps(body), spec.max_attempts if spec else 1),
        )
        conn.commit()
        try:
            result = actions.run_action(
                task_key, {"project_path": project_path, **body.get("inputs", {})},
                lane=lane, setup_confirmed=setup_confirmed,
            )
        except actions.ActionRefused:
            conn.execute("UPDATE jobs SET status='refused', ended_at=? WHERE id=?", (now, job_id))
            conn.commit()
            raise
        except Exception as exc:  # noqa: broad-except
            conn.execute(
                "UPDATE jobs SET status='failed', ended_at=?, error=? WHERE id=?",
                (time.strftime("%Y-%m-%dT%H:%M:%S"), str(exc), job_id),
            )
            conn.commit()
            error_id = self._log_internal_error(exc)
            self._send_json({"ok": False, "error": "internal_error", "error_id": error_id}, 500)
            return
        ended = time.strftime("%Y-%m-%dT%H:%M:%S")
        conn.execute(
            "UPDATE jobs SET status='done', ended_at=?, output_json=? WHERE id=?",
            (ended, json.dumps(result.output), job_id),
        )
        conn.commit()
        _write_receipt(conn, task_key, lane, project, result, "deterministic")
        self._send_json({
            "ok": result.ok, "summary": result.summary, "output": result.output,
            "files_changed": result.files_changed, "warnings": result.warnings, "job_id": job_id,
        })

    def _handle_command(self, body: dict):
        text = (body.get("text") or "").strip().lower()
        intent = "unknown"
        proposed_action = None
        approval = "REQUIRED"
        for key, spec in actions.REGISTRY.items():
            if key.replace("_", " ") in text or spec.label.lower() in text:
                intent = key
                proposed_action = key
                approval = "ONE_CLICK" if spec.write_scope != "none" or True else "AUTO"
                break
        self._send_json({
            "interpreted_request": text,
            "intent": intent,
            "proposed_action": proposed_action,
            "required_approval": approval,
            "note": "Typed commands map to the same bounded action registry as the buttons -- nothing runs without an explicit action key.",
        })

    def _handle_set_mode(self, body: dict):
        mode = body.get("mode", ai_router.DEFAULT_MODE)
        if mode not in ai_router.MODES:
            self._send_json({"ok": False, "error": f"unknown mode {mode}"}, 400)
            return
        conn = get_conn()
        db.set_setting(conn, "ai_mode", mode)
        self._send_json({"ok": True, "mode": mode})


def find_free_port(preferred: int) -> int:
    import socket
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free loopback port found")


def _acquire_single_instance_lock() -> Path:
    """Refuse to start a second instance against the same runtime dir --
    two writers on one SQLite file is exactly the collision this app must
    never create.

    Uses identity.identity_status() -- the same validator START/STOP/
    REPAIR/DIAGNOSTICS use -- instead of a bare PID-alive check. A PID
    that is alive but does not match our recorded identity (creation
    time, executable, server path, runtime dir) is a reused PID, not a
    running instance of us, and must not block startup.
    """
    runtime_dir = DB_PATH.parent
    runtime_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = runtime_dir / "identity.json"
    status, existing = identity.identity_status(
        receipt_path, expect_server_path=SERVER_PATH, expect_runtime_dir=runtime_dir
    )
    if status == identity.RUNNING:
        raise RuntimeError(
            f"DataBossX Command Center is already running (PID {existing['pid']}, "
            f"port {existing['port']}). Close it first, or run 00_STOP_DATABOSSX.bat."
        )
    # ABSENT / STALE / MALFORMED / MISMATCHED all mean "not verifiably us" --
    # safe to reclaim the receipt file without touching whatever PID (if
    # any) it names.
    identity.clear_identity(receipt_path)
    return receipt_path


def main():
    global _IDENTITY
    preferred = int(os.environ.get("DATABOSSX_PORT", "8765"))
    port = find_free_port(preferred)
    receipt_path = _acquire_single_instance_lock()
    get_conn()  # init DB eagerly so startup errors surface immediately
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    # Authoritative identity+port record for launchers -- the .bat scripts
    # must never guess/hard-code a port, since find_free_port() may have
    # moved on from the preferred one.
    _IDENTITY = identity.build_identity(port, SERVER_PATH, DB_PATH.parent)
    identity.write_identity_atomic(_IDENTITY, receipt_path)
    port_path = DB_PATH.parent / "port.txt"
    port_path.write_text(str(port))
    print(f"DataBossX Command Center running at http://127.0.0.1:{port} (pid {os.getpid()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        identity.clear_identity(receipt_path)
        port_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
