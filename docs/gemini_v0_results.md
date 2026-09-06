# Gemini v0 check â€” 6 September 2026

A live fictional sample completed extraction, personal-detail cleanup, Gemini
scoring and local evidence/score validation using `gemini-3.8-flash`.
Sample: `samples/cvs/01_strong.txt`; supplied name: Amina Example.
Returned score: 100; five MET criteria; all five quotes matched cleaned CV text;
flagged_for_human was true. This confirms a happy path, not screening accuracy,
fairness, adversarial robustness or time savings. No real applicant was submitted.
No baseline, API-cost measurement or independent reviewer judgment was recorded.

Observed failure: `gemini-2.5-flash` appeared in model listing but generation
returned HTTP 404. Switching to listed `gemini-3.8-flash` resolved the request.
The latter is now the default; it can be overridden with GEMINI_MODEL.

The CLI previews locally without --send. With --send it contacts Google's official
API over HTTPS using a header credential, with a 60-second timeout. Credentials,
prompts and raw provider errors are not logged. Invalid outputs fail closed.
Official reference: https://ai.google.dev/api/generate-content

## Transient availability handling

After a user-reported HTTP 503, the transport now retries HTTP 500/502/503/504
at most twice, waiting 1 then 2 seconds. Authentication, quota, timeout and
invalid-response errors are not automatically retried. Regression checks prove
503-to-success recovery, exhaustion after three requests, and no retry on 403.
All 13 automated tests passed. Provider availability itself is external.
