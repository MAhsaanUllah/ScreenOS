"""Organization-scoped Job Opening — minimal V1 foundation.

Fields: id, org_id, title, jd_text, status DRAFT/OPEN/CLOSED, rubric_json, rubric_approved, created_at, updated_at.
Reviews may reference job_id nullable for compat.
ponytail: file, no abstraction, DB constraint over app code.
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app import db

STATUSES = ("DRAFT", "OPEN", "CLOSED")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_status(s: str) -> str:
    s = (s or "").strip().upper()
    if s not in STATUSES:
        raise HTTPException(400, f"Status must be one of: {', '.join(STATUSES)}.")
    return s


def list_jobs(org_id: str) -> list[dict]:
    rows = db.rows("SELECT id, org_id, title, jd_text, status, rubric_json, rubric_approved, created_at, updated_at FROM jobs WHERE org_id=? ORDER BY created_at DESC", (org_id,))
    out = []
    for r in rows:
        out.append({**r, "rubric": json.loads(r["rubric_json"]) if r.get("rubric_json") else None})
    return out


def get_job(org_id: str, job_id: str) -> dict:
    row = db.row("SELECT id, org_id, title, jd_text, status, rubric_json, rubric_approved, created_at, updated_at FROM jobs WHERE id=? AND org_id=?", (job_id, org_id))
    if not row:
        raise HTTPException(404, "Job not found.")
    row["rubric"] = json.loads(row["rubric_json"]) if row.get("rubric_json") else None
    return row


def create_job(org_id: str, title: str, jd_text: str = "") -> dict:
    title = (title or "").strip()
    if not title:
        raise HTTPException(400, "Job title is required.")
    if len(title) > 120:
        raise HTTPException(400, "Title too long (max 120).")
    jd_text = (jd_text or "").strip()
    if len(jd_text) > 8000:
        raise HTTPException(400, "JD too long (max 8000).")
    jid = uuid4().hex
    now = _now()
    db.run("INSERT INTO jobs (id, org_id, title, jd_text, status, rubric_json, rubric_approved, created_at, updated_at) VALUES (?,?,?,?,?,?,?, ?,?)",
           (jid, org_id, title, jd_text, "DRAFT", None, 0, now, now))
    return get_job(org_id, jid)


def update_job(org_id: str, job_id: str, title: str | None = None, jd_text: str | None = None, status: str | None = None, rubric: list[dict] | None = None, rubric_approved: int | None = None) -> dict:
    cur = get_job(org_id, job_id)
    updates = []
    params: list = []
    if title is not None:
        title = title.strip()
        if not title:
            raise HTTPException(400, "Title is required.")
        if len(title) > 120:
            raise HTTPException(400, "Title too long.")
        updates.append("title=?"); params.append(title)
    if jd_text is not None:
        jd_text = jd_text.strip()
        if len(jd_text) > 8000:
            raise HTTPException(400, "JD too long.")
        updates.append("jd_text=?"); params.append(jd_text)
    if status is not None:
        status = _valid_status(status)
        # cannot OPEN without approved rubric
        if status == "OPEN" and not cur.get("rubric_json"):
            # allow if rubric passed in same call
            if rubric is None:
                raise HTTPException(400, "Approve rubric before opening.")
        updates.append("status=?"); params.append(status)
    if rubric is not None:
        # validate rubric rows total 100
        if not isinstance(rubric, list) or not rubric:
            raise HTTPException(400, "Rubric must be a list.")
        total = 0
        seen = set()
        for r in rubric:
            req = (r.get("requirement") or "").strip()
            pts = r.get("points")
            ev = (r.get("evidence") or "").strip()
            if not req or not ev:
                raise HTTPException(400, "Each rubric row needs requirement and evidence.")
            if req in seen:
                raise HTTPException(400, "Requirement names must be unique.")
            seen.add(req)
            try:
                pts = float(pts)
            except Exception:
                raise HTTPException(400, "Points must be numbers.") from None
            if not 0 < pts <= 100:
                raise HTTPException(400, "Points 0-100.")
            total += pts
        if total != 100:
            raise HTTPException(400, "Rubric points must total 100.")
        updates.append("rubric_json=?"); params.append(json.dumps(rubric, ensure_ascii=False))
    if rubric_approved is not None:
        rubric_approved = 1 if rubric_approved else 0
        if rubric_approved and not cur.get("rubric_json") and rubric is None:
            raise HTTPException(400, "Add rubric before approval.")
        updates.append("rubric_approved=?"); params.append(rubric_approved)
    if not updates:
        return cur
    updates.append("updated_at=?"); params.append(_now())
    params.extend([job_id, org_id])
    db.run(f"UPDATE jobs SET {', '.join(updates)} WHERE id=? AND org_id=?", tuple(params))
    return get_job(org_id, job_id)


def close_job(org_id: str, job_id: str) -> dict:
    return update_job(org_id, job_id, status="CLOSED")
