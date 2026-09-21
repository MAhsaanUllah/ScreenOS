import json
import os
import tempfile
import unittest

from app import db
from app.calibration import for_org, summarize


def record(verdict, decision, candidate_hash="HASH-" + "a" * 64):
    return {"card": json.dumps({"verdict": verdict}), "decision": decision,
            "candidate_hash": candidate_hash}


class CalibrationChecks(unittest.TestCase):
    def test_flags_only_divergent_strong_and_weak_decisions(self):
        rows = [record("STRONG_MATCH", "APPROVE"), record("WEAK_MATCH", "REJECT"),
                record("STRONG_MATCH", "REJECT"), record("WEAK_MATCH", "APPROVE"),
                record("POSSIBLE_MATCH", "APPROVE"), record("POSSIBLE_MATCH", "REJECT")]
        result = summarize(rows)
        self.assertEqual(result["total"], 6)
        self.assertEqual(result["discrepancies"], 2)
        self.assertEqual({item["verdict"] for item in result["flagged"]},
                         {"STRONG_MATCH", "WEAK_MATCH"})
        self.assertAlmostEqual(result["agreement_rate"], 4 / 6)

    def test_empty_and_malformed_rows_are_ignored(self):
        self.assertEqual(summarize([]),
                         {"total": 0, "discrepancies": 0, "agreement_rate": None, "flagged": []})
        rows = [{"card": None, "decision": "APPROVE"}, {"card": "not json", "decision": "APPROVE"},
                {"card": "{}", "decision": "APPROVE"}]
        result = summarize(rows)
        self.assertEqual(result["discrepancies"], 0)
        self.assertEqual(result["agreement_rate"], 1.0)


class CalibrationOrgChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SCREENOS_DB"] = os.path.join(self.tmp.name, "test.db")
        db.run("INSERT INTO orgs (id, name, created_at) VALUES ('o1', 'Acme', 't'), ('o2', 'Globex', 't')")
        db.run("INSERT INTO users (id, email, pass_salt, pass_hash, created_at) "
               "VALUES ('u1', 'a@b.c', 's', 'h', 't')")

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("SCREENOS_DB", None)

    def _add(self, rid, org, verdict, decision):
        db.run("INSERT INTO reviews (id, org_id, created_by, candidate_hash, cleaned_text, "
               "candidate_data, card, decision, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (rid, org, "u1", "HASH-" + "a" * 64, "t", "t",
                json.dumps({"verdict": verdict}), decision, "2026-01-01"))

    def test_for_org_scopes_and_ignores_undecided(self):
        self._add("r1", "o1", "STRONG_MATCH", "REJECT")  # divergent
        self._add("r2", "o1", "WEAK_MATCH", "REJECT")    # agrees
        self._add("r3", "o1", "STRONG_MATCH", None)      # not decided yet
        self._add("r4", "o2", "WEAK_MATCH", "APPROVE")   # another organization
        result = for_org("o1")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["discrepancies"], 1)
        self.assertEqual(result["flagged"][0]["candidate_hash"], "HASH-" + "a" * 64)
