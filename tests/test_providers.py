import unittest
from unittest.mock import patch

from app import providers
from app.llm_limits import ProviderBusy, ProviderTimeout


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
    def test_busy_failure_message(self, settings):
        busy = lambda _: (_ for _ in ()).throw(ProviderBusy("quota hit"))
        with patch.dict(providers.PROVIDERS, {"deepseek": busy, "gemini": busy}):
            with self.assertRaisesRegex(providers.ScoringUnavailable, "The AI provider is busy \\(rate limit\\)\\. Try again in a minute\\."):
                providers.complete([])

    @patch("app.providers.dotenv_values", return_value={"LLM_PROVIDER": "deepseek,gemini"})
    @patch.dict("app.providers.os.environ", {}, clear=True)
    def test_timeout_failure_message(self, settings):
        timed_out = lambda _: (_ for _ in ()).throw(ProviderTimeout("timed out"))
        with patch.dict(providers.PROVIDERS, {"deepseek": timed_out, "gemini": timed_out}):
            with self.assertRaisesRegex(providers.ScoringUnavailable, "The AI provider took too long\\. Try a faster model or raise LLM_TIMEOUT\\."):
                providers.complete([])

    @patch("app.providers.dotenv_values", return_value={"LLM_PROVIDER": "deepseek,gemini"})
    @patch.dict("app.providers.os.environ", {}, clear=True)
    def test_exception_type_recognition_not_string_matching(self, settings):
        # A plain ValueError whose text has "rate limit" must NOT be treated as ProviderBusy
        fake_busy = lambda _: (_ for _ in ()).throw(ValueError("The AI provider is busy (rate limit)"))
        with patch.dict(providers.PROVIDERS, {"deepseek": fake_busy, "gemini": fake_busy}):
            with self.assertRaisesRegex(providers.ScoringUnavailable, "Scoring is temporarily unavailable\\. Your CV preview is safe; try again shortly\\."):
                providers.complete([])

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
