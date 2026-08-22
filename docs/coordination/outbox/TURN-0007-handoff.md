# TURN-0007 handoff

Issue: I-030 — Add authorization behavior matrix  
Writer: Codex  
Result: Accepted

## Changes

- Added a real-route matrix for all five role guards and all four supported roles.
- Added Bearer and HttpOnly-cookie authentication coverage.
- Added 401 coverage for missing, invalid, expired, disabled-user, malformed and
  oversized-subject credentials.
- Normalized string/Enum role handling so denied string roles return 403 instead
  of raising an attribute error.
- Rejected JWT subject IDs outside the database integer range before querying.

## Verification

- Authorization matrix: 8 passed, 5 warnings.
- Full backend: 151 passed, 8 warnings.
- Independent read-only review: accepted; additional matrix+seed run 11 passed.

## Protocol note

TURN-0007 initially omitted `auth.py` from the generated lease even though the
issue explicitly owned it. The lease was corrected and DECISION-003 records the
process deviation.

## Safety

No external call, email, production/staging database operation, commit, deployment,
or destructive cleanup was performed.
