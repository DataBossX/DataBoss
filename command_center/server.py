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
import next_move
import workers

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = Path(os.environ.get("DATABOSSX_DB_PATH", str(BASE_DIR / "runtime" / "databossx.db")))

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
                self._send_json({"status": "ok", "version": "0.1.0"})
            elif path == "/api/state":
                self._handle_state()
            elif path == "/api/jobs":
                self._handle_jobs()
            elif path == "/api/receipts":
                self._handle_receipts()
            elif path == "/api/workers":
                self._handle_workers()
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: broad-except - never crash the loop
            self._send_json({"error": str(exc), "trace": traceback.format_exc()}, 500)

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
            else:
                self._send_json({"error": "not found"}, 404)
        except actions.ActionRefused as refused:
            self._send_json({"ok": False, "refused": True, "reason": str(refused)}, 403)
        except Exception as exc:  # noqa: broad-except
            self._send_json({"error": str(exc), "trace": traceback.format_exc()}, 500)

    # ------------------------------------------------------------------
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

    def _handle_run_action(self, body: dict):
        task_key = body.get("task")
        project_path = body.get("project_path")
        lane = body.get("lane", "any")
        project = body.get("project", "")
        if not task_key or not project_path:
            self._send_json({"ok": False, "error": "task and project_path are required"}, 400)
            return
        conn = get_conn()
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
            result = actions.run_action(task_key, {"project_path": project_path, **body.get("inputs", {})})
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
            self._send_json({"ok": False, "error": str(exc)}, 500)
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
    never create."""
    lock_path = DB_PATH.parent / "databossx.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().strip())
            os.kill(pid, 0)  # raises OSError if the PID is not alive
            raise RuntimeError(
                f"DataBossX Command Center is already running (PID {pid}). "
                "Close it first, or run 00_STOP_DATABOSSX.bat."
            )
        except (ValueError, ProcessLookupError, OSError):
            pass  # stale lock from a crashed run -- safe to reclaim
    lock_path.write_text(str(os.getpid()))
    return lock_path


def main():
    preferred = int(os.environ.get("DATABOSSX_PORT", "8765"))
    port = find_free_port(preferred)
    lock_path = _acquire_single_instance_lock()
    get_conn()  # init DB eagerly so startup errors surface immediately
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"DataBossX Command Center running at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
