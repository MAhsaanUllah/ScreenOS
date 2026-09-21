"""Anthropic Messages API transport. Never log credentials, prompts or error bodies."""

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "https://api.anthropic.com/v1/messages"
VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-3-5-haiku-latest"


def complete(messages: list[dict[str, str]], *, key: str | None = None,
             model: str | None = None) -> str:
    key = (key or os.getenv("ANTHROPIC_API_KEY", "")).strip()
    model = (model or os.getenv("ANTHROPIC_MODEL", "") or DEFAULT_MODEL).strip()
    if not key:
        raise ValueError("Add your Anthropic key in Settings or as ANTHROPIC_API_KEY in .env.")
    body = {"model": model, "max_tokens": 8192, "system": messages[0]["content"],
            "messages": [{"role": "user", "content": messages[1]["content"]}]}
    request = Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                      headers={"Content-Type": "application/json", "x-api-key": key,
                               "anthropic-version": VERSION}, method="POST")
    for attempt in range(3):
        try:
            with urlopen(request, timeout=120) as response:
                result = json.load(response)
            break
        except HTTPError as exc:
            code = exc.code
            exc.close()
            if code in {500, 502, 503, 504, 529} and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            hint = {400: "Check the Anthropic model name.", 401: "Check your Anthropic key.",
                    403: "Check your Anthropic account permissions.",
                    404: "Check the Anthropic model name.",
                    429: "Anthropic rate limit or quota reached; retry later."}
            raise ValueError(f"Anthropic HTTP {code}. " + hint.get(
                code, "Provider request failed. No score was accepted.")) from None
        except (URLError, TimeoutError, OSError):
            raise ValueError("Could not reach Anthropic. No score was accepted.") from None
        except ValueError:
            raise ValueError("Anthropic returned invalid JSON. No score was accepted.") from None
    try:
        if result.get("stop_reason") != "end_turn":
            raise ValueError("Anthropic did not finish normally; no score was accepted.")
        text = "".join(block.get("text", "") for block in result["content"]
                       if block.get("type") == "text")
        if not text.strip():
            raise ValueError("Anthropic returned no scoring text; human review is required.")
        return text
    except (KeyError, TypeError, AttributeError):
        raise ValueError("Anthropic returned no usable score. Human review is required.") from None
