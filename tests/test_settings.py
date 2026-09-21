import os
import tempfile
import unittest

from fastapi.testclient import TestClient

import app.main as web


class SettingsChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(cls.tmp.name, "test.db")
        cls.client = TestClient(web.app)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)

    def _register(self, org, email, password="password123"):
        reply = self.client.post("/api/auth/register", headers={"X-Screenos": "1"},
                                 json={"org_name": org, "email": email, "password": password})
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()

    def _login(self, email, password="password123"):
        return self.client.post("/api/auth/login", headers={"X-Screenos": "1"},
                                json={"email": email, "password": password})

    def _headers(self, token):
        return {"X-Screenos": "1", "Authorization": f"Bearer {token}"}

    def test_profile_and_rename(self):
        admin = self._register("Settings Co", "admin@settings.test")
        headers = self._headers(admin["token"])
        profile = self.client.get("/api/settings", headers=headers)
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["name"], "Settings Co")
        self.assertEqual(profile.json()["members"], 1)
        self.assertEqual(profile.json()["role"], "ADMIN")

        renamed = self.client.post("/api/settings/org", headers=headers, json={"name": "Renamed Co"})
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["name"], "Renamed Co")
        self.assertEqual(self.client.post("/api/settings/org", headers=headers,
                         json={"name": "   "}).status_code, 400)
        self.assertEqual(self.client.post("/api/settings/org", headers=headers,
                         json={"name": "x" * 81}).status_code, 400)

    def test_only_admin_can_rename(self):
        admin = self._register("Alpha", "admin@alpha.test")
        member = self._register("Beta", "member@beta.test")
        self.client.post("/api/team/members", headers=self._headers(admin["token"]),
                         json={"email": "member@beta.test", "role": "RECRUITER"})
        switched = self.client.post("/api/auth/switch-org", headers=self._headers(member["token"]),
                                    json={"org_id": admin["org"]["id"]})
        headers = self._headers(switched.json()["token"])
        self.assertEqual(self.client.post("/api/settings/org", headers=headers,
                         json={"name": "Hacked"}).status_code, 403)
        self.assertEqual(self.client.get("/api/settings", headers=headers).json()["role"], "RECRUITER")

    def test_password_change_rotates_credentials_and_revokes_other_sessions(self):
        admin = self._register("Gamma", "user@gamma.test")
        second = self._login("user@gamma.test")
        self.assertEqual(second.status_code, 200)
        headers = self._headers(admin["token"])

        self.assertEqual(self.client.post("/api/settings/password", headers=headers,
                         json={"current_password": "wrong", "new_password": "newpassword123"}).status_code, 401)
        self.assertEqual(self.client.post("/api/settings/password", headers=headers,
                         json={"current_password": "password123", "new_password": "short"}).status_code, 400)

        changed = self.client.post("/api/settings/password", headers=headers,
                                   json={"current_password": "password123", "new_password": "newpassword123"})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.client.get("/api/settings", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/settings",
                         headers=self._headers(second.json()["token"])).status_code, 401)
        self.assertEqual(self._login("user@gamma.test").status_code, 401)
        self.assertEqual(self._login("user@gamma.test", "newpassword123").status_code, 200)
