"""Anthropic Messages API transport. Never log credentials, prompts or error bodies."""

import datetime
import email.utils
import json
import logging
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "https://api.anthropic.com/v1/messages"
VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-3-5-haiku-latest"
logger = logging.getLogger("uvicorn.error")


def _parse_retry_after(headers, default: float = 1.0, max_delay: float = 30.0) -> float:
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


def complete(messages: list[dict[str, str]], *, key: str | None = None,
             model: str | None = None, timeout: float | None = None) -> str:
    key = (key or os.getenv("ANTHROPIC_API_KEY", "")).strip()
    model = (model or os.getenv("ANTHROPIC_MODEL", "") or DEFAULT_MODEL).strip()
    if not key:
        raise ValueError("Add your Anthropic key in Settings or as ANTHROPIC_API_KEY in .env.")
    timeout_raw = os.getenv("LLM_TIMEOUT")
    try:
        timeout_sec = float(timeout) if timeout is not None else (float(timeout_raw) if timeout_raw else 60.0)
    except (ValueError, TypeError):
        timeout_sec = 60.0
    # Whole conversation after the system prompt, so a retry's feedback reaches the model.
    body = {"model": model, "max_tokens": 8192, "temperature": 0, "system": messages[0]["content"],
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages[1:]]}

    def build():
        return Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                       headers={"Content-Type": "application/json", "x-api-key": key,
                                "anthropic-version": VERSION}, method="POST")
    request = build()
    retried_429 = False
    retried_503 = False
    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout_sec) as response:
                result = json.load(response)
            break
        except HTTPError as exc:
            code = exc.code
            headers_dict = getattr(exc, "headers", None) or {}
            exc.close()
            if code == 400 and "temperature" in body:  # some models refuse a fixed temperature
                del body["temperature"]
                logger.warning("Anthropic rejected temperature/json mode; retried without it")
                request = build()
                continue
            if code == 429:
                if not retried_429:
                    retried_429 = True
                    delay = _parse_retry_after(headers_dict, default=1.0, max_delay=30.0)
                    time.sleep(delay)
                    continue
                raise ValueError("Anthropic HTTP 429. Anthropic rate limit or quota reached; retry later.") from None
            if code in {503, 529}:
                if not retried_503:
                    retried_503 = True
                    delay = _parse_retry_after(headers_dict, default=2.0, max_delay=30.0)
                    time.sleep(delay)
                    continue
                raise ValueError(f"Anthropic HTTP {code}. Anthropic is temporarily unavailable or overloaded; retry shortly.") from None
            if code in {500, 502, 504} and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            hint = {400: "Check the Anthropic model name.", 401: "Check your Anthropic key.",
                    403: "Check your Anthropic account permissions.",
                    404: "Check the Anthropic model name."}
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
