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
