"""Organization profile settings for the workspace Settings screen."""

from fastapi import HTTPException

from app import db
from app.team import require_admin

NAME_MAX = 80


def profile(ctx: dict) -> dict:
    org = db.row("SELECT id, name, created_at, org_type FROM orgs WHERE id = ?", (ctx["org_id"],))
    if not org:
        raise HTTPException(404, "Organization not found.")
    members = db.row("SELECT COUNT(*) AS total FROM org_members WHERE org_id = ?", (ctx["org_id"],))
    return {"id": org["id"], "name": org["name"], "created_at": org["created_at"],
            "org_type": org.get("org_type") or "internal",
            "members": members["total"], "role": ctx["role"]}


def set_type(ctx: dict, org_type: str) -> dict:
    require_admin(ctx)
    org_type = (org_type or "").strip().lower()
    if org_type not in {"internal", "agency"}:
        raise HTTPException(400, "Type must be internal or agency.")
    db.run("UPDATE orgs SET org_type=? WHERE id=?", (org_type, ctx["org_id"]))
    return profile(ctx)


def rename(ctx: dict, name: str) -> dict:
    require_admin(ctx)
    name = (name or "").strip()
    if not name:
        raise HTTPException(400, "Organization name is required.")
    if len(name) > NAME_MAX:
        raise HTTPException(400, f"Organization name must be at most {NAME_MAX} characters.")
    db.run("UPDATE orgs SET name = ? WHERE id = ?", (name, ctx["org_id"]))
    return profile(ctx)
