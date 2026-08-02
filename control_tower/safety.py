"""Safety primitives: digests, redaction, URL trust, path and payload guards.

These are deliberately small, pure functions. Every one of them fails closed:
the default answer is "no", and a caller must present pinned evidence to get
"yes". Nothing here consults a filename to decide whether something is allowed.
"""

import hashlib
import re

from .constants import (
    ALLOWED_READ_FOLDER_IDS,
    ALLOWED_WRITE_FOLDER_IDS,
    DENIED_URL_HOSTS,
    HOLD,
    POLLED_FOLDER_ID,
    PROHIBITED_UPLOAD_MIME_PREFIXES,
    PROHIBITED_UPLOAD_SUFFIXES,
    PROTECTED_WORKBOOK_SHA256,
    TRUSTED_URL_HOSTS,
    HoldViolation,
    ProtectedArtifactUpload,
    ReadDenied,
    UntrustedUrl,
    WriteDenied,
)

# A Drive file ID is an opaque token. We validate its shape before ever
# interpolating it into a URL, so a hostile "ID" cannot smuggle a host change.
_DRIVE_ID_RE = re.compile(r"\A[A-Za-z0-9_-]{10,128}\Z")

# Patterns whose *values* must never reach a log, a spool, or a receipt.
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(ya29\.[A-Za-z0-9._\-]+)"),
    re.compile(r"(?i)\b(AIza[A-Za-z0-9_\-]{20,})"),
    re.compile(r"(?i)\b(gh[pousr]_[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)\b(sk-[A-Za-z0-9]{20,})"),
    re.compile(r"(?i)(-----BEGIN[A-Z ]*PRIVATE KEY-----)"),
    re.compile(
        r"(?i)\b(?:password|passwd|secret|token|api[_-]?key|authorization|"
        r"client[_-]?secret|refresh[_-]?token)\b\s*[:=]\s*\"?([^\s\"',}]+)"
    ),
)

REDACTED = "[REDACTED]"


def sha256_hex(payload):
    """Uppercase SHA-256 of bytes. The single hashing entry point."""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("sha256_hex requires bytes; encode text explicitly")
    return hashlib.sha256(bytes(payload)).hexdigest().upper()


def canonical_json_bytes(obj):
    """Deterministic JSON bytes so a digest is reproducible across hosts."""
    import json

    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True)
    return (text + "\n").encode("utf-8")


def redact(text):
    """Remove secret *values* while leaving surrounding structure readable."""
    if text is None:
        return None
    out = str(text)
    for pattern in _SECRET_PATTERNS:
        # Replace only the captured group so keys stay visible for debugging.
        def _sub(match):
            whole, value = match.group(0), match.group(match.lastindex or 0)
            return whole.replace(value, REDACTED) if value else whole

        out = pattern.sub(_sub, out)
    return out


def redact_tree(node):
    """Recursively redact strings inside dicts and lists."""
    if isinstance(node, dict):
        return {k: redact_tree(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [redact_tree(v) for v in node]
    if isinstance(node, str):
        return redact(node)
    return node


def canonical_drive_url(file_id):
    """Build a Drive URL from a verified ID only.

    The tower never reuses a ``viewUrl`` returned by metadata, because that
    field has been observed pointing at third-party hosts.
    """
    if not isinstance(file_id, str) or not _DRIVE_ID_RE.match(file_id):
        raise UntrustedUrl("refusing to build a URL from a malformed Drive ID")
    return "https://drive.google.com/file/d/{0}/view".format(file_id)


def assert_trusted_url(url):
    """Reject any URL that is not on a pinned Google host."""
    if not isinstance(url, str):
        raise UntrustedUrl("URL must be a string")
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
    except Exception as exc:  # pragma: no cover - urlparse is total in practice
        raise UntrustedUrl("unparseable URL") from exc
    if parsed.scheme != "https":
        raise UntrustedUrl("refusing non-https URL: {0}".format(parsed.scheme))
    host = (parsed.hostname or "").lower()
    if host in DENIED_URL_HOSTS:
        raise UntrustedUrl("explicitly denied host: {0}".format(host))
    if host not in TRUSTED_URL_HOSTS:
        raise UntrustedUrl("host not on the trusted allowlist: {0}".format(host))
    return url


def assert_pollable(folder_id):
    """Only the single canonical queue folder may be polled."""
    if folder_id != POLLED_FOLDER_ID:
        raise ReadDenied(
            "polling is pinned to the canonical queue folder; refused {0}".format(folder_id)
        )
    return folder_id


def assert_read_allowed(folder_id):
    if folder_id not in ALLOWED_READ_FOLDER_IDS:
        raise ReadDenied("read outside the control package: {0}".format(folder_id))
    return folder_id


def assert_write_allowed(folder_id):
    if folder_id not in ALLOWED_WRITE_FOLDER_IDS:
        raise WriteDenied("write outside approved folders: {0}".format(folder_id))
    return folder_id


def assert_uploadable(payload, filename="", mime_type=""):
    """Refuse to carry protected workbooks or source evidence outward."""
    if not isinstance(payload, (bytes, bytearray)):
        raise ProtectedArtifactUpload("upload payload must be bytes")
    digest = sha256_hex(payload)
    if digest in PROTECTED_WORKBOOK_SHA256:
        raise ProtectedArtifactUpload(
            "payload digest matches a protected workbook baseline"
        )
    lowered = (filename or "").lower()
    for suffix in PROHIBITED_UPLOAD_SUFFIXES:
        if lowered.endswith(suffix):
            raise ProtectedArtifactUpload(
                "refusing to upload artifact type {0}".format(suffix)
            )
    mime = (mime_type or "").lower()
    for prefix in PROHIBITED_UPLOAD_MIME_PREFIXES:
        if mime.startswith(prefix):
            raise ProtectedArtifactUpload(
                "refusing to upload mime type {0}".format(mime_type)
            )
    # A ZIP local-file-header means an Office container even if renamed .json.
    if bytes(payload[:2]) == b"PK":
        raise ProtectedArtifactUpload("payload has a ZIP container signature")
    return digest


def stamp_hold(record):
    """Attach the HOLD to a record, refusing any attempt to change it."""
    if not isinstance(record, dict):
        raise HoldViolation("hold can only be stamped on a mapping")
    existing = record.get("hold")
    if existing is not None and existing != HOLD:
        raise HoldViolation("refusing to alter the HOLD")
    stamped = dict(record)
    stamped["hold"] = HOLD
    return stamped


def assert_hold_intact(record):
    """Verify a record still carries the exact HOLD text."""
    if not isinstance(record, dict):
        raise HoldViolation("record must be a mapping")
    if record.get("hold") != HOLD:
        raise HoldViolation("HOLD missing or altered")
    return record


def verify_readback(uploaded, returned):
    """Byte-exact comparison of what we sent against what Drive returned."""
    from .constants import ReadbackMismatch

    if not isinstance(uploaded, (bytes, bytearray)) or not isinstance(
        returned, (bytes, bytearray)
    ):
        raise ReadbackMismatch("readback comparison requires bytes on both sides")
    if len(uploaded) != len(returned):
        raise ReadbackMismatch(
            "byte count mismatch: sent {0}, returned {1}".format(
                len(uploaded), len(returned)
            )
        )
    if bytes(uploaded) != bytes(returned):
        raise ReadbackMismatch("byte-for-byte mismatch at equal length")
    return sha256_hex(uploaded)
