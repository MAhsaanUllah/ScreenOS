"""Day 2 scorecard contract; the scorer must use validate_scorecard."""

import re
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CriterionScore(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    criterion: str = Field(min_length=1)
    weight: float = Field(gt=0, le=100, allow_inf_nan=False)
    status: Literal["MET", "PARTIALLY_MET", "NOT_FOUND"]
    score: float = Field(ge=0, le=100, allow_inf_nan=False)
    evidence_quote: str

    @model_validator(mode="after")
    def check_award(self):
        expected = self.weight * {"MET": 1, "PARTIALLY_MET": 0.5, "NOT_FOUND": 0}[self.status]
        if self.score != expected:
            raise ValueError("Score must follow the full/half/zero points rule.")
        if not self.criterion.strip():
            raise ValueError("Criterion cannot be blank.")
        if self.status != "NOT_FOUND" and not self.evidence_quote.strip():
            raise ValueError("Positive scores require a supporting quote.")
        if self.status == "NOT_FOUND" and self.evidence_quote != "":
            raise ValueError("NOT_FOUND must use an empty evidence quote.")
        return self


class Scorecard(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_hash: str = Field(pattern=r"^HASH-[0-9a-f]{64}$")
    job_id: str = Field(min_length=1)
    overall_score: float = Field(ge=0, le=100, allow_inf_nan=False)
    verdict: Literal["STRONG_MATCH", "POSSIBLE_MATCH", "WEAK_MATCH"]
    criteria: list[CriterionScore] = Field(min_length=1)
    flagged_for_human: bool
    notes: str

    @model_validator(mode="after")
    def check_totals(self):
        if not self.job_id.strip():
            raise ValueError("Job ID cannot be blank.")
        if not self.flagged_for_human:
            raise ValueError("A human must review every scorecard.")
        names = [item.criterion for item in self.criteria]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate criteria are not allowed.")
        if sum(item.weight for item in self.criteria) != 100:
            raise ValueError("Criterion weights must total 100.")
        if sum(item.score for item in self.criteria) != self.overall_score:
            raise ValueError("Overall score must equal the criterion awards.")
        expected = ("STRONG_MATCH" if self.overall_score >= 75 else
                    "POSSIBLE_MATCH" if self.overall_score >= 50 else "WEAK_MATCH")
        if self.verdict != expected:
            raise ValueError("Verdict does not match the overall score.")
        return self


class EvidenceError(ValueError):
    """Quotes missing from the CV. `criteria` holds rubric-matched names only, never model text."""

    def __init__(self, criteria: list[str]):
        super().__init__("Evidence must be an exact quote from the cleaned CV.")
        self.criteria = criteria


class SkillsListEvidence(ValueError):
    """Quotes that are a skills list, not work. `criteria` holds rubric-matched names only."""

    def __init__(self, criteria: list[str]):
        super().__init__("Evidence must be work, not a skills list.")
        self.criteria = criteria


def _squash(text: str) -> str:
    return " ".join(text.split())


# Past-tense work verbs only. Adjectives that look like verbs ("Distributed Systems",
# "Containerized Apps") must not count, so there is no "-ed" rule.
_WORK_VERBS = frozenset("""
built led wrote developed deployed designed implemented created maintained migrated reduced improved
automated tested shipped launched integrated optimized optimised managed mentored architected delivered
analyzed analysed configured engineered refactored scaled increased introduced established owned trained
processed handled coordinated researched authored published orchestrated monitored secured resolved
streamlined accelerated cut saved grew drove supervised hired onboarded modernized rewrote replaced
""".split())
_SKILLS_HEADING_RE = re.compile(
    r"(?i)^\s*(?:technical\s+skills|skills|technologies|tools|tech\s+stack|core\s+competencies|keywords)"
    r"\s*(?::.*)?$")


def _has_work_verb(text: str) -> bool:
    return any(w in _WORK_VERBS for w in re.findall(r"[a-z]+", text.lower()))


def _is_keyword_list(quote: str) -> bool:
    """3+ comma separated short items and no work verb: "FastAPI, PostgreSQL, Docker"."""
    items = [i.strip() for i in quote.split(",") if i.strip()]
    return len(items) >= 3 and all(len(i.split()) <= 3 for i in items) and not _has_work_verb(quote)


_SECTION_NAME_RE = re.compile(
    r"(?i)(?:work\s+|professional\s+)?experience|employment(?:\s+history)?|education|projects?|summary|profile|"
    r"objective|certifications?|awards?|publications?|interests|references|achievements|training|courses|"
    r"volunteer(?:ing)?|languages|background|about(?:\s+me)?|contact|personal\s+(?:details|information)|links")


def _looks_like_heading(line: str) -> bool:
    """A known CV section name, an ALL CAPS line, or a short line ending with a colon.

    A plain title-case line is NOT a heading: "Kubernetes" alone is a skill, not a new section.
    """
    text = line.strip()
    if not text or len(text.split()) > 4 or text[0] in "-\u2022*\u2013\u2014\u00b7" or re.search(r"[\d,;.]", text):
        return False
    return text.endswith(":") or text.isupper() or bool(_SECTION_NAME_RE.fullmatch(text))


def _skills_section_lines(lines: list[str]) -> list[bool]:
    """True for every line under a Skills-type heading, up to the next heading-like line.

    shortcut: only known section names, ALL CAPS lines and "Word:" lines end the section, so an
    unusual heading ("Volunteer Work") does not; a verb-less line under it is then read as a skill.
    """
    flags, inside = [], False
    for line in lines:
        if _SKILLS_HEADING_RE.match(line):
            inside = True
            flags.append(True)
        elif inside and _looks_like_heading(line):
            inside = False
            flags.append(False)
        else:
            flags.append(inside)
    return flags


def _is_skills_list(quote: str, cleaned_text: str) -> bool:
    """A listed skill proves the word is written, not that the work was done.

    Rejected: a comma list of short items with no work verb, or a quote that only appears under a
    Skills-type heading and has no work verb. "Core Competencies: Built RAG systems" is work, so it passes.
    """
    if _is_keyword_list(quote):
        return True
    if _has_work_verb(quote):
        return False
    pattern = r"\s+".join(re.escape(t) for t in quote.split())
    flags = _skills_section_lines(cleaned_text.split("\n"))
    spans = [(cleaned_text.count("\n", 0, m.start()), cleaned_text.count("\n", 0, m.end()))
             for m in re.finditer(pattern, cleaned_text)]
    return bool(spans) and all(all(flags[a:b + 1]) for a, b in spans)


def validate_scorecard(data: dict, *, cleaned_text: str, candidate_hash: str,
                       job_id: str, rubric: Mapping[str, float]) -> Scorecard:
    """Validate model output against trusted caller inputs, including exact quotes.

    A verbatim quote can still be irrelevant or dishonest; human review remains required.
    """
    card = Scorecard.model_validate(data)
    if card.candidate_hash != candidate_hash or card.job_id != job_id:
        raise ValueError("Scorecard candidate or job does not match the request.")
    if {item.criterion: item.weight for item in card.criteria} != dict(rubric):
        raise ValueError("Criteria and weights must match the trusted job rubric.")
    # Exact words are required; only runs of whitespace (spaces, newlines) are treated as equal.
    haystack = _squash(cleaned_text)
    bad = [i.criterion for i in card.criteria
           if i.evidence_quote and _squash(i.evidence_quote) not in haystack]
    if bad:
        raise EvidenceError(bad)
    listy = [i.criterion for i in card.criteria if i.evidence_quote and _is_skills_list(i.evidence_quote, cleaned_text)]
    if listy:
        raise SkillsListEvidence(listy)
    return card
