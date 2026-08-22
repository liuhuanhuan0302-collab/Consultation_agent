# I-070: Replace deprecated UTC timestamp in public lead limit

Status: Implementing  
Owner: Claude Code  
Turn: TURN-0009

## Objective

Replace the deprecated naive `datetime.utcnow()` call in
`enforce_email_lead_limit` with the repository's canonical `utc_now()` helper,
preserving the current one-hour boundary and lead-exclusion behavior.

## Allowed paths

- `backend/app/api/v1/endpoints/public.py`
- `backend/tests/test_lead_reroll.py`
- `docs/coordination/DEVELOPMENT_LOG.md` (append-only)

## Acceptance conditions

- No `datetime.utcnow()` remains in `backend/app/api/v1/endpoints/public.py`.
- The calculated cutoff remains a naive UTC `datetime`, compatible with existing
  MySQL `DATETIME` values and SQLite test fixtures.
- The existing hourly email-limit behavior and current-lead exclusion are
  preserved.
- Add or adjust a focused regression test if needed to prove the helper is used
  without changing limit behavior.
- `python -B -m pytest -p no:cacheprovider -q tests/test_lead_reroll.py`
  passes.
- Do not stage, commit, deploy, access a production database, or send email.

## Non-goals

No endpoint redesign, rate-limit policy change, schema change, frontend change,
or unrelated warning cleanup.
