"""Credential encryption at rest (BYOK).

AES-128 Fernet. Key order: SCREENOS_CRED_KEY env (Fernet key or any string,
derived) -> data/.cred_key -> a freshly generated random key saved there (0600).
There is no built-in key: a shared default would let anyone decrypt stored keys.
Never log plaintext.
"""
import base64
import hashlib
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

ROOT = Path(__file__).resolve().parents[1]
_FALLBACK_PATH = ROOT / "data" / ".cred_key"
_FERNET_KEY: bytes | None = None
# The old built-in key was public, so a key file holding it is as good as no encryption.
_PUBLIC_DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"screenos-local-dev-key-v1").digest())
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "testserver"}


class CredentialKeyError(ValueError):
    """Stored credential cannot be decrypted with the current key."""


def _derive_key(raw: str) -> bytes:
    raw = raw.strip()
    # Valid Fernet key is 44 urlsafe base64 chars; try as-is
    if len(raw) == 44:
        try:
            base64.urlsafe_b64decode(raw)
            return raw.encode()
        except Exception:
            pass
    # Derive deterministic Fernet key from any string
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def check_config() -> None:
    """Startup guard: a non-local deployment must bring its own key."""
    hosts = {h.strip() for h in os.environ.get("SCREENOS_ALLOWED_HOSTS", "").split(",") if h.strip()}
    if hosts - _LOCAL_HOSTS and not os.environ.get("SCREENOS_CRED_KEY", "").strip():
        raise RuntimeError(
            "SCREENOS_CRED_KEY is required when SCREENOS_ALLOWED_HOSTS includes a non-local host. "
            'Generate one: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')


def _master_key() -> bytes:
    global _FERNET_KEY
    if _FERNET_KEY is not None:
        return _FERNET_KEY
    check_config()
    env = os.environ.get("SCREENOS_CRED_KEY", "").strip()
    if env:
        _FERNET_KEY = _derive_key(env)
        return _FERNET_KEY
    _FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _FALLBACK_PATH.is_file() and _FALLBACK_PATH.read_bytes().strip() == _PUBLIC_DEV_KEY:
        logging.getLogger("uvicorn.error").warning(
            "data/.cred_key held the public dev key; replaced it with a new random key. "
            "Provider keys saved earlier cannot be decrypted: re-enter them in Settings.")
        _FALLBACK_PATH.unlink()
    try:  # exclusive create: two workers racing never overwrite each other's key
        fd = os.open(_FALLBACK_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(Fernet.generate_key())
    except FileExistsError:
        pass
    _FERNET_KEY = _FALLBACK_PATH.read_bytes().strip()
    return _FERNET_KEY


def encrypt_value(plaintext: str) -> str:
    """Encrypt plaintext string; returns a Fernet token."""
    if not plaintext:
        return ""
    return Fernet(_master_key()).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token. Non-Fernet values are legacy plaintext; a Fernet
    token that fails to decrypt (wrong key / corrupt) raises CredentialKeyError."""
    if not token:
        return ""
    if not token.startswith("gAAAA"):
        return token
    try:
        return Fernet(_master_key()).decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise CredentialKeyError(
            "A stored provider key cannot be decrypted with the current SCREENOS_CRED_KEY. "
            "Restore the original key or re-enter the key in Settings.") from None


def reset_key_cache() -> None:
    """For tests: clear cached key."""
    global _FERNET_KEY
    _FERNET_KEY = None
