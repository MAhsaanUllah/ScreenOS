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

from app import auth, batch, compliance, credentials, db, orgs, reviews, rubrics, team
from app.calibration import for_org
from app.extractor import extract_text
from app.guardrails import detect_pii, prepare_candidate, wrap_candidate_data
from app.providers import CATALOG, ScoringUnavailable, complete
from app.scorer import rubric_info, score_prepared

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


@app.post("/api/auth/register")
def register(body: RegisterRequest):
    return auth.register(body.org_name, body.email, body.password)


@app.post("/api/auth/login")
def login(request: Request, body: LoginRequest):
    return auth.login(body.email, body.password, request.client.host if request.client else "")


@app.post("/api/auth/logout")
def logout(request: Request):
    ctx = None
    try:
        ctx = auth.authorize(request)
    except HTTPException:
        # No valid session — still clear any token presented
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if token:
            auth.logout(token)
        return {"ok": True}
    auth.logout(ctx["token"])
    return {"ok": True}


@app.post("/api/auth/switch-org")
def switch_org(request: Request, body: SwitchOrgRequest):
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    return auth.switch_org(token, body.org_id)


def _review(token: str, ctx: dict) -> dict:
    review = db.row("SELECT * FROM reviews WHERE id = ? AND org_id = ?", (token, ctx["org_id"]))
    if not review:
        raise HTTPException(404, "Review expired. Upload the CV again.")
    return review


def _summary(review: dict) -> dict:
    card = json.loads(review["card"]) if review["card"] else None
    return {
        "id": review["id"],
        "short": review["id"][:8],
        "created_at": review["created_at"],
        "decision": review["decision"],
        "status": review["decision"] or ("SCORED" if card else "PENDING"),
        "score": card["overall_score"] if card else None,
        "verdict": card["verdict"] if card else None,
        "job_id": card["job_id"] if card else None,
    }


@app.get("/api/reviews")
def list_reviews(request: Request):
    ctx = auth.authorize(request)
    return [_summary(r) for r in db.rows(
        "SELECT id, card, decision, created_at FROM reviews WHERE org_id = ? ORDER BY created_at DESC",
        (ctx["org_id"],),
    )]


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


@app.get("/api/rubrics")
def rubric_list():
    return rubrics.list_rubrics()


@app.get("/api/analytics")
def analytics(request: Request):
    ctx = auth.authorize(request)
    return for_org(ctx["org_id"])


@app.get("/api/compliance")
def compliance_report(request: Request):
    ctx = auth.authorize(request)
    return compliance.report(ctx)


@app.get("/api/compliance.csv")
def compliance_csv(request: Request):
    ctx = auth.authorize(request)
    return Response(compliance.rows_csv(ctx), media_type="text/csv")


@app.post("/api/preview")
def preview(request: Request, file: UploadFile = File(...)):
    """Phase 1: extract text and detect PII. No removal, no storage."""
    ctx = auth.authorize(request)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".pdf", ".docx"}:
        raise HTTPException(400, "Choose a PDF, DOCX or TXT file.")
    data = file.file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 10 MB.")
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ("resume" + suffix)
            path.write_bytes(data)
            raw_text = extract_text(path)
    except (ValueError, OSError):
        raise HTTPException(400, "Could not read this CV. Check the file format.") from None
    if not raw_text.strip():
        raise HTTPException(400, "Could not extract text from this CV.")
    detected = detect_pii(raw_text)
    return {"raw_text": raw_text, "detected_pii": detected}


@app.post("/api/preview/confirm")
def preview_confirm(request: Request, raw_text: str = Form(...),
                    name: str = Form(""), address: str = Form(""),
                    years: str = Form(""), remove_pii: str = Form("[]")):
    """Phase 2: apply selected PII removals and store the review."""
    ctx = auth.authorize(request)
    if not raw_text.strip():
        raise HTTPException(400, "Candidate text is required.")
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
    return {"review_id": reviews.store_review(ctx, candidate),
            "cleaned_text": candidate["cleaned_text"]}


MAX_ARCHIVE = 25 * 1024 * 1024


@app.post("/api/preview/batch")
def preview_batch(request: Request, file: UploadFile = File(...)):
    ctx = auth.authorize(request)
    data = file.file.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise HTTPException(413, "Batch upload exceeds 25 MB.")
    try:
        return batch.ingest(ctx, data)
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
    try:
        rubric_path = rubrics.path_for(body.job_id)
    except KeyError:
        raise HTTPException(400, "Choose a job rubric that exists.") from None
    org_keys = credentials.resolve(ctx["org_id"])
    transport = (lambda messages: complete(messages, credentials=org_keys)) if org_keys else complete
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


class OrgRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


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


@app.post("/api/settings/password")
def settings_password(request: Request, body: PasswordRequest):
    ctx = auth.authorize(request)
    auth.change_password(ctx, body.current_password, body.new_password)
    return {"changed": True}
