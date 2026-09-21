"""Per-organization provider credentials (BYOK).

Keys belong to the organization, are admin-managed, and are never returned by the
API or written to logs: callers only ever see a masked hint. They are stored as
plain text in the local SQLite file, so whoever can read that file can read the
keys — operators must protect it. ponytail: encrypt at rest when the app is
deployed beyond a trusted local machine.
"""

from datetime import datetime, timezone

from fastapi import HTTPException

from app import db
from app.providers import CATALOG
from app.team import require_admin

PROVIDERS = tuple(CATALOG)
DEFAULT_MODELS = {name: spec["default_model"] for name, spec in CATALOG.items()}


def set_key(ctx: dict, provider: str, model: str, api_key: str) -> list[dict]:
    require_admin(ctx)
    provider = (provider or "").strip().lower()
    if provider not in CATALOG:
        raise HTTPException(400, "Provider must be one of: " + ", ".join(PROVIDERS) + ".")
    api_key = (api_key or "").strip()
    if CATALOG[provider]["needs_key"] and len(api_key) < 8:
        raise HTTPException(400, "That API key looks too short.")
    model = (model or "").strip() or DEFAULT_MODELS[provider]
    db.run(
        "INSERT INTO org_credentials (org_id, provider, model, api_key, updated_at) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT(org_id, provider) DO UPDATE SET "
        "model = excluded.model, api_key = excluded.api_key, updated_at = excluded.updated_at",
        (ctx["org_id"], provider, model, api_key, datetime.now(timezone.utc).isoformat()),
    )
    return list_keys(ctx["org_id"])


def list_keys(org_id: str) -> list[dict]:
    """Settings-screen view: the key itself is replaced by a last-four hint."""
    return [{"provider": row["provider"], "model": row["model"],
             "hint": ("…" + row["api_key"][-4:]) if row["api_key"] else "not required",
             "updated_at": row["updated_at"]}
            for row in db.rows(
                "SELECT provider, model, api_key, updated_at FROM org_credentials "
                "WHERE org_id = ? ORDER BY provider", (org_id,))]


def resolve(org_id: str) -> list[dict]:
    """Ordered credentials for scoring. Server-side only; never serialize this."""
    return db.rows(
        "SELECT provider, model, api_key FROM org_credentials WHERE org_id = ? "
        "ORDER BY CASE provider WHEN 'deepseek' THEN 0 ELSE 1 END",
        (org_id,))
