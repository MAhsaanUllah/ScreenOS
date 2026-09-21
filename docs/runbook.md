# 📖 SCREENOS — Operator Runbook & Handoff Guide

> **Target Audience:** Non-technical Recruiters, Hiring Managers, and Operations Leads  
> **System Scope:** Local, high-trust candidate review workspace with verifiable evidence quotes and human-in-the-loop decision authority.

---

## 🚀 1. Quickstart — Local (3 steps) or VPS (1 command)

### Prerequisites
* Windows/macOS/Linux + Python 3.11+. API key optional — use Ollama local with no key.

### Local (HR laptop) — 3 steps
**Step 1: Install**
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
**Step 2: (Optional) API key**
Copy `.env.example` → `.env`. Skip if using **Ollama (local)** in Settings. Otherwise add one fallback key:
```ini
DEEPSEEK_API_KEY=sk-your-key
LLM_PROVIDER=deepseek,gemini
```
Better: add per-org keys later under **Settings → AI Provider Keys** (encrypted, no env needed).
**Step 3: Run**
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open **`http://127.0.0.1:8000`** → **Help & Guide** in the sidebar has the 4-step HR flow.

### VPS / Production — 1 command (Docker)
```bash
cp .env.example .env
# edit .env: set SCREENOS_ALLOWED_HOSTS=yourdomain.com (or VPS_IP)
# optional: paste SCREENOS_CRED_KEY from: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
docker compose up --build -d
# Open http://YOUR_VPS_IP:8000  (add Nginx/Caddy for HTTPS → HSTS auto-enabled)
```
- Same backend serves API + UI on `:8000`. `data/` volume persists SQLite + encrypted BYOK.
- `SCREENOS_CRED_KEY` encrypts per-org keys at rest; leave empty locally (auto `data/.cred_key`).

### Step 4 (optional): Load demo data
To explore the workspace without typing a CV in, seed a demo organization:
```powershell
.\.venv\Scripts\python.exe scripts/seed_demo.py
```
It signs you in as **`demo@screenos.local` / `demo12345`** with four already-scored candidates. These credentials are for local demo data only — never reuse them on a reachable deployment.

---

## 🧑‍💻 2. Daily Recruiter Workflow (How to Screen a Candidate)

```
1. Select Resume ──> 2. Redact Identity ──> 3. Inspect Preview ──> 4. Generate Scorecard ──> 5. Approve / Reject
```

### Step-by-Step Operator Guide:
1. **Upload Resume:** Drag and drop or browse for a PDF, DOCX, or UTF-8 TXT resume (up to 10 MB).
2. **Enter Candidate Name:** Type the candidate's name in the full name box. This instructs the guardrail system to redact all name occurrences to prevent demographic bias.
3. **Optional Additional Redaction:** Expand *"Additional Identity Redaction"* to strip specific addresses or graduation years if needed.
4. **Click "Prepare & Clean Resume":** The system extracts plaintext and displays a sanitized, audit-ready version in the preview box.
5. **Inspect & Authorize:** Review the sanitized text, check the consent checkbox, and click **"Score Candidate with AI Scorer"**.
6. **Review the Evidence Card:**
   * Look at the overall score (out of 100) and verdict (`STRONG_MATCH`, `POSSIBLE_MATCH`, `WEAK_MATCH`).
   * Review the monospace quote block under each requirement. Verify that the quote demonstrates delivered project work.
7. **Record Decision:** Add recruiter notes (optional) and click **Approve (Interview)** or **Reject**.
   * *Keyboard shortcuts:* Press `Enter` (or `a`) to Approve; press `Esc` (or `r`) to Reject.
8. **Export Audit Trail:** Click **"Download Review JSON"** to save the immutable decision record for ATS import or compliance audit.

---

## ⚙️ 3. How to Customize the Job Rubric (No Coding Required)

All job requirements are defined in plain Markdown in **`rubrics/<job_id>.md`**.

To customize the requirements for a new job opening:
1. Open `rubrics/<job_id>.md` in any text editor (Notepad, VS Code).
2. Edit the criteria, weights, and evidence descriptions in the table:

```markdown
| Requirement | Points | Evidence to look for |
| --- | ---: | --- |
| Build AI tools or automated workflows | 30 | Delivered production workflows, agents, or LLM pipelines |
| Build Python services with FastAPI | 20 | Working backend services with validation and clean APIs |
| Answer questions using documents and source quotes | 20 | RAG pipelines with verifiable citations |
| Design databases with separate customer access | 15 | Multi-tenant schema design, RLS, or access controls |
| Test and release working software | 15 | Automated test suites, CI/CD, and monitoring |
```

> [!IMPORTANT]
> **Rubric Rules:**
> 1. Points across all requirements **must total exactly 100**.
> 2. Requirement names must be unique.
> 3. The scoring engine automatically detects table changes on the next evaluation run.

---

## 🛠️ 4. Operator Troubleshooting & Error Handling

| Scenario / Error Message | Root Cause | Operator Action |
|---|---|---|
| *"A PDF page has no readable text"* | The resume is an image-only scan without selectable text. | Request a text-based PDF, Word (`.docx`), or plaintext (`.txt`) file from the candidate. |
| *"File exceeds 10 MB"* | Resume file size is too large. | Compress the document or save as standard PDF before uploading. |
| *"Scoring is temporarily unavailable"* | Configured AI provider reached rate limits or network timeout. | Wait 30 seconds and click Score again. The candidate preview text is preserved safely. |
| *"Candidate name is required"* | Name input was left empty. | Enter the candidate name so PII redaction can execute before model submission. |

---

## 🔒 5. Data Privacy & Compliance Safeguards

* **Local Data Boundary:** The server binds strictly to `127.0.0.1` (loopback). No unencrypted external endpoints are exposed.
* **Zero PII Logging:** Resumes and candidate names are never written to logs. The redacted text and the final human decision live in the local SQLite database (`data/screenos.db`), scoped to the organization.
* **Regulatory Alignment:** Satisfies NYC Local Law 144 and EU AI Act requirements by enforcing human authority over all hiring decisions.

---

## 🧩 6. Providers, Bulk Intake & Compliance Export

### Bring your own key
Each organization stores its own provider key under **Settings**. Supported providers: DeepSeek, Google Gemini, Anthropic, OpenAI, Groq, OpenRouter, and a local Ollama model (which needs no key). Keys are saved by an administrator, are never shown again after saving (only the last four characters), and a second key acts as an automatic fallback when the first one fails. If an organization has no key at all, scoring replies with a message telling the admin to add one.

### Bulk intake
Upload a ZIP of resumes (up to 50 files, 10 MB each) from the screening screen. The server extracts, redacts and stores one review per file. A bulk upload has no per-candidate name field, so the name is derived from the file name — **check each derived name and correct it before scoring.**

### Compliance export
**Settings → Export compliance report** downloads the organization's audit summary: candidate counts, decisions, verdicts and the guardrails in force. For filing alongside it, `GET /api/compliance.csv` returns the per-candidate records as CSV.
