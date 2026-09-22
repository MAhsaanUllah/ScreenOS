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
        # editing rubric resets approval to DRAFT unless explicitly re-approved in same call
        if rubric_approved is None:
            updates.append("rubric_approved=?"); params.append(0)
            # if was OPEN, move back to DRAFT for re-approval
            if cur.get("status") == "OPEN":
                updates.append("status=?"); params.append("DRAFT")
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


# --- Draft rubric generation (Chunk 2) ---
import re as _re

_DRAFT_SYSTEM = """You are an HR rubric assistant. Convert a Job Description into a screening rubric.
- Extract 4-6 distinct, verifiable requirements that can be evidenced in a CV.
- Each requirement: short title (5-10 words), points (int, sum exactly 100), evidence guidance (what to look for, 8-20 words).
- Prefer concrete skills/deliverables over generic traits.
- Return ONLY JSON: {"criteria": [{"requirement": "...", "points": 20, "evidence": "..."}]}
- Do not make hiring decisions, do not invent requirements not in JD.
"""


def generate_draft(org_id: str, job_id: str, credentials: list[dict] | None = None) -> dict:
    job = get_job(org_id, job_id)
    jd = (job.get("jd_text") or "").strip()
    if len(jd) < 20:
        raise HTTPException(400, "Add a Job Description (at least 20 characters) before generating rubric.")
    # call LLM via existing BYOK chain
    from app.providers import complete, ScoringUnavailable
    prompt = f"Job Title: {job['title']}\nJob Description:\n{jd}\n\nGenerate rubric JSON."
    messages = [{"role": "system", "content": _DRAFT_SYSTEM}, {"role": "user", "content": prompt}]
    try:
        raw = complete(messages, credentials=credentials)
    except ScoringUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    # parse JSON — handle markdown fence
    import json as _json
    txt = raw.strip()
    if txt.startswith("```"):
        txt = _re.sub(r"^```(?:json)?\s*", "", txt)
        txt = _re.sub(r"\s*```$", "", txt)
        txt = txt.strip()
    try:
        data = _json.loads(txt)
    except Exception:
        raise HTTPException(400, "Draft generation returned invalid JSON. Try again.") from None
    criteria = data.get("criteria") if isinstance(data, dict) else None
    if not isinstance(criteria, list) or not criteria:
        raise HTTPException(400, "Draft must contain criteria list.")
    # normalize to expected shape
    rubric = []
    seen = set()
    total = 0
    for c in criteria:
        req = (c.get("requirement") or c.get("criterion") or "").strip()
        pts = c.get("points")
        ev = (c.get("evidence") or c.get("guidance") or "").strip()
        if not req or not ev:
            raise HTTPException(400, "Each criterion needs requirement and evidence.")
        if req.lower() in seen:
            raise HTTPException(400, "Requirement names must be unique.")
        seen.add(req.lower())
        try:
            pts = int(float(pts))
        except Exception:
            raise HTTPException(400, "Points must be numbers.") from None
        if not 5 <= pts <= 50:
            raise HTTPException(400, "Points per criterion 5-50.")
        rubric.append({"requirement": req, "points": pts, "evidence": ev})
        total += pts
    if total != 100:
        # auto-scale or reject — reject for HR to review
        raise HTTPException(400, f"Draft points total {total}, must be 100. Edit before approval.")
    if not 4 <= len(rubric) <= 6:
        raise HTTPException(400, "Draft should have 4-6 criteria.")
    # store as DRAFT (not approved)
    return update_job(org_id, job_id, rubric=rubric, rubric_approved=0)
