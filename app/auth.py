"""Register, login, and tenant-scoped session handling.

Sessions are opaque tokens in the sessions table, not JWTs.
ponytail: stateless single-key JWT if the server ever runs more than one
instance or needs cross-service auth.
"""
import hashlib
import hmac
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, Request

from app import db

PASSWORD_MIN = 8
SESSION_DAYS = 30
LOCKOUT_ATTEMPTS = 5
LOCKOUT_SECONDS = 60

# Failed sign-ins per email address and client address.
# ponytail: in-process only; a multi-instance deployment needs a shared store.
_attempts: dict[str, list[float]] = {}


def _locked_out(key: str) -> bool:
    now = time.monotonic()
    recent = [stamp for stamp in _attempts.get(key, []) if now - stamp < LOCKOUT_SECONDS]
    if recent:
        _attempts[key] = recent
    else:
        _attempts.pop(key, None)
    return len(recent) >= LOCKOUT_ATTEMPTS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex(), digest.hex()


def _verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return hmac.compare_digest(digest.hex(), hash_hex)


def _orgs_for(user_id: str) -> list[dict]:
    return db.rows(
        "SELECT o.id, o.name, m.role FROM org_members m "
        "JOIN orgs o ON o.id = m.org_id WHERE m.user_id = ? ORDER BY o.name",
        (user_id,),
    )


def _new_session(user_id: str, org_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()
    db.run(
        "INSERT INTO sessions (id, user_id, org_id, expires_at, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (token, user_id, org_id, expires, _now()),
    )
    return token


def _payload(token: str, user: dict, org: dict, role: str) -> dict:
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"]},
        "org": {"id": org["id"], "name": org["name"]},
        "role": role,
        "orgs": [{"id": o["id"], "name": o["name"], "role": o["role"]} for o in _orgs_for(user["id"])],
    }


def register(org_name: str, email: str, password: str) -> dict:
    org_name = (org_name or "").strip()
    email = (email or "").strip()
    if not org_name:
        raise HTTPException(400, "Organization name is required.")
    if not email or "@" not in email:
        raise HTTPException(400, "Enter a valid email address.")
    if len(password or "") < PASSWORD_MIN:
        raise HTTPException(400, f"Password must be at least {PASSWORD_MIN} characters.")

    org_id, user_id = uuid4().hex, uuid4().hex
    salt, digest = _hash_password(password)
    statements = [
        ("INSERT INTO orgs (id, name, created_at) VALUES (?, ?, ?)", (org_id, org_name, _now())),
        ("INSERT INTO users (id, email, pass_salt, pass_hash, created_at) VALUES (?, ?, ?, ?, ?)",
         (user_id, email, salt, digest, _now())),
        ("INSERT INTO org_members (org_id, user_id, role) VALUES (?, ?, ?)", (org_id, user_id, "ADMIN")),
    ]
    try:
        db.runs(statements)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "That email is already registered. Sign in instead.") from None

    token = _new_session(user_id, org_id)
    user = db.row("SELECT id, email FROM users WHERE id = ?", (user_id,))
    org = db.row("SELECT id, name FROM orgs WHERE id = ?", (org_id,))
    return _payload(token, user, org, "ADMIN")


def login(email: str, password: str, client: str = "") -> dict:
    email = (email or "").strip()
    key = f"{email.lower()}|{client}"
    if _locked_out(key):
        raise HTTPException(429, "Too many failed sign-in attempts. Wait a minute and try again.")
    user = db.row("SELECT * FROM users WHERE email = ?", (email,))
    if not user or not _verify_password(password or "", user["pass_salt"], user["pass_hash"]):
        _attempts.setdefault(key, []).append(time.monotonic())
        raise HTTPException(401, "Email or password is incorrect.")
    _attempts.pop(key, None)
    orgs = _orgs_for(user["id"])
    if not orgs:
        raise HTTPException(403, "This account has no organizations. Ask an admin to add you.")
    org = db.row("SELECT id, name FROM orgs WHERE id = ?", (orgs[0]["id"],))
    token = _new_session(user["id"], org["id"])
    return _payload(token, user, org, orgs[0]["role"])


def switch_org(token: str, org_id: str) -> dict:
    session = db.row("SELECT * FROM sessions WHERE id = ? AND expires_at > ?", (token, _now()))
    if not session:
        raise HTTPException(401, "Session expired. Sign in again.")
    membership = db.row(
        "SELECT role FROM org_members WHERE user_id = ? AND org_id = ?",
        (session["user_id"], org_id),
    )
    if not membership:
        raise HTTPException(403, "You are not a member of that organization.")
    org = db.row("SELECT id, name FROM orgs WHERE id = ?", (org_id,))
    user = db.row("SELECT id, email FROM users WHERE id = ?", (session["user_id"],))
    new_token = _new_session(session["user_id"], org_id)
    return _payload(new_token, user, org, membership["role"])


def change_password(ctx: dict, current: str, new: str) -> None:
    """Rotate the signed-in user's password and revoke their other sessions."""
    user = db.row("SELECT pass_salt, pass_hash FROM users WHERE id = ?", (ctx["user_id"],))
    if not user or not _verify_password(current or "", user["pass_salt"], user["pass_hash"]):
        raise HTTPException(401, "Current password is incorrect.")
    if len(new or "") < PASSWORD_MIN:
        raise HTTPException(400, f"Password must be at least {PASSWORD_MIN} characters.")
    salt, digest = _hash_password(new)
    db.runs([
        ("UPDATE users SET pass_salt = ?, pass_hash = ? WHERE id = ?", (salt, digest, ctx["user_id"])),
        ("DELETE FROM sessions WHERE user_id = ? AND id <> ?", (ctx["user_id"], ctx["token"])),
    ])


def logout(token: str) -> None:
    """Revoke the current session token (server-side logout)."""
    if token:
        db.run("DELETE FROM sessions WHERE id = ?", (token,))


def authorize(request: Request) -> dict:
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    session = db.row("SELECT * FROM sessions WHERE id = ? AND expires_at > ?", (token, _now()))
    if not session:
        raise HTTPException(401, "Session expired. Sign in again.")
    user = db.row("SELECT id, email FROM users WHERE id = ?", (session["user_id"],))
    membership = db.row(
        "SELECT role FROM org_members WHERE user_id = ? AND org_id = ?",
        (session["user_id"], session["org_id"]),
    )
    if not user or not membership:
        raise HTTPException(401, "Session expired. Sign in again.")
    return {"token": token, "user_id": user["id"], "org_id": session["org_id"], "role": membership["role"]}