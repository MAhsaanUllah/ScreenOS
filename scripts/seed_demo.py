"""Seed a demo organization with sample reviews so the workspace can be explored.

    python scripts/seed_demo.py

The credentials below are local demo data — never reuse them on a reachable
deployment. Re-running replaces the demo organization.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.auth import register  # noqa: E402
from app.extractor import extract_text  # noqa: E402
from app.guardrails import prepare_candidate  # noqa: E402
from app.reviews import store_review  # noqa: E402
from app.scorer import score_prepared  # noqa: E402
from scripts.evaluate_samples import SAMPLES, offline_complete  # noqa: E402

ORG = "Demo Recruiting"
EMAIL = "demo@screenos.local"
PASSWORD = "demo12345"
RUBRIC = ROOT / "rubrics/ai-engineer.md"
SEED = {"01_strong.txt": "APPROVE", "02_python.docx": "APPROVE",
        "05_claims_only.docx": "REJECT", "07_missing_requirements.txt": None}


def reset() -> None:
    """Drop the previous demo organization and everything it owns."""
    org = db.row("SELECT id FROM orgs WHERE name = ?", (ORG,))
    if not org:
        return
    org_id = org["id"]
    members = [row["user_id"] for row in db.rows(
        "SELECT user_id FROM org_members WHERE org_id = ?", (org_id,))]
    for table in ("reviews", "sessions", "org_credentials", "org_members"):
        db.run(f"DELETE FROM {table} WHERE org_id = ?", (org_id,))
    db.run("DELETE FROM orgs WHERE id = ?", (org_id,))
    for user_id in members:
        if not db.row("SELECT 1 FROM org_members WHERE user_id = ?", (user_id,)):
            db.run("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            db.run("DELETE FROM users WHERE id = ?", (user_id,))


def main() -> None:
    reset()
    admin = register(ORG, EMAIL, PASSWORD)
    ctx = {"org_id": admin["org"]["id"], "user_id": admin["user"]["id"], "role": "ADMIN"}

    for filename, decision in SEED.items():
        path = ROOT / "samples/cvs" / filename
        person = SAMPLES[filename][2]
        candidate = prepare_candidate(extract_text(path), name=person)
        card = score_prepared(candidate, complete=offline_complete(filename), rubric_path=RUBRIC)
        review_id = store_review(ctx, candidate)
        db.run("UPDATE reviews SET card = ? WHERE id = ?", (card.model_dump_json(), review_id))
        if decision:
            db.run("UPDATE reviews SET decision = ?, reviewer_notes = ?, decided_at = ? WHERE id = ?",
                   (decision, "Seeded demo decision.", datetime.now(timezone.utc).isoformat(),
                    review_id))

    print(f"Seeded {len(SEED)} reviews for {ORG!r}.")
    print(f"Sign in with {EMAIL} / {PASSWORD}")
    print("API:       python -m uvicorn app.main:app --host 127.0.0.1 --port 8000")
    print("Workspace: http://localhost:5174 (dev)  |  http://127.0.0.1:8000 (built)")


if __name__ == "__main__":
    main()
