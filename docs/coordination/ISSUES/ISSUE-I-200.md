# ISSUE I-200: Add administrator queue settings and management

## Objective

Expose the database-backed report scheduler in the administrator-only System
Settings page so operators can change safe runtime limits, inspect every tier
and stage, and explicitly approve or reject manual-review jobs.

## Human-approved contract

- The existing administrator-only System Settings page contains two clearly
  separated modules: scheduler parameters and queue management.
- Editable parameters are processing concurrency, active queue capacity,
  automatic waiting capacity, PDF concurrency, processing pause and promotion
  pause. Changes take effect from the database without redeployment.
- Active capacity cannot be below processing concurrency; PDF concurrency cannot
  exceed processing concurrency; increasing processing concurrency requires an
  explicit resource-risk confirmation.
- Lowering capacity never moves or cancels existing work. Increasing automatic
  waiting capacity never releases manual-review work.
- Queue management shows tier/lifecycle counts, processing stages, a transparent
  approximate drain-time value, and a manual-review list with single/batch
  approve and reject actions.
- Approved jobs obey the existing capacity and priority rules; rejection is
  terminal. All settings updates, approvals and rejections write administrator
  operation logs.
- Only administrators can read or mutate this module.

## Scope

- Administrator schemas, repository queries, service orchestration and endpoints.
- Existing System Settings frontend types/API/composable/view/styles.
- Focused authorization, validation, summary, approve/reject and audit tests.
- Frontend type/build plus Playwright synthetic-data interaction and responsive QA.

## Non-goals

- No worker execution from HTTP.
- No changes to queue placement/claim semantics already accepted in I-180/I-190.
- No production data, real external calls/email, migration, deployment, stage,
  commit or push.

## Acceptance conditions

1. Administrator GET/PUT queue settings and GET queue overview endpoints expose
   validated settings, counts, stages, ETA and manual-review rows; non-admin roles
   are denied.
2. Single/batch approval and rejection endpoints use the scheduler service,
   preserve capacity semantics and write operation logs.
3. Raising processing concurrency requires a confirmation flag; invalid bounds
   return safe 422/409 responses without partial writes.
4. The System Settings UI loads both modules, presents clear save/pause/risk
   controls, refreshable queue status and usable batch review actions.
5. Focused/full backend, frontend build, compileall, diff-check and synthetic
   Playwright desktop/narrow-screen checks pass with no console errors.

