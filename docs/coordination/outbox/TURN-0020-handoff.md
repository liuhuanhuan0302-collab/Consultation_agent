# TURN-0020 handoff

- Run ID: `backend-architecture-hardening-20260822`
- Turn ID: `TURN-0020`
- Issue ID: `I-130`
- Sender: `claude_code`
- Recipient: Codex
- Timestamp: `2026-08-27T14:54:05+08:00`
- Requested next state: `READY_FOR_REVIEW`

## Outcome

Implemented the administrator-only safe AI-report regeneration workflow. The
new action regenerates content from the existing scored questionnaire and
validated persisted research, preserves the current report until a candidate
passes V2 validation, and never calls research, PDF, delivery-queue or email
operations.

## Changed files

- `backend/app/api/v1/endpoints/admin/leads.py`
  - Added `POST /api/admin/leads/{lead_id}/regenerate-report` with `AdminOnly`,
    404/409/422 mapping and isolated background-task scheduling.
- `backend/app/service/lead_service.py`
  - Added trigger reservation, validated-research gate, duplicate and active
    delivery conflict checks, bounded failure reporting and the background
    orchestration transaction.
  - Success resets only the stale PDF snapshot and preserves delivery rows;
    failure restores the usable status and retains prior content.
- `backend/app/service/reporting.py`
  - Extracted side-effect-free `generate_report_candidate` and transactional
    `apply_report_candidate` while preserving the existing generation API.
- `backend/tests/test_lead_service.py`
  - Covered missing prerequisites, duplicate/active conflicts, success, failure
    preservation, no delivery creation, sent-delivery preservation, audit,
    scheduling, real admin guard and HTTP conflict mapping.
- `backend/tests/test_structured_report.py`
  - Proved invalid candidates pass through existing validation without mutating
    the stored report object.
- `backend/ARCHITECTURE.md`
  - Documented the content-only regeneration boundary and transaction.
- `frontend/src/App.vue`, `frontend/src/api.ts`,
  `frontend/src/composables/useAdmin.ts`, `frontend/src/styles.css`
  - Added the adjacent admin button, confirmation, truthful running state,
    polling/refresh and success/failure feedback.
- `docs/coordination/DEVELOPMENT_LOG.md`
  - Recorded complete evidence in `DEV-I-130-1`; because that record
    accidentally landed after an earlier terminal marker, appended
    `DEV-I-130-2` at the absolute end without rewriting the append-only log.
- `docs/coordination/outbox/TURN-0020-handoff.md`
  - This handoff.

## Commands and exact results

- Focused backend:
  - `python -B -m pytest -p no:cacheprovider -q tests/test_lead_service.py tests/test_structured_report.py`
  - `28 passed, 10 warnings in 2.14s`.
- Complete backend:
  - `python -B -m pytest -p no:cacheprovider -q`
  - `238 passed, 10 warnings in 26.21s`.
- Frontend:
  - `npm run build`
  - passed; TypeScript checks succeeded and Vite transformed 1577 modules in
    4.50s.
- Scoped diff check:
  - `git diff --check --` for every leased implementation/test path.
  - exit 0; only Git LF/CRLF conversion notices.

## Acceptance evidence

- The route dependency is the real `AdminOnly` guard; service/route tests assert
  the guard and 409 conflict mapping.
- Trigger requires a usable current report plus `evidence_version == 1` research
  that passes `validate_structured_research`.
- Candidate generation uses the stored report/submission relationships and is
  guarded by the existing generation semaphore; no research provider is called.
- Old HTML, summary, recommendations, advisor messages and PDF snapshot remain
  untouched while the candidate is generated. Candidate application and audit
  commit together; rollback restores all old persisted rows on failure.
- Success sets `pdf_status=pending`, clears the stale PDF path/timestamps, leaves
  existing sent deliveries unchanged and creates no job.
- Failure restores `generated`/`fallback`, stores an administrator-visible error
  capped at 500 characters and records failed audit status.
- UI copy explicitly says no PDF or email is produced and refreshes the content
  after completion.

## Unverified items and risks

- No live LLM/search/PDF/queue/email/production/deployment operation was run;
  external generation is mocked in tests.
- The isolated FastAPI background task is intentionally not durable. A hard
  process termination after the reservation commit can leave `status=generating`
  until a repair clears it. Durable regeneration-job persistence would require
  a migration and expanded scope, both excluded from TURN-0020.
- Pre-existing unrelated dirty-worktree changes were preserved. No stage,
  commit, push, deletion or destructive cleanup occurred.

READY_FOR_REVIEW
