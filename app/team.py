"""Organization team and role management.

Roles are a fixed pair; whoever registers an organization is its first admin.
ponytail: adding by email only attaches an existing account. Email invites and
pending-invite rows arrive when outbound mail exists.
"""

from fastapi import HTTPException

from app import db

ROLES = ("ADMIN", "RECRUITER")


def members(org_id: str) -> list[dict]:
    return db.rows(
        "SELECT u.id, u.email, m.role FROM org_members m JOIN users u ON u.id = m.user_id "
        "WHERE m.org_id = ? ORDER BY m.role, u.email",
        (org_id,),
    )


def add_member(ctx: dict, email: str, role: str) -> list[dict]:
    require_admin(ctx)
    role = _role(role)
    user = db.row("SELECT id FROM users WHERE email = ?", ((email or "").strip(),))
    if not user:
        raise HTTPException(404, "No account with that email. Ask them to register first.")
    if db.row("SELECT 1 FROM org_members WHERE org_id = ? AND user_id = ?", (ctx["org_id"], user["id"])):
        raise HTTPException(409, "That person is already on this team.")
    db.run("INSERT INTO org_members (org_id, user_id, role) VALUES (?, ?, ?)",
           (ctx["org_id"], user["id"], role))
    return members(ctx["org_id"])


def set_role(ctx: dict, user_id: str, role: str) -> list[dict]:
    require_admin(ctx)
    role = _role(role)
    if user_id == ctx["user_id"]:
        raise HTTPException(400, "You cannot change your own role.")
    if not db.row("SELECT 1 FROM org_members WHERE org_id = ? AND user_id = ?", (ctx["org_id"], user_id)):
        raise HTTPException(404, "That person is not on this team.")
    db.run("UPDATE org_members SET role = ? WHERE org_id = ? AND user_id = ?",
           (role, ctx["org_id"], user_id))
    return members(ctx["org_id"])


def require_admin(ctx: dict) -> None:
    """Shared guard for organization-admin-only actions."""
    if ctx["role"] != "ADMIN":
        raise HTTPException(403, "Only an admin can do that.")


def _role(role: str) -> str:
    role = (role or "").strip().upper()
    if role not in ROLES:
        raise HTTPException(400, "Role must be ADMIN or RECRUITER.")
    return role
