import os
import tempfile
import unittest

from fastapi.testclient import TestClient

import app.main as web


class TeamChecks(unittest.TestCase):
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

    def _id(self, members, email):
        return next(m["id"] for m in members if m["email"] == email)

    def test_admin_can_add_member_and_change_role(self):
        admin = self._register("Acme", "admin@acme.test")
        headers = self._headers(admin["token"])
        self.assertEqual([m["role"] for m in self.client.get("/api/team", headers=headers).json()], ["ADMIN"])

        self._register("Solo", "solo@globex.test")
        added = self.client.post("/api/team/members", headers=headers,
                                 json={"email": "solo@globex.test", "role": "RECRUITER"})
        self.assertEqual(added.status_code, 200, added.text)
        self.assertEqual(len(added.json()), 2)
        self.assertEqual(self.client.post("/api/team/members", headers=headers,
                         json={"email": "solo@globex.test"}).status_code, 409)
        self.assertEqual(self.client.post("/api/team/members", headers=headers,
                         json={"email": "ghost@nowhere.test"}).status_code, 404)
        self.assertEqual(self.client.post("/api/team/members", headers=headers,
                         json={"email": "solo@globex.test", "role": "OWNER"}).status_code, 400)

        member = self._id(added.json(), "solo@globex.test")
        promoted = self.client.post(f"/api/team/members/{member}/role", headers=headers, json={"role": "ADMIN"})
        self.assertEqual(promoted.status_code, 200, promoted.text)
        self.assertEqual(next(m["role"] for m in promoted.json() if m["id"] == member), "ADMIN")
        self.assertEqual(self.client.post(f"/api/team/members/{admin['user']['id']}/role",
                         headers=headers, json={"role": "RECRUITER"}).status_code, 400)
        self.assertEqual(self.client.post("/api/team/members/missing/role",
                         headers=headers, json={"role": "ADMIN"}).status_code, 404)

    def test_recruiter_cannot_manage_team(self):
        admin = self._register("Beta", "admin@beta.test")
        member = self._register("Gamma", "member@gamma.test")
        self.client.post("/api/team/members", headers=self._headers(admin["token"]),
                         json={"email": "member@gamma.test", "role": "RECRUITER"})
        switched = self.client.post("/api/auth/switch-org", headers=self._headers(member["token"]),
                                    json={"org_id": admin["org"]["id"]})
        self.assertEqual(switched.status_code, 200, switched.text)
        self.assertEqual(switched.json()["role"], "RECRUITER")
        headers = self._headers(switched.json()["token"])
        self.assertEqual(len(self.client.get("/api/team", headers=headers).json()), 2)
        self.assertEqual(self.client.post("/api/team/members", headers=headers,
                         json={"email": "member@gamma.test"}).status_code, 403)
        self.assertEqual(self.client.post(f"/api/team/members/{admin['user']['id']}/role",
                         headers=headers, json={"role": "RECRUITER"}).status_code, 403)
