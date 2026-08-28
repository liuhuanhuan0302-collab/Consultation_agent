# ISSUE I-170: Recover crashed AI-report regeneration safely

## Objective

Prevent administrator content-only AI regeneration from remaining permanently
stuck in `generating` after an API restart/process crash, without permitting an
old delayed task to overwrite a newer regeneration attempt.

## Confirmed defect

- The trigger commits `report.status = generating` before scheduling an in-process
  FastAPI `BackgroundTask`.
- A crash/restart loses that task but leaves the committed status indefinitely.
- Subsequent triggers always reject `generating`, so there is no recovery path.

## Approved implementation

- Add a conservative stale timeout derived from model timeout with a safe floor.
- Record the pre-regeneration status and generation start/lease timestamp in the
  existing operation audit detail.
- When a locked report is still actively generating, preserve the 409 conflict.
- When it is stale, restore the audited `generated`/`fallback` status (safe
  `generated` fallback for legacy audit rows), record recovery, and reserve a new
  attempt.
- Pass the reserved generation start timestamp to the background task and fence
  every success/failure write by both status and that timestamp. An older task
  whose lease no longer matches must exit without changing the report.

## Scope

- Lead regeneration service and its audit lookup repository query.
- Admin endpoint background-task arguments.
- Focused service/endpoint tests for active conflict, stale recovery, status
  restoration and old-task fencing.
- Codex-owned durable operating note.

## Non-goals

- No frontend/API response/schema/database migration/report-content/delivery
  behavior change.
- No production/customer-data access, live model/search/email call, deployment,
  stage, commit, push or unrelated cleanup.

## Acceptance conditions

1. A fresh `generating` reservation still returns conflict.
2. A stale reservation can be atomically recovered and retriggered.
3. Historical `fallback` status is restored from audit metadata on recovery.
4. An old background task cannot apply either success or failure after a newer
   reservation changes the lease timestamp.
5. The new task preserves existing success/failure rollback behavior.
6. Focused and complete backend tests, compileall and scoped diff checks pass.
