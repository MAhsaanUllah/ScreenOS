import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main as web


class WebChecks(unittest.TestCase):
    def test_preview_score_and_human_decision(self):
        web.reviews.clear()
        client=TestClient(web.app)
        headers={"X-Screenos":"1"}
        self.assertEqual(client.get("/").status_code,200)
        self.assertEqual(client.post("/api/preview").status_code,403)
        self.assertEqual(client.post("/api/preview",headers={**headers,"Origin":"https://other.test"}).status_code,403)
        reply=client.post("/api/preview",headers=headers,files={"file":("cv.txt",b"Amina Example\nBuilt Python tools.")},data={"name":"Amina Example"})
        self.assertEqual(reply.status_code,200)
        token=reply.json()["review_id"]
        self.assertNotIn("Amina Example",reply.json()["cleaned_text"])
        decision=f"/api/reviews/{token}/decision"
        self.assertEqual(client.post(decision,headers=headers,json={"decision":"APPROVE"}).status_code,409)
        def fake(messages):
            p=json.loads(messages[1]["content"])
            self.assertIn("Reviewed text",p["candidate_data"])
            return json.dumps(dict(candidate_hash=p["candidate_hash"],job_id=p["job_id"],overall_score=0,verdict="WEAK_MATCH",flagged_for_human=True,notes="Test only",criteria=[dict(criterion=k,weight=v,status="NOT_FOUND",score=0,evidence_quote="") for k,v in p["rubric"].items()]))
        with patch.object(web,"complete",fake):
            result=client.post(f"/api/reviews/{token}/score",headers=headers,json={"cleaned_text":"Reviewed text"})
        self.assertEqual(result.status_code,200,result.text)
        with tempfile.TemporaryDirectory() as folder, patch.object(web,"ROOT",Path(folder)):
            saved=client.post(decision,headers=headers,json={"decision":"REJECT","notes":"Needs direct evidence"})
            self.assertEqual(saved.status_code,200)
            self.assertEqual(len(list((Path(folder)/"output").glob("*.json"))),1)
            self.assertEqual(client.post(decision,headers=headers,json={"decision":"APPROVE"}).status_code,409)
        web.reviews.clear()
