"""Bulk ingestion: one review per resume, from a ZIP or a direct multi-file upload.

Both entry points share `_intake`, so PII handling lives in one place. The name
comes from the CV text first, then from the file name (generic words such as
"Resume_Final" stripped). If neither yields a name nothing is guessed or
redacted for it, and the review is flagged `name_not_found`. Every batch review
carries a `pii_flag` and cannot be scored until HR confirms it.

ponytail: extraction runs sequentially. Add a worker queue only when a batch is
big enough that the recruiter notices the wait.
"""

import io
import re
import tempfile
import zipfile
from pathlib import Path

from app import db
from app.extractor import extract_with_report
from app.guardrails import _guess_name, detect_pii, prepare_candidate
from app.reviews import store_review

SUPPORTED = {".pdf", ".docx", ".txt"}
MAX_FILES = 50
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE = 25 * 1024 * 1024
_GENERIC = {"resume", "cv", "final", "updated", "new", "latest"}


def _name_from_filename(filename: str) -> str:
    words = re.sub(r"[_\-.()\[\]]+", " ", Path(filename).stem).split()
    return " ".join(w for w in words
                    if w.lower() not in _GENERIC and not re.fullmatch(r"v\d+|\d+", w, re.IGNORECASE))


def _reject(filename: str, size: int) -> str:
    if Path(filename).suffix.lower() not in SUPPORTED:
        return "unsupported file type"
    if size > MAX_FILE_BYTES:
        return "file exceeds 10 MB"
    return ""


def _intake(ctx: dict, customs: list, filename: str, data: bytes, job_id: str | None) -> dict:
    """Extract, detect, redact and store one CV. Raises ValueError/OSError on bad input."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / ("resume" + Path(filename).suffix.lower())
        path.write_bytes(data)
        raw_text, hidden = extract_with_report(path)
    items = detect_pii(raw_text)
    if hidden:
        items.append({"type": "hidden_text", "value": str(hidden)})
    name = _guess_name(raw_text) or _name_from_filename(filename)
    if name and not any(i["type"] == "name" for i in items):
        items.append({"type": "name", "value": name})
    low = raw_text.lower()
    items += [{"type": r["type"], "value": r["value"]} for r in customs if r["value"].lower() in low]
    candidate = prepare_candidate(raw_text, name=name, remove_pii=items, name_optional=True)
    flag = "unconfirmed" if name else "name_not_found"
    return {"filename": filename, "name_guess": name,
            "candidate_hash": candidate["candidate_hash"],
            "review_id": store_review(ctx, candidate, job_id=job_id, pii_flag=flag),
            "pii_flag": flag, "detected_pii": items}


def _customs(ctx: dict) -> list:
    # Not wrapped in try/except: failing to load org rules must fail the batch, not skip redaction.
    return db.rows("SELECT type, value FROM org_pii_rules WHERE org_id=?", (ctx["org_id"],))


def ingest(ctx: dict, archive: bytes, job_id: str | None = None) -> dict:
    try:
        bundle = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile:
        raise ValueError("That file is not a readable ZIP archive.") from None

    with bundle:
        members = [m for m in bundle.infolist() if not m.is_dir()]
        skipped = [{"filename": m.filename, "reason": f"batch limit is {MAX_FILES} files"}
                   for m in members[MAX_FILES:]]
        customs, reviews = _customs(ctx), []
        for member in members[:MAX_FILES]:
            # size is checked from the ZIP header before the member is read into memory
            reason = _reject(Path(member.filename).name, member.file_size)
            if reason:
                skipped.append({"filename": member.filename, "reason": reason})
                continue
            try:
                reviews.append(_intake(ctx, customs, member.filename, bundle.read(member), job_id))
            except (ValueError, OSError) as exc:
                skipped.append({"filename": member.filename, "reason": str(exc)})
    return {"accepted": len(reviews), "skipped": skipped, "reviews": reviews}


def ingest_files(ctx: dict, uploads: list[tuple[bytes, str]], job_id: str | None = None) -> dict:
    """Direct bulk: list of (bytes, filename) without ZIP. HR selects 50 files in UI."""
    if not uploads:
        raise ValueError("No files provided.")
    skipped = [{"filename": fn, "reason": f"batch limit is {MAX_FILES} files"}
               for _, fn in uploads[MAX_FILES:]]
    customs, reviews = _customs(ctx), []
    for data, filename in uploads[:MAX_FILES]:
        reason = _reject(Path(filename).name, len(data))
        if reason:
            skipped.append({"filename": filename, "reason": reason})
            continue
        try:
            reviews.append(_intake(ctx, customs, filename, data, job_id))
        except (ValueError, OSError) as exc:
            skipped.append({"filename": filename, "reason": str(exc)})
    return {"accepted": len(reviews), "skipped": skipped, "reviews": reviews}
