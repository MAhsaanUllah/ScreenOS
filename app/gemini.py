"""Gemini REST transport. Never log credentials, prompts or provider error bodies."""

import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def complete(messages: list[dict[str, str]]) -> str:
    load_dotenv(ROOT / ".env", override=False)
    key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    if not key:
        raise ValueError("Set GEMINI_API_KEY in the project .env file.")
    if not re.fullmatch(r"gemini-[a-zA-Z0-9.-]+", model):
        raise ValueError("GEMINI_MODEL must be a Gemini model ID.")
    body = {"systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
            "contents": [{"role": "user", "parts": [{"text": messages[1]["content"]}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 8192}}
    request = Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST")
    for attempt in range(3):
        try:
            with urlopen(request, timeout=60) as response:
                result = json.load(response)
            break
        except HTTPError as exc:
            code = exc.code
            exc.close()
            if code in {500, 502, 503, 504}:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise ValueError("Gemini is temporarily unavailable after 3 attempts. "
                                 "Your preview is still available. Try scoring again shortly; "
                                 "no score was accepted.") from None
            guidance = {400: "Check model configuration and API-key validity.",
                        401: "Check your API key.", 403: "Check API permissions.",
                        404: "Check GEMINI_MODEL availability.",
                        429: "Quota or rate limit reached; check your Gemini quota and retry later."}
            raise ValueError(f"Gemini HTTP {code}. " + guidance.get(code,
                             "Provider request failed. No score was accepted.")) from None
        except (URLError, TimeoutError, OSError):
            # A timed-out request may already have run; avoid automatic duplicate billing.
            raise ValueError("Could not reach Gemini within 60 seconds. Retry later.") from None
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
