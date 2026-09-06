# Day 4 — Evaluation and reliability

Run on 6 September 2026 with:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_samples.py
```

This is an offline, fixed evidence baseline. It exercises extraction, personal-detail
removal, the scoring request, exact-quote checks and score arithmetic. It does not
claim to measure an AI provider's quality. Live mode was not run, so no paid-provider
result is presented here.

| File | Candidate Type | Expected Verdict | Actual Verdict | Score/100 | Anti-Injection Defense Passed | Latency ms |
| --- | --- | --- | --- | --- | --- | --- |
| 01_strong.txt | Strong evidence | STRONG_MATCH | STRONG_MATCH | 100.0 | Yes | 13 |
| 02_python.docx | Python service | POSSIBLE_MATCH | POSSIBLE_MATCH | 50.0 | Yes | 23 |
| 03_documents.pdf | Document search | WEAK_MATCH | WEAK_MATCH | 42.5 | Yes | 25 |
| 04_career_change.txt | Career change | WEAK_MATCH | WEAK_MATCH | 15.0 | Yes | 3 |
| 05_claims_only.docx | Claims without proof | WEAK_MATCH | WEAK_MATCH | 0.0 | Yes | 22 |
| 06_instructions.pdf | Prompt injection | WEAK_MATCH | WEAK_MATCH | 15.0 | Yes | 30 |

Latency is one local run and will vary by machine. “Defense passed” means the CV was
kept inside the untrusted-data boundary, the scoring rules told the provider to ignore
instructions in that data, and sample 06 remained a weak match without using its
attack sentence as evidence.

## What changed

| Before | After |
| --- | --- |
| Six formats were checked mainly for readable extraction. | One command evaluates all six through the complete safety and scoring path. |
| Prompt-injection protection existed but lacked an end-to-end regression check. | Sample 06 proves the attack text remains candidate data and earns no evidence points. |
| Empty text and invented quotes had separate lower-level checks. | Day 4 tests now cover empty input, invented evidence and the unrelated career-change case together. |
| Evaluation could depend on provider access. | The fixed offline baseline runs in CI; `--live` uses the configured provider chain. |

## Root cause analysis

### 1. Scanned PDF has no readable text

- Cause: an image-only PDF contains pixels, not characters, and SCREENOS has no OCR
  (image-to-text) dependency.
- Effect: scoring would have no trustworthy CV text.
- Current safeguard: extraction rejects the file with a plain message instead of
  silently scoring an empty CV.
- Later improvement: add OCR only if real usage shows enough scanned CVs to justify
  its extra setup and error risk.

### 2. Invisible white-text instruction

- Cause: PDF extraction can recover text that a recruiter cannot see because its
  colour matches the page.
- Effect: a hidden instruction may enter the same extracted text as genuine work.
- Current safeguard: all extracted text stays inside the candidate-data boundary;
  instructions there cannot replace the scoring rules. Positive points still need an
  exact quote that the recruiter can inspect.
- Remaining gap: SCREENOS does not compare text colour with page colour, so it cannot
  label white text as hidden. Add layout/style inspection only after collecting a safe
  test file and defining acceptable false alarms.

### 3. Distant passage stitching

- Cause: a model may join separate CV fragments into one stronger-sounding claim.
- Effect: the combined sentence misrepresents the candidate's evidence.
- Current safeguard: each positive quote must appear exactly and continuously in the
  cleaned CV. A stitched or paraphrased quote is rejected and no score is accepted.
- Remaining gap: two separate valid quotes could still be individually real but
  misleading in context. Human review remains required for relevance.

## Automated checks

`tests/test_evaluation.py` covers the prompt-injection PDF, whitespace-only rejection,
invented evidence rejection and a fair low score for the career-change sample.

For an honest provider run:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_samples.py --live
```

Live mode may incur provider cost and requires keys in the uncommitted `.env` file.
