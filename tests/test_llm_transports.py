import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from app import anthropic, openai_compat

MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}]
COMPLETION = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}


class OpenAiCompatChecks(unittest.TestCase):
    def test_sends_key_and_model_to_the_configured_base_url(self):
        with patch("app.openai_compat.urlopen",
                   return_value=io.BytesIO(json.dumps(COMPLETION).encode())) as send:
            result = openai_compat.complete(MESSAGES, base_url="https://api.groq.com/openai/v1",
                                            label="Groq", key="gsk-123", model="llama-3.3-70b")
        self.assertEqual(result, "{}")
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer gsk-123")
        self.assertEqual(json.loads(request.data)["model"], "llama-3.3-70b")

    def test_local_provider_needs_no_key(self):
        with patch("app.openai_compat.urlopen",
                   return_value=io.BytesIO(json.dumps(COMPLETION).encode())) as send:
            self.assertEqual(openai_compat.complete(
                MESSAGES, base_url="http://localhost:11434/v1", label="Ollama", model="llama3.1"), "{}")
        self.assertIsNone(send.call_args.args[0].get_header("Authorization"))

    def test_missing_configuration_and_provider_errors(self):
        with self.assertRaisesRegex(ValueError, "Choose a Groq model"):
            openai_compat.complete(MESSAGES, base_url="https://api.groq.com/openai/v1", label="Groq")
        with self.assertRaisesRegex(ValueError, "Groq is not configured"):
            openai_compat.complete(MESSAGES, base_url="", label="Groq", model="m")
        error = HTTPError("https://api.groq.com", 401, "unauthorized", {}, io.BytesIO(b"private body"))
        with patch("app.openai_compat.urlopen", side_effect=error):
            with self.assertRaisesRegex(ValueError, "Check your Groq key") as caught:
                openai_compat.complete(MESSAGES, base_url="https://api.groq.com/openai/v1",
                                       label="Groq", key="k", model="m")
        self.assertNotIn("private", str(caught.exception))

    def test_incomplete_completion_is_rejected(self):
        truncated = {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
        with patch("app.openai_compat.urlopen",
                   return_value=io.BytesIO(json.dumps(truncated).encode())):
            with self.assertRaisesRegex(ValueError, "incomplete scoring text"):
                openai_compat.complete(MESSAGES, base_url="https://x/v1", label="X", model="m")

    def test_configurable_timeouts(self):
        with patch("app.openai_compat.urlopen",
                   return_value=io.BytesIO(json.dumps(COMPLETION).encode())) as send:
            with patch.dict("os.environ", {"LLM_TIMEOUT": "45"}):
                openai_compat.complete(MESSAGES, base_url="https://api.openai.com/v1", label="OpenAI", model="m")
                self.assertEqual(send.call_args.kwargs["timeout"], 45.0)

        with patch("app.openai_compat.urlopen",
                   return_value=io.BytesIO(json.dumps(COMPLETION).encode())) as send:
            with patch.dict("os.environ", {"OLLAMA_TIMEOUT": "180", "LLM_TIMEOUT": "45"}):
                openai_compat.complete(MESSAGES, base_url="http://localhost:11434/v1", label="Ollama", model="m")
                self.assertEqual(send.call_args.kwargs["timeout"], 180.0)

    @patch("app.openai_compat.time.sleep")
    def test_rate_limit_429_retries_once_and_respects_retry_after(self, mock_sleep):
        err = HTTPError("https://api.groq.com", 429, "rate limited", {"Retry-After": "45"}, io.BytesIO(b""))
        with patch("app.openai_compat.urlopen", side_effect=[err, io.BytesIO(json.dumps(COMPLETION).encode())]) as send:
            res = openai_compat.complete(MESSAGES, base_url="https://api.groq.com/openai/v1", label="Groq", model="m")
            self.assertEqual(res, "{}")
            self.assertEqual(send.call_count, 2)
            # Capped at 30 seconds
            mock_sleep.assert_called_once_with(30.0)

    @patch("app.openai_compat.time.sleep")
    def test_503_retries_once_with_distinct_message_on_failure(self, mock_sleep):
        err = HTTPError("https://api.groq.com", 503, "unavailable", {"Retry-After": "10"}, io.BytesIO(b""))
        with patch("app.openai_compat.urlopen", side_effect=[err, err]) as send:
            with self.assertRaisesRegex(ValueError, "temporarily unavailable"):
                openai_compat.complete(MESSAGES, base_url="https://api.groq.com/openai/v1", label="Groq", model="m")
            self.assertEqual(send.call_count, 2)
            mock_sleep.assert_called_once_with(10.0)


class AnthropicChecks(unittest.TestCase):
    REPLY = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "{}"}]}

    def test_uses_the_messages_api_contract(self):
        with patch("app.anthropic.urlopen",
                   return_value=io.BytesIO(json.dumps(self.REPLY).encode())) as send:
            result = anthropic.complete(MESSAGES, key="sk-ant-1", model="claude-3-5-haiku-latest")
        self.assertEqual(result, "{}")
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, anthropic.ENDPOINT)
        self.assertEqual(request.get_header("X-api-key"), "sk-ant-1")
        self.assertEqual(request.get_header("Anthropic-version"), anthropic.VERSION)
        body = json.loads(request.data)
        self.assertEqual(body["system"], "sys")
        self.assertEqual(body["messages"], [{"role": "user", "content": "usr"}])

    def test_missing_key_is_rejected(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaisesRegex(ValueError, "Anthropic key"):
            anthropic.complete(MESSAGES)

    def test_failure_is_reported_without_the_provider_body(self):
        error = HTTPError(anthropic.ENDPOINT, 429, "too many", {}, io.BytesIO(b"private detail"))
        with patch("app.anthropic.urlopen", side_effect=error):
            with self.assertRaisesRegex(ValueError, "rate limit") as caught:
                anthropic.complete(MESSAGES, key="k", model="m")
        self.assertNotIn("private", str(caught.exception))

    def test_unfinished_response_is_rejected(self):
        cut = {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "{}"}]}
        with patch("app.anthropic.urlopen", return_value=io.BytesIO(json.dumps(cut).encode())):
            with self.assertRaisesRegex(ValueError, "did not finish normally"):
                anthropic.complete(MESSAGES, key="k", model="m")

    def test_configurable_timeout(self):
        with patch("app.anthropic.urlopen", return_value=io.BytesIO(json.dumps(self.REPLY).encode())) as send:
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k", "LLM_TIMEOUT": "55"}):
                anthropic.complete(MESSAGES, model="m")
                self.assertEqual(send.call_args.kwargs["timeout"], 55.0)

    @patch("app.anthropic.time.sleep")
    def test_rate_limit_429_retries_once_with_retry_after(self, mock_sleep):
        err = HTTPError(anthropic.ENDPOINT, 429, "rate limited", {"Retry-After": "45"}, io.BytesIO(b""))
        with patch("app.anthropic.urlopen", side_effect=[err, io.BytesIO(json.dumps(self.REPLY).encode())]) as send:
            res = anthropic.complete(MESSAGES, key="k", model="m")
            self.assertEqual(res, "{}")
            self.assertEqual(send.call_count, 2)
            mock_sleep.assert_called_once_with(30.0)
