# TURN-0020 request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0020
- Issue ID: I-130
- Sender: Codex
- Recipient: claude_code
- Timestamp: 2026-08-27T15:30:00+08:00

## Objective

Implement the safe administrator-only AI-report regeneration workflow defined in
`docs/coordination/ISSUES/ISSUE-I-130.md`.

## Leased paths

- `backend/app/api/v1/endpoints/admin/leads.py`
- `backend/app/service/lead_service.py`
- `backend/app/service/reporting.py`
- `backend/tests/test_lead_service.py`
- `backend/tests/test_structured_report.py`
- `backend/ARCHITECTURE.md`
- `frontend/src/App.vue`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/composables/useAdmin.ts`
- `frontend/src/styles.css`
- `docs/coordination/DEVELOPMENT_LOG.md` (append-only)
- `docs/coordination/outbox/TURN-0020-handoff.md`

## Forbidden paths

- `backend/app/models/**`
- `backend/app/repositories/**`
- `backend/app/schemas/**`
- `backend/app/core/**`
- `backend/app/service/report_queue.py`
- `backend/app/service/pdf_service.py`
- `backend/app/service/email_service.py`
- `backend/app/service/company_research.py`
- `backend/migrations/**`
- `backend/Dockerfile`
- `official-website/**`
- all orchestrator-owned coordination files other than the leased development
  log and handoff.

## Required behavior

- Add a dedicated endpoint; do not reuse `resume-delivery`.
- Reuse the persisted company research and questionnaire data. Do not call the
  research provider.
- Do not call PDF, queue or email functions from the regeneration path.
- Preserve the prior report and recommendations if candidate generation fails.
  A rollback/savepoint or equivalent transaction boundary must make this
  executable, not merely best-effort field copying.
- On success replace the report content, set `pdf_status` to `pending`, and keep
  existing sent delivery rows unchanged.
- Reject queued/processing delivery conflicts and duplicate generation.
- Keep API thin and service errors independent of FastAPI.
- Put the admin-only button next to "AI 分析报告" with truthful progress/error
  copy and refresh/poll behavior.
- Preserve every unrelated dirty-worktree change in leased files.

## Acceptance and commands

- Add focused service tests for success, failure rollback, missing research,
  duplicate/active conflicts, no delivery creation and operation logging.
- Add endpoint/background scheduling coverage and authorization coverage using
  real route guards where practical.
- Mock DeepSeek and every external call; no live model/search/email invocation.
- Run focused backend tests for changed behavior.
- Run `python -B -m pytest -p no:cacheprovider -q` from `backend`.
- Run `npm run build` from `frontend`.
- Run scoped `git diff --check` for every leased implementation/test path.
- Append one complete `READY_FOR_REVIEW` record to `DEVELOPMENT_LOG.md` and write
  `docs/coordination/outbox/TURN-0020-handoff.md` with exact results and risks.

## Non-goals

No PDF/delivery behavior change, content/prompt rewrite, migration, live service,
real email, production data, deployment, stage, commit, push, deletion or cleanup.

