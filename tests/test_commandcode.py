import io
import json
import unittest
from unittest.mock import patch
from app.commandcode import complete, ENDPOINT

class CommandCodeChecks(unittest.TestCase):
    @patch("app.commandcode.dotenv_values", return_value={"LLM_API_KEY":"test", "LLM_MODEL":"deepseek/deepseek-v4-flash"})
    @patch.dict("os.environ", {}, clear=True)
    def test_contract_and_incomplete_response(self, config):
        messages=[{"role":"user","content":"test"}]
        for reason in ("stop", "length"):
            reply={"choices":[{"finish_reason":reason,"message":{"content":"{}"}}]}
            with patch("app.commandcode.urlopen",return_value=io.BytesIO(json.dumps(reply).encode())) as send:
                if reason == "stop":
                    self.assertEqual(complete(messages),"{}")
                    req=send.call_args.args[0]
                    self.assertEqual(req.full_url,ENDPOINT)
                    self.assertEqual(req.get_header("Authorization"),"Bearer test")
                    self.assertEqual(json.loads(req.data)["messages"],messages)
                else:
                    with self.assertRaises(ValueError):complete(messages)
