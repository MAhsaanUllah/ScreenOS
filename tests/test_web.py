import json
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main as web
from app.providers import ScoringUnavailable


class WebChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(cls.tmp.name, "test.db")
        cls.client = TestClient(web.app)
        reply = cls.client.post("/api/auth/register", headers={"X-Screenos": "1"}, json={
            "org_name": "Acme Corp", "email": "recruiter@acme.test", "password": "password123"})
        cls.token = reply.json()["token"]
        cls.headers = {"X-Screenos": "1", "Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)

    def test_preview_score_and_human_decision(self):
        client = self.client
        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(client.post("/api/preview", headers={"X-Screenos": "1"},
                                     files={"file": ("cv.txt", b"Amina Example")},
                                     data={"name": "Amina Example"}).status_code, 401)
        self.assertEqual(client.post("/api/preview", headers=self.headers,
                                     files={"file": ("cv.csv", b"Amina Example")},
                                     data={"name": "Amina Example"}).status_code, 400)

        reply = client.post("/api/preview", headers=self.headers,
                            files={"file": ("cv.txt", b"Amina Example\nBuilt Python tools.")},
                            data={"name": "Amina Example"})
        self.assertEqual(reply.status_code, 200)
        token = reply.json()["review_id"]
        self.assertNotIn("Amina Example", reply.json()["cleaned_text"])

        decision = f"/api/reviews/{token}/decision"
        self.assertEqual(client.post(decision, headers=self.headers,
                                    json={"decision": "APPROVE"}).status_code, 409)

        def fake(messages):
            payload = json.loads(messages[1]["content"])
            self.assertIn("Reviewed text", payload["candidate_data"])
            return json.dumps(dict(candidate_hash=payload["candidate_hash"], job_id=payload["job_id"],
                overall_score=0, verdict="WEAK_MATCH", flagged_for_human=True, notes="Test only",
                criteria=[dict(criterion=k, weight=v, status="NOT_FOUND", score=0, evidence_quote="")
                          for k, v in payload["rubric"].items()]))
        with patch.object(web, "complete", fake):
            result = client.post(f"/api/reviews/{token}/score", headers=self.headers,
                                 json={"cleaned_text": "Reviewed text"})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(client.post(f"/api/reviews/{token}/score", headers=self.headers,
                                    json={"cleaned_text": "Reviewed text"}).status_code, 409)

        saved = client.post(decision, headers=self.headers, json={"decision": "REJECT", "notes": "Needs direct evidence"})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["decision"], "REJECT")
        self.assertEqual(client.post(decision, headers=self.headers,
                                    json={"decision": "APPROVE"}).status_code, 409)
        # Queue must surface the stored decision verbatim so the UI filter matches.
        self.assertEqual(client.get("/api/reviews", headers=self.headers).json()[0]["status"], "REJECT")

    def test_provider_downtime_is_safe_and_retryable(self):
        client = self.client
        reply = client.post("/api/preview", headers=self.headers,
                            files={"file": ("cv.txt", b"Sample Candidate\nBuilt Python tools.")},
                            data={"name": "Sample Candidate"})
        token = reply.json()["review_id"]
        with patch.object(web, "complete", side_effect=ScoringUnavailable(
                "Scoring is temporarily unavailable. Your CV preview is safe; try again shortly.")):
            result = client.post(f"/api/reviews/{token}/score", headers=self.headers,
                                 json={"cleaned_text": "Built Python tools."})
        self.assertEqual(result.status_code, 503)
        self.assertIn("preview is safe", result.json()["detail"])

    def test_loopback_dev_origin_is_allowed_but_others_are_not(self):
        client = self.client
        self.assertEqual(client.get("/", headers={"Origin": "http://localhost:5174"}).status_code, 200)
        self.assertEqual(client.get("/", headers={"Origin": "http://127.0.0.1:5175"}).status_code, 200)
        blocked = client.get("/", headers={"Origin": "http://evil.test"})
        self.assertEqual(blocked.status_code, 403)
        self.assertIn("Cross-origin", blocked.json()["detail"])

    def test_register_login_and_tenant_boundary(self):
        client = self.client
        registered = client.post("/api/auth/register", headers={"X-Screenos": "1"}, json={
            "org_name": "Globex", "email": "lead@globex.test", "password": "password123"})
        self.assertEqual(registered.status_code, 200)
        payload = registered.json()
        self.assertEqual(payload["org"]["name"], "Globex")
        self.assertEqual(payload["role"], "ADMIN")
        self.assertEqual([o["name"] for o in payload["orgs"]], ["Globex"])

        login = client.post("/api/auth/login", headers={"X-Screenos": "1"},
                            json={"email": "lead@globex.test", "password": "password123"})
        self.assertEqual(login.status_code, 200)

        switched = client.post("/api/auth/switch-org", headers={"X-Screenos": "1", "Authorization": f"Bearer {payload['token']}"},
                               json={"org_id": "missing-org"})
        self.assertEqual(switched.status_code, 403)

        other = client.post("/api/preview", headers={"X-Screenos": "1", "Authorization": f"Bearer {payload['token']}"},
                            files={"file": ("cv.txt", b"Amina Example")}, data={"name": "Amina Example"})
        self.assertEqual(other.status_code, 200)
        # Acme's recruiter cannot read Globex reviews.
        peek = client.post(f"/api/reviews/{other.json()['review_id']}/score", headers=self.headers,
                           json={"cleaned_text": "x"})
        self.assertEqual(peek.status_code, 404)

    def test_queue_rubric_endpoints_are_tenant_scoped(self):
        client = self.client
        preview = client.post("/api/preview", headers=self.headers,
                              files={"file": ("cv.txt", b"Amina Example\nBuilt Python tools.")},
                              data={"name": "Amina Example"})
        token = preview.json()["review_id"]

        listed = client.get("/api/reviews", headers=self.headers).json()
        self.assertEqual(listed[0]["short"], token[:8])
        self.assertEqual(listed[0]["status"], "PENDING")
        self.assertIsNone(listed[0]["score"])

        detail = client.get(f"/api/reviews/{token}", headers=self.headers).json()
        self.assertIn("Built Python tools.", detail["cleaned_text"])
        self.assertEqual(detail["card"], None)

        rubric = client.get("/api/rubric").json()
        self.assertEqual(rubric["job"], "AI Engineer / Automation")
        self.assertEqual(sum(r["points"] for r in rubric["rows"]), 100)