import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as web
from app.rubrics import DEFAULT, list_rubrics, path_for


class RubricRegistryChecks(unittest.TestCase):
    def test_every_rubric_is_listed_and_resolvable(self):
        listed = list_rubrics()
        job_ids = [entry["job_id"] for entry in listed]
        self.assertIn(DEFAULT, job_ids)
        self.assertIn("python-backend", job_ids)
        for entry in listed:
            self.assertTrue(entry["job"])
            self.assertEqual(entry["points"], 100)
            self.assertEqual(path_for(entry["job_id"]).stem, entry["job_id"])

    def test_unknown_job_id_does_not_resolve(self):
        for job_id in ("missing", "../ai-engineer", "ai-engineer/../ai-engineer"):
            with self.subTest(job_id=job_id), self.assertRaises(KeyError):
                path_for(job_id)


class RubricSelectionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(cls.tmp.name, "test.db")
        cls.client = TestClient(web.app)
        reply = cls.client.post("/api/auth/register", headers={"X-Screenos": "1"},
                                json={"org_name": "Acme", "email": "rubrics@acme.test",
                                      "password": "password123"})
        cls.headers = {"X-Screenos": "1", "Authorization": f"Bearer {reply.json()['token']}"}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)

    def _preview(self):
        reply = self.client.post("/api/preview", headers=self.headers,
                                 files={"file": ("cv.txt", b"Amina Example\nBuilt Python tools.")},
                                 data={"name": "Amina Example"})
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()["review_id"]

    def test_rubrics_endpoint_lists_selectable_rubrics(self):
        reply = self.client.get("/api/rubrics")
        self.assertEqual(reply.status_code, 200)
        self.assertIn("python-backend", [entry["job_id"] for entry in reply.json()])

    def test_scoring_uses_the_selected_rubric(self):
        token = self._preview()
        seen = {}

        def fake(messages):
            payload = json.loads(messages[1]["content"])
            seen["job_id"] = payload["job_id"]
            return json.dumps(dict(candidate_hash=payload["candidate_hash"], job_id=payload["job_id"],
                overall_score=0, verdict="WEAK_MATCH", flagged_for_human=True, notes="Test only",
                criteria=[dict(criterion=k, weight=v, status="NOT_FOUND", score=0, evidence_quote="")
                          for k, v in payload["rubric"].items()]))

        with patch.object(web, "complete", fake):
            reply = self.client.post(f"/api/reviews/{token}/score", headers=self.headers,
                                     json={"cleaned_text": "Built Python tools.", "job_id": "python-backend"})
        self.assertEqual(reply.status_code, 200, reply.text)
        self.assertEqual(seen["job_id"], "python-backend")
        self.assertEqual(reply.json()["job_id"], "python-backend")

        queue = self.client.get("/api/reviews", headers=self.headers).json()
        self.assertEqual(next(row for row in queue if row["id"] == token)["job_id"], "python-backend")

    def test_unknown_rubric_is_rejected(self):
        token = self._preview()
        reply = self.client.post(f"/api/reviews/{token}/score", headers=self.headers,
                                 json={"cleaned_text": "Built Python tools.", "job_id": "missing-role"})
        self.assertEqual(reply.status_code, 400)
