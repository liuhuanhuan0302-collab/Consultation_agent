# TURN-0019 request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0019
- Issue ID: I-120
- Sender: Codex
- Recipient: delegated_report_visual_worker
- Timestamp: 2026-08-27T12:27:09+08:00

## Objective

Implement the reference-aligned report preview defined in
`docs/coordination/ISSUES/ISSUE-I-120.md`. Preserve the report's substantive
content while replacing the current Word cover with the screenshot-controlled
native layout and refining body presentation from the supplied PDF.

## Leased paths

- `backend/app/service/lead_export_service.py`
- `backend/app/service/pdf_service.py`
- `backend/scripts/generate_customer_report.py`
- `backend/tests/test_customer_docx_pdf.py`
- `backend/tests/test_lead_export_structure.py`
- `frontend/src/App.vue`
- `frontend/src/components/ReportCharts.vue`
- `frontend/src/styles.css`
- `docs/coordination/DEVELOPMENT_LOG.md` (append-only)
- `docs/coordination/outbox/TURN-0019-handoff.md`

## Forbidden paths

- `backend/app/api/**`
- `backend/app/core/**`
- `backend/app/models/**`
- `backend/app/repositories/**`
- `backend/app/schemas/**`
- `backend/migrations/**`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/composables/**`
- `official-website/**`
- all orchestrator-owned coordination files other than the leased development
  log and handoff.

## Required workflow

- Read the Documents and PDF skills completely before task actions.
- Inspect every page of the reference PDF and the current TURN-0018 Word render.
- Preserve all existing unrelated dirty-worktree changes.
- Immediately before the first document authoring command, run the Documents
  artifact-operation marker exactly once for one DOCX edit output.
- Immediately before the first PDF authoring command, run the PDF marker exactly
  once for two PDF edit outputs.
- Generate independent TURN-0019 artifacts; do not overwrite TURN-0018 outputs.

## Acceptance and commands

- Add focused tests for cover full/short names, exact five-row metadata, Chinese
  date display, absence of forbidden text and named body-style tokens.
- Run focused backend report tests and the complete backend suite.
- Run `npm run build` in `frontend`.
- Regenerate the database-free fixture using `奥飞娱乐股份有限公司`.
- Attempt packaged `render_docx.py`; use Word 2021 read-only export if `soffice`
  is unavailable, then inspect all Word and fallback pages.
- Use route-isolated synthetic Playwright data at 1440px and 390px; verify the
  cover, tables/callouts/charts, page hierarchy, no overflow and no console
  errors/warnings.
- Run scoped `git diff --check` for leased paths.
- Append a complete READY_FOR_REVIEW record and write the TURN-0019 handoff.

## Non-goals

Do not change report prose/prompts/scoring/API/delivery logic, access real data,
send real email, deploy, stage, commit, push, delete or clean unrelated files.

