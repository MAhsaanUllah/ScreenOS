"""Credential encryption at rest (BYOK).

AES-128 Fernet via `cryptography` — already installed via pdfminer.
Key comes from SCREENOS_CRED_KEY env (Fernet key or any string, derived).
Falls back to local dev key in data/.cred_key or deterministic dev key.
Never log plaintext. Decrypt tries Fernet; on failure assumes legacy plaintext.
ponytail: one file, stdlib fallback if cryptography missing.
"""
import base64
import hashlib
import os
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
    _HAS_FERNET = True
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    _HAS_FERNET = False

ROOT = Path(__file__).resolve().parents[1]
_FALLBACK_PATH = ROOT / "data" / ".cred_key"
_FERNET_KEY: bytes | None = None


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


def _master_key() -> bytes:
    global _FERNET_KEY
    if _FERNET_KEY is not None:
        return _FERNET_KEY
    env = os.environ.get("SCREENOS_CRED_KEY", "").strip()
    if env:
        _FERNET_KEY = _derive_key(env)
        return _FERNET_KEY
    # Local dev: stable file or deterministic fallback
    if _FALLBACK_PATH.is_file():
        try:
            val = _FALLBACK_PATH.read_text().strip()
            if val:
                _FERNET_KEY = val.encode()
                return _FERNET_KEY
        except OSError:
            pass
    # Try to create stable dev key file
    try:
        _FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        dev_raw = base64.urlsafe_b64encode(hashlib.sha256(b"screenos-local-dev-key-v1").digest()).decode()
        # best-effort write, ignore failure
        try:
            _FALLBACK_PATH.write_text(dev_raw)
        except OSError:
            pass
        _FERNET_KEY = dev_raw.encode()
        return _FERNET_KEY
    except Exception:
        pass
    # Last resort deterministic (no file)
    _FERNET_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"screenos-local-dev-key-v1").digest())
    return _FERNET_KEY


def encrypt_value(plaintext: str) -> str:
    """Encrypt plaintext string; returns Fernet token or plaintext if no crypto."""
    if not plaintext:
        return ""
    if not _HAS_FERNET:
        return plaintext  # local fallback; cloud must have cryptography
    f = Fernet(_master_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(token: str) -> str:
    """Decrypt Fernet token; on InvalidToken assume legacy plaintext."""
    if not token:
        return ""
    if not _HAS_FERNET:
        return token
    # Legacy plaintext heuristic: Fernet tokens start with gAAAA...
    if not token.startswith("gAAAA"):
        # Could be legacy plaintext OR Fernet with different key derivation;
        # try decrypt, on failure return as-is
        try:
            f = Fernet(_master_key())
            return f.decrypt(token.encode("utf-8")).decode("utf-8")
        except Exception:
            return token
    try:
        f = Fernet(_master_key())
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Wrong key or corrupted -> treat as plaintext fallback
        return token
    except Exception:
        return token


def reset_key_cache() -> None:
    """For tests: clear cached key."""
    global _FERNET_KEY
    _FERNET_KEY = None
