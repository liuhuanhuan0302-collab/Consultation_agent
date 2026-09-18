# TURN-0038 implementation handoff

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0038
- Issue ID: I-225
- Sender: delegated_org_ui_worker
- Recipient: codex
- Timestamp: 2026-09-17T16:17:49+08:00
- Status: READY_FOR_REVIEW

## Objective completed

Lead detail now exports the customer-facing PDF through the independent report
worker and the existing customer DOCX→LibreOffice renderer contract. HTTP only
prepares typed queue work or downloads a validated persisted artifact. Export
tasks never research, regenerate AI content or send email.

## Changed files

- `backend/app/models/report.py`: added `pdf_export` and nullable 16 MiB
  `customer_pdf_bytes`.
- `backend/migrations/versions/e3f7a9c2d501_store_customer_pdf_exports.py`:
  added the artifact column as the single Alembic head, with metadata-bootstrap
  adoption and downgrade.
- `backend/app/service/report_queue.py`: made PDF export reuse existing queue,
  lease, processing and PDF-slot machinery; publishes export bytes atomically
  with lease-fenced completion and exits before email. Normal delivery persists
  the same local bytes sent to email.
- `backend/app/service/lead_service.py`, `backend/app/repositories/lead_repo.py`:
  prepare dedupe, ready/download validation, audit, detail polling state,
  isolation from customer-delivery processing status, export/regeneration
  conflict and successful-regeneration invalidation.
- `backend/app/api/v1/endpoints/admin/leads.py`,
  `backend/app/schemas/lead.py`, `backend/app/schemas/__init__.py`: thin
  LeadExporter prepare/download HTTP contract.
- `frontend/src/api.ts`, `frontend/src/types.ts`,
  `frontend/src/composables/useAdmin.ts`, `frontend/src/App.vue`: adjacent PDF
  action, ready/queue/poll/failed/timeout flow, automatic download, duplicate
  prevention, timer cleanup and responsive wrapped actions.
- `backend/tests/test_customer_pdf_export.py`,
  `backend/tests/test_pdf_delivery_gate.py`,
  `backend/tests/test_authorization_matrix.py`,
  `backend/tests/test_migration_chain.py`: service, queue, exact-byte, no-email,
  invalidation, role and migration coverage.
- `backend/ARCHITECTURE.md`: documented the worker-only conversion and persisted
  artifact contract.
- `docs/coordination/DEVELOPMENT_LOG.md`: recorded complete `DEV-I-225-1` and
  appended terminal `DEV-I-225-2` as a position correction after the first
  record landed beside an earlier marker rather than at EOF.
- `docs/coordination/outbox/TURN-0038-handoff.md`: this handoff.

## Commands and exact results

1. Focused backend tests: 31 passed, 22 warnings, 13.36s, exit 0.
2. Full backend `pytest -q`: 298 passed, 24 warnings, 41.09s, exit 0.
3. `python -m compileall -q app tests`: passed, exit 0.
4. `alembic heads`: one head, `e3f7a9c2d501 (head)`, exit 0.
5. Final frontend `npm run build`: passed, exit 0; Vue type-check plus Vite,
   1591 modules transformed, completed in 3.85s.
6. Codex separately migrated the local MySQL database from c6 to e3 and
   confirmed the lead-list endpoint returned HTTP 200.
7. Authenticated Playwright QA:
   - desktop width 1036: both Word/PDF actions in bounds; document width 1036;
   - 390x844 after repair: document width 390, both actions in bounds;
   - mocked 422 prepare displayed the backend message;
   - safe mocked queued flow recorded prepare 200, poll 200, download 200 and an
     automatic `lead-1450.pdf` download.

## Unverified items and risks

- No real DOCX→LibreOffice artifact was generated during browser QA, deliberately
  avoiding a real queue mutation and mail-adjacent local workflow. The renderer
  remains covered by the existing suite; new focused tests use parser-valid PDF
  bytes and assert exact identity across worker persistence/email arguments.
- Artifact storage is capped at 16 MiB. Oversized persistence fails through the
  normal retry/manual-review path rather than streaming an untracked file.
- Polling is bounded to about two minutes; timeout leaves durable work intact and
  presents a retry-later message.

## Safety and non-goals

- No real email, external research, AI regeneration, production access,
  deployment, stage, commit, reset or deletion.
- Existing Word export, delivery retry, report regeneration and unrelated UI
  remain intact.

## Requested next state

Codex should independently review the final diff and acceptance evidence, then
record PASS for I-225 if the lease-fenced byte publication, authorization and UI
polling contract are confirmed.
