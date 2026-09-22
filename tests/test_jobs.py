import os, tempfile, unittest
from fastapi.testclient import TestClient
import app.main as web

class JobsChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(cls.tmp.name, "test.db")
        cls.client = TestClient(web.app)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)
    def _reg(self, org, email):
        r = self.client.post("/api/auth/register", headers={"X-Screenos":"1"}, json={"org_name":org,"email":email,"password":"password123"})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()
    def _h(self, tok): return {"X-Screenos":"1","Authorization":f"Bearer {tok}"}
    def test_create_list_get_update(self):
        a = self._reg("AcmeJobs","jobs@acme.test")
        h = self._h(a["token"])
        c = self.client.post("/api/jobs", headers=h, json={"title":"Backend Engineer","jd_text":"Build APIs"})
        self.assertEqual(c.status_code,200,c.text)
        jid = c.json()["id"]
        lst = self.client.get("/api/jobs", headers=h)
        self.assertEqual(len(lst.json()),1)
        get = self.client.get(f"/api/jobs/{jid}", headers=h)
        self.assertEqual(get.json()["title"],"Backend Engineer")
        upd = self.client.put(f"/api/jobs/{jid}", headers=h, json={"title":"Senior Backend"})
        self.assertEqual(upd.json()["title"],"Senior Backend")
        # rubric 100
        rub = [{"requirement":"A","points":50,"evidence":"x"},{"requirement":"B","points":50,"evidence":"y"}]
        r2 = self.client.put(f"/api/jobs/{jid}", headers=h, json={"rubric":rub, "rubric_approved":1})
        self.assertEqual(r2.status_code,200)
        self.assertEqual(r2.json()["rubric_approved"],1)
        # open requires approved
        o = self.client.put(f"/api/jobs/{jid}", headers=h, json={"status":"OPEN"})
        self.assertEqual(o.json()["status"],"OPEN")
        # close
        cl = self.client.post(f"/api/jobs/{jid}/close", headers=h)
        self.assertEqual(cl.json()["status"],"CLOSED")
    def test_cross_org_blocked(self):
        a = self._reg("OrgA","a@a.test")
        b = self._reg("OrgB","b@b.test")
        ha, hb = self._h(a["token"]), self._h(b["token"])
        r = self.client.post("/api/jobs", headers=ha, json={"title":"JobA"})
        jid = r.json()["id"]
        self.assertEqual(self.client.get(f"/api/jobs/{jid}", headers=hb).status_code,404)
        self.assertEqual(self.client.get("/api/jobs", headers=hb).json(),[])
    def test_existing_reviews_still_valid(self):
        u = self._reg("OldOrg","old@test.test")
        h = self._h(u["token"])
        # create review without job (old flow)
        prev = self.client.post("/api/preview", headers=h, files={"file":("cv.txt", b"Amina Example\nBuilt Python")})
        self.assertEqual(prev.status_code,200)
        conf = self.client.post("/api/preview/confirm", headers=h, data={"raw_text":prev.json()["raw_text"]})
        self.assertEqual(conf.status_code,200)
        # list reviews still works
        lst = self.client.get("/api/reviews", headers=h)
        self.assertTrue(len(lst.json())>=1)
    def test_review_can_reference_job(self):
        u = self._reg("RefOrg","ref@test.test")
        h = self._h(u["token"])
        j = self.client.post("/api/jobs", headers=h, json={"title":"RefJob"})
        jid = j.json()["id"]
        # preview + confirm without job_id still works, but we can manually set job_id via direct db? For Chunk1 just ensure column exists
        prev = self.client.post("/api/preview", headers=h, files={"file":("cv.txt", b"Ali Khan\nPython")})
        conf = self.client.post("/api/preview/confirm", headers=h, data={"raw_text":prev.json()["raw_text"]})
        self.assertEqual(conf.status_code,200)
        # ensure reviews table has job_id column
        from app import db
        rows = db.rows("SELECT job_id FROM reviews LIMIT 1")
        self.assertTrue(True)  # column exists if no error

class RubricDraftChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(cls.tmp.name, "test2.db")
        cls.client = TestClient(web.app)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)
    def _reg(self, org, email):
        r = self.client.post("/api/auth/register", headers={"X-Screenos":"1"}, json={"org_name":org,"email":email,"password":"password123"})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()
    def _h(self, tok): return {"X-Screenos":"1","Authorization":f"Bearer {tok}"}
    def test_generate_store_draft(self):
        from unittest.mock import patch
        import json
        a = self._reg("DraftOrg","draft@test.test")
        h = self._h(a["token"])
        j = self.client.post("/api/jobs", headers=h, json={"title":"Backend","jd_text":"Need Python FastAPI and testing and RAG and DB per tenant and monitoring."})
        jid = j.json()["id"]
        fake = json.dumps({"criteria":[{"requirement":"Python FastAPI","points":20,"evidence":"FastAPI service"},{"requirement":"RAG","points":20,"evidence":"RAG with quotes"},{"requirement":"DB per tenant","points":20,"evidence":"tenant isolation"},{"requirement":"Testing","points":20,"evidence":"tests"},{"requirement":"Monitoring","points":20,"evidence":"monitoring"}]})
        with patch("app.providers.complete", return_value=fake):
            r = self.client.post(f"/api/jobs/{jid}/rubric/draft", headers=h)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["rubric_approved"],0)
        self.assertEqual(len(r.json()["rubric"]),5)
    def test_invalid_total_rejected(self):
        a = self._reg("InvOrg","inv@test.test")
        h = self._h(a["token"])
        j = self.client.post("/api/jobs", headers=h, json={"title":"T","jd_text":"JD text long enough for test generation."})
        jid = j.json()["id"]
        bad = [{"requirement":"A","points":30,"evidence":"x"},{"requirement":"B","points":30,"evidence":"y"}]  # 60 not 100
        r = self.client.put(f"/api/jobs/{jid}", headers=h, json={"rubric":bad})
        self.assertEqual(r.status_code,400)
        self.assertIn("100", r.text)
    def test_edit_draft(self):
        a = self._reg("EditOrg","edit@test.test")
        h = self._h(a["token"])
        j = self.client.post("/api/jobs", headers=h, json={"title":"E","jd_text":"JD"})
        jid = j.json()["id"]
        rub = [{"requirement":"A","points":50,"evidence":"x"},{"requirement":"B","points":50,"evidence":"y"}]
        r = self.client.put(f"/api/jobs/{jid}", headers=h, json={"rubric":rub})
        self.assertEqual(r.status_code,200)
        # edit one point
        rub2 = [{"requirement":"A","points":60,"evidence":"x"},{"requirement":"B","points":40,"evidence":"y"}]
        r2 = self.client.put(f"/api/jobs/{jid}", headers=h, json={"rubric":rub2})
        self.assertEqual(r2.status_code,200)
        self.assertEqual(r2.json()["rubric"][0]["points"],60)
    def test_approve_valid(self):
        a = self._reg("ApprOrg","appr@test.test")
        h = self._h(a["token"])
        j = self.client.post("/api/jobs", headers=h, json={"title":"T","jd_text":"JD"})
        jid = j.json()["id"]
        rub = [{"requirement":"A","points":50,"evidence":"x"},{"requirement":"B","points":50,"evidence":"y"}]
        self.client.put(f"/api/jobs/{jid}", headers=h, json={"rubric":rub})
        r = self.client.post(f"/api/jobs/{jid}/rubric/approve", headers=h)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()["rubric_approved"],1)
        self.assertEqual(r.json()["status"],"OPEN")
    def test_cross_org_blocked_rubric(self):
        a = self._reg("C1","c1@test.test")
        b = self._reg("C2","c2@test.test")
        ha, hb = self._h(a["token"]), self._h(b["token"])
        j = self.client.post("/api/jobs", headers=ha, json={"title":"J","jd_text":"JD"})
        jid = j.json()["id"]
        self.assertEqual(self.client.post(f"/api/jobs/{jid}/rubric/draft", headers=hb).status_code,404)
    def test_not_ready_without_approved(self):
        a = self._reg("ReadyOrg","ready@test.test")
        h = self._h(a["token"])
        j = self.client.post("/api/jobs", headers=h, json={"title":"J","jd_text":"JD"})
        jid = j.json()["id"]
        rub = [{"requirement":"A","points":50,"evidence":"x"},{"requirement":"B","points":50,"evidence":"y"}]
        self.client.put(f"/api/jobs/{jid}", headers=h, json={"rubric":rub})
        # still DRAFT, not approved
        get = self.client.get(f"/api/jobs/{jid}", headers=h)
        self.assertEqual(get.json()["rubric_approved"],0)
        self.assertEqual(get.json()["status"],"DRAFT")
    def test_old_review_unchanged_after_rubric_edit(self):
        a = self._reg("HistOrg","hist@test.test")
        h = self._h(a["token"])
        # old review without job
        prev = self.client.post("/api/preview", headers=h, files={"file":("cv.txt", b"Amina Example\nBuilt Python")})
        conf = self.client.post("/api/preview/confirm", headers=h, data={"raw_text":prev.json()["raw_text"]})
        rid = conf.json()["review_id"]
        # create job and edit rubric
        j = self.client.post("/api/jobs", headers=h, json={"title":"J","jd_text":"JD"})
        jid = j.json()["id"]
        rub = [{"requirement":"A","points":50,"evidence":"x"},{"requirement":"B","points":50,"evidence":"y"}]
        self.client.put(f"/api/jobs/{jid}", headers=h, json={"rubric":rub})
        # old review still readable and unchanged
        det = self.client.get(f"/api/reviews/{rid}", headers=h)
        self.assertEqual(det.status_code,200)
        self.assertIsNone(det.json()["card"])
    def test_legacy_global_still_readable(self):
        # GET /api/rubric global still works
        a = self._reg("LegOrg","leg@test.test")
        h = self._h(a["token"])
        r = self.client.get("/api/rubric", headers=h)
        self.assertEqual(r.status_code,200)
        self.assertIn("rows", r.json())
