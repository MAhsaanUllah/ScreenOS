import json
import unittest
from pathlib import Path

from app.extractor import extract_text
from app.guardrails import prepare_candidate
from app.schemas import _has_work_verb, _is_keyword_list
from app.scorer import read_rubric, score_with_rubric

ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = ROOT / "rubrics/ai-engineer.md"
DB = "Design databases with separate customer access"
TEST_RELEASE = "Test and release working software"
SERVICES = "Build Python services with FastAPI"
FEEDBACK = ("Criterion '{}': a skills list is not evidence of work. "
            "Quote a project, job duty or result, or mark NOT_FOUND.")

EXPERIENCE_CV = """Jo Example
Experience
Backend Engineer, Acme (2021 - present)
- Built a FastAPI service for ticket triage with validated requests and clear errors.
  Tech: FastAPI, Postgres
- Wrote 40 pytest tests and deployed the service with automatic rollback.
Skills
FastAPI, Postgres, Docker, pytest
"""


class Script:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, messages):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def card(candidate, awards):
    """awards: {criterion: (status, quote)}; everything else NOT_FOUND."""
    rubric = read_rubric(RUBRIC_PATH)
    items, total = [], 0.0
    for name, weight in rubric.items():
        status, quote = awards.get(name, ("NOT_FOUND", ""))
        score = weight * {"MET": 1, "PARTIALLY_MET": 0.5, "NOT_FOUND": 0}[status]
        total += score
        items.append(dict(criterion=name, weight=weight, status=status, score=score, evidence_quote=quote))
    verdict = "STRONG_MATCH" if total >= 75 else "POSSIBLE_MATCH" if total >= 50 else "WEAK_MATCH"
    return json.dumps(dict(candidate_hash=candidate["candidate_hash"], job_id="ai-engineer", overall_score=total,
                           verdict=verdict, flagged_for_human=True, notes="n", criteria=items))


def run(text, replies, name="Jo Example"):
    candidate = prepare_candidate(text, name=name)
    script = Script(*[card(candidate, r) if isinstance(r, dict) else r for r in replies])
    result = score_with_rubric(candidate, complete=script, rubric=read_rubric(RUBRIC_PATH),
                               guidance=RUBRIC_PATH.read_text(encoding="utf-8"), job_id="ai-engineer")
    return result, script


class SkillsListIsNotEvidence(unittest.TestCase):
    SAMPLE = extract_text(ROOT / "samples/cvs/11_skills_only_stuffing.txt")
    DB_LINE = "PostgreSQL, MySQL, Redis, Multi-tenant, Row Level Security, SQLAlchemy"
    CI_LINE = "Docker, Kubernetes, Terraform, AWS, CI/CD, GitHub Actions, pytest, TDD"
    LAZY = {DB: ("MET", DB_LINE), TEST_RELEASE: ("MET", CI_LINE)}

    def test_a_lazy_model_awarding_met_from_skills_lines_is_rejected_after_one_retry(self):
        with self.assertRaisesRegex(ValueError, "only a skills list") as caught:
            run(self.SAMPLE, [self.LAZY, self.LAZY], name="Mehreen Example")
        self.assertNotIn("Row Level Security", str(caught.exception))

    def test_retry_gets_the_fixed_message_per_criterion_and_nothing_else(self):
        honest = {}  # on the retry the model marks everything NOT_FOUND
        (result, attempts), script = run(self.SAMPLE, [self.LAZY, honest], name="Mehreen Example")
        self.assertEqual((result.overall_score, attempts, len(script.calls)), (0.0, 2, 2))
        feedback = script.calls[1][3]["content"]
        self.assertIn(FEEDBACK.format(DB), feedback)
        self.assertIn(FEEDBACK.format(TEST_RELEASE), feedback)
        for leak in ("Row Level Security", "Kubernetes", "Mehreen"):
            self.assertNotIn(leak, feedback)

    def test_exactly_one_retry_even_when_the_model_keeps_doing_it(self):
        script = Script(*[card(prepare_candidate(self.SAMPLE, name="Mehreen Example"), self.LAZY)] * 3)
        candidate = prepare_candidate(self.SAMPLE, name="Mehreen Example")
        with self.assertRaises(ValueError):
            score_with_rubric(candidate, complete=script, rubric=read_rubric(RUBRIC_PATH), guidance="g", job_id="ai-engineer")
        self.assertEqual(len(script.calls), 2)

    def test_partially_met_from_a_skills_line_is_rejected_too(self):
        partial = {SERVICES: ("PARTIALLY_MET", "FastAPI, Flask, LangChain, LlamaIndex, RAG")}
        with self.assertRaisesRegex(ValueError, "only a skills list"):
            run(self.SAMPLE, [partial, partial], name="Mehreen Example")

    def test_a_single_tool_under_a_skills_heading_is_rejected(self):
        text = "Jo Example\nTechnical Skills\nKubernetes\nExperience\n- Built a FastAPI service for tickets.\n"
        with self.assertRaisesRegex(ValueError, "only a skills list"):
            run(text, [{SERVICES: ("MET", "Kubernetes")}] * 2)


