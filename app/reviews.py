"""Persist a prepared candidate as an organization-scoped review row."""

from datetime import datetime, timezone
from uuid import uuid4

from app import db


def store_review(ctx: dict, candidate: dict) -> str:
    review_id = uuid4().hex
    db.run(
        "INSERT INTO reviews (id, org_id, created_by, candidate_hash, cleaned_text, "
        "candidate_data, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (review_id, ctx["org_id"], ctx["user_id"], candidate["candidate_hash"],
         candidate["cleaned_text"], candidate["candidate_data"],
         datetime.now(timezone.utc).isoformat()),
    )
    return review_id
