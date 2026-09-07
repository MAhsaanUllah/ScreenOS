# 📖 SCREENOS — Operator Runbook & Handoff Guide

> **Target Audience:** Non-technical Recruiters, Hiring Managers, and Operations Leads  
> **System Scope:** Local, high-trust candidate review workspace with verifiable evidence quotes and human-in-the-loop decision authority.

---

## 🚀 1. Three-Step Quickstart (Setup & Launch)

### Prerequisites
* Windows, macOS, or Linux with Python 3.11+ installed.
* API key for at least one supported provider: **DeepSeek** (default) or **Google Gemini**.

### Step 1: Install Dependencies
Open PowerShell or your terminal in the project root:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Step 2: Configure API Key
Create a `.env` file in the root folder (or copy `.env.example`):
```ini
# Primary Provider
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
DEEPSEEK_MODEL=deepseek-v4-flash

# Optional Backup Provider (for automatic failover)
GEMINI_API_KEY=your-gemini-key-here
GEMINI_MODEL=gemini-3.8-flash

# Failover Routing Order
LLM_PROVIDER=deepseek,gemini
```

### Step 3: Start the Local Workspace
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser and navigate to: **`http://127.0.0.1:8000`**

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

All job requirements are defined in plain Markdown in **`rubrics/rubric.md`**.

To customize the requirements for a new job opening:
1. Open `rubrics/rubric.md` in any text editor (Notepad, VS Code).
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
* **Zero PII Logging:** Resumes and candidate names are never written to disk during extraction. Only final human decisions are saved to `output/<token>.json`.
* **Regulatory Alignment:** Satisfies NYC Local Law 144 and EU AI Act requirements by enforcing human authority over all hiring decisions.
