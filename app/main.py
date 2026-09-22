"""Multi-tenant recruiter workspace API.

All /api routes (except auth) require a bearer session token and are scoped
to the organization bound to that session.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import auth, batch, compliance, credentials, db, jobs, orgs, pii_rules, reviews, rubrics, team
from app.calibration import for_org
from app.extractor import extract_text
from app.guardrails import detect_pii, prepare_candidate, wrap_candidate_data
from app.providers import CATALOG, ScoringUnavailable, complete
from app.scorer import rubric_info, score_prepared, score_prepared_with_rubric

ROOT = Path(__file__).resolve().parents[1]
import os as _os
# Cloud: set SCREENOS_ALLOWED_HOSTS=example.com,api.example.com
_allowed = [h.strip() for h in _os.environ.get("SCREENOS_ALLOWED_HOSTS", "").split(",") if h.strip()]
if not _allowed:
    _allowed = ["127.0.0.1", "localhost", "testserver"]
# Always allow testserver for tests
if "testserver" not in _allowed:
    _allowed.append("testserver")
app = FastAPI(title="SCREENOS", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed)
app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")
build_assets = ROOT / "app/static/build/assets"
if build_assets.is_dir():
    app.mount("/assets", StaticFiles(directory=build_assets), name="assets")


def _loopback(origin: str) -> bool:
    """The Vite dev server serves the workspace from a loopback port while the API stays on 8000."""
    return urlparse(origin).hostname in {"localhost", "127.0.0.1", "::1"}


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    if request.method != "GET" and request.headers.get("x-screenos") != "1":
        return JSONResponse({"detail": "Use the SCREENOS page to make this request."}, status_code=403)
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/") and not _loopback(origin):
        return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # HSTS only when behind TLS; harmless locally, enforced when https forwarded
    if request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


@app.get("/")
def index():
    build = ROOT / "app/static/build/index.html"
    return FileResponse(build if build.is_file() else ROOT / "app/static/index.html")


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    org_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    password: str


class SwitchOrgRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    org_id: str = Field(min_length=1)


def _cookie_opts(request: Request) -> dict:
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    return {"httponly": True, "secure": secure, "samesite": "lax", "max_age": 30 * 24 * 3600, "path": "/"}


@app.post("/api/auth/register")
def register(request: Request, body: RegisterRequest):
    data = auth.register(body.org_name, body.email, body.password)
    resp = JSONResponse(data)
    resp.set_cookie("screenos_session", data["token"], **_cookie_opts(request))
    return resp


@app.post("/api/auth/login")
def login(request: Request, body: LoginRequest):
    data = auth.login(body.email, body.password, request.client.host if request.client else "")
    resp = JSONResponse(data)
    resp.set_cookie("screenos_session", data["token"], **_cookie_opts(request))
    return resp


@app.post("/api/auth/logout")
def logout(request: Request):
    ctx = None
    token = request.cookies.get("screenos_session") or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    try:
        ctx = auth.authorize(request)
        token = ctx["token"]
    except HTTPException:
        pass
    if token:
        auth.logout(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("screenos_session", path="/")
    return resp


@app.post("/api/auth/switch-org")
def switch_org(request: Request, body: SwitchOrgRequest):
    token = request.cookies.get("screenos_session") or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    data = auth.switch_org(token, body.org_id)
    resp = JSONResponse(data)
    resp.set_cookie("screenos_session", data["token"], **_cookie_opts(request))
    return resp


def _review(token: str, ctx: dict) -> dict:
    review = db.row("SELECT * FROM reviews WHERE id = ? AND org_id = ?", (token, ctx["org_id"]))
    if not review:
        raise HTTPException(404, "Review expired. Upload the CV again.")
    return review


def _summary(review: dict) -> dict:
    card = json.loads(review["card"]) if review["card"] else None
    # job_id from review row (job-aware) else card's job_id (legacy) — preserves snapshot
    jid = review.get("job_id") or (card["job_id"] if card else None)
    return {
        "id": review["id"],
        "short": review["id"][:8],
        "created_at": review["created_at"],
        "decision": review["decision"],
        "status": review["decision"] or ("SCORED" if card else "PENDING"),
        "score": card["overall_score"] if card else None,
        "verdict": card["verdict"] if card else None,
        "job_id": jid,
        "job_label": jid or "Legacy",
    }


@app.get("/api/reviews")
def list_reviews(request: Request, job_id: str | None = None):
    ctx = auth.authorize(request)
    q = "SELECT id, card, decision, created_at, job_id FROM reviews WHERE org_id = ?"
    params = [ctx["org_id"]]
    if job_id:
        q += " AND job_id = ?"
        params.append(job_id)
    q += " ORDER BY created_at DESC"
    return [_summary(r) for r in db.rows(q, tuple(params))]


@app.get("/api/reviews/{token}")
def review_detail(token: str, request: Request):
    ctx = auth.authorize(request)
    review = _review(token, ctx)
    return {"cleaned_text": review["cleaned_text"],
            "card": json.loads(review["card"]) if review["card"] else None,
            "decision": review["decision"],
            "reviewer_notes": review["reviewer_notes"],
            "decided_at": review["decided_at"]}


@app.get("/api/rubric")
def rubric():
    return rubric_info(rubrics.path_for(rubrics.DEFAULT))


@app.put("/api/rubric")
def rubric_update(request: Request, body: dict):
    ctx = auth.authorize(request)
    # HR Controls: only ADMIN can change rubric (keeps Settings clean)
    from app.team import require_admin
    require_admin(ctx)
    rows = body.get("rows") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise HTTPException(400, "Send rows: [{requirement, points, evidence}].")
    try:
        return rubrics.update_rubric(rubrics.DEFAULT, rows)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from None


@app.get("/api/rubrics")
def rubric_list():
    return rubrics.list_rubrics()


@app.get("/api/rubrics/archive")
def rubric_archive(request: Request):
    ctx = auth.authorize(request)
    from app.team import require_admin
    require_admin(ctx)
    return rubrics.list_archive()


@app.post("/api/rubrics/restore/{filename}")
def rubric_restore(filename: str, request: Request):
    ctx = auth.authorize(request)
    from app.team import require_admin
    require_admin(ctx)
    try:
        return rubrics.restore_archive(rubrics.DEFAULT, filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.get("/api/notifications")
def notifications(request: Request):
    ctx = auth.authorize(request)
    # ponytail: no table, just recent decisions as notifications — add table when email needed
    rows = db.rows("SELECT id, decision, created_at FROM reviews WHERE org_id=? AND decision IS NOT NULL ORDER BY decided_at DESC LIMIT 20", (ctx["org_id"],))
    return [{"id": r["id"][:8], "decision": r["decision"], "at": r["decided_at"] or r["created_at"]} for r in rows]


@app.get("/api/analytics")
def analytics(request: Request, job_id: str | None = None):
    ctx = auth.authorize(request)
    return for_org(ctx["org_id"], job_id=job_id)


@app.get("/api/compliance")
def compliance_report(request: Request, job_id: str | None = None):
    ctx = auth.authorize(request)
    return compliance.report(ctx, job_id=job_id)


@app.get("/api/compliance.csv")
def compliance_csv(request: Request, decision: str | None = None, verdict: str | None = None,
                   from_date: str | None = None, to_date: str | None = None, job_id: str | None = None):
    ctx = auth.authorize(request)
    return Response(compliance.rows_csv(ctx, decision=decision, verdict=verdict,
                                        from_date=from_date, to_date=to_date, job_id=job_id), media_type="text/csv")


@app.post("/api/preview")
def preview(request: Request, file: UploadFile | None = File(None)):
    """Phase 1: extract text and detect PII. No removal, no storage."""
    ctx = auth.authorize(request)
    if not file or not file.filename:
        raise HTTPException(400, "No file selected. Click Choose files again and select a PDF, DOCX or TXT.")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".pdf", ".docx"}:
        raise HTTPException(400, "Choose a PDF, DOCX or TXT file.")
    # merge org custom rules into detected so HR sees them in Review PII
    data = file.file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 10 MB.")
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ("resume" + suffix)
            path.write_bytes(data)
            raw_text = extract_text(path)
    except ValueError as exc:
        # Preserve useful extractor message (e.g. blank page vs generic unreadable)
        raise HTTPException(400, str(exc)) from None
    except OSError:
        raise HTTPException(400, "Could not read this CV. Check the file format.") from None
    if not raw_text.strip():
        raise HTTPException(400, "Could not extract text from this CV.")
    detected = detect_pii(raw_text)
    # Append org custom rules that appear in text (so they show as removable in Review PII)
    try:
        customs = pii_rules.list_rules(ctx["org_id"])
        low = raw_text.lower()
        for r in customs:
            if r["value"].lower() in low:
                detected.append({"type": r["type"], "value": r["value"]})
    except Exception:
        pass
    return {"raw_text": raw_text, "detected_pii": detected}


@app.post("/api/preview/confirm")
def preview_confirm(request: Request, raw_text: str = Form(...),
                    name: str = Form(""), address: str = Form(""),
                    years: str = Form(""), remove_pii: str = Form("[]"),
                    job_id: str = Form("")):
    """Phase 2: apply selected PII removals and store the review. If job_id provided, validates Job is OPEN and rubric approved."""
    ctx = auth.authorize(request)
    if not raw_text.strip():
        raise HTTPException(400, "Candidate text is required.")
    # Job gate — must be OPEN and approved — check approved first so missing rubric message is clear
    jid = (job_id or "").strip() or None
    if jid:
        job = db.row("SELECT id, status, rubric_json, rubric_approved FROM jobs WHERE id=? AND org_id=?", (jid, ctx["org_id"]))
        if not job:
            raise HTTPException(404, "Selected Job not found.")
        if not job["rubric_approved"] or not job["rubric_json"]:
            raise HTTPException(400, "Selected Job has no approved rubric.")
        if job["status"] != "OPEN":
            raise HTTPException(400, "Selected Job is not open for screening.")
        try:
            rj = json.loads(job["rubric_json"])
            if sum(int(r.get("points", 0)) for r in rj) != 100:
                raise HTTPException(400, "Selected Job rubric must total 100.")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(400, "Selected Job rubric is invalid.")
    try:
        pii_items = json.loads(remove_pii) if remove_pii else []
    except (json.JSONDecodeError, TypeError):
        pii_items = []
    try:
        graduation_years = tuple(int(y.strip()) for y in years.split(",") if y.strip())
        candidate = prepare_candidate(raw_text, name=name, address=address,
                                      graduation_years=graduation_years,
                                      remove_pii=pii_items)
    except (ValueError, OSError):
        raise HTTPException(400, "Could not prepare this CV.") from None
    if len(candidate["cleaned_text"]) > 100000:
        raise HTTPException(400, "Resume text is too long; use a shorter CV.")
    return {"review_id": reviews.store_review(ctx, candidate, job_id=jid),
            "cleaned_text": candidate["cleaned_text"]}


MAX_ARCHIVE = 25 * 1024 * 1024


@app.post("/api/preview/batch")
async def preview_batch(request: Request):
    """Bulk: accepts ZIP (field `file`) OR multiple CVs (fields `file`/`files`). If job_id provided, every CV uses same approved Job rubric."""
    ctx = auth.authorize(request)
    form = await request.form()
    # Collect all uploaded files under `file` or `files`
    uploads = []
    for key in ("file", "files"):
        for item in form.getlist(key):
            if hasattr(item, "filename") and item.filename:
                data = await item.read()
                uploads.append((data, item.filename))
    if not uploads:
        raise HTTPException(400, "No files provided. Choose PDF/DOCX/TXT or a ZIP.")
    # Job gate for bulk — same approved rubric for every CV (check approved before OPEN for clear message)
    raw_jid = form.get("job_id", "")
    jid = (raw_jid.strip() if isinstance(raw_jid, str) else "") or None
    if jid:
        job = db.row("SELECT id, status, rubric_json, rubric_approved FROM jobs WHERE id=? AND org_id=?", (jid, ctx["org_id"]))
        if not job:
            raise HTTPException(404, "Selected Job not found.")
        if not job["rubric_approved"] or not job["rubric_json"]:
            raise HTTPException(400, "Selected Job has no approved rubric.")
        if job["status"] != "OPEN":
            raise HTTPException(400, "Selected Job is not open for screening.")
        try:
            rj = json.loads(job["rubric_json"])
            if sum(int(r.get("points", 0)) for r in rj) != 100:
                raise HTTPException(400, "Selected Job rubric must total 100.")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(400, "Selected Job rubric is invalid.")
    # Single ZIP path (existing behaviour)
    if len(uploads) == 1 and Path(uploads[0][1]).suffix.lower() == ".zip":
        data, _ = uploads[0]
        if len(data) > MAX_ARCHIVE:
            raise HTTPException(413, "Batch upload exceeds 25 MB.")
        try:
            return batch.ingest(ctx, data, job_id=jid)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
    # Direct bulk path (HR selects many PDFs)
    try:
        total = sum(len(d) for d, _ in uploads)
        if total > MAX_ARCHIVE:
            raise ValueError("Batch upload exceeds 25 MB. ZIP or select fewer files.")
        return batch.ingest_files(ctx, uploads, job_id=jid)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cleaned_text: str = Field(min_length=1, max_length=100000)
    job_id: str = rubrics.DEFAULT


@app.post("/api/reviews/{token}/score")
def score(token: str, request: Request, body: ScoreRequest):
    ctx = auth.authorize(request)
    review = _review(token, ctx)
    if review["card"]:
        raise HTTPException(409, "This review is already scored.")
    candidate = {"candidate_hash": review["candidate_hash"], "cleaned_text": body.cleaned_text,
                 "candidate_data": wrap_candidate_data(body.cleaned_text)}
    org_keys = credentials.resolve(ctx["org_id"])
    transport = (lambda messages: complete(messages, credentials=org_keys)) if org_keys else complete
    # Job-aware: if review has job_id, use that job's approved rubric (no fallback)
    jid = review.get("job_id")
    if jid:
        job = db.row("SELECT rubric_json, rubric_approved FROM jobs WHERE id=? AND org_id=?", (jid, ctx["org_id"]))
        if not job or not job["rubric_approved"] or not job["rubric_json"]:
            raise HTTPException(400, "This review's Job has no approved rubric. Approve it in HR Controls.")
        try:
            rj = json.loads(job["rubric_json"])
            rubric = {r["requirement"]: float(r["points"]) for r in rj}
            guidance = "\n".join(f"{r['requirement']} ({r['points']}pts): {r['evidence']}" for r in rj)
            if sum(rubric.values()) != 100:
                raise HTTPException(400, "Job rubric must total 100.")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(400, "Job rubric is invalid.")
        try:
            card = score_prepared_with_rubric(candidate, complete=transport, rubric=rubric, rubric_guidance=guidance, job_id=jid)
        except ScoringUnavailable as exc:
            hint = "" if org_keys else " An admin can add a provider key in Settings."
            raise HTTPException(503, str(exc) + hint) from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
    else:
        try:
            rubric_path = rubrics.path_for(body.job_id)
        except KeyError:
            raise HTTPException(400, "Choose a job rubric that exists.") from None
        try:
            card = score_prepared(candidate, complete=transport, rubric_path=rubric_path, job_id=body.job_id)
        except ScoringUnavailable as exc:
            hint = "" if org_keys else " An admin can add a provider key in Settings."
            raise HTTPException(503, str(exc) + hint) from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
    payload = card.model_dump()
    db.run("UPDATE reviews SET card = ?, cleaned_text = ? WHERE id = ?",
           (json.dumps(payload, ensure_ascii=False), body.cleaned_text, token))
    return payload


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["APPROVE", "REJECT"]
    notes: str = Field(default="", max_length=2000)


@app.post("/api/reviews/{token}/decision")
def decide(token: str, request: Request, body: DecisionRequest):
    ctx = auth.authorize(request)
    review = _review(token, ctx)
    if not review["card"]:
        raise HTTPException(409, "Generate and review a scorecard first.")
    if review["decision"]:
        raise HTTPException(409, "Decision already saved. Start a new review to reassess.")
    record = {"scorecard": json.loads(review["card"]), "decision": body.decision,
              "reviewer_notes": body.notes, "decided_at": datetime.now(timezone.utc).isoformat()}
    db.run("UPDATE reviews SET decision = ?, reviewer_notes = ?, decided_at = ? WHERE id = ?",
           (body.decision, body.notes, record["decided_at"], token))
    return record


class MemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    role: str = "RECRUITER"


class RoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str


@app.get("/api/team")
def team_list(request: Request):
    ctx = auth.authorize(request)
    return team.members(ctx["org_id"])


@app.post("/api/team/members")
def team_add(request: Request, body: MemberRequest):
    ctx = auth.authorize(request)
    return team.add_member(ctx, body.email, body.role)


@app.post("/api/team/members/{user_id}/role")
def team_role(user_id: str, request: Request, body: RoleRequest):
    ctx = auth.authorize(request)
    return team.set_role(ctx, user_id, body.role)


class CredentialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    api_key: str
    model: str = ""


@app.get("/api/settings/llm")
def llm_settings(request: Request):
    ctx = auth.authorize(request)
    return credentials.list_keys(ctx["org_id"])


@app.get("/api/providers")
def provider_catalog():
    """Provider options for the settings dropdown."""
    return [{"id": name, "label": spec["label"], "default_model": spec["default_model"],
             "needs_key": spec["needs_key"]}
            for name, spec in CATALOG.items()]


@app.post("/api/settings/llm")
def set_llm_settings(request: Request, body: CredentialRequest):
    ctx = auth.authorize(request)
    return credentials.set_key(ctx, body.provider, body.model, body.api_key)


class PiiRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(min_length=1, max_length=20)
    value: str = Field(min_length=1, max_length=120)


@app.get("/api/settings/pii")
def pii_list(request: Request):
    ctx = auth.authorize(request)
    return pii_rules.list_rules(ctx["org_id"])


@app.post("/api/settings/pii")
def pii_add(request: Request, body: PiiRuleRequest):
    ctx = auth.authorize(request)
    return pii_rules.add_rule(ctx, body.type, body.value)


@app.delete("/api/settings/pii/{rule_id}")
def pii_delete(rule_id: str, request: Request):
    ctx = auth.authorize(request)
    return pii_rules.delete_rule(ctx, rule_id)


class OrgRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class OrgTypeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    org_type: str


class PasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str
    new_password: str


@app.get("/api/settings")
def settings_profile(request: Request):
    ctx = auth.authorize(request)
    return orgs.profile(ctx)


@app.post("/api/settings/org")
def settings_rename(request: Request, body: OrgRequest):
    ctx = auth.authorize(request)
    return orgs.rename(ctx, body.name)


@app.post("/api/settings/org-type")
def settings_org_type(request: Request, body: OrgTypeRequest):
    ctx = auth.authorize(request)
    return orgs.set_type(ctx, body.org_type)


@app.post("/api/settings/password")
def settings_password(request: Request, body: PasswordRequest):
    ctx = auth.authorize(request)
    auth.change_password(ctx, body.current_password, body.new_password)
    return {"changed": True}


# --- Jobs ---
class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    jd_text: str = Field(default="", max_length=8000)


class JobUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=120)
    jd_text: str | None = Field(default=None, max_length=8000)
    status: str | None = None
    rubric: list[dict] | None = None
    rubric_approved: int | None = None


@app.get("/api/jobs")
def jobs_list(request: Request):
    ctx = auth.authorize(request)
    return jobs.list_jobs(ctx["org_id"])


@app.post("/api/jobs")
def jobs_create(request: Request, body: JobCreate):
    ctx = auth.authorize(request)
    return jobs.create_job(ctx["org_id"], body.title, body.jd_text)


@app.get("/api/jobs/{job_id}")
def jobs_get(job_id: str, request: Request):
    ctx = auth.authorize(request)
    return jobs.get_job(ctx["org_id"], job_id)


@app.put("/api/jobs/{job_id}")
def jobs_update(job_id: str, request: Request, body: JobUpdate):
    ctx = auth.authorize(request)
    return jobs.update_job(ctx["org_id"], job_id, title=body.title, jd_text=body.jd_text, status=body.status, rubric=body.rubric, rubric_approved=body.rubric_approved)


@app.post("/api/jobs/{job_id}/close")
def jobs_close(job_id: str, request: Request):
    ctx = auth.authorize(request)
    return jobs.close_job(ctx["org_id"], job_id)


# --- Job Rubric Draft/Approve ---
@app.post("/api/jobs/{job_id}/rubric/draft")
def jobs_rubric_draft(job_id: str, request: Request):
    ctx = auth.authorize(request)
    # BYOK per org — reuse provider chain
    creds = credentials.resolve(ctx["org_id"])
    return jobs.generate_draft(ctx["org_id"], job_id, credentials=creds if creds else None)


@app.post("/api/jobs/{job_id}/rubric/approve")
def jobs_rubric_approve(job_id: str, request: Request):
    ctx = auth.authorize(request)
    job = jobs.get_job(ctx["org_id"], job_id)
    rubric = job.get("rubric")
    if not rubric:
        raise HTTPException(400, "Generate a draft rubric first.")
    total = sum(int(r.get("points", 0)) for r in rubric)
    if total != 100:
        raise HTTPException(400, f"Rubric points total {total}, must be 100 before approval.")
    # validate via existing contract (unique, points range already checked on save)
    return jobs.update_job(ctx["org_id"], job_id, rubric_approved=1, status="OPEN")
