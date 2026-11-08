import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as web
from app import db
from app.guardrails import _guess_name, detect_pii, prepare_candidate

CV = (Path(__file__).parent / "fixtures" / "realistic_cv.txt").read_text(encoding="utf-8")
NO_NAME = "Built Python tools. Reviewed CV templates."


def _zip(name, data=b"x"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as bundle:
        bundle.writestr(name, data)
    return buf.getvalue()


class BatchPiiChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(cls.tmp.name, "t.db")
        cls.client = TestClient(web.app)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)

    def _headers(self, email):
        r = self.client.post("/api/auth/register", headers={"X-Screenos": "1"},
                             json={"org_name": email, "email": email, "password": "password123"})
        return {"X-Screenos": "1", "Authorization": f"Bearer {r.json()['token']}"}

    def _batch(self, headers, filename, text, via):
        files = ({"file": ("b.zip", _zip(filename))} if via == "zip"
                 else {"file": (filename, b"x")})
        with patch("app.batch.extract_text", return_value=text):
            reply = self.client.post("/api/preview/batch", headers=headers, files=files)
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()["reviews"][0]

    def _cleaned(self, headers, rid):
        return self.client.get(f"/api/reviews/{rid}", headers=headers).json()["cleaned_text"]

    def test_real_name_phone_urls_and_edu_years_never_reach_stored_text(self):
        for via in ("zip", "files"):
            with self.subTest(via=via):
                h = self._headers(f"pii-{via}@t.test")
                row = self._batch(h, "Resume_Final.pdf", CV, via)
                text = self._cleaned(h, row["review_id"])
                for gone in ("Ahmed Raza Khan", "0300 1234567", "ahmed.raza@gmail.com",
                             "linkedin.com/in/ahmedraza", "github.com/ahmedraza", "2018", "2014"):
                    self.assertNotIn(gone, text)
                for kept in ("Senior Software Engineer", "2019 - 2023", "promoted in 2021"):
                    self.assertIn(kept, text)
                self.assertEqual(row["pii_flag"], "unconfirmed")

    def test_generic_file_name_is_not_redacted_and_review_is_flagged(self):
        for via in ("zip", "files"):
            with self.subTest(via=via):
                h = self._headers(f"cv-{via}@t.test")
                row = self._batch(h, "CV.pdf", NO_NAME, via)
                self.assertEqual(row["pii_flag"], "name_not_found")
                self.assertIn("CV", self._cleaned(h, row["review_id"]))

    def _fake(self, messages):
        payload = json.loads(messages[1]["content"])
        return json.dumps(dict(candidate_hash=payload["candidate_hash"], job_id=payload["job_id"],
            overall_score=0, verdict="WEAK_MATCH", flagged_for_human=True, notes="t",
            criteria=[dict(criterion=k, weight=v, status="NOT_FOUND", score=0, evidence_quote="")
                      for k, v in payload["rubric"].items()]))

    def _score(self, h, rid):
        with patch.object(web, "complete", self._fake):
            return self.client.post(f"/api/reviews/{rid}/score", headers=h, json={})

    def test_flagged_review_cannot_be_scored_until_confirmed(self):
        h = self._headers("gate@t.test")
        rid = self._batch(h, "Resume_Final.pdf", CV, "zip")["review_id"]
        blocked = self._score(h, rid)
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["detail"], "Confirm personal details before scoring.")

        before = db.row("SELECT COUNT(*) AS n FROM reviews")["n"]
        done = self.client.post(f"/api/reviews/{rid}/confirm-pii", headers=h,
                                json={"remove_pii": [{"type": "custom", "value": "Python"}]})
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(db.row("SELECT COUNT(*) AS n FROM reviews")["n"], before)
        self.assertNotIn("Python", done.json()["cleaned_text"])
        self.assertEqual(self._score(h, rid).status_code, 200)

    def test_other_org_cannot_confirm(self):
        owner, other = self._headers("own@t.test"), self._headers("oth@t.test")
        rid = self._batch(owner, "Resume_Final.pdf", CV, "zip")["review_id"]
        reply = self.client.post(f"/api/reviews/{rid}/confirm-pii", headers=other, json={})
        self.assertEqual(reply.status_code, 404)
        self.assertEqual(self._score(owner, rid).status_code, 409)  # still flagged

    def test_name_not_found_needs_a_name_or_explicit_confirmation(self):
        h = self._headers("nn@t.test")

        def confirm(body):
            rid = self._batch(h, "CV.pdf", NO_NAME, "zip")["review_id"]
            return self.client.post(f"/api/reviews/{rid}/confirm-pii", headers=h, json=body).status_code

        self.assertEqual(confirm({}), 400)
        self.assertEqual(confirm({"confirm_no_name": True}), 200)
        self.assertEqual(confirm({"name": "Python"}), 200)
        self.assertEqual(confirm({"remove_pii": [{"type": "name", "value": "Python"}]}), 200)
        self.assertEqual(confirm({"raw_text": "x"}), 422)


class GuardrailRules(unittest.TestCase):
    def test_job_title_line_is_not_a_name(self):
        self.assertEqual(_guess_name(CV), "Ahmed Raza Khan")
        self.assertIsNone(_guess_name("Full Stack Developer\nBuilt things."))

    def test_year_ranges_are_not_phones(self):
        text = "Acme (2019 - 2023)\nBeta 2015-2018\nCall 0300 1234567"
        phones = [i["value"] for i in detect_pii(text) if i["type"] == "phone"]
        self.assertEqual(phones, ["0300 1234567"])

    def test_urls_are_detected(self):
        urls = {i["value"] for i in detect_pii(CV) if i["type"] == "url"}
        self.assertEqual(urls, {"linkedin.com/in/ahmedraza", "github.com/ahmedraza"})

    def test_degree_abbreviations_are_case_sensitive(self):
        for line in ("BS Software Engineering 2018", "FSc Pre-Medical 2014", "O Levels 2012", "B.Sc Physics 2010"):
            self.assertTrue(any(i["type"] == "year" for i in detect_pii(line)), line)
        for line in ("It may be 2018", "ma thesis due 2019", "intermediate Python since 2018"):
            self.assertFalse(any(i["type"] == "year" for i in detect_pii(line)), line)

    def test_graduation_year_does_not_touch_job_dates(self):
        text = "Acme (2019 - 2023)\nBS Computer Science, 2019"
        out = prepare_candidate(text, name="Zed", remove_pii=detect_pii(text))["cleaned_text"]
        self.assertIn("2019 - 2023", out)
        self.assertIn("[YEAR REMOVED]", out)


if __name__ == "__main__":
    unittest.main()
