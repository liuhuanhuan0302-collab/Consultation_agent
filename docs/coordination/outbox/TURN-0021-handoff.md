# TURN-0021 handoff

- Run ID: `backend-architecture-hardening-20260822`
- Turn ID: `TURN-0021`
- Issue ID: `I-140`
- Sender: `claude_code`
- Recipient: `codex`
- Timestamp: `2026-08-28T01:39:23+08:00`
- Requested next state: `READY_FOR_REVIEW`

## Outcome

Implemented the approved customer-report presentation and delivery contract.
The public report, administrator report preview, standalone customer Word,
customer-detail Word part 3 and emailed PDF now use the same complete customer
report structure: cover, compact score, ranking and radar charts, exactly five
numbered chapters, deterministic render-time M01-M09 judgments, the exact short
scene note, numbered scene headings and the approved no-heading contact callout.
Persisted AI HTML, prose and score snapshots are not rewritten by presentation.

Customer email PDF is now strictly generated from the customer DOCX. Conversion
is attempted exactly three times. Exhaustion immediately creates a visible
manual-handling failure and sends no email; Chromium remains available only as
an explicit local preview helper and is not an attachment fallback. The new
administrator `重新生成附件并发送` action resets only PDF/delivery state, keeps the
reviewed AI body and rejects queued, processing or already-sent duplicates. The
TURN-0020 AI regeneration action remains content-only.

## Changed files

- `.env.production.example`
- `.env.staging.example`
- `backend/.env.example`
- `backend/ARCHITECTURE.md`
- `backend/app/api/v1/endpoints/admin/leads.py`
- `backend/app/api/v1/endpoints/public.py`
- `backend/app/core/config.py`
- `backend/app/service/lead_export_service.py`
- `backend/app/service/lead_service.py`
- `backend/app/service/pdf_service.py`
- `backend/app/service/report_content.py`
- `backend/app/service/report_queue.py`
- `backend/app/service/reporting.py`
- `backend/scripts/generate_customer_report.py`
- `backend/tests/test_customer_docx_pdf.py`
- `backend/tests/test_lead_export_structure.py`
- `backend/tests/test_lead_service.py`
- `backend/tests/test_pdf_delivery_gate.py`
- `backend/tests/test_structured_report.py`
- `backend/tests/test_system_settings.py` (only the two lease-approved obsolete
  visual-copy assertions)
- `frontend/src/App.vue`
- `frontend/src/api.ts`
- `frontend/src/components/CustomerReportView.vue`
- `frontend/src/composables/useAdmin.ts`
- `frontend/src/styles.css`
- `docs/coordination/DEVELOPMENT_LOG.md` (append-only records
  `DEV-I-140-1` and terminal landing record `DEV-I-140-2`)
- `docs/coordination/outbox/TURN-0021-handoff.md`

## Key implementation evidence

- `build_report_presentation_html` is the shared non-persistent presentation
  contract. It removes the visible sixth/management section, derives M01-M09
  judgment copy from the snapshotted module score, normalizes the exact scene
  note and reconstructs the historical contact snapshot without a heading.
- Word rendering uses the same presentation HTML for standalone and internal
  output. Internal Word part 3 appends the complete customer report, including
  its customer cover and score/charts, after the existing first two internal
  sections.
- The score overview is a compact two-cell `诊断得分 total / max` and
  `综合得分率` row with a restrained progress line. The contradiction table uses
  full width, 25/45/30 columns and vertical centering. Scenario titles are
  numbered and their expected-benefit paragraphs use ordinary body rhythm.
- The chart-only M01 label safely shortens to `用户/客户中心` so the radar label
  is not ellipsized; the complete module title remains unchanged in the body.
- `render_report_pdf_bytes` generates one customer DOCX and invokes only the
  DOCX converter in a three-attempt loop. `CustomerPdfConversionError` is
  terminal in the delivery worker, and the email call is never reached.
- `POST /api/admin/leads/{lead_id}/retry-attachment-delivery` is admin-only and
  delegates orchestration to `lead_service` before scheduling the queue wake.
