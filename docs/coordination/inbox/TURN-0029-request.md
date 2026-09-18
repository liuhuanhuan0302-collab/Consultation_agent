# TURN-0029 request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0029
- Issue ID: I-210
- Sender: Codex orchestrator
- Recipient: Claude Code implementation worker
- Timestamp: 2026-09-04T12:20:00+08:00

## Evidence

- Actual configured development MySQL Alembic version is `3e7d1b9c5a20`.
- `GET /api/admin/leads/1450` reproduction traceback is MySQL 1054:
  `Unknown column 'report_delivery_jobs.queue_state' in 'field list'`.
- `alembic upgrade head` currently stops at a4d7c9e2f601 with MySQL 1050 because
  `report_queue_settings` already exists (created by metadata bootstrap), while
  `report_delivery_jobs` lacks queue columns.

## Required work

1. Update the existing a4 migration using inspector/portable checks so the
   pre-created settings table is adopted rather than recreated; preserve its
   values, ensure the singleton seed exists, then add queue columns/indexes.
   Keep c8 task-kind migration compatible and do not add runtime ALTER statements.
2. Audit `lead_service.get_lead_detail`, its repository queries and any response
   contract. Ensure missing report/submission/delivery and null optional queue
   values serialize safely. Do not hide SQL schema errors; migrations must be
   the fix for missing columns.
3. Add focused tests for all acceptance cases and existing lead list behavior.

## Forbidden

- Do not edit frontend files.
- Do not swallow 500s or add a frontend fallback.
- Do not access production/customer data or send email.

End with exact migration upgrade/current evidence on a disposable or local
development database, full backend tests, compileall, diff-check and a complete
READY_FOR_REVIEW handoff.

