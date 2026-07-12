"""Local authentication, project-scoped RBAC, sessions, and audit logging."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROLES = ("Owner", "Examiner", "Reviewer", "Analyst", "Read-Only")
ROLE_PERMISSIONS = {
    "Owner": frozenset(
        {"view", "process", "approve_title", "adjudicate", "manage_users", "approve_delivery"}
    ),
    "Examiner": frozenset({"view", "process", "approve_title"}),
    "Reviewer": frozenset({"view", "process", "adjudicate"}),
    "Analyst": frozenset({"view", "process"}),
    "Read-Only": frozenset({"view"}),
}
ALL_PERMISSIONS = frozenset().union(*ROLE_PERMISSIONS.values())
PASSWORD_SCHEME = "scrypt"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32
DEFAULT_SESSION_TTL = dt.timedelta(hours=8)


class AuthError(ValueError):
    """Base error for local authentication operations."""


class AuthenticationError(AuthError):
    """Credentials or a session could not be authenticated."""


class AuthorizationError(AuthError):
    """An authenticated user lacks a required project permission."""


@dataclass(frozen=True)
class Principal:
    user_id: int
    username: str
    expires_at: str


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _timestamp(value: dt.datetime | None = None) -> str:
    value = value or _utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat()


def _connect(database: str | os.PathLike[str]) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(database))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def initialize_db(database: str | os.PathLike[str]) -> Path:
    """Create or migrate a local authentication database."""
    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_roles (
                user_id INTEGER NOT NULL REFERENCES users(id),
                project TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN
                    ('Owner', 'Examiner', 'Reviewer', 'Analyst', 'Read-Only')),
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, project, role)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY,
                actor TEXT,
                project TEXT,
                action TEXT NOT NULL,
                outcome TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS sessions_token_hash ON sessions(token_hash);
            CREATE INDEX IF NOT EXISTS audit_timestamp ON audit_events(timestamp);
            CREATE TRIGGER IF NOT EXISTS audit_events_no_update
            BEFORE UPDATE ON audit_events BEGIN
                SELECT RAISE(ABORT, 'audit events are append-only');
            END;
            CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
            BEFORE DELETE ON audit_events BEGIN
                SELECT RAISE(ABORT, 'audit events are append-only');
            END;
            """
        )
    return path


def _password_bytes(password: str | bytes) -> bytes:
    return password.encode("utf-8") if isinstance(password, str) else password


def hash_password(password: str) -> str:
    """Hash a password with a fresh random salt using stdlib scrypt."""
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.scrypt(
        _password_bytes(password),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_BYTES,
    )
    return f"{PASSWORD_SCHEME}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time password verification; malformed hashes simply fail."""
    try:
        scheme, n, r, p, salt_hex, expected_hex = encoded.split("$")
        if scheme != PASSWORD_SCHEME:
            return False
        expected = bytes.fromhex(expected_hex)
        actual = hashlib.scrypt(
            _password_bytes(password),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(actual, expected)


def validate_strong_password(password: str, *, username: str = "") -> None:
    """Reject short, common, default, or single-class bootstrap passwords."""
    lowered = password.casefold()
    defaults = {
        "admin",
        "administrator",
        "changeme",
        "changeit",
        "databoss",
        "default",
        "letmein",
        "password",
        "password123",
        "welcome",
    }
    if (
        len(password) < 12
        or lowered in defaults
        or (username and username.casefold() in lowered)
        or not re.search(r"[a-z]", password)
        or not re.search(r"[A-Z]", password)
        or not re.search(r"\d", password)
        or not re.search(r"[^A-Za-z0-9]", password)
    ):
        raise AuthError(
            "password must be at least 12 characters and include upper, lower, "
            "number, and symbol characters; common/default passwords are rejected"
        )


def _audit(
    connection: sqlite3.Connection,
    *,
    actor: str | None,
    project: str | None,
    action: str,
    outcome: str,
    details: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events(actor, project, action, outcome, timestamp, details)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (actor, project, action, outcome, _timestamp(), json.dumps(details or {}, sort_keys=True)),
    )


def bootstrap_owner(
    database: str | os.PathLike[str], username: str, password: str, project: str
) -> int:
    """Create the first account. It must be an explicitly supplied project Owner."""
    if not username.strip() or not project.strip():
        raise AuthError("username and project must be explicit non-empty values")
    validate_strong_password(password, username=username)
    initialize_db(database)
    with _connect(database) as connection:
        if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            raise AuthError("bootstrap is only allowed when no users exist")
        cursor = connection.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
            (username.strip(), hash_password(password), _timestamp()),
        )
        user_id = int(cursor.lastrowid)
        connection.execute(
            "INSERT INTO project_roles(user_id, project, role, created_at) VALUES (?, ?, 'Owner', ?)",
            (user_id, project.strip(), _timestamp()),
        )
        _audit(
            connection,
            actor=username.strip(),
            project=project.strip(),
            action="bootstrap_owner",
            outcome="success",
            details={"role": "Owner"},
        )
    return user_id


