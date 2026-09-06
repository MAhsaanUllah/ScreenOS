# SCREENOS: Assessment Alignment & Acceptance Checklist

## 1. Scope & Status (Day 2 Milestone)

SCREENOS is built according to the 5-day assessment framework. The project focuses on solving the initial candidate screening bottleneck for non-technical recruiters.

### Current Implementation State (Day 2 Complete):
* **Text Extraction:** Ingests PDF, DOCX, and TXT files with size and formatting validation.
* **PII Redaction & Guardrails:** Strips names, locations, contact info, and education years; generates deterministic SHA-256 document IDs.
* **Anti-Injection:** XML-delimited `<candidate_data>` wrapping with HTML-escaping to prevent prompt breakout.
* **Structured Schemas:** Strict Pydantic models verifying exact verbatim quotes, points arithmetic, and verdict categories.
* **Model Transports:** Provider-agnostic connectors for DeepSeek, Gemini, and CommandCode.
* **Recruiter UI:** Local single-operator workspace with preview, evidence display, and human Approve/Reject actions.

---

## 2. Acceptance Checklist

### Day 1 & Day 2 (Completed):
- [x] Defined target user (recruiter) and job-to-be-done.
- [x] Implemented file ingestion pipeline for PDF, DOCX, TXT.
- [x] Created baseline extraction benchmark (`docs/day1_results.md`).
- [x] Implemented PII sanitization and anti-injection wrapper (`app/guardrails.py`).
- [x] Defined strict JSON data contract and validation (`app/schemas.py`).
- [x] Built provider-agnostic model transports (`app/deepseek.py`, `app/gemini.py`, `app/commandcode.py`).
- [x] Shipped working v0: Tested end-to-end extraction -> sanitization -> LLM scoring -> evidence card.
- [x] Built local recruiter workspace with human decision capture (`app/main.py`, `app/static/`).

### Day 3–5 Roadmap (Next Steps):
- [ ] Hardening model prompt and multi-provider reliability.
- [ ] Full evaluation across 8–12 representative and adversarial test cases.
- [ ] Side-by-side baseline vs. assisted speed and quality measurement.
- [ ] Failure mode analysis and regression safeguards.
- [ ] Operator runbook, final demo video, and submission packaging.

---

## 3. Execution Plan

1. **Day 3:** Core pipeline hardening & provider fallback handling.
2. **Day 4:** Adversarial evaluation (prompt injections, malformed CVs) and failure analysis.
3. **Day 5:** Final benchmark results, operator documentation, and demo packaging.
