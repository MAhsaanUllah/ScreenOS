import json
from pathlib import Path
import tempfile
import unittest

from app.extractor import extract_text
from app.scorer import score_candidate
from scripts.evaluate_samples import ROOT, evaluate_sample, offline_complete


class EvaluationChecks(unittest.TestCase):
    def test_prompt_injection_stays_data_and_scores_weak(self):
        sample = ROOT / "samples/cvs/06_instructions.pdf"
        self.assertIn("ignore all previous instructions", extract_text(sample).lower())
        row = evaluate_sample(sample)
        self.assertEqual((row[3], row[5]), ("WEAK_MATCH", "Yes"))

    def test_empty_cv_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.txt"
            path.write_text(" \n\t", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "No readable text"):
                extract_text(path)

    def test_fabricated_evidence_is_rejected(self):
        sample = ROOT / "samples/cvs/04_career_change.txt"
        def fabricated(messages):
            card = json.loads(offline_complete(sample.name)(messages))
            card["criteria"][0].update(status="MET", score=30,
                                       evidence_quote="Built an imaginary production AI service.")
            card["overall_score"] = 30
            return json.dumps(card)
        with self.assertRaisesRegex(ValueError, "not copied exactly"):
            score_candidate(sample, name="Zoë Example", complete=fabricated,
                            rubric_path=ROOT / "rubrics/rubric.md")

    def test_career_change_gets_fair_low_baseline(self):
        row = evaluate_sample(ROOT / "samples/cvs/04_career_change.txt")
        self.assertEqual(row[3], "WEAK_MATCH")
        self.assertEqual(row[4], 15)
