import unittest
from unittest.mock import patch

from app import providers


class ProviderFailoverChecks(unittest.TestCase):
    @patch("app.providers.dotenv_values", return_value={"LLM_PROVIDER": "deepseek,gemini"})
    @patch.dict("app.providers.os.environ", {}, clear=True)
    def test_rate_limit_fails_over_without_exposing_provider_error(self, settings):
        with patch.dict(providers.PROVIDERS, {
            "deepseek": lambda _: (_ for _ in ()).throw(ValueError("secret rate-limit body")),
            "gemini": lambda _: "{}",
        }):
            with self.assertLogs("uvicorn.error", "INFO") as logs:
                self.assertEqual(providers.complete([]), "{}")
        self.assertNotIn("secret", " ".join(logs.output))

    @patch("app.providers.dotenv_values", return_value={"LLM_PROVIDER": "deepseek,gemini"})
    @patch.dict("app.providers.os.environ", {}, clear=True)
    def test_all_failures_return_recruiter_friendly_message(self, settings):
        unavailable = lambda _: (_ for _ in ()).throw(ValueError("private provider detail"))
        with patch.dict(providers.PROVIDERS, {"deepseek": unavailable, "gemini": unavailable}):
            with self.assertRaisesRegex(providers.ScoringUnavailable, "preview is safe") as caught:
                providers.complete([])
        self.assertNotIn("private", str(caught.exception))

    @patch("app.providers.dotenv_values", return_value={"LLM_PROVIDER": "deepseek,gemini"})
    @patch.dict("app.providers.os.environ", {}, clear=True)
    def test_rate_limit_failure_message_is_distinct(self, settings):
        rate_limited = lambda _: (_ for _ in ()).throw(ValueError("DeepSeek HTTP 429. Check quota or rate limits; retry later."))
        with patch.dict(providers.PROVIDERS, {"deepseek": rate_limited, "gemini": rate_limited}):
            with self.assertRaisesRegex(providers.ScoringUnavailable, "rate limit reached") as caught:
                providers.complete([])
        self.assertIn("preview is safe", str(caught.exception))

    @patch("app.providers.dotenv_values", return_value={"LLM_PROVIDER": "ollama"})
    @patch.dict("app.providers.os.environ", {}, clear=True)
    def test_ollama_uses_default_base_url(self, settings):
        with patch("app.openai_compat.complete", return_value="{}") as mock_complete:
            res = providers.complete([])
            self.assertEqual(res, "{}")
            mock_complete.assert_called_once()
            self.assertEqual(mock_complete.call_args.kwargs["base_url"], "http://localhost:11434/v1")

    @patch("app.providers.dotenv_values", return_value={"LLM_PROVIDER": "ollama"})
    @patch.dict("app.providers.os.environ", {"OLLAMA_BASE_URL": "http://host.docker.internal:11434/v1"}, clear=True)
    def test_ollama_uses_env_base_url(self, settings):
        with patch("app.openai_compat.complete", return_value="{}") as mock_complete:
            res = providers.complete([])
            self.assertEqual(res, "{}")
            mock_complete.assert_called_once()
            self.assertEqual(mock_complete.call_args.kwargs["base_url"], "http://host.docker.internal:11434/v1")
