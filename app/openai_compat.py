"""OpenAI-compatible chat-completions transport.

One implementation serves OpenAI, Groq, OpenRouter and local Ollama: they all
speak the same ``POST {base_url}/chat/completions`` contract. Only the base URL,
an optional key and the model differ. Never log credentials, prompts or bodies.
"""

import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.llm_limits import ProviderBusy, ProviderTimeout, llm_timeout, retry_wait

logger = logging.getLogger("uvicorn.error")


def complete(messages: list[dict[str, str]], *, base_url: str, label: str,
             key: str | None = None, model: str | None = None,
             timeout: float | None = None) -> str:
    if not base_url:
        raise ValueError(f"{label} is not configured. Add its base URL.")
    model = (model or "").strip()
    if not model:
        raise ValueError(f"Choose a {label} model before scoring.")
    is_local = label.lower().startswith("ollama") or "ollama" in base_url
    timeout_sec = llm_timeout(local=is_local, explicit=timeout)
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    body = {"model": model, "messages": messages, "temperature": 0,
            "response_format": {"type": "json_object"}}

    def build():
        return Request(base_url.rstrip("/") + "/chat/completions",
                       data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
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
            if code == 400 and "response_format" in body:  # e.g. a provider without JSON mode
                del body["response_format"], body["temperature"]
                logger.warning("%s rejected temperature/json mode; retried without it", label)
                request = build()
                continue
            if code == 429:
                if not retried_429:
                    retried_429 = True
                    delay = retry_wait(headers_dict, default=1.0, max_delay=30.0)
                    time.sleep(delay)
                    continue
                raise ProviderBusy(f"{label} HTTP 429. The AI provider is busy (rate limit). Try again in a minute.") from None
            if code == 503:
                if not retried_503:
                    retried_503 = True
                    delay = retry_wait(headers_dict, default=2.0, max_delay=30.0)
                    time.sleep(delay)
                    continue
                raise ValueError(f"{label} HTTP 503. {label} is temporarily unavailable; retry shortly.") from None
            if code in {500, 502, 504} and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            hint = {401: f"Check your {label} key.", 403: f"Check your {label} account permissions.",
                    404: f"Check the {label} model name and base URL."}
            raise ValueError(f"{label} HTTP {code}. " + hint.get(
                code, "Provider request failed. No score was accepted.")) from None
        except (URLError, TimeoutError, OSError) as exc:
            if isinstance(exc, TimeoutError) or (isinstance(exc, URLError) and "timed out" in str(getattr(exc, "reason", "")).lower()):
                raise ProviderTimeout("The AI provider took too long. Try a faster model or raise LLM_TIMEOUT.") from None
            raise ValueError(f"Could not reach {label}. No score was accepted.") from None
        except ValueError:
            raise ValueError(f"{label} returned invalid JSON. No score was accepted.") from None
    try:
        choice = result["choices"][0]
        text = choice["message"]["content"]
        if choice.get("finish_reason") != "stop" or not isinstance(text, str) or not text.strip():
            raise ValueError(f"{label} returned incomplete scoring text. No score was accepted.")
        return text
    except (KeyError, TypeError, IndexError, AttributeError):
        raise ValueError(f"{label} returned no usable score. Human review is required.") from None
