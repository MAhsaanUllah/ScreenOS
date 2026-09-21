import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as web
from app import deepseek, providers
from app.credentials import resolve
from app.providers import CATALOG


class CredentialChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(cls.tmp.name, "test.db")
        cls.client = TestClient(web.app)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)

    def _register(self, org, email):
        reply = self.client.post("/api/auth/register", headers={"X-Screenos": "1"},
                                 json={"org_name": org, "email": email, "password": "password123"})
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()

    def _headers(self, token):
        return {"X-Screenos": "1", "Authorization": f"Bearer {token}"}

    def test_key_is_stored_but_never_returned(self):
        admin = self._register("Acme", "keys@acme.test")
        headers = self._headers(admin["token"])
        secret = "sk-live-abcdef123456"
        saved = self.client.post("/api/settings/llm", headers=headers,
                                 json={"provider": "deepseek", "api_key": secret})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()[0], {"provider": "deepseek", "model": "deepseek-v4-flash",
                                           "hint": "…3456", "updated_at": saved.json()[0]["updated_at"]})
        self.assertNotIn(secret, saved.text)

        listed = self.client.get("/api/settings/llm", headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn(secret, listed.text)

        # The server can still resolve the real key for scoring.
        self.assertEqual(resolve(admin["org"]["id"])[0]["api_key"], secret)

    def test_upsert_validation_and_org_isolation(self):
        admin = self._register("Beta", "keys@beta.test")
        headers = self._headers(admin["token"])
        body = {"provider": "gemini", "api_key": "gemini-key-000111222"}
        self.assertEqual(self.client.post("/api/settings/llm", headers=headers, json=body).status_code, 200)
        again = self.client.post("/api/settings/llm", headers=headers,
                                 json={**body, "model": "gemini-9-pro", "api_key": "gemini-key-333444555"})
        self.assertEqual(len(again.json()), 1)
        self.assertEqual(again.json()[0]["model"], "gemini-9-pro")
        self.assertEqual(again.json()[0]["hint"], "…4555")

        self.assertEqual(self.client.post("/api/settings/llm", headers=headers,
                         json={"provider": "commandcode", "api_key": "x" * 20}).status_code, 400)
        self.assertEqual(self.client.post("/api/settings/llm", headers=headers,
                         json={"provider": "deepseek", "api_key": "short"}).status_code, 400)

        stranger = self._register("Beta Two", "keys@beta2.test")
        self.assertEqual(self.client.get("/api/settings/llm",
                         headers=self._headers(stranger["token"])).json(), [])

    def test_only_admin_can_set_keys(self):
        admin = self._register("Gamma", "admin@gamma.test")
        member = self._register("Delta", "member@delta.test")
        self.client.post("/api/team/members", headers=self._headers(admin["token"]),
                         json={"email": "member@delta.test", "role": "RECRUITER"})
        switched = self.client.post("/api/auth/switch-org", headers=self._headers(member["token"]),
                                    json={"org_id": admin["org"]["id"]})
        headers = self._headers(switched.json()["token"])
        self.assertEqual(self.client.post("/api/settings/llm", headers=headers,
                         json={"provider": "deepseek", "api_key": "sk-member-123456"}).status_code, 403)
        # A recruiter can still see which providers are configured.
        self.assertEqual(self.client.get("/api/settings/llm", headers=headers).status_code, 200)

    def test_scoring_reaches_the_provider_with_the_organization_key(self):
        admin = self._register("Epsilon", "byok@epsilon.test")
        headers = self._headers(admin["token"])
        secret = "sk-org-key-999888777"
        self.client.post("/api/settings/llm", headers=headers,
                         json={"provider": "deepseek", "api_key": secret, "model": "org-model"})
        preview = self.client.post("/api/preview", headers=headers,
                                   files={"file": ("cv.txt", b"Amina Example\nBuilt Python tools.")},
                                   data={"name": "Amina Example"})
        token = preview.json()["review_id"]
        seen = {}

        def fake(messages, **kwargs):
            seen.update(kwargs)
            payload = json.loads(messages[1]["content"])
            return json.dumps(dict(candidate_hash=payload["candidate_hash"], job_id=payload["job_id"],
                overall_score=0, verdict="WEAK_MATCH", flagged_for_human=True, notes="byok",
                criteria=[dict(criterion=k, weight=v, status="NOT_FOUND", score=0, evidence_quote="")
                          for k, v in payload["rubric"].items()]))

        with patch.dict(providers.PROVIDERS, {"deepseek": fake}):
            reply = self.client.post(f"/api/reviews/{token}/score", headers=headers,
                                     json={"cleaned_text": "Built Python tools."})
        self.assertEqual(reply.status_code, 200, reply.text)
        self.assertEqual(seen, {"key": secret, "model": "org-model"})

    def test_every_catalog_provider_can_be_configured(self):
        admin = self._register("Zeta", "catalog@zeta.test")
        headers = self._headers(admin["token"])
        for provider, spec in CATALOG.items():
            with self.subTest(provider=provider):
                key = "sk-" + provider + "-123456" if spec["needs_key"] else ""
                reply = self.client.post("/api/settings/llm", headers=headers,
                                         json={"provider": provider, "api_key": key})
                self.assertEqual(reply.status_code, 200, reply.text)
        listed = {row["provider"]: row
                  for row in self.client.get("/api/settings/llm", headers=headers).json()}
        self.assertEqual(set(listed), set(CATALOG))
        self.assertEqual(listed["ollama"]["hint"], "not required")
        self.assertEqual(listed["openai"]["model"], CATALOG["openai"]["default_model"])

        catalog = self.client.get("/api/providers").json()
        self.assertEqual({row["id"] for row in catalog}, set(CATALOG))
        self.assertFalse(next(row for row in catalog if row["id"] == "ollama")["needs_key"])


class ByokFailoverChecks(unittest.TestCase):
    def test_org_keys_are_tried_in_order_with_fallback(self):
        calls = []

        def primary(messages, **kwargs):
            calls.append(("deepseek", kwargs))
            raise ValueError("primary provider is down")

        def backup(messages, **kwargs):
            calls.append(("gemini", kwargs))
            return "{}"

        entries = [{"provider": "deepseek", "api_key": "k1", "model": "m1"},
                   {"provider": "gemini", "api_key": "k2", "model": "m2"}]
        with patch.dict(providers.PROVIDERS, {"deepseek": primary, "gemini": backup}):
            self.assertEqual(providers.complete([], credentials=entries), "{}")
        self.assertEqual(calls, [("deepseek", {"key": "k1", "model": "m1"}),
                                 ("gemini", {"key": "k2", "model": "m2"})])

    def test_all_org_keys_down_stays_recruiter_friendly(self):
        down = lambda messages, **kwargs: (_ for _ in ()).throw(ValueError("private provider detail"))
        with patch.dict(providers.PROVIDERS, {"deepseek": down, "gemini": down}):
            with self.assertRaisesRegex(providers.ScoringUnavailable, "preview is safe") as caught:
                providers.complete([], credentials=[{"provider": "deepseek", "api_key": "k", "model": "m"}])
        self.assertNotIn("private", str(caught.exception))

    @patch("app.deepseek.dotenv_values", return_value={})
    @patch.dict("os.environ", {}, clear=True)
    def test_transport_prefers_the_supplied_key_over_the_environment(self, _config):
        reply = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
        messages = [{"role": "user", "content": "test"}]
        with patch("app.deepseek.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())) as send:
            self.assertEqual(deepseek.complete(messages, key="org-key", model="org-model"), "{}")
        request = send.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer org-key")
        self.assertEqual(json.loads(request.data)["model"], "org-model")
