"""Choose configured scoring providers and fail over without logging CV data."""

import logging
import os

from dotenv import dotenv_values

from app import commandcode, deepseek, gemini


logger = logging.getLogger("uvicorn.error")
PROVIDERS = {
    "deepseek": deepseek.complete,
    "gemini": gemini.complete,
    "commandcode": commandcode.complete,
}


class ScoringUnavailable(ValueError):
    """All configured scoring providers were unavailable."""


def complete(messages: list[dict[str, str]]) -> str:
    """Use LLM_PROVIDER order, for example ``deepseek,gemini``."""
    settings = {**dotenv_values(deepseek.ROOT / ".env"), **os.environ}
    names = [name.strip().lower() for name in
             (settings.get("LLM_PROVIDER") or "deepseek").split(",") if name.strip()]
    unknown = [name for name in names if name not in PROVIDERS]
    if not names or unknown:
        choices = ", ".join(PROVIDERS)
        raise ScoringUnavailable(f"Scoring provider setting is invalid. Choose from: {choices}.")

    for number, name in enumerate(names, start=1):
        logger.info("Scoring attempt %d/%d using %s", number, len(names), name)
        try:
            result = PROVIDERS[name](messages)
            logger.info("Scoring completed using %s", name)
            return result
        except (ValueError, OSError):
            logger.warning("Scoring provider %s was unavailable", name)

    raise ScoringUnavailable(
        "Scoring is temporarily unavailable. Your CV preview is safe; try again shortly."
    )
