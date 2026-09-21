"""Per-organization provider credentials (BYOK).

Keys are encrypted at rest (Fernet, key from SCREENOS_CRED_KEY) and never
returned by the API or written to logs — callers only see a last-four hint.
Resolves decrypt server-side only. Legacy plaintext rows auto-decrypt & migrate.
"""

from datetime import datetime, timezone

from fastapi import HTTPException

from app import crypto, db
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
    model = (model or "").strip() or DEFAULT_MODELS[provider]
    if len(model) > 120:
        raise HTTPException(400, "Model name is too long (max 120).")
    if len(api_key) > 512:
        raise HTTPException(400, "API key is too long.")
    if CATALOG[provider]["needs_key"] and len(api_key) < 8:
        raise HTTPException(400, "That API key looks too short.")
    enc = crypto.encrypt_value(api_key) if api_key else ""
    db.run(
        "INSERT INTO org_credentials (org_id, provider, model, api_key, updated_at) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT(org_id, provider) DO UPDATE SET "
        "model = excluded.model, api_key = excluded.api_key, updated_at = excluded.updated_at",
        (ctx["org_id"], provider, model, enc, datetime.now(timezone.utc).isoformat()),
    )
    return list_keys(ctx["org_id"])


def list_keys(org_id: str) -> list[dict]:
    """Settings-screen view: the key itself is replaced by a last-four hint."""
    out = []
    for row in db.rows(
            "SELECT provider, model, api_key, updated_at FROM org_credentials "
            "WHERE org_id = ? ORDER BY provider", (org_id,)):
        raw = crypto.decrypt_value(row["api_key"]) if row["api_key"] else ""
        hint = ("…" + raw[-4:]) if raw else "not required"
        out.append({"provider": row["provider"], "model": row["model"],
                    "hint": hint, "updated_at": row["updated_at"]})
    return out


def resolve(org_id: str) -> list[dict]:
    """Ordered credentials for scoring. Server-side only; never serialize this."""
    rows = db.rows(
        "SELECT provider, model, api_key FROM org_credentials WHERE org_id = ? "
        "ORDER BY CASE provider WHEN 'deepseek' THEN 0 ELSE 1 END",
        (org_id,))
    # Decrypt; lazy-migrate legacy plaintext to encrypted
    decoded = []
    for r in rows:
        plain = crypto.decrypt_value(r["api_key"]) if r["api_key"] else ""
        # Legacy plaintext starts not with gAAAA — after decrypt we still have plain,
        # but stored value was plaintext; re-encrypt lazily if needed
        if r["api_key"] and not r["api_key"].startswith("gAAAA"):
            try:
                enc = crypto.encrypt_value(plain)
                if enc != r["api_key"]:
                    db.run("UPDATE org_credentials SET api_key=? WHERE org_id=? AND provider=?",
                           (enc, org_id, r["provider"]))
            except Exception:
                pass
        decoded.append({"provider": r["provider"], "model": r["model"], "api_key": plain})
    return decoded
