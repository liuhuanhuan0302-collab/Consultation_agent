# TURN-0016 request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0016
- Issue ID: I-100
- Sender: Codex
- Recipient: delegated_report_visual_worker
- Timestamp: 2026-08-26T18:24:21+08:00

## Objective

Implement `ISSUE-I-100.md`: visually unify and elevate the customer report
across Word, LibreOffice PDF, Chromium fallback PDF, and online presentation.

## Required evidence and constraints

- Read `AGENTS.md`, `backend/ARCHITECTURE.md`, `docs/coordination/PROTOCOL.md`,
  `docs/coordination/STATE.json`, `docs/coordination/ISSUES/ISSUE-I-100.md`, and
  the TURN-0016 lease before editing.
- Inspect the supplied reference PDF. Treat it as a visual reference only.
- Preserve all pre-existing accepted dirty changes in leased files.
- Do not edit `backend/app/service/reporting.py`: report content is explicitly
  accepted and out of scope.
- Use the white/navy/red/light-gray executive-consulting direction in the issue;
  avoid dark gradient hero/dashboard styling.

## Leased paths

- `backend/app/service/lead_export_service.py`
- `backend/app/service/pdf_service.py`
- `backend/scripts/generate_customer_report.py`
- `backend/tests/test_customer_docx_pdf.py`
- `backend/tests/test_lead_export_structure.py`
- `frontend/src/App.vue`
- `frontend/src/styles.css`
- `docs/coordination/DEVELOPMENT_LOG.md` (append only)
- `docs/coordination/outbox/TURN-0016-handoff.md`

All other application, test, migration, configuration, and coordination paths
are forbidden.

## Acceptance commands

- `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py tests/test_lead_export_structure.py`
- `cd backend && python -B -m pytest -p no:cacheprovider -q`
- `cd frontend && npm run build`
- Run the database-free fixture and produce DOCX plus Chromium fallback visual
  artifacts; inspect at least the cover and one representative content page.
- `git diff --check -- backend/app/service/lead_export_service.py backend/app/service/pdf_service.py backend/scripts/generate_customer_report.py backend/tests/test_customer_docx_pdf.py backend/tests/test_lead_export_structure.py frontend/src/App.vue frontend/src/styles.css`

## Handoff

Append one complete `READY_FOR_REVIEW` record to `DEVELOPMENT_LOG.md`, write the
required handoff with changed files, exact commands/results, visual findings,
unverified items, risks, and requested next state, then exit.
