import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from app.gemini import complete


class GeminiChecks(unittest.TestCase):
    @patch("app.gemini.load_dotenv")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-3.8-flash"})
    def test_transport_success_and_safe_failures(self, load):
        messages = [{"role": "system", "content": "trusted"}, {"role": "user", "content": "data"}]
        reply = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}
        with patch("app.gemini.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())) as send:
            self.assertEqual(complete(messages), "{}")
            request = send.call_args.args[0]
            self.assertNotIn("test-key", request.full_url)
            self.assertEqual(json.loads(request.data)["systemInstruction"]["parts"][0]["text"], "trusted")
        with patch("app.gemini.urlopen", side_effect=HTTPError("https://example",429,"secret",{},None)):
            with self.assertRaisesRegex(ValueError, "Quota or rate limit") as caught:
                complete(messages)
            self.assertNotIn("secret", str(caught.exception))
        for reply in ({}, {"candidates": [{"finishReason": "MAX_TOKENS"}]}):
            with patch("app.gemini.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())):
                with self.assertRaises(ValueError):
                    complete(messages)


    @patch("app.gemini.load_dotenv")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    @patch("app.gemini.time.sleep")
    def test_transient_retry_is_bounded(self, sleep, load):
        messages = [{"content": "trusted"}, {"content": "data"}]
        reply = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "{}"}]}}]}
        def unavailable():
            return HTTPError("https://example", 503, "private error body", {}, None)
        with patch("app.gemini.urlopen", side_effect=[unavailable(), io.BytesIO(json.dumps(reply).encode())]) as send:
            self.assertEqual(complete(messages), "{}")
            self.assertEqual(send.call_count, 2)
        sleep.reset_mock()
        with patch("app.gemini.urlopen", side_effect=[unavailable(), unavailable(), unavailable()]) as send:
            with self.assertRaisesRegex(ValueError, "after 3 attempts"):
                complete(messages)
            self.assertEqual(send.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])
        with patch("app.gemini.urlopen", side_effect=HTTPError("https://example",403,"secret",{},None)) as send:
            with self.assertRaises(ValueError):
                complete(messages)
            self.assertEqual(send.call_count, 1)
