# TURN-0025 handoff

- Run ID: `backend-architecture-hardening-20260822`
- Turn ID: `TURN-0025`
- Issue ID: `I-170`
- Sender: `claude_code`
- Recipient: `codex`
- Timestamp: `2026-08-28T13:46:14+08:00`
- Lease: `lease-turn-0025`
- Terminal state requested: `READY_FOR_REVIEW`

## Objective completed

Administrator content-only AI regeneration can recover a crashed/stale
in-process attempt without allowing an older delayed task to overwrite the
newer reservation. The public HTTP response remains unchanged and no delivery
workflow is entered.

## Explicit non-goals preserved

- No frontend, schema, model, migration, report-content or delivery behavior
  change.
- No production/customer data, live model/search/converter/SMTP call, real
  email, deployment, stage, commit, push, deletion or unrelated cleanup.

## Changed files

- `backend/app/repositories/lead_repo.py`
  - Added the operation-log query that returns the latest matching regeneration
    reservation detail and its audit timestamp for a lead/report pair.
- `backend/app/service/lead_service.py`
  - Added a conservative stale threshold: configured model timeout × 10, with a
    15-minute floor.
  - Reservations now persist audited `previous_status` and a whole-second UTC
    `generation_started_at` lease timestamp.
  - A stale row-locked reservation restores audited `generated`/`fallback`
    semantics, uses safe `generated` for legacy/malformed prior status, records
    recovery, and atomically reserves the new attempt.
  - The background task checks status plus timestamp before model work, before
    candidate application and before failure rollback.
- `backend/app/api/v1/endpoints/admin/leads.py`
  - Passes the service-returned lease timestamp to the background task; its
    response contract is unchanged.
- `backend/tests/test_lead_service.py`
  - Added deterministic fixed-time coverage for fresh conflict, stale fallback
    recovery, audit persistence, endpoint scheduling and old-task fencing on
    both successful-candidate and exception paths.
- `docs/coordination/DEVELOPMENT_LOG.md`
  - Appended `DEV-I-170-1` and `DEV-I-170-2`; their generic patch anchors placed
    them after earlier terminal records, so `DEV-I-170-3` was appended after
    the unique final `DEV-I-160-2` record without rewriting or removing any
    prior text.
- `docs/coordination/outbox/TURN-0025-handoff.md`
  - This handoff.

## Acceptance evidence

1. A report reserved one minute ago still raises the existing conflict.
2. A reservation older than the derived timeout is recovered while holding the
   report row lock and receives a new timestamp.
3. An audited historical `fallback` status is retained as the new attempt's
   rollback status and appears in both recovery and reservation audit records.
4. Tests change the stored timestamp during mocked generation, then prove the
   old task applies neither a successful candidate nor a failure rollback/log.
5. Existing successful replacement and failed-candidate snapshot preservation
   tests remain passing with the new lease argument.
6. Verification results:
   - `python -m pytest tests/test_lead_service.py -q` -> `29 passed, 10 warnings
     in 3.34s`.
   - `python -m pytest -q` -> `251 passed, 10 warnings in 20.84s`.
   - `python -m compileall -q app tests` -> exit 0.
   - Scoped `git diff --check` -> exit 0 with only LF/CRLF conversion notices.

The ten warnings are the pre-existing Pydantic v2 `json_encoders` deprecation
warnings; no new warning was introduced by this turn.

## Unverified items and residual risk

- No live external or deployed flow was exercised by design.
- The regeneration executor remains an in-process FastAPI background task; this
  issue provides bounded recovery rather than a durable worker. Administrators
  must wait until the conservative timeout before retrying a genuinely crashed
  attempt.
- No known residual correctness defect remains within I-170. Codex must
  independently inspect and rerun acceptance before approval.

READY_FOR_REVIEW
