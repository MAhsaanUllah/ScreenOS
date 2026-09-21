"""SQLite persistence. Single local file; swapped for Postgres when self-hosted.

Reads SCREENOS_DB env override so tests use a temp database.
"""
import os
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "screenos.db"

_lock = threading.Lock()
_init = threading.Lock()
_ready = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  pass_salt TEXT NOT NULL,
  pass_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS org_members (
  org_id TEXT NOT NULL REFERENCES orgs(id),
  user_id TEXT NOT NULL REFERENCES users(id),
  role TEXT NOT NULL,
  PRIMARY KEY (org_id, user_id)
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  org_id TEXT NOT NULL REFERENCES orgs(id),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  created_by TEXT NOT NULL REFERENCES users(id),
  candidate_hash TEXT NOT NULL,
  cleaned_text TEXT NOT NULL,
  candidate_data TEXT NOT NULL,
  card TEXT,
  decision TEXT,
  reviewer_notes TEXT,
  decided_at TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reviews_org ON reviews(org_id, created_at);

CREATE TABLE IF NOT EXISTS org_credentials (
  org_id TEXT NOT NULL REFERENCES orgs(id),
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  api_key TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (org_id, provider)
);

CREATE TABLE IF NOT EXISTS org_pii_rules (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  type TEXT NOT NULL,
  value TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pii_org ON org_pii_rules(org_id);
"""


def path() -> str:
    return os.environ.get("SCREENOS_DB") or str(DB_PATH)


def connect() -> sqlite3.Connection:
    path_value = path()
    Path(path_value).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path_value)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    if path_value not in _ready:
        with _init:
            if path_value not in _ready:
                con.executescript(SCHEMA)
                _ready.add(path_value)
    return con


def rows(sql: str, params=()) -> list[dict]:
    with _lock:
        con = connect()
        try:
            return [dict(r) for r in con.execute(sql, params).fetchall()]
        finally:
            con.close()


def row(sql: str, params=()) -> dict | None:
    result = rows(sql, params)
    return result[0] if result else None


def run(sql: str, params=()) -> None:
    with _lock:
        con = connect()
        try:
            con.execute(sql, params)
            con.commit()
        finally:
            con.close()


def runs(statements: list[tuple[str, tuple]]) -> None:
    with _lock:
        con = connect()
        try:
            for sql, params in statements:
                con.execute(sql, params)
            con.commit()
        finally:
            con.close()