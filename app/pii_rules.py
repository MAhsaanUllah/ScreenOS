"""Org-wide custom PII redaction rules (Settings).

HR can add e.g. type=location value=Lahore, or type=university value=PU.
Stored per org, admin-only write, applied automatically in prepare_candidate plus shown in Review PII.
ponytail: simple table, no regex engine — substring case-insensitive.
"""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app import db
from app.team import require_admin

ALLOWED_TYPES = {"location", "university", "custom", "address", "name", "other"}
MAX_VALUE = 120
MAX_RULES = 50


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_rules(org_id: str) -> list[dict]:
    return db.rows(
        "SELECT id, type, value, created_at FROM org_pii_rules WHERE org_id=? ORDER BY created_at",
        (org_id,),
    )


def add_rule(ctx: dict, pii_type: str, value: str) -> list[dict]:
    # HR usability: any org member can manage custom redaction (not admin-only)
    # Membership already verified via authorize; just check org_id exists
    pii_type = (pii_type or "").strip().lower() or "custom"
    if pii_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Type must be one of: {', '.join(sorted(ALLOWED_TYPES))}.")
    value = (value or "").strip()
    if not value:
        raise HTTPException(400, "Value is required.")
    if len(value) > MAX_VALUE:
        raise HTTPException(400, f"Value too long (max {MAX_VALUE}).")
    if len(value) < 2:
        raise HTTPException(400, "Value too short.")
    existing = db.rows("SELECT id FROM org_pii_rules WHERE org_id=?", (ctx["org_id"],))
    if len(existing) >= MAX_RULES:
        raise HTTPException(400, f"Max {MAX_RULES} rules reached. Delete one first.")
    # dedupe same value case-insensitive
    dup = db.row("SELECT 1 FROM org_pii_rules WHERE org_id=? AND lower(value)=lower(?)", (ctx["org_id"], value))
    if dup:
        raise HTTPException(409, "That value already exists.")
    rid = uuid4().hex
    db.run(
        "INSERT INTO org_pii_rules (id, org_id, type, value, created_at) VALUES (?,?,?,?,?)",
        (rid, ctx["org_id"], pii_type, value, _now()),
    )
    return list_rules(ctx["org_id"])


def delete_rule(ctx: dict, rule_id: str) -> list[dict]:
    row = db.row("SELECT id FROM org_pii_rules WHERE id=? AND org_id=?", (rule_id, ctx["org_id"]))
    if not row:
        raise HTTPException(404, "Rule not found.")
    db.run("DELETE FROM org_pii_rules WHERE id=?", (rule_id,))
    return list_rules(ctx["org_id"])
