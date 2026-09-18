# TURN-0026 handoff

- Run ID: `backend-architecture-hardening-20260822`
- Turn ID: `TURN-0026`
- Issue ID: `I-180`
- Sender: `claude_code`
- Recipient: `codex`
- Timestamp: `2026-08-28T17:54:38+08:00`
- Lease: `lease-turn-0026`
- Terminal state requested: `READY_FOR_REVIEW`

## Objective completed

Implemented the persistent three-tier report queue domain foundation: queue
states and lifecycle cancellation, singleton database settings, settings-row
serialized placement/promotion/approval/rejection, safe legacy backfill, and
focused migration/domain tests. This phase is intentionally disconnected from
HTTP and worker execution.

## Explicit non-goals preserved

- No public/admin HTTP, schema, submission-service, existing worker, core
  configuration, frontend or deployment behavior was changed.
- No live database/service/model/search/converter/SMTP call, customer or
  production data access, real email, deployment, stage, commit, push,
  deletion or unrelated cleanup occurred.

## Changed files

- `backend/app/models/report.py`
  - Added `cancelled`, four persistent queue states, `queue_state`,
    `processing_stage`, `approved_at` and `approved_by`.
- `backend/app/models/system_setting.py`
  - Added the checked singleton `ReportQueueSetting` model with defaults
    2 / 50 / 200 / 1 and both pause flags.
- `backend/app/models/__init__.py`
  - Added compatibility exports for the new queue enum and settings model.
- `backend/app/repositories/report_queue_repo.py`
  - Added row-lock reads, capacity counts, ordered waiting reads and state
    assignment persistence primitives.
- `backend/app/repositories/system_setting_repo.py`
  - Added read and `FOR UPDATE` singleton settings access.
- `backend/app/service/report_queue_scheduler.py`
  - Added service-owned atomic setting update, placement, promotion, batch
    approval and batch rejection boundaries with domain exceptions.
- `backend/migrations/versions/a4d7c9e2f601_add_report_queue_scheduler.py`
  - Added the settings table, scheduler columns and query indexes, seeded the
    singleton, and backfilled existing `queued`/`processing` jobs to `active`
    without applying capacity eviction.
- `backend/tests/test_report_queue_scheduler.py`
  - Added default 251-task distribution, validation/rollback, manual hold,
    approved priority/capacity and cancellation coverage.
- `backend/tests/test_migration_chain.py`
  - Advanced the expected head and verifies settings defaults, schema and
    nonterminal legacy backfill.
- `docs/coordination/DEVELOPMENT_LOG.md`
  - Appended `DEV-I-180-1`.
- `docs/coordination/outbox/TURN-0026-handoff.md`
  - This handoff.

## Acceptance evidence

1. Defaults persist as processing 2, active 50, automatic 200, PDF 1, both
   pause flags false; service and database checks enforce active >= processing,
   PDF <= processing and valid integer/boolean types.
2. Sequential placement of 251 tasks produces exactly 50 `active`, 200
   `automatic_waiting` and 1 `manual_review`.
3. Increasing capacity promotes automatic/approved tasks but never releases an
   unapproved manual-review task.
4. Approved waiting tasks are promoted before both ordinary automatic waiting
   tasks and a newly placed task, without exceeding either configured capacity.
5. Migration backfills only legacy `queued`/`processing` rows to `active`;
   terminal rows retain a null queue state.
6. Every placement, promotion, settings update, approval and rejection starts
   by locking singleton settings row 1; task rows are then locked in stable ID
   order for batch mutations.
7. Verification results:
   - Focused scheduler + migration tests: `13 passed in 14.58s`.
   - Complete backend suite: `261 passed, 10 warnings in 29.21s`.
   - `python -m compileall -q app tests`: exit 0.
   - `python -m alembic -c alembic.ini heads`: exactly
     `a4d7c9e2f601 (head)`.
   - Global `git diff --check`: exit 0; output only contained Windows LF/CRLF
     conversion notices.
   - Direct trailing-whitespace scan over every leased application/migration/
     test path, including new untracked files: `SCOPED_TRAILING_WHITESPACE_OK`.

The ten warnings are the pre-existing Pydantic v2 `json_encoders` deprecation
warnings; this turn introduced no new warning.

## Unverified items and residual risk

- This is the deliberately disconnected domain phase. Until a later issue
  wires it into submission/HTTP and the independent worker, existing runtime
  execution behavior remains unchanged.
- SQLite migration/domain tests cannot exercise MySQL row-lock contention;
  production-targeted serialization is expressed by the singleton
  `SELECT ... FOR UPDATE` boundary and stable task-row locking, but concurrent
  MySQL integration remains for the wiring phase.
- `AGENTS.md` is orchestrator-owned and forbidden to this worker. Because the
  persistent queue is an important architecture/delivery boundary, Codex should
  add the accepted invariant to Project operating notes before landing I-180.

READY_FOR_REVIEW
