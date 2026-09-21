"""Per-organization compliance summary for algorithmic-hiring audits.

Aggregates the decisions that already exist so a recruiter can hand a
filing-ready summary to legal. No CV text, no demographics and no new
dependencies leave this module.
"""

import json
from datetime import datetime, timezone

from app import db


def report(ctx: dict) -> dict:
    org = db.row("SELECT id, name FROM orgs WHERE id = ?", (ctx["org_id"],)) or {}
    rows = db.rows(
        "SELECT candidate_hash, card, decision, decided_at, created_at FROM reviews "
        "WHERE org_id = ? ORDER BY created_at", (ctx["org_id"],))

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


def _card(value) -> dict:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return {}
    return value or {}