def login(
    database: str | os.PathLike[str],
    username: str,
    password: str,
    *,
    ttl: dt.timedelta = DEFAULT_SESSION_TTL,
) -> str:
    """Authenticate and return a new opaque session token to the direct caller."""
    if ttl <= dt.timedelta(0):
        raise AuthError("session TTL must be positive")
    initialize_db(database)
    token: str | None = None
    with _connect(database) as connection:
        row = connection.execute(
            "SELECT id, username, password_hash, active FROM users WHERE username=?",
            (username,),
        ).fetchone()
        valid = bool(row and row["active"] and verify_password(password, row["password_hash"]))
        if not valid:
            _audit(
                connection,
                actor=username or None,
                project=None,
                action="login",
                outcome="failure",
                details={"reason": "invalid_credentials"},
            )
        else:
            token = secrets.token_urlsafe(32)
            now = _utcnow()
            connection.execute(
                """
                INSERT INTO sessions(user_id, token_hash, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (row["id"], _token_hash(token), _timestamp(now), _timestamp(now + ttl)),
            )
            _audit(
                connection,
                actor=row["username"],
                project=None,
                action="login",
                outcome="success",
                details={},
            )
    if token is None:
        raise AuthenticationError("invalid username or password")
    return token


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate_session(
    database: str | os.PathLike[str], token: str, *, now: dt.datetime | None = None
) -> Principal:
    if not token:
        raise AuthenticationError("session is missing")
    with _connect(database) as connection:
        row = connection.execute(
            """
            SELECT users.id AS user_id, users.username, users.active, sessions.expires_at,
                   sessions.revoked_at
            FROM sessions JOIN users ON users.id=sessions.user_id
            WHERE sessions.token_hash=?
            """,
            (_token_hash(token),),
        ).fetchone()
    current = now or _utcnow()
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    if (
        not row
        or not row["active"]
        or row["revoked_at"] is not None
        or dt.datetime.fromisoformat(row["expires_at"]) <= current
    ):
        raise AuthenticationError("session is invalid, expired, or revoked")
    return Principal(int(row["user_id"]), str(row["username"]), str(row["expires_at"]))


def revoke_session(database: str | os.PathLike[str], token: str) -> None:
    with _connect(database) as connection:
        row = connection.execute(
            """
            SELECT sessions.id, users.username FROM sessions
            JOIN users ON users.id=sessions.user_id WHERE sessions.token_hash=?
            """,
            (_token_hash(token),),
        ).fetchone()
        if not row:
            raise AuthenticationError("session is invalid")
        connection.execute(
            "UPDATE sessions SET revoked_at=COALESCE(revoked_at, ?) WHERE id=?",
            (_timestamp(), row["id"]),
        )
        _audit(
            connection,
            actor=row["username"],
            project=None,
            action="logout",
            outcome="success",
            details={},
        )


def roles_for_user(
    database: str | os.PathLike[str], user_id: int, project: str | None = None
) -> list[dict[str, str]]:
    query = "SELECT project, role FROM project_roles WHERE user_id=?"
    parameters: tuple[Any, ...] = (user_id,)
    if project is not None:
        query += " AND project=?"
        parameters += (project,)
    query += " ORDER BY project, role"
    with _connect(database) as connection:
        return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def require_permission(
    database: str | os.PathLike[str], token: str, project: str, permission: str
) -> Principal:
    """Central project authorization check. Denials are always audited."""
    if permission not in ALL_PERMISSIONS:
        raise AuthError(f"unknown permission: {permission}")
    try:
        principal = authenticate_session(database, token)
    except AuthenticationError:
        with _connect(database) as connection:
            _audit(
                connection,
                actor=None,
                project=project,
                action=f"authorize:{permission}",
                outcome="denied",
                details={"reason": "invalid_session"},
            )
        raise
    roles = [item["role"] for item in roles_for_user(database, principal.user_id, project)]
    if not any(permission in ROLE_PERMISSIONS[role] for role in roles):
        with _connect(database) as connection:
            _audit(
                connection,
                actor=principal.username,
                project=project,
                action=f"authorize:{permission}",
                outcome="denied",
                details={"roles": roles},
            )
        raise AuthorizationError(
            f"{principal.username} lacks {permission!r} permission for project {project!r}"
        )
    return principal


def create_user(
    database: str | os.PathLike[str],
    actor_token: str,
    project: str,
    username: str,
    password: str,
    role: str,
) -> int:
    actor = require_permission(database, actor_token, project, "manage_users")
    if role not in ROLES:
        raise AuthError(f"role must be one of: {', '.join(ROLES)}")
    validate_strong_password(password, username=username)
    with _connect(database) as connection:
        cursor = connection.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
            (username.strip(), hash_password(password), _timestamp()),
        )
        user_id = int(cursor.lastrowid)
        connection.execute(
            "INSERT INTO project_roles(user_id, project, role, created_at) VALUES (?, ?, ?, ?)",
            (user_id, project, role, _timestamp()),
        )
        _audit(
            connection,
            actor=actor.username,
            project=project,
            action="user_create",
            outcome="success",
            details={"username": username.strip(), "role": role},
        )
    return user_id


def set_project_roles(
    database: str | os.PathLike[str],
    actor_token: str,
    project: str,
    username: str,
    roles: Iterable[str],
) -> None:
    actor = require_permission(database, actor_token, project, "manage_users")
    selected = tuple(dict.fromkeys(roles))
    if not selected or any(role not in ROLES for role in selected):
        raise AuthError(f"roles must be non-empty and drawn from: {', '.join(ROLES)}")
    with _connect(database) as connection:
        user = connection.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
        if not user:
            raise AuthError("user does not exist")
        connection.execute(
            "DELETE FROM project_roles WHERE user_id=? AND project=?", (user["id"], project)
        )
        connection.executemany(
            "INSERT INTO project_roles(user_id, project, role, created_at) VALUES (?, ?, ?, ?)",
            ((user["id"], project, role, _timestamp()) for role in selected),
        )
        _audit(
            connection,
            actor=actor.username,
            project=project,
            action="role_change",
            outcome="success",
            details={"username": username, "roles": list(selected)},
        )


def audit_summary(
    database: str | os.PathLike[str], *, limit: int = 100
) -> dict[str, Any]:
    if limit < 1 or limit > 10_000:
        raise AuthError("limit must be between 1 and 10000")
    with _connect(database) as connection:
        totals = [
            dict(row)
            for row in connection.execute(
                """
                SELECT action, outcome, COUNT(*) AS count FROM audit_events
                GROUP BY action, outcome ORDER BY action, outcome
                """
            ).fetchall()
        ]
        events = [
            {**dict(row), "details": json.loads(row["details"])}
            for row in connection.execute(
                """
                SELECT id, actor, project, action, outcome, timestamp, details
                FROM audit_events ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        ]
    return {"totals": totals, "events": events}
