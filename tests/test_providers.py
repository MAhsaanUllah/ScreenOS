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
