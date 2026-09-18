# TURN-0028 handoff

- Run ID: `backend-architecture-hardening-20260822`
- Turn ID: `TURN-0028`
- Issue ID: `I-200`
- Sender: `claude_code`
- Recipient: `codex`
- Timestamp: `2026-08-28T19:12:00+08:00`
- Status: `READY_FOR_REVIEW`

## Objective and lease

Implemented ISSUE-I-200 under `lease-turn-0028`: administrator queue
settings, queue overview and manual-review actions in the existing System
Settings backend/frontend. The turn spans two Claude sessions; the first
session ended at the UI-acceptance step because of an account usage limit and
this session completed the remaining acceptance commands and the final
responsive fix.

## Changed files

- `backend/app/api/v1/endpoints/admin/system_settings.py`
  - thin admin-only GET/PUT queue-settings, GET overview, POST approve/reject
    endpoints; maps scheduler-domain errors to 404/409/422; no queue logic in
    the HTTP layer.
- `backend/app/schemas/system_setting.py`
  - `ReportQueueSettingsUpdate/Read`, `ReportQueueManualJobRead`,
    `ReportQueueOverviewRead`, `ReportQueueActionRequest/Response` with bounds
    and the `confirm_processing_increase` flag.
- `backend/app/service/system_setting_service.py`
  - orchestration only: overview assembly (state/lifecycle/stage counts,
    transparent ETA), settings update with before/after audit, batch
    approve/reject with audit; delegates placement/promotion semantics to
    `report_queue_scheduler`; rolls back without partial writes.
- `backend/app/repositories/system_setting_repo.py`
  - singleton settings-row read and `SELECT ... FOR UPDATE` lock helper.
- `backend/app/repositories/report_queue_repo.py`
  - grouped queue-state/lifecycle/stage counts, manual-review rows joined with
    company/report identifiers, recent completed durations for the ETA basis.
- `backend/app/service/report_queue_scheduler.py`
  - settings validation, confirmation-required enforcement on concurrency
    increase, admin approve/reject transitions that preserve accepted
    capacity/priority semantics (approved work is promoted by the existing
    rules; rejection is terminal).
- `backend/tests/test_system_settings.py`, `test_report_queue_scheduler.py`,
  `test_authorization_matrix.py`
  - settings bounds/409 confirmation, overview counts/ETA null paths,
    approve/reject capacity semantics, audit writes, admin-only authorization.
- `frontend/src/types.ts`, `frontend/src/api.ts`,
  `frontend/src/composables/useAdmin.ts`, `frontend/src/App.vue`,
  `frontend/src/styles.css`
  - two clearly separated System Settings modules: scheduler parameters
    (4 numeric fields, 2 pause toggles, save with client+server validation and
    explicit risk confirmation) and queue management (tier metrics, lifecycle
    summary, stage list, transparent ETA, manual-review table with selection,
    batch and single-row approve/reject, reject reason, refresh).
  - `styles.css`: responsive grids (4/2/1 columns), stacked header and single
    column batch actions at narrow widths, plus the final fix described below.
- `docs/coordination/DEVELOPMENT_LOG.md` — append-only landing record.
- `docs/coordination/outbox/TURN-0028-handoff.md` — this handoff.

## Commands and exact results

- Focused backend tests
  (`tests/test_system_settings.py tests/test_report_queue_scheduler.py
  tests/test_authorization_matrix.py`): `30 passed, 61 warnings in 12.97s`.
- Complete backend suite: `266 passed, 63 warnings in 33.38s`.
- `python -m compileall -q app tests`: exit 0.
- `python -m alembic heads`: exactly `c8e1f4a7b203 (head)`.
- `frontend: npm run build` (`vue-tsc --noEmit && vite build`): passed twice
  (4.43s, then 3.90s after the final CSS fix); 1579 modules; output
  `dist/index.html` 2.44 kB, CSS 54.21 kB, JS 380.22 kB.
- Global `git diff --check`: exit 0; output contained only Git LF-to-CRLF
  working-copy notices.
- Synthetic browser QA (dedicated throwaway SQLite database seeded with
  QA-only companies/reports/jobs; no real customer data was loaded or
  captured; the database and seed script were removed after the run):
  - Settings tab loaded both modules with seeded values: tiers 2/2/3/1,
    lifecycle 2/3/0, stages research 1 / pdf 1, ETA `7.5 分钟`.
  - Save validation: active capacity below concurrency and PDF concurrency
    above processing concurrency each showed the expected error toast and sent
    no PUT request.
  - Increase-risk confirmation: the confirmation prompt fired with the
    resource-risk message; declining aborted the save with no request;
    accepting sent the PUT with the confirmation flag, returned 200, persisted
    `processing_concurrency: 3` with `updated_by: admin@example.com`.
  - Refresh button re-fetched settings and overview.
  - Batch approve of 2 manual jobs: manual 3→1, selection cleared, approved
    jobs promoted per existing capacity rules.
  - Batch reject with reason: toast `已拒绝 1 个任务`, manual→0, empty state
    `当前没有待人工审核任务`, selection and reason input cleared; job persisted
    as cancelled with `管理员 admin@example.com 拒绝：合成验收拒绝：附件服务已下线`.
  - Single-row approve of a freshly seeded manual job: manual 1→0, active
    7→8.
  - Pausing processing saved successfully and the ETA switched to
    `预计清空：暂无可靠估算`; unpausing restored the numeric estimate.
  - Operation log verified in the database: one audit row per UI action
    (3× `update_report_queue_settings`, 2× `approve_report_queue_jobs`,
    1× `reject_report_queue_jobs`).
  - Desktop 1280×800: document 1280/1280, no page-level horizontal overflow,
    scheduler and metrics grids 4 columns, table fits its wrapper
    (939/939).
  - Narrow 390×844: document 390/390, no page-level horizontal overflow,
    grids collapse to 1 column, batch actions single column, header stacks.
  - Responsive defect found and fixed during QA: the queue table is
    `min-width: 900px`, and the panel's grid items defaulted to
    `min-width: auto`, so the table wrapper stretched to 900px and was clipped
    by `.admin-main`'s `overflow-x: hidden` — the rightmost columns were
    unreachable at narrow widths. Fixed with
    `.system-settings-panel > * { min-width: 0; }`; re-verified the wrapper
    scrolls internally (client 329 / scroll 900) and the last column becomes
    visible at right edge 359 within the 390 viewport.
  - Console: 0 errors and 0 warnings after login; the only recorded error was
    the expected pre-login `GET /api/admin/me → 401` session probe.
- Tooling note: the preview pane's click tool intermittently timed out after
  mobile-size emulation; reloading the page and resetting to the desktop
  preset restored it, and the affected steps were re-run successfully. This
  did not change any result.

## Tests not run / unverified

- No live external services, real customer or production data, real email,
  deployment, staging, commit or push. Browser QA ran against the dedicated
  synthetic database only.
- The repository has no Playwright package; QA used the preview-pane browser
  with the synthetic backend, which covers the same acceptance interactions
  (save validation, risk confirmation, refresh, batch/single approve and
  reject, responsive layout, console errors).
- SQLite cannot prove MySQL row-lock contention for the settings singleton;
  the lock path is unchanged from the reviewed I-180 implementation and is
  exercised by the scheduler tests.

## Known risks

- None blocking within I-200. The UI intentionally hides no queue state; ETA
  is transparently absent when paused or when no completed-job history exists.

## Requested next state

Codex independently reviews TURN-0028 (including re-running the acceptance
commands above) and accepts I-200 when every acceptance condition passes.
