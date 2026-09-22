# SCREENOS

Open-source, self-hostable AI resume screening workspace for evidence-backed, human-reviewed hiring.

<p>
  <a href="https://github.com/MAhsaanUllah/ScreenOS/releases/tag/v1.0.0"><img src="https://img.shields.io/badge/Release-v1.0.0-blue?style=flat-square" alt="Release v1.0.0"></a>
  <a href="https://github.com/MAhsaanUllah/ScreenOS/blob/main/.github/workflows/tests.yml"><img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11"></a>
  <a href="https://github.com/MAhsaanUllah/ScreenOS/blob/main/frontend/package.json"><img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React 18"></a>
  <a href="https://github.com/MAhsaanUllah/ScreenOS/actions"><img src="https://img.shields.io/badge/Tests-80%20passing-brightgreen?style=flat-square" alt="Tests 80 passing"></a>
  <a href="https://github.com/MAhsaanUllah/ScreenOS/blob/main/Dockerfile"><img src="https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="https://github.com/MAhsaanUllah/ScreenOS#quick-start"><img src="https://img.shields.io/badge/Self--Hosted-yes-informational?style=flat-square" alt="Self-Hosted"></a>
</p>

<p align="center">
  <img src="screenshots/screenos-dashboard.png"
       alt="ScreenOS recruiter dashboard"
       width="100%">
</p>

## What is ScreenOS?

ScreenOS helps HR teams screen many CVs consistently without losing human control. Create a job, paste its description, generate an HR-approved 100-point rubric, then score 1–50 CVs against that same rubric with verbatim evidence from each CV.

## Why ScreenOS?

- **Job-specific screening** — Each job has its own approved rubric; bulk batches use the same rubric.
- **PII-aware** — Auto-detects name, email, phone, graduation year plus custom filters; recruiter confirms redactions before scoring.
- **Evidence-backed** — Every point requires an exact quote from the cleaned CV (`MET` full, `PARTIALLY_MET` half, `NOT_FOUND` zero).
- **Human-in-the-loop** — AI proposes scores and evidence; a human must Approve or Reject.
- **Bulk screening** — Drag & drop 1–50 CVs (PDF, DOCX, TXT, or ZIP).
- **BYOK** — Per-organization keys for DeepSeek, Gemini, Anthropic, OpenAI, Groq, OpenRouter, or local Ollama (no key). Keys are Fernet-encrypted; only `…last4` shown.
- **Self-hostable** — SQLite by default, Postgres via `DATABASE_URL`; `HttpOnly` sessions, `Fernet` at rest, tenant-isolated.
- **Team-ready** — Organizations, Admin/Recruiter roles, job-aware queue/analytics.

## How It Works

```
Create Job → Paste JD → Generate Draft Rubric → HR Review & Approve (100 pts) → Select Job
→ Upload CVs → PII Review → Redaction → Score against approved Job rubric
→ Criterion breakdown + verbatim evidence → Human Decision → Job-aware Queue/Analytics → Export
```

Detailed pipeline: `extractor` (10 MB) → `guardrails` (PII + `<candidate_data>` boundary) → `scorer` (LLM) → `schemas` (quote + arithmetic) → `Queue/Analytics`.

## Quick Start

### Local — 3 steps
**1. Setup**
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
**2. (Optional) AI key** — Skip if using Ollama. Otherwise copy `.env.example` → `.env`:
```ini
DEEPSEEK_API_KEY=sk-your-key
LLM_PROVIDER=deepseek,gemini
```
Or add per-org keys later in **Settings → AI Provider Keys** (encrypted).

**3. Run**
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open `http://127.0.0.1:8000` → *Help & Guide* has the 4-step walkthrough. Or `http://localhost:5174` for Vite dev (`/api` proxy to 8000).

Optional demo data:
```powershell
.\.venv\Scripts\python.exe scripts/seed_demo.py
# login demo@screenos.local / demo12345 (local demo only)
```

### VPS / Docker — 1 command
```bash
cp .env.example .env   # edit SCREENOS_ALLOWED_HOSTS=yourdomain.com
# Optional: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" # → SCREENOS_CRED_KEY
docker compose up --build -d
# Open http://YOUR_VPS_IP:8000 (behind Caddy/Nginx for HTTPS → HSTS auto)
```
`data/` persists SQLite + keys. `SCREENOS_CRED_KEY` encrypts BYOK at rest.

## Supported AI Providers

DeepSeek (default), Gemini, Anthropic, OpenAI, Groq, OpenRouter, Ollama local (`needs_key: false`). Configure per-organization in **Settings** or fallback via `.env` `LLM_PROVIDER=deepseek,gemini`.

