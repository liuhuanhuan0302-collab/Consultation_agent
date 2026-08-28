# TURN-0018 handoff

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0018
- Issue ID: I-110
- Sender: delegated_report_visual_worker
- Recipient: Codex
- Timestamp: 2026-08-27T11:31:36+08:00

## Objective completed

Implemented the human-approved compact editorial cover across customer DOCX,
Chromium fallback PDF/HTML and both online-report entry points. The existing
body content and visual system remain in place, and the score strip was moved
below the cover rather than removed.

## Scope and boundaries

Implementation changes are confined to the leased report paths:

- `backend/app/service/lead_export_service.py`
- `backend/app/service/pdf_service.py`
- `backend/tests/test_customer_docx_pdf.py`
- `frontend/src/App.vue`
- `frontend/src/styles.css`

`backend/scripts/generate_customer_report.py` and
`backend/tests/test_lead_export_structure.py` were leased and exercised but did
not need a new TURN-0018 edit. This append-only development record and handoff
are the remaining leased write paths. Existing accepted I-090/I-100 changes in
the shared dirty worktree were preserved. No forbidden path was edited for this
turn.

## Implementation summary

- DOCX keeps `standard_business_brief` for the body and uses the named
  `approved_reference_editorial_cover` first-page override following the
  `editorial_cover` pattern.
- The A4 cover now has a small gray full company name; two centered navy title
  lines; regular red subtitle; explicit 16.2 cm red rule; explicit 13.4 cm,
  borderless metadata table with fixed 3.0/10.4 cm columns and compact cell
  margins; and the navy footer statement. First-page header/footer content and
  the former top rule are suppressed.
- The metadata block has exactly five rows: `评估对象`, `报告类型`, `评估范围`,
  `报告编号`, `出具日期`. Confidentiality text, `请妥善保管` and the English
  kicker are absent.
- The DOCX score content now begins after the cover page break. The Chromium
  fallback places the same score content in a post-cover overview section.
- The Chromium fallback mirrors the compact editorial hierarchy and retains the
  accepted body/chart/table system. Print-only spacing was tightened so the
  final fallback remains four clean A4 pages without an orphaned final item.
- Both online report hero variants now use the same hierarchy and five metadata
  rows. Responsive rules make the red rule and metadata block full-width within
  the 390px content column while retaining the desktop 77%/64% proportions.
- Focused OOXML/HTML tests cover text presence/absence, first-page header
  behavior, fixed metadata geometry, compact cell margins, hidden borders and
  score relocation.

## Acceptance commands and exact results

- Focused backend report tests:
  - `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py tests/test_lead_export_structure.py`
  - Passed: `31 passed in 10.43s`.
- Complete backend suite:
  - `cd backend && python -B -m pytest -p no:cacheprovider -q`
  - Passed: `229 passed, 10 warnings in 31.08s`.
  - The warnings are existing Pydantic `json_encoders` deprecations from
    site-packages.
- Frontend production build:
  - `cd frontend && npm run build`
  - Passed TypeScript checks; Vite transformed 1577 modules and built in 4.90s.
- Database-free fixture:
  - `cd backend && python -B scripts/generate_customer_report.py --fixture --outdir output/turn-0018`
  - Generated the DOCX, fallback HTML and fallback PDF without a database query.
  - The normal Word-to-PDF branch printed exactly:
    `跳过 PDF 转换：未找到 LibreOffice（soffice），无法执行 Word→PDF 转换`.
- Bundled document renderer attempt:
  - Bundled Python ran the packaged `render_docx.py` with `--emit_pdf --verbose`.
  - It failed in `subprocess.Popen` with
    `FileNotFoundError: [WinError 2] 系统找不到指定的文件。` because `soffice`
    is not installed.
- Word 2021 read-only review export:
  - Word COM export succeeded with `WORD_EXPORT_OK`.
  - `pdfinfo` reports 4 pages at `595.32 x 841.92 pts (A4)`.
  - All four PNG pages in `backend/output/turn-0018/word-review-pages/` were
    inspected at original resolution. The cover, score page, body, charts and
    tables have no clipping, overlap or unwanted first-page rule.
- Chromium fallback visual QA:
  - Final PDF is 4 pages at `594.96 x 841.92 pts (A4)`, 223201 bytes.
  - All four final PNG pages in
    `backend/output/turn-0018/fallback-pages-v2/` were inspected at original
    resolution. The cover proportions are sound, score begins on page 2 and no
    orphaned content, clipping or overlap remains.
- Route-isolated synthetic Playwright validation:
  - The route interception was limited to
    `/api/public/reports/visualfixture`; no database or customer data was used.
  - At 1440 x 1100: document `scrollWidth=1440`; hero content was 838px, the
    645.25px red rule was 76.999% of it, and the 536.31px metadata block was
    63.999%. Exactly five rows rendered, every `dt`/`dd` overlap check was
    false, the score strip began below the cover, and forbidden cover text was
    absent.
  - At 390 x 844: document and body `scrollWidth=390`; hero, rule, metadata and
    score were inside the viewport; all five metadata rows and both title lines
    were readable; all three 313px problem cards were inside the viewport and
    every order/name/percentage overlap check was false.
  - Console collection: 0 warnings and 0 errors.
  - Full-page screenshots were visually inspected:
    `output/playwright/turn0018-desktop-1440.png` and
    `output/playwright/turn0018-mobile-390.png`.
- Scoped diff check:
  - `git diff --check -- backend/app/service/lead_export_service.py backend/app/service/pdf_service.py backend/scripts/generate_customer_report.py backend/tests/test_customer_docx_pdf.py backend/tests/test_lead_export_structure.py frontend/src/App.vue frontend/src/styles.css`
  - Exit 0; only Git LF/CRLF conversion notices.

## Unverified items and residual risks

- LibreOffice is unavailable, so no LibreOffice-derived PDF exists. Word 2021
  read-only export plus all-page PNG inspection supplies the local DOCX visual
  evidence requested by the fallback rule.
- The online regenerate button is visible only in the synthetic local-testing
  route; it is not part of customer production cover output.
- No deployment, production/staging/customer data access, real email, stage,
  commit, push or destructive cleanup occurred.
- No known blocker or human-intervention gate remains within TURN-0018 scope.

## Requested next state

`READY_FOR_REVIEW`: Codex should independently inspect the changed report files,
the generated Word/Chromium/browser artifacts and the recorded measurements,
then accept I-110 when all acceptance conditions pass.