- Public and administrator HTML both render `CustomerReportView.vue`; it owns
  the complete cover/score/charts/body structure and uses the same normalized
  report HTML from the backend.

## Commands and exact results

1. Final acceptance-focused backend selection:

   `python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py::test_m01_chart_label_is_concise_while_report_name_stays_unchanged tests/test_customer_docx_pdf.py::test_docx_failure_retries_three_times_and_never_calls_browser tests/test_pdf_delivery_gate.py::test_conversion_exhaustion_reaches_manual_state_and_never_sends_email tests/test_lead_service.py::test_retry_attachment_delivery_rejects_duplicate_or_sent`

   Result: `6 passed, 10 warnings in 1.69s`.

2. Complete backend suite from `backend`:

   `python -B -m pytest -p no:cacheprovider -q`

   Result: `246 passed, 10 warnings in 19.22s`. All warnings are the existing
   Pydantic `json_encoders` deprecation emitted from site-packages.

3. Backend compilation from `backend`:

   `python -m compileall app`

   Result: exit 0.

4. Frontend production build from `frontend`:

   `npm run build`

   Result: TypeScript checks passed; Vite transformed 1579 modules and built in
   3.79s.

5. Database-free representative output:

   `E:\Consultation_agent\.venv\Scripts\python.exe scripts\generate_customer_report.py --fixture --outdir output\turn-0021`

   Result: generated
   `backend/output/turn-0021/示例科技集团有限公司_AI诊断报告.docx` without a
   database query. Local conversion reported exactly
   `未找到 LibreOffice（soffice），无法执行 Word→PDF 转换`; no browser customer
   attachment was generated. The project `.venv` was used because the Codex
   bundled Python does not contain this repository's SQLAlchemy dependency.

6. Word 2021 visual proof:

   The synthetic DOCX was opened read-only through Word COM and exported with
   `ExportAsFixedFormat` to
   `backend/output/turn-0021/示例科技集团有限公司_AI诊断报告.pdf`.

   Result: Microsoft Word 2021 producer, 436168 bytes, A4
   `595.32 x 841.92 pt`, 6 pages. Poppler rendered all six pages at 150 DPI to
   `tmp/pdfs/turn-0021/customer-report-page-1.png` through page 6. Every page was
   visually inspected after the final M01 chart-label repair: no clipping,
   overlap, missing glyphs, table overflow or pagination regression. The M02
   split table repeats its header on the continuation page.

7. Structural artifact checks:

   DOCX has 56 paragraphs, 15 tables and one section. DOCX/PDF both contain all
   five chapter headings. M01-M09, `134 / 242`, `55%`, the exact scene sentence,
   numbered scenarios and historical contact snapshot are present. Neither
   contains a sixth chapter, `管理层` or a `进一步沟通` heading.

8. Scoped whitespace validation:

   `git diff --check --` was run across every leased implementation/test path.
   Result: exit 0; output contained only LF/CRLF conversion notices. The two
   leased untracked files, `CustomerReportView.vue` and
   `test_system_settings.py`, were additionally run through
   `git diff --no-index --check`; each returned the expected content-diff exit 1
   and no whitespace-error output.

## Unverified items

- This Windows host has no LibreOffice, so the Ubuntu/Docker LibreOffice output,
  pagination and installed-font behavior were not verified locally.
- No live LLM, live search, production or staging database, real SMTP email,
  deployed administrator/browser flow or server deployment was exercised.
- No stage, commit, push, deletion, cleanup or destructive command was run.

## Risks and operator action

- The deployment must install/configure LibreOffice (`soffice`) before automatic
  customer attachment delivery can succeed. Until then, the intended behavior
  is a manual-handling failure with zero customer email, never a mismatched
  Chromium PDF.
- Word 2021 visual proof passed, but LibreOffice can paginate differently. Run a
  server-environment synthetic DOCX-to-PDF acceptance check and inspect all pages
  before enabling customer delivery.
- Existing unrelated dirty-worktree changes and all accepted TURN-0020 changes
  were preserved. No forbidden path was edited in TURN-0021.

READY_FOR_REVIEW
