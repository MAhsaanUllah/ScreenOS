"""Gemini REST transport. Never log credentials, prompts or provider error bodies."""

import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from app.llm_limits import ProviderBusy, ProviderTimeout, llm_timeout, retry_wait

ROOT = Path(__file__).resolve().parents[1]


def complete(messages: list[dict[str, str]], *, key: str | None = None,
             model: str | None = None, timeout: float | None = None) -> str:
    load_dotenv(ROOT / ".env", override=False)
    key = (key or os.getenv("GEMINI_API_KEY", "")).strip()
    model = (model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")).strip()
    if not key:
        raise ValueError("Add your Gemini key in Settings or as GEMINI_API_KEY in .env.")
    if not re.fullmatch(r"gemini-[a-zA-Z0-9.-]+", model):
        raise ValueError("GEMINI_MODEL must be a Gemini model ID.")
    timeout_sec = llm_timeout(local=False, explicit=timeout)
    body = {"systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
            "contents": [{"role": "model" if m.get("role") == "assistant" else "user",
                          "parts": [{"text": m["content"]}]} for m in messages[1:]],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 8192,
                                 "temperature": 0}}
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
    retried_429 = False
    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout_sec) as response:
                result = json.load(response)
            break
        except HTTPError as exc:
            code = exc.code
            headers_dict = getattr(exc, "headers", None) or {}
            exc.close()
            if code == 429:
                if not retried_429:
                    retried_429 = True
                    delay = retry_wait(headers_dict, default=1.0, max_delay=30.0)
                    time.sleep(delay)
                    continue
                raise ProviderBusy("Gemini HTTP 429. The AI provider is busy (rate limit). Quota or rate limit reached; retry later.") from None
            if code in {500, 502, 503, 504}:
                if attempt < 2:
                    delay = retry_wait(headers_dict, default=2 ** attempt, max_delay=30.0) if (code == 503 and (headers_dict.get("Retry-After") or headers_dict.get("retry-after"))) else (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise ValueError("Gemini is temporarily unavailable after 3 attempts. "
                                 "Your preview is still available. Try scoring again shortly; "
                                 "no score was accepted.") from None
            guidance = {400: "Check model configuration and API-key validity.",
                        401: "Check your API key.", 403: "Check API permissions.",
                        404: "Check GEMINI_MODEL availability."}
            raise ValueError(f"Gemini HTTP {code}. " + guidance.get(code,
                             "Provider request failed. No score was accepted.")) from None
        except (URLError, TimeoutError, OSError) as exc:
            if isinstance(exc, TimeoutError) or (isinstance(exc, URLError) and "timed out" in str(getattr(exc, "reason", "")).lower()):
                raise ProviderTimeout("The AI provider took too long. Try a faster model or raise LLM_TIMEOUT.") from None
            # A timed-out request may already have run; avoid automatic duplicate billing.
            raise ValueError(f"Could not reach Gemini within {int(timeout_sec)} seconds. Retry later.") from None
        except (ValueError, UnicodeError):
            raise ValueError("Gemini returned an unreadable response; no score was accepted.") from None
    try:
        candidate = result["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise ValueError("Gemini did not finish normally; no score was accepted.")
        text = "".join(part.get("text", "") for part in candidate["content"]["parts"]
                       if not part.get("thought"))
        if not text.strip():
            raise ValueError("Gemini returned no scoring text; human review is required.")
        return text
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ValueError("Gemini returned no usable candidate; human review is required.") from None
