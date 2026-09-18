# ISSUE I-210: Repair local migration bootstrap and admin lead detail compatibility

## Objective

Make the local/development database safely reach Alembic head when
`Base.metadata.create_all()` has pre-created the queue settings table, and make
admin lead detail return 200 for complete and historical/incomplete lead data.

## Scope

- Idempotent-safe `a4d7c9e2f601` migration bootstrap for the known pre-created
  settings table, without runtime DDL.
- Admin lead-detail repository/service/schema compatibility for absent Report,
  delivery job and optional queue fields.
- Focused regression tests for complete, no-report, submission-without-delivery,
  historical optional fields and response construction.

## Non-goals

- No frontend changes, queue behavior changes, or new migration revision unless
  strictly required by the schema repair.
- No production database, deployment, real email, commit or push.

## Acceptance conditions

1. A database at `3e7d1b9c5a20` with an already-existing queue-settings table can
   run `alembic upgrade head` successfully and reports `c8e1f4a7b203`.
2. Existing data is preserved; the migration adds missing queue columns and task
   kind fields exactly once and seeds settings only when needed.
3. Admin detail returns a serializable 200-shaped payload for complete reports,
   no Report, no delivery job, and historical rows with null optional queue data.
4. Existing lead-list and authorization behavior remains green.
5. Focused/full backend tests, compileall, migration-head and diff-check pass.

