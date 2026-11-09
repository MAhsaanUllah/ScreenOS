import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from app.llm_limits import ProviderBusy, ProviderTimeout, llm_timeout, retry_wait
from app import openai_compat

MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}]
COMPLETION = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}


class LlmLimitsChecks(unittest.TestCase):
    @patch("app.llm_limits.dotenv_values", return_value={})
    @patch.dict("os.environ", {}, clear=True)
    def test_default_timeouts_120_and_300(self, mock_env):
        self.assertEqual(llm_timeout(local=False), 120.0)
        self.assertEqual(llm_timeout(local=True), 300.0)

    @patch("app.llm_limits.dotenv_values", return_value={"LLM_TIMEOUT": "150"})
    @patch.dict("os.environ", {}, clear=True)
    def test_dotenv_llm_timeout_reaches_openai_compat_without_gemini(self, mock_env):
        with patch("app.openai_compat.urlopen", return_value=io.BytesIO(json.dumps(COMPLETION).encode())) as send:
            openai_compat.complete(MESSAGES, base_url="https://api.openai.com/v1", label="OpenAI", model="m")
            self.assertEqual(send.call_args.kwargs["timeout"], 150.0)

    def test_typed_exceptions_are_value_errors(self):
        self.assertTrue(issubclass(ProviderBusy, ValueError))
        self.assertTrue(issubclass(ProviderTimeout, ValueError))

    @patch("app.llm_limits.dotenv_values", return_value={})
    @patch.dict("os.environ", {}, clear=True)
    def test_timeout_raises_provider_timeout_with_correct_message(self, mock_env):
        timeout_err = URLError("connection timed out")
        with patch("app.openai_compat.urlopen", side_effect=timeout_err):
            with self.assertRaises(ProviderTimeout) as caught:
                openai_compat.complete(MESSAGES, base_url="https://api.openai.com/v1", label="OpenAI", model="m")
            self.assertEqual(str(caught.exception), "The AI provider took too long. Try a faster model or raise LLM_TIMEOUT.")

    def test_retry_wait_capping_and_parsing(self):
        self.assertEqual(retry_wait({"Retry-After": "15"}), 15.0)
        self.assertEqual(retry_wait({"retry-after": "60"}), 30.0)  # Capped at 30s
        self.assertEqual(retry_wait({"Retry-After": "invalid"}, default=2.0), 2.0)
        self.assertEqual(retry_wait({}, default=1.5), 1.5)
