"""CommandCode chat-completions transport using the owner's supplied API contract."""
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://api.commandcode.ai/provider/v1/chat/completions"


def complete(messages: list[dict[str, str]]) -> str:
    settings = {**dotenv_values(ROOT / ".env"), **os.environ}
    key = (settings.get("LLM_API_KEY") or "").strip()
    model = settings.get("LLM_MODEL") or "deepseek/deepseek-v4-flash"
    endpoint = settings.get("LLM_BASE_URL") or ENDPOINT
    if not key:
        raise ValueError("Add your CommandCode key as LLM_API_KEY in .env.")
    if endpoint.rstrip("/") != ENDPOINT:
        raise ValueError("LLM_BASE_URL must be the configured CommandCode chat-completions endpoint.")
    request = Request(ENDPOINT, data=json.dumps({"model": model, "messages": messages}).encode("utf-8"),
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    for attempt in range(3):
        try:
            with urlopen(request, timeout=60) as response:
                result = json.load(response)
            break
        except HTTPError as exc:
            code = exc.code
            exc.close()
            if code in {500, 502, 503, 504} and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            hint = {401: "Check your CommandCode key.", 403: "Check account permissions.",
                    429: "Check quota or rate limits; retry later.", 404: "Check the model ID."}
            raise ValueError(f"CommandCode HTTP {code}. " + hint.get(code,
                             "Provider request failed; try again later. No score was accepted.")) from None
        except (URLError, TimeoutError, OSError):
            raise ValueError("CommandCode connection failed or timed out. No score was accepted.") from None
        except ValueError:
            raise ValueError("CommandCode returned invalid JSON. No score was accepted.") from None
    try:
        choice = result["choices"][0]
        text = choice["message"]["content"]
        if choice.get("finish_reason") != "stop" or not isinstance(text, str) or not text.strip():
            raise ValueError("CommandCode returned incomplete scoring text. No score was accepted.")
        return text
    except (KeyError, TypeError, IndexError, AttributeError):
        raise ValueError("CommandCode returned no usable score. Human review is required.") from None
