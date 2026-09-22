"""SQLite persistence. Single local file; swapped for Postgres when self-hosted.

Reads SCREENOS_DB / DATABASE_URL env so tests use temp DB and VPS can use Postgres.
ponytail: Postgres path is thin — same SQL, psycopg if DATABASE_URL=postgres:// and driver present, else SQLite.
"""
import os
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "screenos.db"

_lock = threading.Lock()
_init = threading.Lock()
_ready = set()

# Postgres detection — stdlib first, driver later
_DATABASE_URL = os.environ.get("DATABASE_URL") or ""
_USE_PG = _DATABASE_URL.startswith("postgres")
try:
    import psycopg  # type: ignore
    from psycopg.rows import dict_row  # type: ignore
    _HAS_PG = True
except ImportError:
    psycopg = None  # type: ignore
    _HAS_PG = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  org_type TEXT NOT NULL DEFAULT 'internal'
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

CREATE TABLE IF NOT EXISTS login_attempts (
  id TEXT PRIMARY KEY,
  key TEXT NOT NULL,
  at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_key ON login_attempts(key, at);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES orgs(id),
  title TEXT NOT NULL,
  jd_text TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'DRAFT',
  rubric_json TEXT,
  rubric_approved INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_org ON jobs(org_id, created_at);
-- reviews.job_id added via migration (nullable for compat)
"""


def path() -> str:
    return os.environ.get("SCREENOS_DB") or str(DB_PATH)


def _is_pg() -> bool:
    url = os.environ.get("DATABASE_URL") or ""
    return url.startswith("postgres") and _HAS_PG


_pool = None  # type: ignore

def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    try:
        from psycopg_pool import ConnectionPool  # type: ignore
        _pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=5, kwargs={"row_factory": dict_row})  # type: ignore
        return _pool
    except ImportError:
        return None  # fallback to per-call connect


def _ensure_org_type(con, pg: bool) -> None:
    # ponytail: one ALTER per DB, ignore if column exists
    try:
        if pg:
            with con.cursor() as cur:
                cur.execute("ALTER TABLE orgs ADD COLUMN IF NOT EXISTS org_type TEXT DEFAULT 'internal'")
            con.commit()
        else:
            # SQLite: try add, ignore duplicate
            try:
                con.execute("ALTER TABLE orgs ADD COLUMN org_type TEXT DEFAULT 'internal'")
                con.commit()
            except Exception:
                pass
    except Exception:
        pass


def _ensure_jobs(con, pg: bool) -> None:
    # ponytail: add jobs table + reviews.job_id if missing (idempotent)
    try:
        if pg:
            with con.cursor() as cur:
                cur.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS job_id TEXT")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_job ON reviews(job_id)")
            con.commit()
        else:
            try:
                con.execute("ALTER TABLE reviews ADD COLUMN job_id TEXT")
                con.commit()
            except Exception:
                pass
            try:
                con.execute("CREATE INDEX IF NOT EXISTS idx_reviews_job ON reviews(job_id)")
                con.commit()
            except Exception:
                pass
            # ensure jobs table exists via SCHEMA (already CREATE IF NOT EXISTS)
            try:
                con.executescript("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, org_id TEXT NOT NULL, title TEXT NOT NULL, jd_text TEXT DEFAULT '', status TEXT DEFAULT 'DRAFT', rubric_json TEXT, rubric_approved INTEGER DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_jobs_org ON jobs(org_id, created_at);")
                con.commit()
            except Exception:
                pass
    except Exception:
        pass


def connect():
    if _is_pg():
        # ponytail: pool if psycopg_pool present, else per-call — add pool when VPS sees contention
        pool = _get_pool()
        if pool:
            con = pool.getconn()
            # wrapper to return to pool on close
            orig_close = con.close
            def _close():
                try:
                    pool.putconn(con)
                except Exception:
                    orig_close()
            con.close = _close  # type: ignore
            key = "pg:pool:" + os.environ["DATABASE_URL"]
            if key not in _ready:
                with _init:
                    if key not in _ready:
                        with con.cursor() as cur:
                            cur.execute(SCHEMA)
                        con.commit()
                        _ensure_org_type(con, True)
                        _ensure_jobs(con, True)
                        _ready.add(key)
            else:
                _ensure_org_type(con, True)
                _ensure_jobs(con, True)
            return con
        url = os.environ["DATABASE_URL"]
        con = psycopg.connect(url, row_factory=dict_row)  # type: ignore
        # ensure schema exists once per process (PG CREATE IF NOT EXISTS is safe)
        key = "pg:" + url
        if key not in _ready:
            with _init:
                if key not in _ready:
                    with con.cursor() as cur:
                        cur.execute(SCHEMA)
                    con.commit()
                    _ensure_org_type(con, True)
                    _ensure_jobs(con, True)
                    _ready.add(key)
        else:
            _ensure_org_type(con, True)
            _ensure_jobs(con, True)
        return con
    path_value = path()
    Path(path_value).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path_value)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    if path_value not in _ready:
        with _init:
            if path_value not in _ready:
                con.executescript(SCHEMA)
                _ensure_org_type(con, False)
                _ensure_jobs(con, False)
                _ready.add(path_value)
    else:
        # ensure existing DB gets new column (idempotent)
        _ensure_org_type(con, False)
        _ensure_jobs(con, False)
    return con


def _pg_sql(sql: str) -> str:
    return sql.replace("?", "%s") if _is_pg() else sql


def rows(sql: str, params=()) -> list[dict]:
    with _lock:
        con = connect()
        try:
            pg = _is_pg()
            q = _pg_sql(sql)
            if pg:
                with con.cursor() as cur:
                    cur.execute(q, params)
                    return cur.fetchall()  # type: ignore
            return [dict(r) for r in con.execute(q, params).fetchall()]
        finally:
            con.close()


def row(sql: str, params=()) -> dict | None:
    result = rows(sql, params)
    return result[0] if result else None


def run(sql: str, params=()) -> None:
    with _lock:
        con = connect()
        try:
            q = _pg_sql(sql)
            if _is_pg():
                with con.cursor() as cur:
                    cur.execute(q, params)
                con.commit()
            else:
                con.execute(q, params)
                con.commit()
        finally:
            con.close()


def runs(statements: list[tuple[str, tuple]]) -> None:
    with _lock:
        con = connect()
        try:
            pg = _is_pg()
            if pg:
                with con.cursor() as cur:
                    for sql, params in statements:
                        cur.execute(_pg_sql(sql), params)
                con.commit()
            else:
                for sql, params in statements:
                    con.execute(sql, params)
                con.commit()
        finally:
            con.close()