## Privacy & Security

- **PII-aware** — Names, emails, phones, graduation years auto-detected via regex; custom `location`/`university` filters in **HR Controls**; all selected PII replaced with `[NAME REMOVED]`/`[REDACTED]` before scoring.
- **Untrusted boundary** — CV text is escaped (`html.escape`) inside `<candidate_data>` and treated as data via system prompt; not instructions.
- **Evidence validation** — Pydantic strict, `evidence_quote in cleaned_text`, sum `points == 100`, verdict `≥75 STRONG`/`≥50 POSSIBLE`/else `WEAK`.
- **Tenant isolation** — Every `reviews/credentials/pii/jobs` query is `WHERE org_id = ?` (verified cross-org 404).
- **BYOK encryption** — Fernet `SCREENOS_CRED_KEY` or auto `data/.cred_key`; `GET /settings/llm` returns `…last4` only.
- **Human final decision** — `POST /decision` `APPROVE/REJECT` separate from `card`; AI cannot auto-decide.

Not claimed: bias-free, prompt-injection proof, guaranteed fair hiring.

## Scoring Philosophy

> A ScreenOS score is the percentage of the HR-approved job rubric supported by evidence found in the CV.

It is **not** a probability of success, quality score, or hiring recommendation. Rubric total must be **exactly 100** before approval; historical `reviews.card` JSON is immutable.

## Self Hosting

- **Default:** `data/screenos.db` SQLite, `127.0.0.1:8000`.
- **Postgres (optional):** `DATABASE_URL=postgresql://user:pass@host/db` + `pip install psycopg[binary]` → `?`→`%s` + `psycopg_pool` if present.
- **Backups:** `python scripts/backup.py` → `backups/<ts>/` (DB + `rubrics/archive`).
- **Reverse proxy:** `Caddyfile.example` → `reverse_proxy 127.0.0.1:8000`.

## Tech Stack

FastAPI 0.141 + Pydantic 2.13, SQLite/Postgres, React 18 + Vite 5 + Tailwind, pdfplumber + python-docx, `urllib.request` (no heavy SDKs), `cryptography` Fernet. CI: Python 3.11 + Node 20 (`tests.yml`).

## Current V1 Scope

V1 does: job creation (`title` + JD), AI draft rubric (BYOK), HR edit/approve (100 pts), job-aware upload & scoring (1–50, same rubric), PII review, evidence scorecards, human decision, job-aware queue/analytics, CSV/JSON export, team & BYOK, self-host. Legacy reviews (`job_id NULL`) remain readable as *Legacy*.

## Limitations

- Manual CV ingestion (PDF/DOCX/TXT/ZIP) in V1; no job-board/ATS sync.
- Image-only scanned PDFs are rejected with guidance; OCR via `pytesseract` is optional.
- Human review is required for every scorecard.

## Testing

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# 80 tests — extraction, PII, scoring, evidence, BYOK, bulk, Jobs, rubrics, tenant isolation
```

## Repository Structure

```
SCREENOS/
├── app/
│   ├── main.py             # FastAPI routes
│   ├── db.py               # SQLite/Postgres, jobs + reviews.job_id
│   ├── auth.py             # PBKDF2, sessions (HttpOnly), lockout
│   ├── jobs.py             # Job openings + rubric draft/approve
│   ├── extractor.py        # PDF/DOCX/TXT 10 MB
│   ├── guardrails.py       # PII + <candidate_data> boundary
│   ├── scorer.py           # LLM + evidence validation
│   ├── schemas.py          # Strict scorecard models
│   ├── providers.py        # 7 providers + failover
│   ├── credentials.py      # Per-org keys (Fernet)
│   ├── rubrics.py          # Global rubric + archive
│   ├── batch.py            # Bulk intake (ZIP/direct)
│   ├── calibration.py      # Disagreement analytics
│   ├── compliance.py       # Audit + CSV (filters)
│   ├── pii_rules.py        # Custom PII per org
│   └── static/build/       # Vite build
├── frontend/               # React + Vite
├── rubrics/                # ai-engineer.md + archive/
├── samples/cvs/            # Synthetic fixtures (no real PII)
├── tests/                  # Automated tests
├── scripts/backup.py       # Tiny backup
├── Dockerfile / docker-compose.yml / Caddyfile.example
└── README.md
```

## Maintainer

**Muhammad Ahsaan Ullah** — Creator & Maintainer  
🔗 [GitHub](https://github.com/MAhsaanUllah) · [Email](mailto:dev.ahsaan@gmail.com)
