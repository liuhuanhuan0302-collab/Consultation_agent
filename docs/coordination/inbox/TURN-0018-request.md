# TURN-0018 request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0018
- Issue ID: I-110
- Sender: Codex
- Recipient: delegated_report_visual_worker
- Timestamp: 2026-08-27T11:08:30+08:00

## Objective

Implement the human-approved compact editorial cover described in
`docs/coordination/ISSUES/ISSUE-I-110.md` across customer DOCX, Chromium
fallback and online report output, while preserving all accepted report body
content and behavior.

## Design and document decisions

- Read the source PDF's first page as visual evidence only.
- Keep A4 output; reproduce its relative typography and layout geometry.
- DOCX body preset remains `standard_business_brief`; use the named first-page
  override `approved_reference_editorial_cover` and the `editorial_cover`
  pattern.
- Cover table is wide and shallow with exactly five compact rows and no visible
  borders. No confidentiality row or wording.
- Move the existing score strip below the cover page; do not drop it.

## Leased paths

- `backend/app/service/lead_export_service.py`
- `backend/app/service/pdf_service.py`
- `backend/scripts/generate_customer_report.py`
- `backend/tests/test_customer_docx_pdf.py`
- `backend/tests/test_lead_export_structure.py`
- `frontend/src/App.vue`
- `frontend/src/styles.css`
- `docs/coordination/DEVELOPMENT_LOG.md` (append-only)
- `docs/coordination/outbox/TURN-0018-handoff.md`

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

## Dependencies and evidence

- I-080, I-090 and I-100 are accepted.
- The user's approved concept contains five metadata rows and no confidentiality
  row. The source page render is available at
  `tmp/pdfs/cover-reference/page-1.png` for read-only comparison.
- Preserve all existing unrelated I-090/I-100 dirty-worktree changes.

## Acceptance and commands

- Add focused tests for cover text presence/absence, metadata geometry/style and
  score relocation.
- Run focused backend report tests.
- Run the complete backend suite.
- Run `npm run build` in `frontend`.
- Regenerate the database-free fixture.
- Attempt the bundled document skill `render_docx.py`; record exact result. If
  LibreOffice is unavailable, use the existing Word 2021 read-only review export
  and render every page to PNG for inspection.
- Render/inspect the fallback PDF and verify explicit A4 geometry.
- Use route-isolated synthetic Playwright data at 1440px and 390px; require no
  horizontal overflow and no console errors/warnings.
- Run scoped `git diff --check` for leased implementation paths.
- Append a complete READY_FOR_REVIEW record and write the TURN-0018 handoff.

## Non-goals

Do not change report prose/prompts/scoring/API/delivery logic, access real data,
send real email, deploy, stage, commit, push, or clean unrelated files.

