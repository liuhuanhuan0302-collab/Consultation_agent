# TURN-0006 handoff

Issue: I-020 — Extract admin lead workflows  
Writer: Codex  
Result: Accepted

## Changes

- Added a lead repository for detail, delivery, message, report and export-audit
  queries; latest-submission selection delegates to the original repository.
- Added an HTTP-independent lead service for CSV/Word export, diagnostic email,
  detail aggregation, research triggering/background execution, deletion, and
  associated transaction/audit orchestration.
- Reduced the admin lead endpoints to permissions, HTTP error mapping, streaming
  responses and post-commit background scheduling.
- Kept the original deletion cascade and exact latest-report definition.

## Verification

- Focused: 18 passed, 8 warnings.
- Full backend: 143 passed, 8 warnings.
- Independent read-only review: no confirmed regression or human-gate change.

## Safety

No commit, deployment, external API, email, production/staging database operation,
or destructive cleanup was performed.
