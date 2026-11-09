"""Centralized timeout resolution, retry handling and typed provider exceptions."""

import datetime
import email.utils
import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


class ProviderBusy(ValueError):
    """The provider is rate-limited or overloaded (HTTP 429)."""


class ProviderTimeout(ValueError):
    """The provider request timed out."""


def _get_settings() -> dict:
    return {**dotenv_values(ROOT / ".env"), **os.environ}


def llm_timeout(local: bool = False, explicit: float | None = None) -> float:
    """Resolve the timeout in seconds for an LLM call.

    Remote providers default to 120s; local Ollama defaults to 300s.
    Reads both .env and os.environ.
    """
    if explicit is not None and explicit > 0:
        return float(explicit)
    settings = _get_settings()
    if local:
        raw = settings.get("OLLAMA_TIMEOUT") or settings.get("LLM_TIMEOUT")
        default = 300.0
    else:
        raw = settings.get("LLM_TIMEOUT")
        default = 120.0
    try:
        val = float(raw)
        return val if val > 0 else default
    except (ValueError, TypeError):
        return default


def retry_wait(headers, default: float = 1.0, max_delay: float = 30.0) -> float:
    """Parse Retry-After header (seconds or HTTP date), capped at max_delay."""
    if headers:
        raw = None
        if hasattr(headers, "get"):
            raw = headers.get("Retry-After") or headers.get("retry-after")
        if raw is not None:
            try:
                val = float(raw)
                return max(0.0, min(val, max_delay))
            except (ValueError, TypeError):
                try:
                    dt = email.utils.parsedate_to_datetime(str(raw))
                    diff = (dt - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                    return max(0.0, min(diff, max_delay))
                except Exception:
                    pass
    return default
