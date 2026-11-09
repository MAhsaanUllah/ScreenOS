import io
import json
import unittest
from unittest.mock import patch
from app.deepseek import complete, ENDPOINT

class DeepSeekChecks(unittest.TestCase):
    @patch("app.deepseek.dotenv_values", return_value={"DEEPSEEK_API_KEY":"test", "DEEPSEEK_MODEL":"deepseek-v4-flash"})
    @patch.dict("os.environ", {}, clear=True)
    def test_contract_and_incomplete_response(self, config):
        messages=[{"role":"user","content":"test"}]
        for reason in ("stop", "length"):
            reply={"choices":[{"finish_reason":reason,"message":{"content":"{}"}}]}
            with patch("app.deepseek.urlopen",return_value=io.BytesIO(json.dumps(reply).encode())) as send:
                if reason == "stop":
                    self.assertEqual(complete(messages),"{}")
                    req=send.call_args.args[0]
                    self.assertEqual(req.full_url,ENDPOINT)
                    self.assertEqual(req.get_header("Authorization"),"Bearer test")
                    self.assertEqual(json.loads(req.data)["messages"],messages)
                else:
                    with self.assertRaises(ValueError):complete(messages)

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test", "LLM_TIMEOUT": "85"})
    def test_configurable_timeout(self):
        reply={"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}
        with patch("app.deepseek.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())) as send:
            complete([{"role":"user","content":"test"}])
            self.assertEqual(send.call_args.kwargs["timeout"], 85.0)

    @patch("app.deepseek.dotenv_values", return_value={"DEEPSEEK_API_KEY":"test"})
    @patch.dict("os.environ", {}, clear=True)
    @patch("app.deepseek.time.sleep")
    def test_rate_limit_429_retries_once_with_retry_after(self, sleep, config):
        from urllib.error import HTTPError
        reply={"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}
        err = HTTPError("https://example", 429, "rate limited", {"Retry-After": "45"}, None)
        with patch("app.deepseek.urlopen", side_effect=[err, io.BytesIO(json.dumps(reply).encode())]) as send:
            self.assertEqual(complete([{"role":"user","content":"test"}]), "{}")
            self.assertEqual(send.call_count, 2)
            sleep.assert_called_once_with(30.0)
