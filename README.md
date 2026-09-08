# SCREENOS — Fair & Evidence-Based Recruiter Workspace

SCREENOS is an AI-assisted candidate screening workspace designed for non-technical recruiters. It automates repetitive first-pass resume evaluation while enforcing strict anti-bias, anti-prompt-injection guardrails, and requiring verifiable evidence quotes from the candidate's CV.

> **Current Milestone: Day 5 (Handoff, Case Study & Submission Ready)**  
> Ingestion, PII redaction, structured scorecard schemas, provider failover (DeepSeek / Gemini / CommandCode), local recruiter workspace, full 10-sample evaluation suite with adversarial defense, operator runbook, AI collaboration note, and demo video script are fully verified and packaged.

### 📚 Official Sprint Deliverables
1. **Working System:** Reproducible local repository with 3-step setup (see below).
2. **Evaluation Package:** [docs/evaluation_package.md](docs/evaluation_package.md) (10 test cases, baseline comparison, RCA).
3. **Case Study:** [docs/case_study.md](docs/case_study.md) (User, bottleneck, architecture, trade-offs, HITL, roadmap).
4. **AI Collaboration Note:** [docs/ai_collaboration.md](docs/ai_collaboration.md) (Tools used, verified results, rejected outputs, owned decisions).
5. **Operator Runbook:** [docs/runbook.md](docs/runbook.md) (3-step setup, recruiter operation, rubric customization).
6. **Demo Video Script:** [docs/demo_script.md](docs/demo_script.md) (Timestamped 5-minute walkthrough).

---

## 🚀 Quickstart (3 Steps)

### 1. Setup Environment
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Configure API Key
Create a `.env` file in the root directory (see `.env.example`):
```ini
# DeepSeek (Default)
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-v4-flash

# Or Google Gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash

# Try DeepSeek first, then Gemini if it is unavailable or rate-limited
LLM_PROVIDER=deepseek,gemini
```

### 3. Launch the Recruiter Workspace
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open **`http://127.0.0.1:8000`** in your browser.

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
│   ├── extractor.py        # Text extraction from PDF/DOCX/TXT
│   ├── guardrails.py       # PII removal, document hashing & escaping
│   ├── schemas.py          # Strict Pydantic models for scorecards
│   ├── scorer.py           # Provider-agnostic scoring logic & prompt
│   ├── deepseek.py         # DeepSeek API transport
│   ├── gemini.py           # Gemini API transport
│   ├── commandcode.py      # CommandCode API transport
│   ├── main.py             # FastAPI backend & API routes
│   └── static/             # Recruiter web interface (HTML/CSS/JS)
├── rubrics/
│   └── rubric.md           # Customizable 100-point job requirement rubric
├── samples/
│   └── cvs/                # Test resumes (strong, partial, edge cases)
├── tests/                  # Unit and integration test suite
├── docs/                   # Benchmark results and architecture documentation
├── requirements.txt        # Python dependencies
└── README.md
```
