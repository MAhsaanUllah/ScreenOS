# 🤖 AI Collaboration Note

> **Author:** Candidate (Muhammad Ahsaan Ullah)  
> **Project:** SCREENOS (Fair & Evidence-Based Recruiter Workspace)  
> **Date:** 7 September 2026

---

## 1. AI Tools Used & Roles

| AI Tool | Role & Responsibility |
|---|---|
| **Google Antigravity IDE** | Lead Architecture Planning, Mentor Persona Guidance, Codebase Auditing, Documentation & Git Hygiene. |
| **OpenAI Codex / CLI** | Fast code scaffolding, multi-provider failover implementation, and adversarial test expansion. |
| **DeepSeek (V4 Flash) & Gemini (3.8 Flash)** | Production LLM inference engines used for candidate-rubric evaluation and evidence extraction. |

---

## 2. Work Delegated to AI

* **Boilerplate & Plumbing:** Generation of initial REST client wrappers (`urllib.request`), FastAPI routing scaffolds, and static HTML/CSS layout templates.
* **Test Suite Expansion:** Writing parametrized unit tests for edge cases (empty files, BOM headers, missing fields, rate-limit retries).
* **Regex Pattern Scaffolding:** Drafting initial regular expression patterns for email, address, and graduation year redaction in `app/guardrails.py`.
* **Benchmark Script Automation:** Generating execution timer scripts (`scripts/measure_extraction.py`, `scripts/evaluate_samples.py`).

---

## 3. How AI-Generated Results Were Verified

To prevent AI hallucinations and errors from entering the codebase:
1. **Deterministic Schema Verification:** Every model output is passed through strict Pydantic v2 validation (`app/schemas.py`). Model-generated scores must match arithmetic rules exactly.
2. **Verbatim Text Anchoring:** Model quotes are string-verified against the original cleaned resume text. Any invented quote triggers immediate validation failure.
3. **Automated Test Suite:** A suite of **23 automated unit and integration tests** (`tests/`) runs before any milestone commit.
4. **Offline Mock Pipeline:** Developed offline baselines to test system plumbing without depending on model availability.

---

## 4. Key AI Outputs Rejected or Manually Corrected

* **Rejected Single-Provider Hardcoding:** Early AI generation hardcoded a single provider import (`from app.deepseek import complete`). This was rejected and refactored into a resilient multi-provider router (`app/providers.py`) with automatic failover to Google Gemini upon rate-limiting.
* **Corrected Prompt Injection Handling:** Rejected weak prompt instructions that assumed models would naturally ignore injected instructions. Replaced with strict XML `<candidate_data>` wrapping and HTML character escaping to physically prevent delimiter breakouts.
* **Purged Internal Prompt Slop from Git History:** Identified that early iterations tracked internal AI prompt files (`MENTOR.md`, `PROJECT_DETAILS.md`). Rebuilt Git history from scratch with clean Conventional Commits to ensure production-grade repository hygiene.

---

## 5. Core Decisions Personally Owned by the Candidate

1. **Problem Definition & Scope:** Decided to solve the initial recruiter bottleneck ("evidence-based first pass") rather than over-engineering an unverified full ATS platform.
2. **The 4 Guardrails Architecture:** Conceived and enforced the 4 foundational guardrails: PII Stripping, Anti-Prompt-Injection Boundary, Verbatim Evidence Requirement, and Mandatory Human-in-the-Loop Decision.
3. **Evaluation Strategy:** Designed the 10 representative, edge-case, and adversarial sample CVs (`samples/cvs/`) to evaluate real edge cases (career changers, claims without proof, delimiter breakouts, and prompt injections).
4. **Honest Quality Reporting:** Documented the real 50% live model agreement variance in `docs/day4_results.md` instead of faking 100% precision.
