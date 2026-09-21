import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as web


class ComplianceChecks(unittest.TestCase):
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
        return {"X-Screenos": "1", "Authorization": f"Bearer {reply.json()['token']}"}

    def _screened(self, headers, decision=None):
        preview = self.client.post("/api/preview", headers=headers,
                                   files={"file": ("cv.txt", b"Amina Example\nBuilt Python tools.")},
                                   data={"name": "Amina Example"})
        token = preview.json()["review_id"]

        def fake(messages):
            payload = json.loads(messages[1]["content"])
            return json.dumps(dict(candidate_hash=payload["candidate_hash"], job_id=payload["job_id"],
                overall_score=0, verdict="WEAK_MATCH", flagged_for_human=True, notes="test",
                criteria=[dict(criterion=k, weight=v, status="NOT_FOUND", score=0, evidence_quote="")
                          for k, v in payload["rubric"].items()]))

        with patch.object(web, "complete", fake):
            self.client.post(f"/api/reviews/{token}/score", headers=headers,
                             json={"cleaned_text": "Built Python tools."})
        if decision:
            self.client.post(f"/api/reviews/{token}/decision", headers=headers,
                             json={"decision": decision})
        return token

    def test_report_counts_decisions_and_stays_org_scoped(self):
        headers = self._register("Acme", "admin@acme.test")
        self._screened(headers, "REJECT")
        self._screened(headers)

        report = self.client.get("/api/compliance", headers=headers)
        self.assertEqual(report.status_code, 200)
        body = report.json()
        self.assertEqual(body["organization"]["name"], "Acme")
        self.assertEqual(body["totals"], {"screened": 2, "decided": 1, "pending": 1})
        self.assertEqual(body["decisions"], {"APPROVE": 0, "REJECT": 1})
        self.assertEqual(body["verdicts"]["WEAK_MATCH"], 2)
        self.assertTrue(all(body["guardrails"].values()))
        self.assertEqual(len(body["records"]), 2)
        self.assertEqual(set(body["records"][0]),
                         {"candidate_hash", "score", "verdict", "decision", "screened_at", "decided_at"})
        # CV text and demographics never leave the screening tables.
        self.assertNotIn("Amina", report.text)

        stranger = self._register("Other", "admin@other.test")
        self.assertEqual(self.client.get(
            "/api/compliance", headers=stranger).json()["totals"]["screened"], 0)
