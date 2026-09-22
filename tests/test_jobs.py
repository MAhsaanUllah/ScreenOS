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
