"""Calibration view: flag reviewed decisions where the human diverged from the AI verdict.

Roadmap item (Day 9-10). Only STRONG/WEAK verdicts carry an expectation, so
borderline (POSSIBLE_MATCH) decisions never count as divergence.
"""

import json

from app import db

EXPECTED = {"STRONG_MATCH": "APPROVE", "WEAK_MATCH": "REJECT"}


def summarize(records: list[dict]) -> dict:
    """`records` are review rows carrying `card` (scorecard JSON text), `decision` and `candidate_hash`."""
    flagged = []
    for row in records:
        try:
            verdict = json.loads(row["card"])["verdict"]
        except (KeyError, TypeError, ValueError):
            continue  # unscored or malformed row
        expected = EXPECTED.get(verdict)
        if expected and row.get("decision") != expected:
            flagged.append({"candidate_hash": row.get("candidate_hash"), "verdict": verdict,
                            "decision": row.get("decision")})
    total = len(records)
    return {"total": total, "discrepancies": len(flagged),
            "agreement_rate": (total - len(flagged)) / total if total else None,
            "flagged": flagged}


def for_org(org_id: str, job_id: str | None = None) -> dict:
    """Calibration summary across one organization's decided reviews."""
    q = "SELECT card, decision, candidate_hash FROM reviews WHERE org_id = ? AND card IS NOT NULL AND decision IS NOT NULL"
    params = [org_id]
    if job_id:
        q += " AND job_id = ?"
        params.append(job_id)
    return summarize(db.rows(q, tuple(params)))
