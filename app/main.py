"""Local single-operator recruiter UI. Bind only to 127.0.0.1."""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from threading import Lock
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.extractor import extract_text
from app.guardrails import prepare_candidate, wrap_candidate_data
from app.providers import ScoringUnavailable, complete
from app.scorer import score_prepared

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="SCREENOS", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")
# Local demo only: at most 20 in-memory reviews. Restart clears unsaved previews.
reviews = {}
lock = Lock()


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    if request.method != "GET" and request.headers.get("x-screenos") != "1":
        return JSONResponse({"detail": "Use the SCREENOS page to make this request."}, status_code=403)
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response


@app.get("/")
def index():
    return FileResponse(ROOT / "app/static/index.html")


@app.post("/api/preview")
def preview(file: UploadFile = File(...), name: str = Form(...), address: str = Form(""), years: str = Form("")):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".pdf", ".docx"}:
        raise HTTPException(400, "Choose a PDF, DOCX or TXT file.")
    data = file.file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 10 MB.")
    try:
        graduation_years = tuple(int(y.strip()) for y in years.split(",") if y.strip())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ("resume" + suffix)
            path.write_bytes(data)
            candidate = prepare_candidate(extract_text(path), name=name, address=address,
                                          graduation_years=graduation_years)
        if len(candidate["cleaned_text"]) > 100000:
            raise ValueError("Resume text is too long; use a shorter CV.")
    except (ValueError, OSError):
        raise HTTPException(400, "Could not prepare this CV. Check the file, name and comma-separated graduation years.") from None
    with lock:
        if len(reviews) >= 20:
            raise HTTPException(429, "Review limit reached. Restart the local server to clear unsaved reviews.")
        token = uuid4().hex
        reviews[token] = {"candidate": candidate, "busy": False, "card": None, "decision": None}
    return {"review_id": token, "cleaned_text": candidate["cleaned_text"]}


class ScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cleaned_text: str = Field(min_length=1, max_length=100000)


@app.post("/api/reviews/{token}/score")
def score(token: str, body: ScoreRequest):
    with lock:
        review = reviews.get(token)
        if not review:
            raise HTTPException(404, "Review expired. Upload the CV again.")
        if review["busy"] or review["card"]:
            raise HTTPException(409, "This review is already scoring or scored.")
        review["busy"] = True
    try:
        candidate = dict(review["candidate"], cleaned_text=body.cleaned_text,
                         candidate_data=wrap_candidate_data(body.cleaned_text))
        card = score_prepared(candidate, complete=complete, rubric_path=ROOT / "rubrics/rubric.md")
        with lock:
            review["candidate"] = candidate
            review["card"] = card.model_dump()
        return review["card"]
    except ScoringUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    finally:
        with lock:
            review["busy"] = False


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["APPROVE", "REJECT"]
    notes: str = Field(default="", max_length=2000)


@app.post("/api/reviews/{token}/decision")
def decide(token: str, body: DecisionRequest):
    with lock:
        review = reviews.get(token)
        if not review or not review["card"]:
            raise HTTPException(409, "Generate and review a scorecard first.")
        if review["decision"]:
            raise HTTPException(409, "Decision already saved. Start a new review to reassess.")
        record = {"scorecard": review["card"], "decision": body.decision,
                  "reviewer_notes": body.notes, "decided_at": datetime.now(timezone.utc).isoformat()}
        try:
            output = ROOT / "output"
            output.mkdir(exist_ok=True)
            pending = output / f"{token}.tmp"
            pending.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            pending.replace(output / f"{token}.json")
        except OSError:
            raise HTTPException(500, "Decision could not be saved. Check disk access and retry.") from None
        review["decision"] = record
    return record
