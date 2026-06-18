"""Credential encryption and secure storage using Fernet symmetric encryption."""

import os
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_KEY_FILE = Path(os.getenv("DOTO_KEY_FILE", Path.home() / ".doto_commander" / "master.key"))


def _load_or_create_key() -> bytes:
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()
    env_key = os.getenv("ENCRYPTION_KEY")
    if env_key:
        key = env_key.encode()
        try:
            Fernet(key)  # validate before persisting
        except Exception as exc:
            raise ValueError(
                "ENCRYPTION_KEY is not a valid Fernet key "
                "(urlsafe base64-encoded 32-byte key)."
            ) from exc
    else:
        key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    _KEY_FILE.chmod(0o600)
    return key


def _get_fernet() -> Fernet:
    return Fernet(_load_or_create_key())


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()


def derive_key_from_password(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480_000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))
