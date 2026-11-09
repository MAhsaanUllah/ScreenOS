"""DeepSeek chat-completions transport using the official direct API."""
import datetime
import email.utils
import json
import logging
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://api.deepseek.com/chat/completions"
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
    settings = {**dotenv_values(ROOT / ".env"), **os.environ}
    key = (key or settings.get("DEEPSEEK_API_KEY") or "").strip()
    model = (model or settings.get("DEEPSEEK_MODEL") or "deepseek-v4-flash").strip()
    endpoint = settings.get("DEEPSEEK_BASE_URL") or ENDPOINT
    timeout_raw = settings.get("LLM_TIMEOUT") or os.getenv("LLM_TIMEOUT")
    try:
        timeout_sec = float(timeout) if timeout is not None else (float(timeout_raw) if timeout_raw else 60.0)
    except (ValueError, TypeError):
        timeout_sec = 60.0
    if not key:
        raise ValueError("Add your DeepSeek key in Settings or as DEEPSEEK_API_KEY in .env.")
    if endpoint.rstrip("/") != ENDPOINT:
        raise ValueError("DEEPSEEK_BASE_URL must be the configured DeepSeek chat-completions endpoint.")
    body = {"model": model, "messages": messages, "temperature": 0,
            "response_format": {"type": "json_object"}}

    def build():
        return Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                       headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
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
            if code == 400 and "response_format" in body:
                del body["response_format"], body["temperature"]
                logger.warning("DeepSeek rejected temperature/json mode; retried without it")
                request = build()
                continue
            if code == 429:
                if not retried_429:
                    retried_429 = True
                    delay = _parse_retry_after(headers_dict, default=1.0, max_delay=30.0)
                    time.sleep(delay)
                    continue
                raise ValueError("DeepSeek HTTP 429. Check quota or rate limits; retry later.") from None
            if code == 503:
                if not retried_503:
                    retried_503 = True
                    delay = _parse_retry_after(headers_dict, default=2.0, max_delay=30.0)
                    time.sleep(delay)
                    continue
                raise ValueError("DeepSeek HTTP 503. DeepSeek is temporarily unavailable; retry shortly.") from None
            if code in {500, 502, 504} and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            hint = {401: "Check your DeepSeek key.", 403: "Check account permissions.",
                    404: "Check the model ID."}
            raise ValueError(f"DeepSeek HTTP {code}. " + hint.get(code,
                             "Provider request failed; try again later. No score was accepted.")) from None
        except (URLError, TimeoutError, OSError):
            raise ValueError("DeepSeek connection failed or timed out. No score was accepted.") from None
        except ValueError:
            raise ValueError("DeepSeek returned invalid JSON. No score was accepted.") from None
    try:
        choice = result["choices"][0]
        text = choice["message"]["content"]
        if choice.get("finish_reason") != "stop" or not isinstance(text, str) or not text.strip():
            raise ValueError("DeepSeek returned incomplete scoring text. No score was accepted.")
        return text
    except (KeyError, TypeError, IndexError, AttributeError):
        raise ValueError("DeepSeek returned no usable score. Human review is required.") from None
