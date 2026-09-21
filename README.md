# SCREENOS — Fair & Evidence-Based Recruiter Workspace

SCREENOS is an AI-assisted candidate screening workspace designed for non-technical recruiters. It automates repetitive first-pass resume evaluation while enforcing strict anti-bias, anti-prompt-injection guardrails, and requiring verifiable evidence quotes from the candidate's CV.

> **Current Milestone: Day 5 handoff delivered, two-week plan underway**  
> Ingestion, PII redaction, evidence-backed scorecards and the 10-sample evaluation suite were delivered on Day 5. Since then the workspace has grown into a multi-tenant service: organizations, roles and sessions; per-organization LLM keys (bring your own key) across seven providers; a React workspace; bulk ZIP intake; calibration analytics; and a compliance export. 58 automated tests and a CI build cover it.

### 📚 Official Sprint Deliverables
1. **Working System:** Reproducible local repository with 3-step setup (see below).
2. **Evaluation Package:** [docs/evaluation_package.md](docs/evaluation_package.md) (10 test cases, baseline comparison, RCA).
3. **Case Study:** [docs/case_study.md](docs/case_study.md) (User, bottleneck, architecture, trade-offs, HITL, roadmap).
4. **AI Collaboration Note:** [docs/ai_collaboration.md](docs/ai_collaboration.md) (Tools used, verified results, rejected outputs, owned decisions).
5. **Operator Runbook:** [docs/runbook.md](docs/runbook.md) (3-step setup, recruiter operation, rubric customization).
6. **Demo Video Script:** [docs/demo_script.md](docs/demo_script.md) (Timestamped 5-minute walkthrough).

---

## 🚀 Quickstart — Local (3 steps) or VPS (1 command)

### Local — for HR on Windows/Mac
**1. Setup**
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
**2. (Optional) AI key** — skip if using Ollama local. Otherwise copy `.env.example` to `.env` and add one key (fallback). Better: add per-org keys later under **Settings → AI Provider Keys** (encrypted, no env needed).
```ini
DEEPSEEK_API_KEY=sk-your-key
LLM_PROVIDER=deepseek,gemini
```
**3. Run**
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open **`http://127.0.0.1:8000`** → Help & Guide has the 4-step HR walkthrough.

### VPS / Docker — same code, one command
```bash
cp .env.example .env   # then edit SCREENOS_ALLOWED_HOSTS=yourdomain.com
# Optional: generate BYOK encryption key for cloud
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # paste as SCREENOS_CRED_KEY
docker compose up --build -d
# Open http://YOUR_VPS_IP:8000  (or behind Nginx/Caddy for HTTPS)
```
- `Dockerfile` + `docker-compose.yml` included — no manual venv on server. `data/` persists SQLite + encrypted keys.
- `SCREENOS_ALLOWED_HOSTS` = your domain/IP (comma sep). `SCREENOS_CRED_KEY` = strong random for BYOK at rest.
- Frontend already built (`app/static/build`); backend serves API + UI on same port.

---

## 🏗️ Architecture & Pipeline

```
Resume Upload (PDF / DOCX / TXT)
   │
   ▼
[app/extractor.py] ────────── Extract clean text from files (up to 10 MB)
   │
   ▼
[app/guardrails.py] ───────── Redact PII (Name, Address, Grad Year, Contact) + Document SHA-256
   │
   ▼
[Anti-Injection Wrapper] ──── Wrap candidate text in safe <candidate_data> delimiters
   │
   ▼
[app/scorer.py] ───────────── Compare candidate against job rubric via LLM transport
   │
   ▼
[app/schemas.py] ──────────── Validate strictly via Pydantic (Exact Quotes + Arithmetic check)
   │
   ▼
[app/main.py & Web UI] ────── Display Evidence Card (Human Recruiter clicks Approve / Reject)
```

---

## 🛡️ Core Guardrails

1. **PII Redaction & Document Hash:** Removes candidate names, contact details, addresses, and graduation years before model evaluation. Generates a deterministic SHA-256 document identifier for auditing.
2. **Anti-Prompt-Injection Boundary:** CV text is treated as untrusted data inside `<candidate_data>` tags and escaped against delimiter attacks.
3. **Verbatim Evidence Requirement:** Every positive point awarded requires an exact, word-for-word quote from the resume. Scores without matching textual evidence fail validation.
4. **Human-in-the-Loop:** The system produces evidence and suggestions; a human recruiter retains 100% final authority to Approve or Reject.

---

## 🧪 Testing & Verification

Run the full automated test suite:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Test extraction benchmarks:
```powershell
.\.venv\Scripts\python.exe scripts/measure_extraction.py
```

---

## 📁 Repository Structure

```
SCREENOS/
├── app/
│   ├── main.py             # FastAPI routes for the workspace API
│   ├── db.py               # SQLite persistence
│   ├── auth.py             # Sign-up, sessions, password rotation
│   ├── reviews.py          # Review persistence
│   ├── extractor.py        # Text extraction from PDF/DOCX/TXT
│   ├── guardrails.py       # PII removal, document hashing & escaping
│   ├── scorer.py           # Rubric loading and scoring orchestration
│   ├── schemas.py          # Strict Pydantic models for scorecards
│   ├── providers.py        # Provider catalog and failover
│   ├── credentials.py      # Per-organization provider keys
│   ├── deepseek.py         # DeepSeek transport
│   ├── gemini.py           # Gemini transport
│   ├── anthropic.py        # Anthropic transport
│   ├── openai_compat.py    # OpenAI, Groq, OpenRouter and Ollama transport
│   ├── commandcode.py      # Owner's personal transport
│   ├── rubrics.py          # Rubric registry
│   ├── batch.py            # Bulk ZIP intake
│   ├── calibration.py      # AI vs human disagreement
│   ├── compliance.py       # Audit summary and CSV export
│   ├── orgs.py             # Organization profile settings
│   ├── team.py             # Members and roles
│   └── static/             # Built workspace assets
├── frontend/               # React + Vite + Tailwind workspace
├── rubrics/                # One 100-point rubric per job id
├── samples/
│   └── cvs/                # Test resumes (strong, partial, edge cases)
├── tests/                  # 58 automated tests
├── docs/                   # Benchmarks, case study, runbook
├── .github/workflows/      # CI: Python tests and frontend build
├── requirements.txt        # Python dependencies
└── README.md
```
