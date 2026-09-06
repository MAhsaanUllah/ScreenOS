# Day 2 results — 6 September 2026

Implemented personal-detail cleanup, SHA-256 document identifiers, escaped
candidate-data wrapping, and Pydantic scorecards. Added Pydantic 2.13.5.

Verification: `.venv/Scripts/python.exe -m unittest discover -s tests -v`
passed all 8 tests (5 existing extraction checks and 3 Day 2 checks with subcases).
Checks cover repeated supplied names, empty input, supplied address/year removal,
labelled details and email cleanup, education year removal while preserving a work
year, stable/content-sensitive hashes, hostile closing tags, valid half points,
JSON roundtrip, invalid totals/verdicts/statuses, missing/invented evidence,
changed candidate/job/rubric, extra fields and enforced human review.

This is a bounded rule-based implementation. Name is supplied by the caller;
unlabelled addresses and graduation years require caller input. It does not
promise full anonymization or fairness. See README for input and layout limits.
SHA-256 is deterministic and unkeyed, not encryption or proof of anonymity.
Escaped tags protect the textual delimiter, not the model's instruction-following.
No adversarial LLM test has run because AI scoring belongs to Day 3.
A matching quote proves occurrence, not relevance or truth.

Manual baseline remains unmeasured because owner data is unavailable; this is
not a blocker and no time/cost savings are claimed. Day 3 is not started.
