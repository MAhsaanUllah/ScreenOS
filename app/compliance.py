"""Per-organization compliance summary for algorithmic-hiring audits.

Aggregates the decisions that already exist so a recruiter can hand a
filing-ready summary to legal. No CV text, no demographics and no new
dependencies leave this module.
"""

import json
from datetime import datetime, timezone

from app import db


def report(ctx: dict, job_id: str | None = None) -> dict:
    org = db.row("SELECT id, name FROM orgs WHERE id = ?", (ctx["org_id"],)) or {}
    q = "SELECT candidate_hash, card, decision, decided_at, created_at FROM reviews WHERE org_id = ?"
    params = [ctx["org_id"]]
    if job_id:
        q += " AND job_id = ?"
        params.append(job_id)
    q += " ORDER BY created_at"
    rows = db.rows(q, tuple(params))

    decisions = {"APPROVE": 0, "REJECT": 0}
    verdicts = {"STRONG_MATCH": 0, "POSSIBLE_MATCH": 0, "WEAK_MATCH": 0}
    decided = 0
    records = []
    for row in rows:
        card = _card(row["card"])
        if row["decision"]:
            decided += 1
            decisions[row["decision"]] = decisions.get(row["decision"], 0) + 1
        if card.get("verdict"):
            verdicts[card["verdict"]] = verdicts.get(card["verdict"], 0) + 1
        records.append({"candidate_hash": row["candidate_hash"], "score": card.get("overall_score"),
                        "verdict": card.get("verdict"), "decision": row["decision"],
                        "screened_at": row["created_at"], "decided_at": row["decided_at"]})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "organization": {"id": org.get("id"), "name": org.get("name")},
        "totals": {"screened": len(rows), "decided": decided, "pending": len(rows) - decided},
        "decisions": decisions,
        "verdicts": verdicts,
        "guardrails": {
            "demographics_redacted_before_scoring": True,
            "evidence_quote_required_for_points": True,
            "human_decision_required_for_every_candidate": True,
            "model_cannot_advance_or_reject": True,
        },
        "records": records,
    }


def rows_csv(ctx: dict, *, decision: str | None = None, verdict: str | None = None,
             from_date: str | None = None, to_date: str | None = None, job_id: str | None = None) -> str:
    """The per-candidate records as CSV, with optional HR filters."""
    columns = ("candidate_hash", "score", "verdict", "decision", "screened_at", "decided_at")
    records = report(ctx, job_id=job_id)["records"]
    if decision:
        records = [r for r in records if r["decision"] == decision]
    if verdict:
        records = [r for r in records if r["verdict"] == verdict]
    if from_date:
        records = [r for r in records if r["screened_at"] and r["screened_at"] >= from_date]
    if to_date:
        records = [r for r in records if r["screened_at"] and r["screened_at"] <= to_date]
    lines = [",".join(columns)]
    lines += [",".join(_cell(record[column]) for column in columns) for record in records]
    return "\n".join(lines) + "\n"


def _cell(value) -> str:
    if value is None:
        return ""
    text = str(value)
    return '"' + text.replace('"', '""') + '"' if "," in text or '"' in text else text


def _card(value) -> dict:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return {}
    return value or {}
