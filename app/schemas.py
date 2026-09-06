"""Day 2 scorecard contract; the scorer must use validate_scorecard."""

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
    for item in card.criteria:
        if item.evidence_quote and item.evidence_quote not in cleaned_text:
            raise ValueError("Evidence must be an exact quote from the cleaned CV.")
    return card
