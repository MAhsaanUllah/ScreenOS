# SCREENOS: Assessment Alignment & Acceptance Checklist

## 1. Scope & Status (Day 5 Milestone — Submission Ready)

SCREENOS is built according to the authoritative 5-day assessment brief. It solves the operational screening bottleneck for non-technical recruiters through an evidence-first, bias-free, and injection-resistant architecture.

### Current Implementation State (100% Complete):
* **Text Extraction (Day 1):** Ingests PDF, DOCX, and TXT files with size validation and corrupt/blank page rejection.
* **PII Redaction & Guardrails (Day 2):** Strips names, locations, contact info, and education years; generates deterministic SHA-256 document IDs.
* **Anti-Injection (Day 2):** XML-delimited `<candidate_data>` wrapping with HTML-escaping to prevent prompt breakout attacks.
* **Structured Schemas (Day 2):** Strict Pydantic models verifying exact verbatim quotes, points arithmetic, and verdict categories.
* **Multi-Provider Failover (Day 3):** Resilient routing across DeepSeek, Gemini, and CommandCode with automatic rate-limit recovery.
* **Full Evaluation & Adversarial Hardening (Day 4):** 23/23 tests passed, prompt injection neutralization verified, and Root Cause Analysis documented.
* **Handoff & Submission Packaging (Day 5):** Operator runbook (`docs/runbook.md`), case study (`docs/case_study.md`), AI collaboration note (`docs/ai_collaboration.md`), and 5-min demo video script (`docs/demo_script.md`).

---

## 2. Acceptance Checklist

### Day 1 (Problem & Ingestion) — Completed:
- [x] Defined target user (recruiter) and job-to-be-done.
- [x] Implemented file ingestion pipeline for PDF, DOCX, TXT (`app/extractor.py`).
- [x] Created baseline extraction benchmark (`docs/day1_results.md`).
- [x] Defined 100-point customizable job rubric (`rubrics/rubric.md`).

### Day 2 (Safety, Schemas & v0) — Completed:
- [x] Implemented PII sanitization and anti-injection wrapper (`app/guardrails.py`).
- [x] Defined strict JSON data contract and validation (`app/schemas.py`).
- [x] Shipped working v0: Tested end-to-end extraction -> sanitization -> LLM scoring -> evidence card.
- [x] Built local recruiter workspace with human decision capture (`app/main.py`, `app/static/`).

### Day 3 (Working Core & Reliability) — Completed:
- [x] Built multi-provider failover routing (`app/providers.py`).
- [x] Added recruiter-friendly downtime handling (HTTP 503 preserving candidate preview).
- [x] Automated unit and integration tests for failover recovery.

### Day 4 (Evaluate, Break & Harden) — Completed:
- [x] Built automated 6-sample evaluation runner (`scripts/evaluate_samples.py`).
- [x] Executed and recorded offline baseline (7–30ms) vs live AI evaluation (15–36s) in `docs/day4_results.md`.
- [x] Verified 100% prompt injection defense on adversarial sample (`06_instructions.pdf`).
- [x] Documented Root Cause Analysis (RCA) on 3 failure modes with before-and-after safeguards.

### Day 5 (Handoff, Case Study & Packaging) — Completed:
- [x] 3-step setup guide and operator runbook (`docs/runbook.md`).
- [x] Portfolio-ready case study (`docs/case_study.md`).
- [x] Official AI Collaboration Note (`docs/ai_collaboration.md`).
- [x] 5-minute video demo script with exact timestamps (`docs/demo_script.md`).
- [x] Clean, conventional Git commit history without prompt leakage.
