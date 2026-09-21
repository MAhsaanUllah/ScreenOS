"""OpenAI-compatible chat-completions transport.

One implementation serves OpenAI, Groq, OpenRouter and local Ollama: they all
speak the same ``POST {base_url}/chat/completions`` contract. Only the base URL,
an optional key and the model differ. Never log credentials, prompts or bodies.
"""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TIMEOUT = 120


def complete(messages: list[dict[str, str]], *, base_url: str, label: str,
             key: str | None = None, model: str | None = None) -> str:
    if not base_url:
        raise ValueError(f"{label} is not configured. Add its base URL.")
    model = (model or "").strip()
    if not model:
        raise ValueError(f"Choose a {label} model before scoring.")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = Request(base_url.rstrip("/") + "/chat/completions",
                      data=json.dumps({"model": model, "messages": messages}).encode("utf-8"),
                      headers=headers, method="POST")
    for attempt in range(3):
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                result = json.load(response)
            break
        except HTTPError as exc:
            code = exc.code
            exc.close()
            if code in {500, 502, 503, 504} and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            hint = {401: f"Check your {label} key.", 403: f"Check your {label} account permissions.",
                    404: f"Check the {label} model name and base URL.",
                    429: f"{label} rate limit or quota reached; retry later."}
            raise ValueError(f"{label} HTTP {code}. " + hint.get(
                code, "Provider request failed. No score was accepted.")) from None
        except (URLError, TimeoutError, OSError):
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
