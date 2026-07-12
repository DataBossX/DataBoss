"""Authenticated, single-use, expiring human-approval records.

The spoofable ``human_approved`` boolean is replaced by a cryptographically
signed approval record. A promotion to ``APPROVED`` or ``DELIVERED`` is only
accepted when a detached Ed25519 signature over the exact approval payload
verifies against a *trusted public key configured outside the SQLite database*.

Guarantees enforced here:

* exact asset hash and exact target state are bound into the signed payload;
* the approval is scoped to a single promotion action;
* the approval expires;
* the approval is single-use (the ledger rejects a re-used nonce);
* tampering with any field invalidates the signature.

The private signing key is never stored in the repository or the database. Only
public verifier keys are configured, via ``DATABOSSX_APPROVAL_PUBKEYS`` (a path
to a JSON authorities file) or an explicit mapping. If no trusted verifier is
configured, verification fails closed.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:  # pragma: no cover - exercised indirectly; import guard keeps errors clear
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization

    _CRYPTO_AVAILABLE = True
    _CRYPTO_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover
    _CRYPTO_AVAILABLE = False
    _CRYPTO_IMPORT_ERROR = exc

APPROVAL_SCHEMA = "dbx.approval.v1"
PUBKEYS_ENV = "DATABOSSX_APPROVAL_PUBKEYS"
_MAX_CLOCK_SKEW_SECONDS = 300

_REQUIRED_FIELDS = (
    "schema",
    "key_id",
    "project_id",
    "asset_id",
    "asset_sha256",
    "from_state",
    "to_state",
    "subject",
    "scope",
    "nonce",
    "issued_at",
    "expires_at",
    "signature",
)


class ApprovalError(ValueError):
    """Raised when an approval record is missing, invalid, or unverifiable."""


class VerifierNotConfigured(ApprovalError):
    """Raised when no trusted approval verifier is available (fail closed)."""


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _parse_iso(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ApprovalError(f"{field} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ApprovalError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ApprovalRecord:
    key_id: str
    subject: str
    nonce: str
    project_id: str
    asset_id: str
    asset_sha256: str
    from_state: str
    to_state: str
    scope: str
    issued_at: str
    expires_at: str
    token_json: str


def _load_public_key(entry: Any) -> "Ed25519PublicKey":
    if isinstance(entry, Mapping):
        pem = entry.get("public_key_pem")
        if not pem:
            raise ApprovalError("authority entry missing public_key_pem")
        material: bytes = str(pem).encode("utf-8")
    else:
        material = str(entry).encode("utf-8")
    try:
        key = serialization.load_pem_public_key(material)
    except Exception as exc:
        raise ApprovalError(f"invalid authority public key: {exc}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise ApprovalError("approval authorities must use Ed25519 public keys")
    return key


class ApprovalVerifier:
    """Verifies signed approval records against trusted Ed25519 public keys."""

    def __init__(self, authorities: Mapping[str, Any]):
        if not _CRYPTO_AVAILABLE:  # pragma: no cover
            raise VerifierNotConfigured(
                f"cryptography is required for approval verification: {_CRYPTO_IMPORT_ERROR}"
            )
        if not authorities:
            raise VerifierNotConfigured("no approval authorities configured")
        self._keys = {str(key_id): _load_public_key(entry) for key_id, entry in authorities.items()}

    @property
    def key_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._keys))

    def verify(
        self,
        token: Mapping[str, Any],
        *,
        project_id: str,
        asset_id: str,
        asset_sha256: str,
        from_state: str,
        to_state: str,
        now: datetime | None = None,
    ) -> ApprovalRecord:
        if not isinstance(token, Mapping):
            raise ApprovalError("approval token must be a mapping")
        missing = [field for field in _REQUIRED_FIELDS if field not in token]
        if missing:
            raise ApprovalError(f"approval token missing fields: {', '.join(missing)}")
        if token.get("schema") != APPROVAL_SCHEMA:
            raise ApprovalError("unsupported approval schema")

        key_id = str(token["key_id"])
        public_key = self._keys.get(key_id)
        if public_key is None:
            raise ApprovalError(f"unknown approval authority: {key_id}")

        payload = {key: value for key, value in token.items() if key != "signature"}
        try:
            signature = base64.b64decode(str(token["signature"]), validate=True)
        except (ValueError, TypeError) as exc:
            raise ApprovalError("approval signature is not valid base64") from exc
        try:
            public_key.verify(signature, _canonical_bytes(payload))
        except InvalidSignature as exc:
            raise ApprovalError("approval signature verification failed") from exc

        # Exact-binding checks. Any mismatch means the approval does not authorize
        # THIS promotion, even though the signature itself is valid.
        if str(token["project_id"]) != project_id:
            raise ApprovalError("approval is bound to a different project")
        if str(token["asset_id"]) != asset_id:
            raise ApprovalError("approval is bound to a different asset")
        if str(token["asset_sha256"]).lower() != str(asset_sha256).lower():
            raise ApprovalError("approval is bound to a different asset content hash")
        if str(token["from_state"]) != from_state:
            raise ApprovalError("approval is bound to a different source state")
        if str(token["to_state"]) != to_state:
            raise ApprovalError("approval is bound to a different target state")
        if str(token["scope"]) != f"promote:{to_state}":
            raise ApprovalError("approval scope does not authorize this action")

        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        issued_at = _parse_iso(token["issued_at"], "issued_at")
        expires_at = _parse_iso(token["expires_at"], "expires_at")
        if expires_at <= issued_at:
            raise ApprovalError("approval expires_at must be after issued_at")
        if (issued_at - current).total_seconds() > _MAX_CLOCK_SKEW_SECONDS:
            raise ApprovalError("approval issued_at is in the future")
        if current >= expires_at:
            raise ApprovalError("approval has expired")

        nonce = str(token["nonce"]).strip()
        if not nonce:
            raise ApprovalError("approval nonce is required")
        subject = str(token["subject"]).strip()
        if not subject:
            raise ApprovalError("approval subject is required")

        return ApprovalRecord(
            key_id=key_id,
            subject=subject,
            nonce=nonce,
            project_id=project_id,
            asset_id=asset_id,
            asset_sha256=str(token["asset_sha256"]).lower(),
            from_state=from_state,
            to_state=to_state,
            scope=str(token["scope"]),
            issued_at=issued_at.isoformat(),
            expires_at=expires_at.isoformat(),
            token_json=json.dumps(dict(token), sort_keys=True, separators=(",", ":")),
        )


def _read_authorities(source: str | os.PathLike[str] | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(source, Mapping):
        return source
    path = Path(source)
    if not path.exists():
        raise VerifierNotConfigured(f"approval authorities file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerifierNotConfigured(f"cannot read approval authorities: {exc}") from exc
    if isinstance(data, Mapping) and "authorities" in data:
        data = data["authorities"]
    if not isinstance(data, Mapping):
        raise VerifierNotConfigured("approval authorities file must map key_id -> public key")
    return data


def load_verifier(
    source: str | os.PathLike[str] | Mapping[str, Any] | None = None,
) -> ApprovalVerifier | None:
    """Load the trusted verifier, or return ``None`` when none is configured.

    ``None`` means the caller must fail closed for APPROVED/DELIVERED.
    """
    if source is None:
        source = os.environ.get(PUBKEYS_ENV) or None
    if source is None:
        return None
    authorities = _read_authorities(source)
    return ApprovalVerifier(authorities)


# --- Signing helpers (for approver tooling and tests only) -------------------
# These never run inside CI verification; the private key stays with the human
# approver. They are provided so an authorized signer can mint a token offline.

def sign_payload(private_key_pem: bytes, payload: Mapping[str, Any]) -> dict[str, Any]:
    if not _CRYPTO_AVAILABLE:  # pragma: no cover
        raise ApprovalError("cryptography is required to sign approvals")
    key = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ApprovalError("approval signing key must be Ed25519")
    body = {key_name: value for key_name, value in payload.items() if key_name != "signature"}
    signature = key.sign(_canonical_bytes(body))
    signed = dict(body)
    signed["signature"] = base64.b64encode(signature).decode("ascii")
    return signed
