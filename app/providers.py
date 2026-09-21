"""Choose configured scoring providers and fail over without logging CV data."""

import logging
import os
from functools import partial

from dotenv import dotenv_values

from app import anthropic, deepseek, gemini, openai_compat

logger = logging.getLogger("uvicorn.error")

# Every provider the workspace offers. `generic` entries share one OpenAI-compatible
# transport (only base URL and label differ); `needs_key` is False for local models.
CATALOG = {
    "deepseek": {"label": "DeepSeek", "env": "DEEPSEEK_API_KEY",
                 "default_model": "deepseek-v4-flash", "needs_key": True},
    "gemini": {"label": "Google Gemini", "env": "GEMINI_API_KEY",
               "default_model": "gemini-3.8-flash", "needs_key": True},
    "anthropic": {"label": "Anthropic", "env": "ANTHROPIC_API_KEY",
                  "default_model": "claude-3-5-haiku-latest", "needs_key": True},
    "openai": {"label": "OpenAI", "env": "OPENAI_API_KEY", "default_model": "gpt-4o-mini",
               "needs_key": True, "generic": True},
    "groq": {"label": "Groq", "env": "GROQ_API_KEY", "default_model": "llama-3.3-70b-versatile",
             "needs_key": True, "generic": True},
    "openrouter": {"label": "OpenRouter", "env": "OPENROUTER_API_KEY",
                   "default_model": "openai/gpt-4o-mini", "needs_key": True, "generic": True},
    "ollama": {"label": "Ollama (local)", "env": "", "default_model": "llama3.1",
               "needs_key": False, "generic": True},
}

PROVIDERS = {
    "deepseek": deepseek.complete,
    "gemini": gemini.complete,
    "anthropic": anthropic.complete,
    "openai": partial(openai_compat.complete, base_url="https://api.openai.com/v1", label="OpenAI"),
    "groq": partial(openai_compat.complete, base_url="https://api.groq.com/openai/v1", label="Groq"),
    "openrouter": partial(openai_compat.complete, base_url="https://openrouter.ai/api/v1",
                          label="OpenRouter"),
    "ollama": partial(openai_compat.complete, base_url="http://localhost:11434/v1", label="Ollama"),
}


class ScoringUnavailable(ValueError):
    """All configured scoring providers were unavailable."""


def complete(messages: list[dict[str, str]], *, credentials: list[dict] | None = None) -> str:
    """Score with the organization's own keys, in the order they were configured.

    ``credentials`` entries look like ``{provider, api_key, model}``; the first
    provider that answers wins, so a second key acts as a fallback. Without
    credentials the deployment-wide ``LLM_PROVIDER`` environment chain is used.
    """
    settings = {**dotenv_values(deepseek.ROOT / ".env"), **os.environ}
    if credentials:
        chain = [(entry["provider"], entry) for entry in credentials]
    else:
        chain = [(name.strip().lower(), None) for name in
                 (settings.get("LLM_PROVIDER") or "deepseek").split(",") if name.strip()]

    unknown = [name for name, _ in chain if name not in PROVIDERS]
    if not chain or unknown:
        raise ScoringUnavailable(
            f"Scoring provider setting is invalid. Choose from: {', '.join(CATALOG)}.")

    for number, (name, entry) in enumerate(chain, start=1):
        logger.info("Scoring attempt %d/%d using %s", number, len(chain), name)
        try:
            result = PROVIDERS[name](messages, **_options(name, entry, settings))
            logger.info("Scoring completed using %s", name)
            return result
        except (ValueError, OSError):
            logger.warning("Scoring provider %s was unavailable", name)

    raise ScoringUnavailable(
        "Scoring is temporarily unavailable. Your CV preview is safe; try again shortly."
    )


def _options(name: str, entry: dict | None, settings: dict) -> dict:
    """Organization values when present; generic providers may also read a key from the environment.

    Providers outside the catalog (the owner's personal transport) keep using their own env settings.
    """
    spec = CATALOG.get(name)
    if entry:
        return {"key": entry["api_key"], "model": entry["model"] or spec["default_model"]}
    if spec and spec.get("generic"):
        return {"key": settings.get(spec["env"]) or "", "model": spec["default_model"]}
    return {}
