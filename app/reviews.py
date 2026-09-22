"""Persist a prepared candidate as an organization-scoped review row."""

from datetime import datetime, timezone
from uuid import uuid4

from app import db


def store_review(ctx: dict, candidate: dict, job_id: str | None = None) -> str:
    review_id = uuid4().hex
    # job_id nullable for legacy compat — validated by caller if present
    db.run(
        "INSERT INTO reviews (id, org_id, created_by, candidate_hash, cleaned_text, "
        "candidate_data, job_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (review_id, ctx["org_id"], ctx["user_id"], candidate["candidate_hash"],
         candidate["cleaned_text"], candidate["candidate_data"], job_id,
         datetime.now(timezone.utc).isoformat()),
    )
    return review_id
