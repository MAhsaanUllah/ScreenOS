import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as web
from app import db


def _card(messages):
    payload = json.loads(messages[1]["content"])
    return json.dumps(dict(candidate_hash=payload["candidate_hash"], job_id=payload["job_id"],
        overall_score=0, verdict="WEAK_MATCH", flagged_for_human=True, notes="test",
        criteria=[dict(criterion=k, weight=v, status="NOT_FOUND", score=0, evidence_quote="")
                  for k, v in payload["rubric"].items()]))


class NotificationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(cls.tmp.name, "t.db")
        cls.client = TestClient(web.app, raise_server_exceptions=False)  # see the real status, not a raised error
        reply = cls.client.post("/api/auth/register", headers={"X-Screenos": "1"},
                                json={"org_name": "Org", "email": "n@test.test", "password": "password123"})
        cls.h = {"X-Screenos": "1", "Authorization": f"Bearer {reply.json()['token']}"}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)

    def _decide(self, decision):
        raw = self.client.post("/api/preview", headers=self.h,
                               files={"file": ("cv.txt", b"Amina Example\nBuilt Python tools.")}).json()["raw_text"]
        rid = self.client.post("/api/preview/confirm", headers=self.h,
                               data={"raw_text": raw, "name": "Amina Example"}).json()["review_id"]
        with patch.object(web, "complete", _card):
            self.assertEqual(self.client.post(f"/api/reviews/{rid}/score", headers=self.h, json={}).status_code, 200)
        self.assertEqual(self.client.post(f"/api/reviews/{rid}/decision", headers=self.h,
                                          json={"decision": decision}).status_code, 200)
        return rid

    def test_notifications_list_recent_decisions_newest_first(self):
        empty = self.client.get("/api/notifications", headers=self.h)
        self.assertEqual((empty.status_code, empty.json()), (200, []))

        first = self._decide("APPROVE")
        second = self._decide("REJECT")
        reply = self.client.get("/api/notifications", headers=self.h)
        self.assertEqual(reply.status_code, 200, reply.text)  # was a 500 (KeyError: 'decided_at')
        items = reply.json()
        self.assertEqual([i["id"] for i in items], [second[:8], first[:8]])
        self.assertEqual([i["decision"] for i in items], ["REJECT", "APPROVE"])
        stamp = db.row("SELECT decided_at FROM reviews WHERE id = ?", (second,))["decided_at"]
        self.assertEqual(items[0]["at"], stamp)  # the decision time, not the upload time

    def test_notifications_are_scoped_to_the_organisation(self):
        other = self.client.post("/api/auth/register", headers={"X-Screenos": "1"},
                                 json={"org_name": "Other", "email": "o@test.test", "password": "password123"})
        h = {"X-Screenos": "1", "Authorization": f"Bearer {other.json()['token']}"}
        self.assertEqual(self.client.get("/api/notifications", headers=h).json(), [])


if __name__ == "__main__":
    unittest.main()
