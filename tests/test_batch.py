import io
import os
import tempfile
import unittest
import zipfile

from fastapi.testclient import TestClient

import app.main as web


def archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, data in files.items():
            bundle.writestr(name, data)
    return buffer.getvalue()


class BatchChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(cls.tmp.name, "test.db")
        cls.client = TestClient(web.app)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)

    def _headers(self, org, email):
        reply = self.client.post("/api/auth/register", headers={"X-Screenos": "1"},
                                 json={"org_name": org, "email": email, "password": "password123"})
        self.assertEqual(reply.status_code, 200, reply.text)
        return {"X-Screenos": "1", "Authorization": f"Bearer {reply.json()['token']}"}

    def _post(self, headers, payload):
        return self.client.post("/api/preview/batch", headers=headers,
                                files={"file": ("batch.zip", payload)})

    def test_ingests_named_resumes_and_reports_the_rest(self):
        headers = self._headers("Acme", "batch@acme.test")
        reply = self._post(headers, archive({
            "Amina_Example.txt": b"Amina Example\nBuilt Python tools.",
            "notes.png": b"\x89PNG",
            "blank.txt": b"   ",
        }))
        self.assertEqual(reply.status_code, 200, reply.text)
        body = reply.json()
        self.assertEqual(body["accepted"], 1)
        self.assertEqual(body["reviews"][0]["name_guess"], "Amina Example")
        self.assertEqual({item["filename"] for item in body["skipped"]}, {"notes.png", "blank.txt"})
        self.assertTrue(all(item["reason"] for item in body["skipped"]))

        detail = self.client.get(f"/api/reviews/{body['reviews'][0]['review_id']}", headers=headers)
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn("Amina Example", detail.json()["cleaned_text"])

    def test_caps_the_batch_and_rejects_non_zip_uploads(self):
        headers = self._headers("Beta", "batch@beta.test")
        overflow = self._post(headers, archive(
            {f"candidate{i}.txt": b"Sample Candidate\nBuilt Python tools." for i in range(51)}))
        self.assertEqual(overflow.status_code, 200, overflow.text)
        self.assertEqual(overflow.json()["accepted"], 50)
        self.assertEqual([item["reason"] for item in overflow.json()["skipped"]],
                         ["batch limit is 50 files"])

        broken = self._post(headers, b"definitely not a zip")
        self.assertEqual(broken.status_code, 400)
        self.assertIn("ZIP", broken.json()["detail"])
