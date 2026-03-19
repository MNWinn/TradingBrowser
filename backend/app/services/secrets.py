import base64
import hashlib

from app.core.config import settings

try:
    from cryptography.fernet import Fernet
except ModuleNotFoundError:  # pragma: no cover
    Fernet = None


class _FallbackCipher:
    """Dev-only reversible cipher fallback when cryptography is unavailable."""

    def __init__(self, key: str):
        self.key_bytes = hashlib.sha256(key.encode()).digest()

    def encrypt(self, raw: bytes) -> bytes:
        out = bytes([b ^ self.key_bytes[i % len(self.key_bytes)] for i, b in enumerate(raw)])
        return base64.urlsafe_b64encode(out)

    def decrypt(self, token: bytes) -> bytes:
        raw = base64.urlsafe_b64decode(token)
        out = bytes([b ^ self.key_bytes[i % len(self.key_bytes)] for i, b in enumerate(raw)])
        return out


def _cipher():
    if not settings.encryption_key:
        raise ValueError("ENCRYPTION_KEY is required for credential encryption")
    if Fernet is not None:
        return Fernet(settings.encryption_key.encode())
    return _FallbackCipher(settings.encryption_key)


def encrypt_json(raw: str) -> str:
    return _cipher().encrypt(raw.encode()).decode()


def decrypt_json(token: str) -> str:
    return _cipher().decrypt(token.encode()).decode()


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def generate_encryption_key() -> str:
    if Fernet is not None:
        return Fernet.generate_key().decode()
    return base64.urlsafe_b64encode(hashlib.sha256(b"dev-fallback-key").digest()).decode()
