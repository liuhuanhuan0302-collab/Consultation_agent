# TURN-0005 handoff

Issue: I-010 — Extract questionnaire submission workflow  
Writer: Codex  
Result: Accepted

## Changes

- Added a submission repository for row locking, active-question lookup,
  capacity queries, answer upsert, and report persistence.
- Added an HTTP-independent submission service owning completeness checks,
  scoring orchestration, transaction commit/rollback, MySQL deadlock retry,
  report/job creation, tracking, and immutable post-commit response snapshots.
- Reduced the final-submit endpoint to HTTP/session mapping, service invocation,
  response serialization, and post-commit task scheduling.
- Removed FastAPI exceptions from the diagnosis service.
- Serialized draft and final writes on the same submission row; late drafts are
  rejected after scoring so answers cannot diverge from stored scores.

## Verification

- Focused: 42 passed, 8 warnings.
- Full backend: 135 passed, 8 warnings.
- Compile and diff checks completed without errors.
- Independent read-only review: accepted after two reproduced transaction bugs
  were fixed.

## Unverified

Real MySQL concurrent-request blocking was not executed. SQLite test databases
ignore `SELECT FOR UPDATE`; correctness is supported by query structure and
stale-identity-map tests, not a live MySQL integration test.

## Safety

No commit, deployment, network API, email, production/staging database operation,
or destructive cleanup was performed.
