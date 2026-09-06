# SCREENOS: Case Study & Problem Analysis

## 1. Executive Summary & Problem Scope

In modern technical recruiting, recruiters face overwhelming application volumes. Reviewing hundreds of resumes per role manually leads to:
* **Severe Time Bottlenecks:** Manual screening takes hours of repetitive reading to locate relevant qualifications.
* **Reviewer Fatigue & Inconsistency:** Fatigue causes human reviewers to rely on heuristics or miss key qualifications.
* **Demographic Bias:** Unconscious bias based on candidate names, locations, or graduation years often skews early screening.

**SCREENOS** is built to solve the initial screening bottleneck for non-technical recruiters by transforming unstructured resumes into structured, evidence-backed evaluation cards while stripping personal identifiers and defending against prompt injection.

---

## 2. Research & Industry Context

* **Application Volume:** [Ashby's Applications Per Job Report](https://sales.ashbyhq.com/hubfs/Ashby%20-%20Trends%20in%20Application%20per%20Job.pdf) documented a ~3x increase in weekly application volume across high-growth tech companies.
* **Prompt Injection Risks:** As AI-assisted applications become standard, an increasing number of applicants include hidden adversarial prompts (e.g., invisible text instructing LLMs to give top scores).
* **Bias Reduction:** Research indicates anonymized first-round screening significantly improves fairness across underrepresented groups.

---

## 3. The 4 System Guardrails

1. **PII Stripping & Document Hashing:** Identifiers (name, phone, email, address, graduation year) are sanitized before LLM evaluation. A SHA-256 hash tracks document integrity without storing personal details.
2. **Anti-Injection Boundary:** Resumes are enclosed within strict `<candidate_data>` XML-style delimiters with escaped tags to prevent context escape.
3. **Verbatim Evidence Anchoring:** The LLM cannot award points without providing an exact, verbatim text quote directly from the CV. No hallucinations are accepted.
4. **Human-in-the-Loop Authority:** The system provides decision-support evidence; the final Approve/Reject verdict remains exclusively in the hands of the human recruiter.

---

## 4. Evaluation & Baseline Plan

To measure real-world performance:
* **Extraction Speed:** Measured across PDF, DOCX, and TXT file formats (see `docs/day1_results.md`).
* **Scoring Consistency:** Evaluated against fixed criteria rubrics (see `rubrics/rubric.md`).
* **Manual vs. Assisted Benchmark:** Framework defined in `docs/manual_baseline.csv` to track review duration and score alignment across candidate test sets.

---

## 5. Known Constraints & Boundary Conditions

* **Scanned Documents:** Image-only PDFs require OCR before ingestion.
* **Layout Complexity:** Multi-column tables and non-standard layouts require clean plaintext normalization.
* **Quote Relevance:** An exact quote verifies occurrence in the CV; human recruiter judgment verifies its contextual depth.
