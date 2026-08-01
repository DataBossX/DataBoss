"""Minimal PostgreSQL v3 wire-protocol client (standard library only).

No driver is installable in this environment (no PyPI route), and the
single-writer invariant is too important to leave proven only on SQLite. This
speaks enough of the protocol to run the control kernel against a real
PostgreSQL server: startup and authentication, the extended query protocol with
bound parameters, and typed result decoding.

Scope is deliberate. It implements the extended query protocol (Parse/Bind/
Describe/Execute/Sync) so parameters are **never** interpolated into SQL text --
the server binds them, exactly as a real driver would. It does not implement
COPY, cursors, notifications, or binary result formats, none of which the kernel
uses.

Auth: trust (0), cleartext (3), md5 (5), and SASL SCRAM-SHA-256 (10).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import socket
import struct
from typing import Any, Iterable, Optional, Sequence

PROTOCOL_VERSION = 196608  # 3.0

# Type OIDs the control-plane schema can actually produce.
OID_BOOL = 16
OID_INT8 = 20
OID_INT2 = 21
OID_INT4 = 23
OID_TEXT = 25
OID_FLOAT4 = 700
OID_FLOAT8 = 701
OID_VARCHAR = 1043
OID_BPCHAR = 1042
OID_NUMERIC = 1700

_INT_OIDS = {OID_INT2, OID_INT4, OID_INT8}
_FLOAT_OIDS = {OID_FLOAT4, OID_FLOAT8, OID_NUMERIC}


class PgError(Exception):
    """An ErrorResponse from the server, with its SQLSTATE preserved."""

    def __init__(self, fields: dict):
        self.fields = fields
        self.sqlstate = fields.get("C", "")
        self.primary = fields.get("M", "")
        super().__init__(f"{fields.get('S', 'ERROR')}: {self.primary} [{self.sqlstate}]")


class PgIntegrityError(PgError):
    """Constraint violation -- unique, foreign key, check, not-null."""


class PgRaisedError(PgError):
    """A plpgsql ``RAISE EXCEPTION`` -- how this schema enforces its triggers."""


# SQLSTATE class 23 is integrity_constraint_violation.
def _classify(fields: dict) -> PgError:
    state = fields.get("C", "")
    if state.startswith("23"):
        return PgIntegrityError(fields)
    if state == "P0001":  # raise_exception
        return PgRaisedError(fields)
    return PgError(fields)


class Row:
    """Result row supporting both ``row[0]`` and ``row["name"]``."""

    __slots__ = ("_values", "_names", "_index")

    def __init__(self, values: Sequence, names: Sequence[str], index: dict):
        self._values = values
        self._names = names
        self._index = index

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        try:
            return self._values[self._index[key]]
        except KeyError as exc:
            raise KeyError(f"no column named {key!r}") from exc

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return list(self._names)

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def __repr__(self):
        return f"Row({dict(zip(self._names, self._values))!r})"


class _Result:
    """Cursor-shaped result, matching the subset of sqlite3 the kernel uses."""

    def __init__(self, rows: list, rowcount: int):
        self._rows = rows
        self._pos = 0
        self.rowcount = rowcount

    def fetchone(self):
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row

    def fetchall(self):
        rows = self._rows[self._pos:]
        self._pos = len(self._rows)
        return rows

    def close(self):
        self._rows = []


def _pack(tag: Optional[bytes], body: bytes) -> bytes:
    header = struct.pack(">I", len(body) + 4)
    return (tag or b"") + header + body


def _cstr(text: str) -> bytes:
    return text.encode("utf-8") + b"\x00"


class PgConnection:
    """A single synchronous connection. Not thread-safe, by design.

    The kernel gives each thread its own connection so that races are settled by
    the database rather than by a Python lock.
    """

    def __init__(self, host: str, port: int, user: str, database: str,
                 password: Optional[str] = None, timeout: float = 30.0,
                 schema: Optional[str] = None):
        self._sock = socket.create_connection((host, port), timeout)
        self._sock.settimeout(timeout)
        self._buf = b""
        self._closed = False
        self.parameters: dict = {}
        self.transaction_status = b"I"
        self._startup(user, database, password, schema)

    # ------------------------------------------------------------- transport
    def _send(self, data: bytes) -> None:
        self._sock.sendall(data)

    def _recv_exact(self, count: int) -> bytes:
        while len(self._buf) < count:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise ConnectionError("PostgreSQL closed the connection")
            self._buf += chunk
        data, self._buf = self._buf[:count], self._buf[count:]
        return data

    def _read_message(self):
        tag = self._recv_exact(1)
        (length,) = struct.unpack(">I", self._recv_exact(4))
        body = self._recv_exact(length - 4) if length > 4 else b""
        return tag, body

    @staticmethod
    def _parse_error_fields(body: bytes) -> dict:
        fields = {}
        for part in body.split(b"\x00"):
            if part:
                fields[chr(part[0])] = part[1:].decode("utf-8", "replace")
        return fields

    # ------------------------------------------------------------- handshake
    def _startup(self, user: str, database: str, password: Optional[str],
                 schema: Optional[str] = None) -> None:
        params = {"user": user, "database": database, "client_encoding": "UTF8",
                  "application_name": "databossx-command-center"}
        if schema:
            # Pins search_path for the whole session, so every statement lands
            # in the caller's schema without rewriting any SQL.
            params["options"] = f"-csearch_path={schema}"

        body = struct.pack(">I", PROTOCOL_VERSION)
        for param_key, param_value in params.items():
            body += _cstr(param_key) + _cstr(param_value)
        body += b"\x00"
        self._send(_pack(None, body))

        while True:
            tag, body = self._read_message()
            if tag == b"R":
                self._authenticate(body, user, password)
            elif tag == b"S":
                name, _, rest = body.partition(b"\x00")
                self.parameters[name.decode()] = rest.split(b"\x00")[0].decode()
            elif tag == b"K":
                pass  # BackendKeyData; cancellation is not used here
            elif tag == b"Z":
                self.transaction_status = body[:1]
                return
            elif tag == b"E":
                raise _classify(self._parse_error_fields(body))
            elif tag == b"N":
                continue  # NoticeResponse
            else:
                raise PgError({"M": f"unexpected startup message {tag!r}"})

    def _authenticate(self, body: bytes, user: str, password: Optional[str]) -> None:
        (code,) = struct.unpack(">I", body[:4])
        if code == 0:
            return  # trust / already authenticated
        if code == 3:  # cleartext
            secret = self._require_password(password)
            self._send(_pack(b"p", _cstr(secret)))
        elif code == 5:  # md5
            secret = self._require_password(password)
            salt = body[4:8]
            inner = hashlib.md5(f"{secret}{user}".encode()).hexdigest()
            digest = "md5" + hashlib.md5(inner.encode() + salt).hexdigest()
            self._send(_pack(b"p", _cstr(digest)))
        elif code == 10:  # SASL
            self._scram(body[4:], self._require_password(password))
        else:
            raise PgError({"M": f"unsupported authentication method {code}"})

    @staticmethod
    def _require_password(password: Optional[str]) -> str:
        """Return the password, or refuse. Narrows Optional for callers."""
        if password is None:
            raise PgError({"M": "server requested a password but none was supplied"})
        return password

    def _scram(self, body: bytes, password: str) -> None:
        mechanisms = [m.decode() for m in body.split(b"\x00") if m]
        if "SCRAM-SHA-256" not in mechanisms:
            raise PgError({"M": f"no supported SASL mechanism in {mechanisms}"})

        nonce = base64.b64encode(os.urandom(18)).decode()
        client_first_bare = f"n=,r={nonce}"
        initial = b"n,," + client_first_bare.encode()
        self._send(_pack(b"p", _cstr("SCRAM-SHA-256") + struct.pack(">I", len(initial)) + initial))

        tag, resp = self._read_message()
        if tag == b"E":
            raise _classify(self._parse_error_fields(resp))
        (code,) = struct.unpack(">I", resp[:4])
        if code != 11:
            raise PgError({"M": f"expected SASLContinue, got {code}"})
        server_first = resp[4:].decode()
        attrs = dict(part.split("=", 1) for part in server_first.split(","))
        salt = base64.b64decode(attrs["s"])
        iterations = int(attrs["i"])
        server_nonce = attrs["r"]
        if not server_nonce.startswith(nonce):
            raise PgError({"M": "SCRAM server nonce does not extend the client nonce"})

        salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
        client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
        stored_key = hashlib.sha256(client_key).digest()
        final_bare = f"c=biws,r={server_nonce}"
        auth_message = f"{client_first_bare},{server_first},{final_bare}".encode()
        client_sig = hmac.new(stored_key, auth_message, hashlib.sha256).digest()
        proof = base64.b64encode(bytes(a ^ b for a, b in zip(client_key, client_sig))).decode()
        self._send(_pack(b"p", f"{final_bare},p={proof}".encode()))

        while True:
            tag, resp = self._read_message()
            if tag == b"E":
                raise _classify(self._parse_error_fields(resp))
            if tag == b"R":
                (code,) = struct.unpack(">I", resp[:4])
                if code == 12:      # SASLFinal
                    continue
                if code == 0:       # authentication OK
                    return
            elif tag in (b"S", b"K", b"N"):
                continue
            elif tag == b"Z":
                self.transaction_status = resp[:1]
                return

    # --------------------------------------------------------------- queries
    @staticmethod
    def _encode_param(value: Any) -> Optional[bytes]:
        if value is None:
            return None
        if isinstance(value, bool):
            return b"true" if value else b"false"
        if isinstance(value, bytes):
            return b"\\x" + value.hex().encode()
        return str(value).encode("utf-8")

    @staticmethod
    def _decode(value: Optional[bytes], oid: int):
        if value is None:
            return None
        if oid in _INT_OIDS:
            return int(value)
        if oid in _FLOAT_OIDS:
            return float(value)
        if oid == OID_BOOL:
            return value == b"t"
        return value.decode("utf-8")

    def execute(self, sql: str, params: Iterable = ()) -> _Result:
        """Run one statement via the extended protocol.

        Parameters are bound by the server. They are never substituted into the
        SQL text, so this cannot be a SQL-injection vector.
        """
        if self._closed:
            raise PgError({"M": "connection is closed"})
        values = list(params)

        body = _cstr("") + _cstr(sql) + struct.pack(">h", 0)
        out = _pack(b"P", body)

        bind = _cstr("") + _cstr("") + struct.pack(">h", 0) + struct.pack(">h", len(values))
        for value in values:
            encoded = self._encode_param(value)
            if encoded is None:
                bind += struct.pack(">i", -1)
            else:
                bind += struct.pack(">i", len(encoded)) + encoded
        bind += struct.pack(">h", 0)
        out += _pack(b"B", bind)
        out += _pack(b"D", b"P" + _cstr(""))
        out += _pack(b"E", _cstr("") + struct.pack(">I", 0))
        out += _pack(b"S", b"")
        self._send(out)

        names: list = []
        oids: list = []
        index: dict = {}
        rows: list = []
        rowcount = -1
        error: Optional[PgError] = None

        while True:
            tag, body = self._read_message()
            if tag == b"T":  # RowDescription
                (count,) = struct.unpack(">h", body[:2])
                offset = 2
                names, oids, index = [], [], {}
                for position in range(count):
                    end = body.index(b"\x00", offset)
                    name = body[offset:end].decode()
                    offset = end + 1
                    _table, _col, type_oid, _len, _mod, _fmt = struct.unpack(
                        ">IhIhih", body[offset:offset + 18])
                    offset += 18
                    names.append(name)
                    oids.append(type_oid)
                    index[name] = position
            elif tag == b"D":  # DataRow
                (count,) = struct.unpack(">h", body[:2])
                offset = 2
                values = []
                for position in range(count):
                    (length,) = struct.unpack(">i", body[offset:offset + 4])
                    offset += 4
                    if length == -1:
                        values.append(None)
                    else:
                        values.append(self._decode(body[offset:offset + length], oids[position]))
                        offset += length
                rows.append(Row(values, names, index))
            elif tag == b"C":  # CommandComplete
                parts = body.split(b"\x00")[0].decode().split()
                if parts:
                    try:
                        rowcount = int(parts[-1])
                    except ValueError:
                        rowcount = -1
            elif tag == b"E":
                error = _classify(self._parse_error_fields(body))
            elif tag == b"Z":  # ReadyForQuery
                self.transaction_status = body[:1]
                break
            elif tag in (b"1", b"2", b"n", b"s", b"N", b"t", b"I"):
                continue  # Parse/Bind complete, NoData, notices, empty query
            else:
                continue

        if error is not None:
            raise error
        if rowcount < 0:
            rowcount = len(rows)
        return _Result(rows, rowcount)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._send(_pack(b"X", b""))
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass


def connect(dsn: str, timeout: float = 30.0) -> PgConnection:
    """Connect from a ``postgresql://user:pass@host:port/database`` URL.

    A ``?schema=NAME`` query parameter pins ``search_path`` for the session,
    which is how the test suite isolates concurrent runs without needing a
    separate database per test.
    """
    from urllib.parse import parse_qs, unquote, urlparse

    parsed = urlparse(dsn)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ValueError(f"not a PostgreSQL DSN: {dsn!r}")
    schema_values = parse_qs(parsed.query).get("schema") or []
    schema: Optional[str] = schema_values[0] if schema_values else None
    return PgConnection(
        host=parsed.hostname or "127.0.0.1",
        port=parsed.port or 5432,
        user=unquote(parsed.username or "postgres"),
        database=(parsed.path or "/postgres").lstrip("/") or "postgres",
        password=unquote(parsed.password) if parsed.password else None,
        timeout=timeout,
        schema=schema,
    )
