"""Bulk ingestion: turn one uploaded ZIP into one review per resume.

A batch has no per-candidate name field, so each name is guessed from the file
name and redacted before anything is stored — de-identification still happens
server-side, and the recruiter corrects a wrong guess before scoring.

ponytail: extraction runs sequentially. Add a worker queue only when a batch is
big enough that the recruiter notices the wait.
"""

import io
import re
import tempfile
import zipfile
from pathlib import Path

from app.extractor import extract_text
from app.guardrails import detect_pii, prepare_candidate
from app.reviews import store_review

SUPPORTED = {".pdf", ".docx", ".txt"}
MAX_FILES = 50
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE = 25 * 1024 * 1024


def ingest(ctx: dict, archive: bytes) -> dict:
    try:
        bundle = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile:
        raise ValueError("That file is not a readable ZIP archive.") from None

    with bundle, tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        members = [member for member in bundle.infolist() if not member.is_dir()]
        skipped = [{"filename": member.filename, "reason": f"batch limit is {MAX_FILES} files"}
                   for member in members[MAX_FILES:]]
        reviews = []
        for member in members[:MAX_FILES]:
            name = Path(member.filename).name
            guess = re.sub(r"[_\-.]+", " ", Path(name).stem).strip()
            reason = _reject(member, name, guess)
            if reason:
                skipped.append({"filename": member.filename, "reason": reason})
                continue
            try:
                path = root / ("resume" + Path(name).suffix.lower())
                path.write_bytes(bundle.read(member))
                raw_text = extract_text(path)
                detected = detect_pii(raw_text)
                candidate = prepare_candidate(raw_text, name=guess)
            except (ValueError, OSError) as exc:
                skipped.append({"filename": member.filename, "reason": str(exc)})
                continue
            reviews.append({"filename": member.filename, "name_guess": guess,
                            "candidate_hash": candidate["candidate_hash"],
                            "review_id": store_review(ctx, candidate),
                            "detected_pii": detected})
    return {"accepted": len(reviews), "skipped": skipped, "reviews": reviews}


def _reject(member: zipfile.ZipInfo, name: str, guess: str) -> str:
    if Path(name).suffix.lower() not in SUPPORTED:
        return "unsupported file type"
    if member.file_size > MAX_FILE_BYTES:
        return "file exceeds 10 MB"
    if not guess:
        return "cannot derive a candidate name from the file name"
    return ""


def ingest_files(ctx: dict, uploads: list[tuple[bytes, str]]) -> dict:
    """Direct bulk: list of (bytes, filename) without ZIP. HR selects 50 files in UI."""
    if not uploads:
        raise ValueError("No files provided.")
    if len(uploads) > MAX_FILES:
        # keep first 50, mark rest skipped
        extra = uploads[MAX_FILES:]
        uploads = uploads[:MAX_FILES]
        skipped = [{"filename": fn, "reason": f"batch limit is {MAX_FILES} files"} for _, fn in extra]
    else:
        skipped: list[dict] = []
    reviews: list[dict] = []
    import tempfile as _tf
    for data, filename in uploads:
        name = Path(filename).name
        guess = re.sub(r"[_\-.]+", " ", Path(name).stem).strip()
        if Path(name).suffix.lower() not in SUPPORTED:
            skipped.append({"filename": filename, "reason": "unsupported file type"})
            continue
        if len(data) > MAX_FILE_BYTES:
            skipped.append({"filename": filename, "reason": "file exceeds 10 MB"})
            continue
        if not guess:
            skipped.append({"filename": filename, "reason": "cannot derive a candidate name from the file name"})
            continue
        try:
            with _tf.TemporaryDirectory() as folder:
                path = Path(folder) / ("resume" + Path(name).suffix.lower())
                path.write_bytes(data)
                raw_text = extract_text(path)
                detected = detect_pii(raw_text)
                candidate = prepare_candidate(raw_text, name=guess)
        except (ValueError, OSError) as exc:
            skipped.append({"filename": filename, "reason": str(exc)})
            continue
        reviews.append({"filename": filename, "name_guess": guess,
                        "candidate_hash": candidate["candidate_hash"],
                        "review_id": store_review(ctx, candidate),
                        "detected_pii": detected})
    return {"accepted": len(reviews), "skipped": skipped, "reviews": reviews}
