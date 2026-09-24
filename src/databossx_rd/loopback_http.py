"""127.0.0.1-only HTTP client. Cloud hosts, redirects, and writes are rejected."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .constants import LOOPBACK_HOST, UNKNOWN

Transport = Callable[[str, str, Optional[bytes], Mapping[str, str]], "HttpResult"]


class LoopbackHttpError(Exception):
    """Raised when a request violates the loopback/read-only policy."""


@dataclass(frozen=True)
class HttpResult:
    ok: bool
    url: str
    status: Any = UNKNOWN
    headers: dict[str, str] = field(default_factory=dict)
    body_text: Any = UNKNOWN
    json_body: Any = UNKNOWN
    error: Any = UNKNOWN

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "url": self.url,
            "status": self.status,
            "headers": dict(self.headers),
            "json": self.json_body,
            "error": self.error,
        }


class _FailClosedRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        parsed = urlparse(newurl)
        if parsed.hostname != LOOPBACK_HOST:
            raise LoopbackHttpError(
                f"redirect_to_non_loopback:{parsed.hostname or UNKNOWN}"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def assert_loopback_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise LoopbackHttpError(f"unsupported_scheme:{parsed.scheme or UNKNOWN}")
    if parsed.hostname != LOOPBACK_HOST:
        raise LoopbackHttpError(f"non_loopback_host:{parsed.hostname or UNKNOWN}")
    if parsed.username or parsed.password:
        raise LoopbackHttpError("url_userinfo_forbidden")


def assert_allowed_path(method: str, path: str, allowed: set[tuple[str, str]]) -> None:
    normalized = path.split("?", 1)[0] or "/"
    if (method.upper(), normalized) not in allowed:
        raise LoopbackHttpError(f"path_not_allowlisted:{method.upper()} {normalized}")


def _decode_body(raw: bytes) -> tuple[Any, Any]:
    if not raw:
        return "", UNKNOWN
    text = raw.decode("utf-8", errors="replace")
    try:
        return text, json.loads(text)
    except json.JSONDecodeError:
        return text, UNKNOWN


def _header_map(headers: Mapping[str, str]) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in {"authorization", "cookie", "set-cookie", "x-n8n-api-key"}:
            safe[key] = "REDACTED"
        else:
            safe[key] = value
    return safe


def default_transport(
    method: str,
    url: str,
    body: Optional[bytes],
    headers: Mapping[str, str],
    timeout: float = 2.0,
) -> HttpResult:
    assert_loopback_url(url)
    request = Request(url=url, data=body, method=method.upper())
    for key, value in headers.items():
        request.add_header(key, value)
    opener = build_opener(_FailClosedRedirectHandler)
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
            text, payload = _decode_body(raw)
            return HttpResult(
                ok=200 <= int(response.status) < 300,
                url=url,
                status=int(response.status),
                headers=_header_map(response.headers),
                body_text=text,
                json_body=payload,
                error=UNKNOWN,
            )
    except LoopbackHttpError as exc:
        return HttpResult(ok=False, url=url, error=str(exc))
    except HTTPError as exc:
        raw = exc.read() if exc.fp is not None else b""
        text, payload = _decode_body(raw)
        return HttpResult(
            ok=False,
            url=url,
            status=int(exc.code),
            headers=_header_map(exc.headers or {}),
            body_text=text,
            json_body=payload,
            error=f"http_error:{exc.code}",
        )
    except URLError as exc:
        return HttpResult(
            ok=False,
            url=url,
            error=f"unreachable:{exc.reason}",
        )
    except Exception as exc:  # pragma: no cover - fail closed
        return HttpResult(ok=False, url=url, error=f"request_failed:{type(exc).__name__}")


class LoopbackClient:
    def __init__(self, transport: Optional[Transport] = None, timeout: float = 2.0) -> None:
        self.transport = transport
        self.timeout = timeout

    def request(
        self,
        method: str,
        host: str,
        port: int,
        path: str,
        *,
        allowed: set[tuple[str, str]],
        body: Any = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> HttpResult:
        if host != LOOPBACK_HOST:
            raise LoopbackHttpError(f"non_loopback_host:{host}")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise LoopbackHttpError("invalid_port")
        normalized = path if path.startswith("/") else f"/{path}"
        assert_allowed_path(method, normalized, allowed)
        url = f"http://{host}:{port}{normalized}"
        raw: Optional[bytes] = None
        hdrs = dict(headers or {})
        if body is not None:
            raw = json.dumps(body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
            hdrs.setdefault("Accept", "application/json")
        if self.transport is not None:
            return self.transport(method.upper(), url, raw, hdrs)
        return default_transport(method.upper(), url, raw, hdrs, timeout=self.timeout)
