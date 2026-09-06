from copy import deepcopy
import unittest

from app.schemas import Scorecard, validate_scorecard


class ScorecardChecks(unittest.TestCase):
    def test_valid_card_and_invalid_model_outputs(self):
        rubric = {"Agents": 30, "Python": 20, "Documents": 20, "Database": 15, "Tests": 15}
        statuses = ["MET", "MET", "NOT_FOUND", "PARTIALLY_MET", "NOT_FOUND"]
        card = dict(candidate_hash="HASH-" + "a" * 64, job_id="ai-engineer",
                    overall_score=57.5, verdict="POSSIBLE_MATCH", flagged_for_human=True,
                    notes="Database evidence is partial; reviewer must check it.", criteria=[])
        for (name, weight), status in zip(rubric.items(), statuses):
            card["criteria"].append(dict(criterion=name, weight=weight, status=status,
                score=weight * {"MET": 1, "PARTIALLY_MET": .5, "NOT_FOUND": 0}[status],
                evidence_quote="Built a service." if status != "NOT_FOUND" else ""))
        def validate(data):
            return validate_scorecard(data, cleaned_text="Built a service.",
                candidate_hash=card["candidate_hash"], job_id="ai-engineer", rubric=rubric)
        self.assertEqual(validate(card).overall_score, 57.5)
        self.assertEqual(Scorecard.model_validate_json(validate(card).model_dump_json()).overall_score, 57.5)
        for field, value in (("overall_score", 60), ("overall_score", float("nan")),
                             ("verdict", "STRONG_MATCH"), ("flagged_for_human", False),
                             ("flagged_for_human", 1), ("job_id", "other"),
                             ("candidate_hash", "HASH-" + "b" * 64), ("extra", "bad")):
            bad = deepcopy(card)
            bad[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate(bad)
        for field, value in (("evidence_quote", "invented quote"), ("evidence_quote", ""),
                             ("status", "UNKNOWN"), ("score", 15),
                             ("criterion", "Python"), ("criterion", "Other"), ("weight", 10)):
            bad = deepcopy(card)
            bad["criteria"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate(bad)