class WorkIsStillEvidence(unittest.TestCase):
    def test_experience_bullet_is_accepted(self):
        quote = "Built a FastAPI service for ticket triage with validated requests and clear errors."
        (result, attempts), script = run(EXPERIENCE_CV, [{SERVICES: ("MET", quote)}])
        self.assertEqual((result.overall_score, attempts, len(script.calls)), (20.0, 1, 1))

    def test_tech_line_inside_an_experience_bullet_is_fine(self):
        for quote in ("Built a FastAPI service for ticket triage with validated requests and clear errors.",
                      "Tech: FastAPI, Postgres"):
            with self.subTest(quote=quote):
                self.assertEqual(run(EXPERIENCE_CV, [{SERVICES: ("MET", quote)}])[0][1], 1)

    def test_a_verb_under_a_skills_heading_is_work_not_a_list(self):
        for text, quote in (
                ("Jo Example\nCore Competencies: Built RAG systems with LangChain\nEducation\nBS\n",
                 "Core Competencies: Built RAG systems with LangChain"),
                ("Jo Example\nCore Competencies: Built RAG systems with LangChain\nEducation\nBS\n",
                 "Built RAG systems with LangChain"),
                ("Jo Example\nSkills\nBuilt RAG systems with LangChain\nDeployed them on AWS\nExperience\nx\n",
                 "Built RAG systems with LangChain\nDeployed them on AWS")):
            with self.subTest(text=text[:40], quote=quote[:30]):
                (result, attempts), script = run(text, [{"Build AI tools or automated workflows": ("MET", quote)}])
                self.assertEqual((attempts, len(script.calls)), (1, 1))

    def test_quote_in_the_experience_section_is_not_affected_by_a_skills_section_elsewhere(self):
        quote = "Wrote 40 pytest tests and deployed the service with automatic rollback."
        self.assertEqual(run(EXPERIENCE_CV, [{TEST_RELEASE: ("MET", quote)}])[0][1], 1)


class KeywordListRule(unittest.TestCase):
    def test_lists_without_a_work_verb_are_keyword_lists(self):
        for quote in ("FastAPI, PostgreSQL, Docker", "Distributed Systems, Advanced SQL, Containerized Apps",
                      "Python, Django, FastAPI, PostgreSQL, Docker, pytest, Git"):
            with self.subTest(quote=quote):
                self.assertTrue(_is_keyword_list(quote))

    def test_participle_adjectives_are_not_verbs(self):
        for word in ("Distributed", "Advanced", "Containerized", "Embedded", "Experienced", "Skilled"):
            self.assertFalse(_has_work_verb(word + " Systems"))

    def test_work_verbs_and_short_lists_are_not_keyword_lists(self):
        for quote in ("Built APIs, Docker, Redis", "Tech: FastAPI, Postgres", "Built a service, tested it, shipped it",
                      "Built a FastAPI service for ticket triage with validated requests and clear errors."):
            with self.subTest(quote=quote):
                self.assertFalse(_is_keyword_list(quote))

    def test_the_verb_list_has_the_common_cv_verbs(self):
        for verb in ("built led wrote developed deployed designed implemented created maintained migrated "
                     "reduced improved automated tested shipped launched integrated optimized managed mentored").split():
            self.assertTrue(_has_work_verb(f"{verb} things"), verb)


class TwoColumnCv(unittest.TestCase):
    """two_column.pdf has a Skills heading in the sidebar and its evidence in the experience column."""
    TEXT = extract_text(ROOT / "tests/fixtures/two_column.pdf")
    WORKFLOWS = "Build AI tools or automated workflows"

    def test_sidebar_skills_heading_is_read_before_the_experience(self):
        self.assertLess(self.TEXT.index("Skills"), self.TEXT.index("Experience"))

    def test_evidence_from_the_experience_column_is_accepted(self):
        quote = "Built a claims triage workflow that reads insurance emails in four steps:"
        (result, attempts), script = run(self.TEXT, [{self.WORKFLOWS: ("MET", quote)}], name="Sana Iqbal Malik")
        self.assertEqual((result.overall_score, attempts, len(script.calls)), (30.0, 1, 1))

    def test_the_sidebar_skills_list_is_still_not_evidence(self):
        skills = {SERVICES: ("MET", "Python, FastAPI, Pydantic")}
        with self.assertRaisesRegex(ValueError, "only a skills list"):
            run(self.TEXT, [skills, skills], name="Sana Iqbal Malik")


if __name__ == "__main__":
    unittest.main()
