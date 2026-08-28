# TURN-0019 handoff

- Run ID: `backend-architecture-hardening-20260822`
- Turn ID: `TURN-0019`
- Issue ID: `I-120`
- Sender: `delegated_report_visual_worker`
- Recipient: Codex
- Timestamp: `2026-08-27T12:58:10+08:00`
- Requested next state: `READY_FOR_REVIEW`

## Outcome

Implemented the screenshot-authoritative, Word-native customer cover and the
reference-PDF-aligned body system without changing report prose, scores, API
contracts or delivery behavior. The customer DOCX, Chromium fallback and both
online report variants now share the approved white/navy/red/gray editorial
vocabulary. The fallback pagination was rebalanced after visual review: page 2
contains the score, executive summary and bar chart; page 3 contains the radar
chart plus analysis; page 4 contains the remaining action sections.

## Changed files

- `backend/app/service/lead_export_service.py`
  - Kept `standard_business_brief` and added named
    `reference_consulting_body_v2` body tokens.
  - Rebuilt the cover as native Word geometry following
    `approved_reference_editorial_cover`: full legal company name, adaptive
    short display title, exact five compact borderless metadata rows, Chinese
    date, no confidentiality copy, no English kicker and no top rule.
  - Applied explicit A4/body typography, reference colors, native tables,
    callouts, quiet running header and footer with real centered page fields.
- `backend/app/service/pdf_service.py`
  - Aligned the Chromium fallback with the same cover/body tokens.
  - Moved the existing score off the cover and preserved it in the overview.
  - Split the executive summary from sanitized content for balanced print flow;
    retained it exactly once and preserved all remaining content order.
  - Added a nonvisual ISO date compatibility attribute while displaying the
    required Chinese date.
- `backend/scripts/generate_customer_report.py`
  - Updated the database-free fixture to use `奥飞娱乐股份有限公司` and added
    representative lead/callout content for visual validation.
- `backend/tests/test_customer_docx_pdf.py`
  - Added assertions for full/short company names, exact metadata rows, Chinese
    date, forbidden cover text, adaptive title bounds, named body tokens,
    native Word callout/table styling and fallback content ordering.
- `frontend/src/App.vue`
  - Applied full/short cover names, adaptive title classes, Chinese date and the
    named body token to both report paths.
  - Added `report-document` to the online report article so wrapperless sanitized
    report HTML receives the approved body styles.
- `frontend/src/components/ReportCharts.vue`
  - Aligned chart colors, rules and headings with the reference palette.
- `frontend/src/styles.css`
  - Rebuilt online cover spacing and metadata geometry and applied the approved
    body hierarchy, table, callout and responsive tokens.
- `docs/coordination/DEVELOPMENT_LOG.md`
  - Appended `DEV-I-120-1` at the absolute end.
- `docs/coordination/outbox/TURN-0019-handoff.md`
  - This handoff.

## Commands and exact results

- Required Documents artifact marker: completed once immediately before the
  first DOCX authoring action for one DOCX edit output.
- Required PDF artifact marker: completed once immediately before the first PDF
  authoring action for two PDF edit outputs.
- Focused backend:
  - `python -m pytest tests/test_customer_docx_pdf.py tests/test_lead_export_structure.py tests/test_pdf_delivery_gate.py::test_customer_pdf_template_excludes_internal_lead_and_research_fields -q`
  - `34 passed in 9.88s`.
- Complete backend:
  - `python -m pytest -q`
  - `231 passed, 10 warnings in 51.03s`.
  - Warnings are existing Pydantic `json_encoders` deprecations from
    site-packages.
- Frontend:
  - `npm run build`
  - passed; TypeScript checks succeeded, Vite transformed 1577 modules in
    4.03s.
- Database-free fixture:
  - `python -B scripts/generate_customer_report.py --fixture --outdir output/turn-0019`
  - generated the full-legal-name DOCX, fallback HTML and fallback PDF without
    database access; printed the expected missing-LibreOffice guidance.
- Packaged renderer:
  - bundled `render_docx.py` was attempted against the TURN-0019 DOCX.
  - exact result: `FileNotFoundError: [WinError 2] 系统找不到指定的文件。`
    from the unavailable `soffice` executable.
- Word 2021 read-only export:
  - returned `WORD_EXPORT_OK`.
  - produced 4 A4 pages (`595.32 x 841.92 pts`, 354918 bytes).
  - all four pages were inspected at original resolution: no clipping,
    overlap, missing glyphs or broken tables; the cover and representative body
    pages match the approved hierarchy.
- Final Chromium fallback:
  - 4 A4 pages (`594.96 x 841.92 pts`, 246697 bytes).
  - all four final balanced pages were inspected at original resolution with no
    clipping, overlap, broken rows or orphan-only page.
- Route-isolated synthetic Playwright:
  - desktop 1440px: document `scrollWidth=1440`; exact five cover rows, full
    legal name, short title, Chinese date and body token present; three problem
    cards were non-overlapping; overflow scan was empty.
  - mobile 390 x 844: `innerWidth=390`, document/body `scrollWidth=390`; problem
    cards were `313 x 72px` at x=`40..353`, with tops `1028/1110/1192` and
    10px vertical gaps; overflow scan was empty.
  - computed tokens after the online-wrapper fix: H2 navy `24px` desktop / `18px`
    mobile, lead red `16.67px`, navy/white table header, pale-red callout with
    red left border, blue chart heading.
  - console: `0` warnings and `0` errors.
- Scoped leased-path `git diff --check -- ...`: exit 0; only Git LF/CRLF
  conversion notices.

## Review artifacts

- `backend/output/turn-0019/奥飞娱乐股份有限公司_AI诊断报告.docx`
- `backend/output/turn-0019/奥飞娱乐股份有限公司_AI诊断报告-word-review.pdf`
- `backend/output/turn-0019/word-review-pages/page-1.png` through `page-4.png`
- `backend/output/turn-0019/奥飞娱乐股份有限公司_AI诊断报告-fallback.html`
- `backend/output/turn-0019/奥飞娱乐股份有限公司_AI诊断报告-fallback.pdf`
- `backend/output/turn-0019/fallback-pages-balanced-v2/page-1.png` through
  `page-4.png`
- `output/playwright/turn-0019-desktop-1440-final.png`
- `output/playwright/turn-0019-mobile-390.png`

## Unverified items and risks

- LibreOffice is not installed, so no LibreOffice-derived PDF exists. Required
  visual evidence is supplied by Word 2021 read-only export plus the Chromium
  fallback.
- The Chromium fallback uses a quiet centered `报告正文` footer label because
  Chromium DOM content does not expose the Word PAGE field; the customer DOCX
  and Word export contain the required real centered page number.
- No deployment, production/staging/customer data access, real email, stage,
  commit, push, deletion or destructive cleanup occurred.
- No known blocker remains within TURN-0019.

READY_FOR_REVIEW
