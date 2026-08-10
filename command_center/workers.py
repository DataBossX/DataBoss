"""AI & Workers observation.

Distinguishes DataBossX-owned workers (recorded in our own registry table
with a launch marker we control) from merely-observed processes on the
box. We never auto-kill anything we cannot prove we own.
"""
import subprocess
import time

OBSERVE_KEYWORDS = ("python", "powershell", "ollama", "claude", "codex", "cursor", "node")


def list_databossx_workers(conn) -> list:
    rows = conn.execute("SELECT * FROM workers ORDER BY start_time DESC").fetchall()
    return [dict(r) for r in rows]


def register_worker(conn, pid: int, task: str, model: str = "deterministic") -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        """
        INSERT INTO workers (pid, owner, task, model, start_time, heartbeat, status, idle_seconds, retry_count)
        VALUES (?, 'databossx', ?, ?, ?, ?, 'running', 0, 0)
        ON CONFLICT(pid) DO UPDATE SET task=excluded.task, model=excluded.model,
            heartbeat=excluded.heartbeat, status='running'
        """,
        (pid, task, model, now, now),
    )
    conn.commit()


def mark_worker_done(conn, pid: int) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        "UPDATE workers SET status = 'done', heartbeat = ? WHERE pid = ?", (now, pid)
    )
    conn.commit()


def list_observed_processes() -> list:
    """Best-effort process listing via `ps`. Read-only, no assumptions of
    ownership -- everything here is labeled OBSERVED, never auto-stopped."""
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,comm,etimes"], capture_output=True, text=True, timeout=5
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    observed = []
    for line in out.stdout.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, comm, etimes = parts
        lower = comm.lower()
        if any(k in lower for k in OBSERVE_KEYWORDS):
            observed.append({
                "pid": int(pid),
                "name": comm,
                "uptime_seconds": int(etimes) if etimes.isdigit() else None,
                "ownership": "OBSERVED_NOT_OWNED",
            })
    return observed


def stop_databossx_worker(conn, pid: int, registered_pids: set) -> bool:
    """Only ever stops a PID that our own registry recorded. Refuses
    everything else -- no name-matching kill."""
    if pid not in registered_pids:
        raise PermissionError(
            f"Refusing to stop PID {pid}: not in the DataBossX worker registry."
        )
    mark_worker_done(conn, pid)
    return True
