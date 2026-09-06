import json
from pathlib import Path
import tempfile
import unittest

from app.scorer import read_rubric, score_candidate

ROOT = Path(__file__).resolve().parents[1]


class ScoringFlowChecks(unittest.TestCase):
    def test_offline_pipeline_and_rejected_evidence(self):
        # Stub proves plumbing only, not actual AI scoring quality or API connectivity.
        def response(messages):
            self.assertEqual(messages[0]["role"], "system")
            payload = json.loads(messages[1]["content"])
            self.assertNotIn("Amina Example", payload["candidate_data"])
            self.assertEqual(len(payload["rubric"]), 5)
            return json.dumps(dict(candidate_hash=payload["candidate_hash"],
                job_id=payload["job_id"], overall_score=0, verdict="WEAK_MATCH",
                flagged_for_human=True, notes="Offline transport stub; not a real evaluation.",
                criteria=[dict(criterion=k, weight=v, status="NOT_FOUND", score=0,
                               evidence_quote="") for k, v in payload["rubric"].items()]))
        kwargs = dict(name="Amina Example", rubric_path=ROOT / "rubrics/rubric.md")
        sample = ROOT / "samples/cvs/01_strong.txt"
        self.assertEqual(score_candidate(sample, complete=response, **kwargs).overall_score, 0)
        def fabricated(messages):
            card = json.loads(response(messages))
            card["criteria"][0].update(status="MET", score=30, evidence_quote="Invented achievement")
            card["overall_score"] = 30
            return json.dumps(card)
        with self.assertRaisesRegex(ValueError, "not copied exactly"):
            score_candidate(sample, complete=fabricated, **kwargs)
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            score_candidate(sample, complete=lambda _: "not JSON", **kwargs)

    def test_invalid_rubric(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rubric.md"
            for text in ("", "| Python | nan | Work |", "| Python | 50 | Work |",
                         "| Python | 50 | Work |\n| Python | 50 | Work |"):
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(ValueError):
                    read_rubric(path)
