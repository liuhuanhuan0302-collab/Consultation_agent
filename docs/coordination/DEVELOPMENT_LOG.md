# Development log

Claude Code is the sole writer. Append only; never modify earlier records.

## Record template

```md
## DEV-<task-id>-<attempt>

- Task: <issue ID>
- Attempt: <positive integer>
- Timestamp: <ISO-8601 with timezone>
- Allowed paths: <paths>
- Changed paths: <paths, or none>
- Summary: <what changed and why>
- Commands actually run: <commands and exact results; redact secrets>
- Not run / unverified: <items>
- Risks / blockers: <items or none>

READY_FOR_REVIEW

## DEV-I-170-1

- Task: I-170
- Attempt: 1 (TURN-0025 implementation)
- Timestamp: 2026-08-28T13:46:14+08:00
- Allowed paths: `backend/app/api/v1/endpoints/admin/leads.py`,
  `backend/app/repositories/lead_repo.py`,
  `backend/app/service/lead_service.py`, `backend/tests/test_lead_service.py`,
  `docs/coordination/DEVELOPMENT_LOG.md` (append-only), and
  `docs/coordination/outbox/TURN-0025-handoff.md`.
- Changed paths: all six allowed paths listed above. No forbidden path was
  edited by this worker.
- Summary: content-only report regeneration now uses a conservative timeout
  derived from the configured model timeout with a 15-minute floor. Each
  reservation persists its previous report status and whole-second UTC start
  timestamp in the operation log. A row-locked stale reservation restores the
  audited `generated`/`fallback` status (or safe `generated` legacy fallback),
  records recovery and atomically creates a new reservation. Background tasks
  receive the reserved timestamp and require both `generating` status and an
  exact timestamp match before model work, success replacement, or failure
  rollback, so an older task cannot overwrite a newer lease.
- Commands and exact results:
  - `python -m pytest tests/test_lead_service.py -q` -> `29 passed, 10 warnings
    in 3.34s`.
  - `python -m pytest -q` -> `251 passed, 10 warnings in 20.84s`.
  - `python -m compileall -q app tests` -> exit 0.
  - Scoped `git diff --check` over the four application/test paths -> exit 0
    with only Git LF/CRLF conversion notices.
- Tests not run / unverified: no live model/search/converter/SMTP service,
  production/customer data, deployment, stage, commit or push. No migration or
  API response contract change was required.
- Known risks / blockers: none known within I-170. The in-process background
  task remains intentionally non-durable, but a crashed reservation is now
  recoverable after the conservative timeout and late writers are fenced.
- Requested next state: Codex independently reviews TURN-0025 and accepts I-170
  when all acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-140-1

- Task: I-140
- Attempt: 1
- Timestamp: 2026-08-28T01:39:23+08:00
- Allowed paths: all TURN-0021 leased paths in
  `docs/coordination/inbox/TURN-0021-request.md` and active
  `lease-turn-0021`, including the approved expansions for
  `frontend/src/components/CustomerReportView.vue` and the two obsolete
  I-140-conflicting assertions in `backend/tests/test_system_settings.py`.
- Changed paths:
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
  - `backend/tests/test_system_settings.py`
  - `frontend/src/App.vue`
  - `frontend/src/api.ts`
  - `frontend/src/components/CustomerReportView.vue`
  - `frontend/src/composables/useAdmin.ts`
  - `frontend/src/styles.css`
  - `docs/coordination/DEVELOPMENT_LOG.md` (this append-only record)
  - `docs/coordination/outbox/TURN-0021-handoff.md`
- Summary: unified the public report, administrator report preview, standalone
  customer Word, customer-detail Word part 3 and emailed PDF around one complete
  customer-report presentation contract. The visible contract has the approved
  cover, compact score overview, both charts, exactly five numbered chapters,
  deterministic render-time M01-M09 judgments, exact short scene note, numbered
  scene headings and the approved no-heading contact callout. Stored AI HTML and
  score snapshots are not rewritten. The internal Word now appends the complete
  customer report rather than only the body fragment.
- Delivery behavior: customer email PDF is now strictly customer DOCX to PDF.
  Conversion is bounded to exactly three attempts; exhaustion creates an
  explicit manual-handling failure and sends zero email. The former silent
  Chromium customer-attachment fallback is bypassed. The administrator action
  `重新生成附件并发送` retries only the attachment/delivery state, preserves AI
  prose and safely rejects queued, processing or already-sent duplicates. The
  existing AI regeneration action remains content-only.
- Commands and exact results:
  - Final acceptance-focused backend selection (M01 chart label, exactly three
    conversion attempts, exhaustion with zero email, and queued/processing/sent
    duplicate rejection) -> `6 passed, 10 warnings in 1.69s`.
  - Final complete backend -> `246 passed, 10 warnings in 19.22s`; warnings are
    the existing Pydantic `json_encoders` deprecations from site-packages.
  - `python -m compileall app` from `backend` -> exit 0.
  - Final `npm run build` from `frontend` -> passed; TypeScript checks succeeded,
    Vite transformed 1579 modules and built in 3.79s.
  - Database-free synthetic fixture using the project `.venv` -> generated
    `backend/output/turn-0021/示例科技集团有限公司_AI诊断报告.docx`; no database
    was queried. The Codex bundled Python was not used for this project script
    because it lacks the repository's SQLAlchemy dependency.
  - Local LibreOffice conversion -> correctly reported
    `未找到 LibreOffice（soffice），无法执行 Word→PDF 转换` and generated no
    browser customer-attachment fallback.
  - Word 2021 read-only export -> generated
    `backend/output/turn-0021/示例科技集团有限公司_AI诊断报告.pdf`, 436168 bytes,
    6 A4 pages. Poppler rendered all six pages at 150 DPI; every page was
    inspected without clipping, overlap, missing glyphs or table overflow.
    The chart-only M01 label is the complete concise `用户/客户中心`, while the
    body retains the complete `M01 一心：以用户/客户为中心` title.
  - DOCX/PDF structural inspection -> all five chapter headings present, M01-M09
    present, score `134 / 242` and `55%` present, exact scene note and approved
    contact present, and no sixth chapter, `管理层` or `进一步沟通` heading.
  - Scoped tracked leased-path `git diff --check -- ...` -> exit 0; only Git
    LF/CRLF conversion notices. The two leased untracked files were also checked
    with `git diff --no-index --check`; each returned the expected content-diff
    exit 1 with no whitespace-error output.
- Not run / unverified: this Windows host has no LibreOffice, so the server's
  Ubuntu/Docker LibreOffice pagination and conversion remain unverified locally.
  No live LLM/search, production or staging data, real SMTP email, deployed
  administrator flow, deployment, stage, commit, push, deletion or destructive
  cleanup occurred.
- Risks / blockers: the deployment must install and configure LibreOffice for
  automatic customer attachment delivery. Until then, the intentional strict
  behavior is a visible manual-handling failure with no customer email, not a
  mismatched browser PDF. Word 2021 visual proof passed, but LibreOffice may have
  minor pagination differences and needs an environment acceptance run.
- Requested next state: Codex independently reviews TURN-0021 using
  `docs/coordination/outbox/TURN-0021-handoff.md` and accepts I-140 when all
  acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-130-1

- Task: I-130
- Attempt: 1
- Timestamp: 2026-08-27T14:54:05+08:00
- Allowed paths: all TURN-0020 leased paths listed in
  `docs/coordination/inbox/TURN-0020-request.md` and `lease-turn-0020`.
- Changed paths:
  - `backend/app/api/v1/endpoints/admin/leads.py`
  - `backend/app/service/lead_service.py`
  - `backend/app/service/reporting.py`
  - `backend/tests/test_lead_service.py`
  - `backend/tests/test_structured_report.py`
  - `backend/ARCHITECTURE.md`
  - `frontend/src/App.vue`
  - `frontend/src/api.ts`
  - `frontend/src/composables/useAdmin.ts`
  - `frontend/src/styles.css`
  - `docs/coordination/DEVELOPMENT_LOG.md` (this append-only record)
  - `docs/coordination/outbox/TURN-0020-handoff.md`
- Summary: added a dedicated administrator-only content regeneration action.
  The trigger requires an existing usable report and an evidence-validated
  persisted research snapshot, serializes duplicate starts, rejects queued or
  processing deliveries, and schedules an isolated task. Report generation now
  supports a side-effect-free validated candidate; regeneration applies that
  candidate in one transaction only after a second delivery-conflict check.
  Failure restores the prior usable report status and preserves old HTML,
  summary, recommendations and PDF snapshot while exposing a bounded admin
  error. Success marks the PDF stale/pending but does not generate it, create or
  alter delivery work, or send email. The admin UI confirms the action, shows
  truthful progress, polls and refreshes the rendered report, and reports
  success/failure without claiming delivery.
- Commands and exact results:
  - Focused backend: `python -B -m pytest -p no:cacheprovider -q
    tests/test_lead_service.py tests/test_structured_report.py` -> `28 passed,
    10 warnings in 2.14s` (final focused run). Warnings are existing Pydantic
    `json_encoders` deprecations from site-packages.
  - Complete backend: `python -B -m pytest -p no:cacheprovider -q` -> `238
    passed, 10 warnings in 26.21s`.
  - Frontend: `npm run build` -> passed; TypeScript checks succeeded and Vite
    transformed 1577 modules in 4.50s.
  - Scoped leased implementation/test `git diff --check -- ...` -> exit 0;
    only Git LF/CRLF conversion notices.
- Tests not run / unverified: no live LLM, search, PDF conversion, delivery
  queue, SMTP, production/staging database or deployment was invoked. All new
  external-model behavior is mocked. No stage, commit, push, deletion or
  destructive cleanup occurred.
- Risks: the deliberately isolated in-process background task is not a durable
  queue. A hard process termination after reservation can leave the report in
  `generating` until an administrator/repair flow clears it; adding durable
  regeneration-job persistence was explicitly outside this issue and lease.
  No known blocker remains for the accepted in-process workflow.
- Requested next state: Codex independently reviews TURN-0020 and accepts I-130
  when all acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-140-2

- Task: I-140
- Attempt: 1 (append-only landing record)
- Timestamp: 2026-08-28T01:39:23+08:00
- Allowed paths: all TURN-0021 leased paths in
  `docs/coordination/inbox/TURN-0021-request.md` and active
  `lease-turn-0021`.
- Changed paths and implementation evidence: the complete path list, behavior
  description, commands, artifact evidence, unverified items and risks are
  recorded in `DEV-I-140-1` and
  `docs/coordination/outbox/TURN-0021-handoff.md`. `DEV-I-140-1` accidentally
  landed after an earlier terminal marker instead of the absolute end; it has
  not been rewritten, removed or truncated. This complete landing record is
  appended at the absolute end.
- Summary: unified all five customer-report surfaces around the approved cover,
  compact score, charts, exactly five chapters, render-time M01-M09 judgments,
  short scene note and no-heading contact callout. Customer email PDF is strict
  DOCX-to-PDF with exactly three conversion attempts, zero email on exhaustion
  and an explicit manual state. The administrator attachment retry preserves AI
  content and rejects active/already-sent duplicates.
- Commands and exact results:
  - Final acceptance-focused backend -> `6 passed, 10 warnings in 1.69s`.
  - Final complete backend -> `246 passed, 10 warnings in 19.22s`.
  - `python -m compileall app` -> exit 0.
  - Frontend `npm run build` -> passed; 1579 modules transformed in 3.79s.
  - Synthetic fixture -> customer DOCX generated without database access;
    LibreOffice absence reported exactly and no browser attachment generated.
  - Word 2021 export -> 436168-byte, 6-page A4 PDF; all six Poppler-rendered
    pages visually inspected clean after the M01 chart-label repair.
  - Scoped leased tracked-path `git diff --check -- ...` -> exit 0; the two
    leased untracked files produced no whitespace findings under
    `git diff --no-index --check`.
- Not run / unverified: Ubuntu/Docker LibreOffice output, live LLM/search,
  production/staging data, real email, deployed flow and deployment were not
  exercised. No stage, commit, push, deletion or cleanup occurred.
- Risks / blockers: the deployment must provide LibreOffice; until then the
  intentional outcome is a visible manual-handling failure with zero email.
  Word 2021 visual proof passed, while LibreOffice pagination still requires an
  environment acceptance run.
- Requested next state: Codex independently reviews TURN-0021 using the handoff
  and accepts I-140 when all acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-110-1

- Task: I-110
- Attempt: 1
- Timestamp: 2026-08-27T11:31:36+08:00
- Allowed paths: all TURN-0018 leased paths listed in
  `docs/coordination/inbox/TURN-0018-request.md` and `lease-turn-0018`.
- Changed paths:
  - `backend/app/service/lead_export_service.py`
  - `backend/app/service/pdf_service.py`
  - `backend/tests/test_customer_docx_pdf.py`
  - `frontend/src/App.vue`
  - `frontend/src/styles.css`
  - `docs/coordination/DEVELOPMENT_LOG.md` (this append-only record)
  - `docs/coordination/outbox/TURN-0018-handoff.md`
- Summary: Implemented the approved compact editorial cover across customer
  DOCX, Chromium fallback and both online report entry points. The DOCX retains
  the `standard_business_brief` body preset and uses the named
  `approved_reference_editorial_cover` first-page override. The cover uses two
  navy title lines, a regular red subtitle, explicit wide rule and fixed
  borderless five-row metadata geometry, with no confidentiality wording,
  English kicker or top rule. Existing total/max/rate content now follows the
  cover. Accepted report body, chart, table, prose, scoring and API behavior are
  preserved.
- Commands actually run:
  - Focused backend -> `31 passed in 10.43s`.
  - Full backend -> `229 passed, 10 warnings in 31.08s`; warnings are existing
    Pydantic `json_encoders` deprecations from site-packages.
  - Frontend build -> passed; TypeScript checks succeeded and Vite transformed
    1577 modules in 4.90s.
  - Database-free fixture -> regenerated customer DOCX, fallback HTML/PDF and
    printed `跳过 PDF 转换：未找到 LibreOffice（soffice），无法执行 Word→PDF 转换`.
  - Packaged `render_docx.py --emit_pdf --verbose` with bundled Python -> failed
    in `subprocess.Popen` with
    `FileNotFoundError: [WinError 2] 系统找不到指定的文件。` because `soffice`
    is unavailable.
  - Word 2021 read-only export -> `WORD_EXPORT_OK`; 4 pages, A4
    (`595.32 x 841.92 pts`). Every rendered page was visually inspected with no
    clipping or overlap.
  - Final Chromium fallback -> 4 pages, A4 (`594.96 x 841.92 pts`), 223201
    bytes. Every rendered page was inspected; no orphan, clipping or overlap
    remained.
  - Route-isolated Playwright desktop -> document `scrollWidth=1440`; rule
    76.999% and metadata 63.999% of the 838px hero content; exactly five rows,
    no row overlap, score after cover and no forbidden text.
  - Route-isolated Playwright at 390 x 844 -> document/body `scrollWidth=390`;
    all cover elements and three 313px problem cards were inside the viewport,
    metadata and problem-card overlap checks were all false; console contained
    0 warnings and 0 errors. Both full-page screenshots were visually inspected.
  - Required leased implementation-path `git diff --check -- ...` -> exit 0;
    only Git LF/CRLF conversion notices.
- Not run / unverified: no LibreOffice-derived PDF exists because LibreOffice is
  not installed. Word 2021 plus all-page PNG review supplies the specified local
  fallback evidence. No deployment, production/staging/customer data access,
  real email, stage, commit, push or destructive cleanup occurred.
- Risks / blockers: none known within bounded TURN-0018. The local-testing-only
  regenerate button appears in the synthetic browser evidence but not customer
  production output.
- Requested next state: Codex independently reviews TURN-0018 and accepts I-110
  when the implementation, tests and visual artifacts satisfy the issue.

READY_FOR_REVIEW

## DEV-I-100-3

- Task: I-100
- Attempt: 3
- Timestamp: 2026-08-27T10:01:28+08:00
- Allowed paths: `frontend/src/components/ReportCharts.vue`,
  `frontend/src/styles.css`, `docs/coordination/DEVELOPMENT_LOG.md`
  (append-only), and `docs/coordination/outbox/TURN-0017-handoff.md`.
- Changed paths:
  - `frontend/src/components/ReportCharts.vue`
  - `frontend/src/styles.css`
  - `docs/coordination/DEVELOPMENT_LOG.md` (this append-only record)
  - `docs/coordination/outbox/TURN-0017-handoff.md`
- Summary: Repaired only the two online/mobile findings from `REV-I-100-1`.
  The narrow current-problem grid now becomes a readable one-column list with
  horizontal, separated labels and percentages. The scoped charts now use the
  approved flat white/navy/red/gray consulting system, and grid/canvas
  containment prevents mobile page overflow. Accepted TURN-0016 report content,
  Word/PDF/backend behavior and desktop information structure were preserved.
- Commands actually run:
  - `cd frontend && npm run build` -> passed; TypeScript checks succeeded and
    Vite transformed 1577 modules in 3.98s.
  - Route-isolated Playwright synthetic report at 1440 x 1100 -> document
    `scrollWidth=1440`, two 480px chart columns, two 434px canvases; screenshot
    visually inspected as sound.
  - Route-isolated Playwright synthetic report at 390 x 844 ->
    `innerWidth=390`, document and body `scrollWidth=390`; three problem cards
    were one 313px column, every label was `horizontal-tb`, every label-to-rate
    gap was 10px and every overlap check was false; two chart cards were 362px
    wide at x=14..376 and canvases were 328px wide at x=31..359, all inside the
    viewport. Console reported 0 warnings and 0 errors. The full-page mobile
    screenshot was visually inspected; labels, percentages and both charts were
    readable and non-overlapping.
  - `git diff --check -- frontend/src/components/ReportCharts.vue frontend/src/styles.css`
    -> exit 0; only Git LF/CRLF conversion notices.
- Browser artifacts:
  - `output/playwright/turn0017-desktop-1440.png`
  - `output/playwright/turn0017-mobile-390.png`
- Not run / unverified: no backend or document-generation suite was rerun because
  TURN-0017 is explicitly bounded to the two frontend findings. No deployment,
  production/customer data access, real email, stage, commit, push or destructive
  operation occurred.
- Risks / blockers: none known within the bounded TURN-0017 repair. The supplied
  Playwright wrapper is a Bash script and this Windows host has no Bash runtime,
  so the same documented `@playwright/cli` command used inside the wrapper was
  invoked directly through the verified `npx.ps1` prerequisite.
- Requested next state: Codex independently reviews TURN-0017 and accepts I-100
  when the two `REV-I-100-1` findings and the recorded measurements pass.

READY_FOR_REVIEW

## DEV-I-100-1

- Task: I-100
- Attempt: 1
- Timestamp: 2026-08-26T18:44:26+08:00
- Allowed paths: backend/app/service/lead_export_service.py,
  backend/app/service/pdf_service.py,
  backend/scripts/generate_customer_report.py,
  backend/tests/test_customer_docx_pdf.py,
  backend/tests/test_lead_export_structure.py,
  frontend/src/App.vue, frontend/src/styles.css,
  docs/coordination/DEVELOPMENT_LOG.md (append-only), and
  docs/coordination/outbox/TURN-0016-handoff.md.
- Changed paths:
  - backend/app/service/lead_export_service.py
  - backend/app/service/pdf_service.py
  - backend/scripts/generate_customer_report.py
  - backend/tests/test_customer_docx_pdf.py
  - frontend/src/App.vue
  - frontend/src/styles.css
  - docs/coordination/DEVELOPMENT_LOG.md (this append-only record)
  - docs/coordination/outbox/TURN-0016-handoff.md
- Summary:
  - Preserved the accepted I-090 report-format/version and report-contact
    changes already present in leased files; made no change to report prompts,
    section wording, scoring, snapshots, APIs, queueing or delivery policy.
  - Refined the shared Word renderer to an A4 executive-consulting system:
    white generous cover, navy hierarchy, restrained red rule/judgment accent,
    cool-gray metadata and zebra tables, fixed header/footer, flat score block,
    consistent charts, pagination controls and non-orphaning repeated table
    headers. Internal Word part three and customer DOCX still invoke the same
    `build_final_diagnosis_report` body renderer.
  - Replaced the Chromium fallback's dark gradient/dashboard treatment with a
    self-contained A4 print source using the same cover, score, heading, table,
    callout and chart vocabulary. Print page boundaries separate the cover,
    visual summary and report body; screen-only responsive rules no longer alter
    printed A4 grids.
  - Extended the database-free fixture to always produce customer DOCX,
    fallback HTML and validated Chromium PDF artifacts, while retaining the
    optional LibreOffice conversion path and manual hint when LibreOffice is
    unavailable.
  - Restyled the online report chrome and sanitized report body without
    changing `v-html`, data loading or application behavior. The online cover,
    scores, analysis panels, headings, tables and structured report blocks now
    use the same white/navy/red/light-gray system and remain responsive.
  - Added focused A4/color/pagination/no-dashboard/privacy/fixture artifact
    assertions. Existing ZIP/XML privacy sentinels and shared internal/customer
    layout-signature tests continue to pass.
- Commands actually run:
  - `python -B -m py_compile backend/app/service/lead_export_service.py backend/app/service/pdf_service.py backend/scripts/generate_customer_report.py`
    -> exit 0.
  - Initial focused backend command found one test-only XML accessor error:
    `1 failed, 29 passed in 10.34s`; implementation output was valid. After
    correcting the focused assertion, the final required command
    `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py tests/test_lead_export_structure.py`
    -> `30 passed in 9.43s`.
  - `cd backend && python -B scripts/generate_customer_report.py --fixture --outdir output/turn-0016`
    -> generated `奥飞娱乐_AI诊断报告.docx`,
    `奥飞娱乐_AI诊断报告-fallback.html` and validated
    `奥飞娱乐_AI诊断报告-fallback.pdf`; optional LibreOffice conversion was
    skipped with the expected actionable message because LibreOffice is absent.
  - `pdfinfo` on the final fallback -> 4 pages, A4
    (`594.96 x 841.92 pts`), readable Chromium PDF.
  - Microsoft Word 2021 read-only fixture export to ignored local
    `奥飞娱乐_AI诊断报告-word-review.pdf` -> succeeded; `pdfinfo` reports
    4 pages, A4 (`595.32 x 841.92 pts`). The cover and representative body
    pages from both renderers were rasterized with `pdftoppm` and visually
    inspected. The final Word inspection confirmed the repeated table header
    no longer orphans at the prior page boundary.
  - `cd backend && python -B -m pytest -p no:cacheprovider -q`
    -> `228 passed, 10 warnings in 27.37s`; warnings are existing Pydantic
    `json_encoders` deprecations in site-packages.
  - `cd frontend && npm run build` -> passed; Vue TypeScript check succeeded,
    Vite transformed 1577 modules and built in 4.62s.
  - Required leased-path `git diff --check -- ...` -> exit 0; only Git LF/CRLF
    conversion notices.
- Visual inspection findings:
  - Chromium cover: centered executive title on white, restrained red subtitle
    and rule, compact gray metadata matrix, flat three-column score band with
    only the score-rate judgment emphasized in red.
  - Chromium content: navy/red chart vocabulary, evidence-first navy table
    headers, gray zebra rows, crisp A4 margins and no gradient hero or rounded
    dashboard cards.
  - Word cover/body: same A4 hierarchy and palette; fixed navy/red header rule,
    centered page footer, navy tables, red section numbering/strong findings,
    matching ranking/radar charts, and clean multi-page table flow.
- Not run / unverified:
  - LibreOffice is not installed on this Windows host, so no real
    LibreOffice-produced PDF was generated. The Word 2021 A4 export visually
    verifies the DOCX itself, and the existing mocked LibreOffice command/filter
    tests plus full backend suite pass.
  - No online browser E2E screenshot was produced; responsive markup/styles
    compile through the production Vue build.
  - No deployment, production/staging data access, real email, stage, commit,
    push, destructive operation or customer-data fixture was used.
- Risks / blockers:
  - Linux LibreOffice may substitute Noto Sans CJK SC for Microsoft YaHei;
    container typography can differ slightly while retaining the tested layout,
    palette and shared renderer.
  - No blocker or human-intervention gate remains within TURN-0016.
- Requested next state: Codex independently reviews TURN-0016, reruns the
  acceptance checks, inspects the ignored local visual artifacts if desired,
  and accepts I-100 if satisfied.

READY_FOR_REVIEW

## DEV-I-090-1

- Task: I-090
- Attempt: 1
- Timestamp: 2026-08-26T11:22:52+08:00
- Allowed paths: active `lease-turn-0014` paths in `docs/coordination/OWNERSHIP.yaml`.
- Changed paths:
  - backend/ARCHITECTURE.md
  - backend/app/api/v1/endpoints/admin/__init__.py
  - backend/app/api/v1/endpoints/admin/system_settings.py
  - backend/app/models/__init__.py
  - backend/app/models/system_setting.py
  - backend/app/schemas/__init__.py
  - backend/app/schemas/system_setting.py
  - backend/app/repositories/system_setting_repo.py
  - backend/app/service/system_setting_service.py
  - backend/app/service/reporting.py
  - backend/app/service/pdf_service.py
  - backend/migrations/versions/3e7d1b9c5a20_add_report_contact_settings.py
  - backend/tests/test_system_settings.py
  - frontend/src/App.vue
  - frontend/src/api.ts
  - frontend/src/composables/useAdmin.ts
  - frontend/src/styles.css
  - frontend/src/types.ts
- Summary:
  - Added an administrator-only singleton report-contact settings domain through API, service, repository, model, schema and Alembic migration layers, plus a responsive admin "系统设置" screen.
  - New and explicitly regenerated reports persist `report_format_version = 2` and a trimmed contact snapshot in `summary_json`. Empty fields and the all-empty contact block are omitted. The contact metadata is excluded from the LLM prompt.
  - Version 2 reports use the exact cautious section-five disclaimer, retain dynamic evidence-backed scene suggestions and expected benefits, and omit management actions from the prompt contract, validation and rendering. Legacy reports without a format version retain their historical fifth and sixth sections.
  - HTML, customer Word, converted PDF and email attachment paths continue to derive from persisted report HTML/summary rather than live settings, preserving prior report snapshots and later setting-change immutability.
  - Added focused coverage for GET/PUT authorization, trimming and persistence, partial/all-empty settings, generation-time snapshot persistence, snapshot immutability, exact wording, renderer-only prompt metadata exclusion, legacy compatibility and Word output.
- Commands actually run:
  - `cd backend && ..\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q tests/test_system_settings.py tests/test_structured_report.py tests/test_report_content.py tests/test_report_structure_validation.py tests/test_customer_docx_pdf.py tests/test_pdf_delivery_gate.py tests/test_lead_export_structure.py` -> `52 passed, 16 warnings in 6.47s`.
  - `cd backend && ..\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q` -> `223 passed, 2 failed, 46 warnings in 17.77s`. Both failures are in `tests/test_migration_chain.py` because its unleased `HEAD_REVISION` constant remains `8279863b17cb`; the migration command itself succeeds and records the actual new head `3e7d1b9c5a20` in both tests.
  - `cd frontend && npm run build` -> exit 0; Vue type-check and Vite build passed, 1577 modules transformed.
  - `cd backend && ..\.venv\Scripts\python.exe -m alembic heads` -> `3e7d1b9c5a20 (head)`.
  - `.\.venv\Scripts\python.exe -m compileall -q backend/app backend/migrations/versions/3e7d1b9c5a20_add_report_contact_settings.py` -> exit 0.
  - `git diff --check` -> exit 0; only Git line-ending conversion warnings.
  - An additional `alembic upgrade head --sql` offline check was attempted and stopped in pre-existing migration `5d4...`, which uses database reflection unsupported by Alembic's offline mock connection. This does not affect the required online migration-chain runs above.
- Not run / unverified:
  - No production deployment, production/staging data access, real email, stage, commit or push.
  - No manual browser interaction was needed; the admin UI was type-checked and production-built.
- Risks / blockers:
  - `backend/tests/test_migration_chain.py` is not part of `lease-turn-0014`, while the protocol forbids editing unleased paths. Its hard-coded head revision must be updated to `3e7d1b9c5a20` under an expanded or follow-up lease before the full backend suite can pass.
  - Application implementation and focused acceptance coverage are complete; no other code-review finding remains.
- Requested next state: expand or issue a bounded follow-up lease containing `backend/tests/test_migration_chain.py`, update its head expectation, rerun the full suite, then review I-090.

BLOCKED

## DEV-I-160-1

- Task: I-160
- Attempt: 1 (TURN-0024 P1 attachment-only delivery repair)
- Timestamp: 2026-08-28T12:16:24+08:00
- Run / sender / recipient: `backend-architecture-hardening-20260822` /
  `claude_code` / `codex`.
- Allowed paths: `backend/app/service/report_queue.py`,
  `backend/tests/test_lead_service.py`,
  `backend/tests/test_pdf_delivery_gate.py`,
  `docs/coordination/DEVELOPMENT_LOG.md` (append-only), and
  `docs/coordination/outbox/TURN-0024-handoff.md`.
- Changed paths: all five allowed paths listed above. No forbidden path was
  edited by this worker.
- Summary: aligned the queue's reusable-body condition with the administrator
  attachment retry gate. Both `generated` and `fallback` reports with non-empty
  persisted HTML now skip research and AI generation. Regression coverage
  proves the fallback status, exact HTML and stored content metadata remain
  unchanged while mocked PDF rendering and email sending each execute once;
  the administrator retry test now covers both reusable statuses.
- Commands and exact results:
  - New/adjacent focused cases: `4 passed, 10 warnings in 2.07s`.
  - Complete affected delivery/service files plus existing queue tests:
    `52 passed, 10 warnings in 3.87s`.
  - `python -m compileall -q app tests` exited 0.
  - Complete backend `python -m pytest -q`:
    `248 passed, 10 warnings in 25.28s`.
  - Scoped `git diff --check` exited 0; output contained only Git LF/CRLF
    conversion notices.
- Tests not run / unverified: no live research, model, DOCX/PDF converter,
  SMTP, customer/production data, deployment or external service was used.
  No stage, commit, push, deletion or destructive cleanup occurred.
- Known risks: none known within I-160. This change intentionally retains the
  existing research/generation behavior for missing or incomplete bodies.
- Requested next state: Codex independently reviews TURN-0024 and accepts
  I-160 when all acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-170-2

- Task: I-170
- Attempt: 1 (absolute-end append-only landing record)
- Timestamp: 2026-08-28T13:46:14+08:00
- Allowed paths: all TURN-0025 paths in active `lease-turn-0025`.
- Changed paths and evidence: `DEV-I-170-1` and
  `docs/coordination/outbox/TURN-0025-handoff.md` contain the complete changed
  path list, implementation evidence, exact commands, unverified items and
  risks. `DEV-I-170-1` was appended after an earlier terminal marker rather
  than the absolute end; it has not been rewritten, removed or truncated. This
  complete record is appended at the absolute end.
- Summary: stale content-only regeneration can be safely retriggered after a
  conservative timeout; audited prior status is preserved, and old background
  tasks are fenced by exact generation-start timestamp on success and failure.
- Commands and exact results: focused lead-service suite `29 passed, 10
  warnings in 3.34s`; complete backend `251 passed, 10 warnings in 20.84s`;
  `python -m compileall -q app tests` exit 0; scoped `git diff --check` exit 0
  with only LF/CRLF conversion notices.
- Tests not run / unverified: no live services, customer/production data,
  email, deployment, stage, commit, push, deletion or cleanup.
- Risks / blockers: none known within I-170; recovery intentionally waits for
  the conservative stale threshold because execution remains in-process.
- Requested next state: Codex independently reviews TURN-0025 and accepts I-170
  when all acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-090-3

- Task: I-090
- Attempt: 3
- Timestamp: 2026-08-26T11:31:14+08:00
- Allowed paths: backend/app/api/v1/endpoints/admin/system_settings.py,
  backend/tests/test_system_settings.py, backend/tests/test_migration_chain.py,
  frontend/src/composables/useAdmin.ts,
  docs/coordination/DEVELOPMENT_LOG.md (append-only), and
  docs/coordination/outbox/TURN-0015-handoff.md.
- Changed paths:
  - backend/app/api/v1/endpoints/admin/system_settings.py
  - backend/tests/test_system_settings.py
  - backend/tests/test_migration_chain.py
  - frontend/src/composables/useAdmin.ts
  - docs/coordination/DEVELOPMENT_LOG.md
  - docs/coordination/outbox/TURN-0015-handoff.md
- Summary:
  - Updated the migration-chain expectation from the previous revision to the
    current single Alembic head `3e7d1b9c5a20`.
  - Replaced compatibility imports in the system-settings endpoint and focused
    test with canonical database, model, schema, and reporting module imports.
  - Added a defensive `loadAdminTab` redirect: a non-admin programmatic request
    for `settings` resolves to `overview` before tab state or API loading occurs.
    The backend `AdminOnly` dependency remains the authoritative authorization
    boundary.
- Commands actually run:
  - `cd backend && ..\\.venv\\Scripts\\python.exe -B -m pytest -p no:cacheprovider -q tests/test_system_settings.py tests/test_migration_chain.py`
    -> `10 passed, 16 warnings in 7.18s` on the final imports.
  - `cd backend && ..\\.venv\\Scripts\\python.exe -B -m pytest -p no:cacheprovider -q`
    -> `225 passed, 46 warnings in 16.77s`.
  - `cd frontend && npm run build` -> passed; TypeScript check completed and
    Vite transformed 1577 modules in 3.73s.
  - `cd backend && ..\\.venv\\Scripts\\python.exe -B -m alembic -c alembic.ini heads`
    -> `3e7d1b9c5a20 (head)`.
  - `git diff --check` -> exit 0; only Git line-ending conversion warnings.
- Not run / unverified: no deployment, production/staging data access, real
  email, stage, commit or push. No browser E2E test was added because this
  bounded repair has no leased frontend test path; the TypeScript production
  build verifies the guard compiles.
- Risks / blockers: none known within this bounded repair.
- Requested next state: Codex independently reviews TURN-0015 and accepts I-090
  if the three REV-I-090-1 findings and acceptance checks pass.

READY_FOR_REVIEW

## DEV-I-080-1

- Task: I-080
- Attempt: 1
- Timestamp: 2026-08-23T20:53:14+08:00
- Allowed paths: backend/app/service/lead_export_service.py, backend/app/service/pdf_service.py, backend/app/core/config.py, backend/Dockerfile, backend/.env.example, .env.production.example, .env.staging.example, backend/ARCHITECTURE.md, backend/scripts/generate_customer_report.py, backend/tests/test_customer_docx_pdf.py, backend/tests/test_pdf_delivery_gate.py, backend/tests/test_lead_export_structure.py, docs/coordination/DEVELOPMENT_LOG.md (append-only), docs/coordination/outbox/TURN-0010-handoff.md
- Changed paths:
  - backend/app/service/lead_export_service.py
  - backend/app/service/pdf_service.py
  - backend/app/core/config.py
  - backend/Dockerfile
  - backend/.env.example
  - .env.production.example
  - .env.staging.example
  - backend/ARCHITECTURE.md
  - backend/scripts/generate_customer_report.py
  - backend/tests/test_customer_docx_pdf.py
  - backend/tests/test_lead_export_structure.py
- Summary:
  - Extracted `build_final_diagnosis_report` as the one Word renderer used by internal Word part three and the customer-only DOCX. The customer document adds a fixed-layout navy/gray business header with persisted report metadata and score snapshot, then reuses the same headings, tables, widths, fonts, spacing, page break and two chart builders.
  - Customer DOCX construction receives only the company name plus final report fields; focused ZIP/XML sentinel tests prove contact, phone, email, WeChat, source, search/research and admin/view sentinels never enter the package.
  - Formal delivery now snapshots ORM-backed report values on the owning thread, builds DOCX/fallback HTML bytes before background conversion, and passes only bytes to `asyncio.to_thread`, avoiding cross-thread SQLAlchemy lazy loads.
  - Added isolated LibreOffice input/output/profile directories, bounded 10-600 second timeout, executable discovery, `pdf:writer_pdf_Export`, stdout/stderr diagnostics, cleanup, and configuration-controlled Chromium fallback that preserves the LibreOffice root error whenever fallback is disabled or browser rendering is unavailable.
  - Added LibreOffice Writer, fontconfig and Noto CJK to the report-worker image; documented the Microsoft YaHei to Noto Sans CJK SC Linux fallback; exposed DOCX/fallback/LibreOffice variables in all three environment templates.
  - Added a database-free `--fixture` command for an 奥飞娱乐 DOCX and optional locally converted PDF, plus fixed-layout, shared-layout-signature, score, isolation, filename, conversion, timeout, cleanup, fallback and ORM-thread-boundary tests.
- Commands actually run:
  - `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py tests/test_pdf_delivery_gate.py tests/test_lead_export_structure.py tests/test_report_queue_claim.py` -> `44 passed in 6.36s`.
  - `cd backend && python -B -m pytest -p no:cacheprovider -q` -> `211 passed, 9 warnings in 18.23s`; warnings are pre-existing Pydantic `json_encoders` deprecations in site-packages.
  - `docker compose config --no-env-resolution -q` -> exit 0.
  - `docker compose --profile staging config --no-env-resolution -q` -> exit 0.
  - Exact `docker compose config` and `docker compose --profile staging config` -> could not resolve because this checkout intentionally has no local `.env.production` / `.env.staging` files; no env files were created or secrets accessed.
  - `git diff --check -- <all leased tracked implementation paths>` -> exit 0 (only line-ending warnings).
  - Exact repository-wide `git diff --check` -> one pre-existing/orchestrator-owned failure at `docs/coordination/MILESTONES.md:29` (`Issues: I-080, I-060` trailing spaces); worker did not modify the forbidden orchestration file.
  - `docker build --check -f backend/Dockerfile backend` -> not executed successfully because Docker Desktop Linux daemon is unavailable (`npipe:////./pipe/dockerDesktopLinuxEngine` missing); no image build was attempted afterward per orchestrator instruction.
- Not run / unverified:
  - No real LibreOffice conversion or visual PDF comparison on this Windows host because LibreOffice is not installed and Docker daemon is unavailable. The subprocess invocation, Writer filter, isolated directories/profile, diagnostics and cleanup are covered with focused tests; fixture DOCX generation is exercised in a subprocess without database queries.
  - No deployment, production/staging data access, real email, commit, stage or push.
- Risks / blockers:
  - Container font substitution uses the distributable Noto Sans CJK SC fallback rather than shipping proprietary Microsoft YaHei; final visual parity should be checked once in the built Linux image.
  - Exact Compose config needs local env files supplied by the human/deployment environment. Repository-wide diff check needs the orchestrator-owned trailing whitespace removed after this writer exits.

READY_FOR_REVIEW
```

Use `BLOCKED` instead of `READY_FOR_REVIEW` only when a protocol human-intervention
gate applies. Do not write a record until all fields are complete.

## DEV-I-070-1

- Task: I-070
- Attempt: 1
- Timestamp: 2026-08-23T00:52:32+08:00
- Allowed paths: backend/app/api/v1/endpoints/public.py, backend/tests/test_lead_reroll.py, docs/coordination/DEVELOPMENT_LOG.md (append-only)
- Changed paths:
  - backend/app/api/v1/endpoints/public.py
  - backend/tests/test_lead_reroll.py
- Summary:
  - Replaced the deprecated naive `datetime.utcnow()` in `enforce_email_lead_limit`
    with the canonical `utc_now()` helper from `app.utils.time_utils`
    (`datetime.now(timezone.utc).replace(tzinfo=None)`), keeping the one-hour
    window, the case-insensitive email match, and the current-lead exclusion
    unchanged. `utc_now()` returns a naive UTC datetime, so the cutoff stays
    compatible with MySQL DATETIME values and SQLite test fixtures.
  - `from datetime import datetime, timedelta` became `from datetime import
    timedelta` (datetime no longer referenced); added
    `from app.utils.time_utils import utc_now`.
  - Added focused regression test
    `test_email_hourly_limit_cutoff_uses_utc_now_helper` in
    backend/tests/test_lead_reroll.py: monkeypatches `public.utc_now` to a fixed
    naive UTC clock (2020-01-01 12:00:00) and asserts (a) 3 leads within the
    hour raise 429, (b) excluding the current lead drops the count to 2 and
    passes, (c) 10 leads older than one hour are not counted. If the
    implementation fell back to `datetime.utcnow()`, the fixed past clock would
    place the "within-hour" leads outside the real cutoff and the test would
    fail, proving the helper is consulted.
  - Note: public.py carried pre-existing uncommitted changes from earlier work;
    this turn only touched the three lines described above.
- Commands actually run:
  - `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_lead_reroll.py`
    -> `4 passed, 5 warnings in 1.32s` (warnings are pre-existing Pydantic
    `json_encoders` deprecations in site-packages).
  - `grep -n "utcnow|datetime" backend/app/api/v1/endpoints/public.py`
    -> only `15:from datetime import timedelta`; no `datetime.utcnow()` remains.
- Not run / unverified:
  - Full backend test suite not run (out of scope; only the required focused
    test was executed).
  - No runtime HTTP check of the endpoint; behavior verified via direct function
    call against an in-memory SQLite engine.
- Risks / blockers: none.

READY_FOR_REVIEW

## DEV-I-080-2

- Task: I-080
- Attempt: 2
- Timestamp: 2026-08-23T20:56:00+08:00
- Allowed paths: backend/app/service/lead_export_service.py, backend/app/service/pdf_service.py, backend/app/core/config.py, backend/Dockerfile, backend/.env.example, .env.production.example, .env.staging.example, backend/ARCHITECTURE.md, backend/scripts/generate_customer_report.py, backend/tests/test_customer_docx_pdf.py, backend/tests/test_pdf_delivery_gate.py, backend/tests/test_lead_export_structure.py, docs/coordination/DEVELOPMENT_LOG.md (append-only), docs/coordination/outbox/TURN-0010-handoff.md
- Changed paths: docs/coordination/DEVELOPMENT_LOG.md only in this attempt; this attempt only repairs the log landing position and makes no additional application-code change. Application changes from TURN-0010 remain in the leased paths listed in `docs/coordination/outbox/TURN-0010-handoff.md`.
- Summary: Only repaired the development-log landing point by appending this complete record at the absolute end of the file. No application code, test, environment template, Dockerfile, architecture document, fixture script, or handoff content was changed in Attempt 2.
- Commands actually run (reused completed TURN-0010 validation evidence; no command was rerun in this log-only attempt):
  - `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py tests/test_pdf_delivery_gate.py tests/test_lead_export_structure.py tests/test_report_queue_claim.py` -> `44 passed in 6.36s`.
  - `cd backend && python -B -m pytest -p no:cacheprovider -q` -> `211 passed, 9 warnings in 18.23s`; warnings are pre-existing Pydantic `json_encoders` deprecations.
  - `docker compose config --no-env-resolution -q` -> exit 0.
  - `docker compose --profile staging config --no-env-resolution -q` -> exit 0.
  - Leased implementation paths passed `git diff --check` (line-ending warnings only).
- Not run / unverified: Exact Compose config remains unavailable because local `.env.production` / `.env.staging` files are absent; Docker daemon remains unavailable, so no image build or real LibreOffice visual conversion was run. No deployment, production/staging data access, real email, stage, commit or push occurred.
- Risks / blockers: Repository-wide `git diff --check` still has only the orchestrator-owned `docs/coordination/MILESTONES.md:29` trailing whitespace. Container font substitution and final PDF visual parity still require verification in a built Linux image.

READY_FOR_REVIEW

## DEV-I-090-2

- Task: I-090
- Attempt: 2
- Timestamp: 2026-08-26T11:22:52+08:00
- Allowed paths: `docs/coordination/DEVELOPMENT_LOG.md` (append-only) and the existing `lease-turn-0014` implementation paths.
- Changed paths: `docs/coordination/DEVELOPMENT_LOG.md` only in this attempt. This entry repairs the completion-record landing point at the absolute end of the append-only log; application changes and verification evidence remain exactly as recorded in `DEV-I-090-1` and `docs/coordination/outbox/TURN-0014-handoff.md`.
- Summary: No application code, migration, test, frontend or handoff content changed in Attempt 2. The I-090 implementation is complete within its lease, but full-suite acceptance remains blocked by the stale hard-coded Alembic head in unleased `backend/tests/test_migration_chain.py`.
- Commands actually run: no command was rerun in this log-only attempt. Final evidence remains focused backend `52 passed, 16 warnings in 6.47s`; full backend `223 passed, 2 failed, 46 warnings in 17.77s`; frontend build passed; Alembic reports `3e7d1b9c5a20 (head)`; compileall and `git diff --check` passed.
- Not run / unverified: no deployment, production/staging access, real email, stage, commit or push.
- Risks / blockers: changing `HEAD_REVISION = "8279863b17cb"` to `"3e7d1b9c5a20"` requires a lease expansion or bounded follow-up lease for `backend/tests/test_migration_chain.py`.
- Requested next state: expand the lease for that single test file, update the expected head, rerun the full backend suite, and review I-090.

BLOCKED

## DEV-I-090-4

- Task: I-090
- Attempt: 4
- Timestamp: 2026-08-26T11:32:00+08:00
- Allowed paths: backend/app/api/v1/endpoints/admin/system_settings.py,
  backend/tests/test_system_settings.py, backend/tests/test_migration_chain.py,
  frontend/src/composables/useAdmin.ts,
  docs/coordination/DEVELOPMENT_LOG.md (append-only), and
  docs/coordination/outbox/TURN-0015-handoff.md.
- Changed paths: `docs/coordination/DEVELOPMENT_LOG.md` only in this landing-point
  repair. The TURN-0015 application/test changes are recorded in DEV-I-090-3
  and `docs/coordination/outbox/TURN-0015-handoff.md`.
- Summary: Appended this complete completion marker at the absolute end after
  DEV-I-090-3 landed before the prior terminal record. TURN-0015 changed the
  migration expected head to `3e7d1b9c5a20`, adopted canonical imports in the
  endpoint/test, and redirected non-admin `settings` tab requests to `overview`.
- Commands actually run:
  - Focused backend -> `10 passed, 16 warnings in 7.18s`.
  - Full backend -> `225 passed, 46 warnings in 16.77s`.
  - Frontend build -> passed; 1577 modules transformed in 3.73s.
  - Alembic heads -> `3e7d1b9c5a20 (head)`.
  - Final repository `git diff --check` -> exit 0 with line-ending warnings only.
- Not run / unverified: no browser E2E test was added within this bounded lease.
  No deployment, production/staging data access, real email, stage, commit or
  push occurred.
- Risks / blockers: none known within the bounded TURN-0015 repair.
- Requested next state: Codex independently reviews TURN-0015 and accepts I-090
  if the three REV-I-090-1 findings pass.

READY_FOR_REVIEW

## DEV-I-100-2

- Task: I-100
- Attempt: 2
- Timestamp: 2026-08-27T09:44:05+08:00
- Allowed paths: all TURN-0016 leased paths listed in
  `docs/coordination/inbox/TURN-0016-request.md` and `lease-turn-0016`.
- Changed paths in this landing-point repair:
  - `docs/coordination/DEVELOPMENT_LOG.md` (append-only record)
  - `docs/coordination/outbox/TURN-0016-handoff.md`
- Application changes: no application or test implementation changed in this
  landing-point repair. The complete I-100 implementation paths and description
  are recorded in `DEV-I-100-1` and
  `docs/coordination/outbox/TURN-0016-handoff.md`. `DEV-I-100-1` landed before
  the prior absolute end during the interrupted root turn; it was not rewritten,
  truncated or removed. This complete record is appended at the absolute end.
- Commands actually rerun after resuming TURN-0016:
  - `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py tests/test_lead_export_structure.py`
    -> `30 passed in 15.00s`.
  - `cd backend && python -B -m pytest -p no:cacheprovider -q`
    -> `228 passed, 10 warnings in 24.72s`; warnings are existing Pydantic
    `json_encoders` deprecations in site-packages.
  - `cd frontend && npm run build` -> passed; TypeScript checks succeeded and
    Vite transformed 1577 modules in 4.06s.
  - `cd backend && python -B scripts/generate_customer_report.py --fixture --outdir output/turn-0016`
    -> regenerated customer DOCX, fallback HTML and validated Chromium fallback
    PDF without a database query. LibreOffice remained unavailable and printed
    the expected manual conversion guidance.
  - Final Chromium fixture PDF -> 4 pages, A4
    (`594.96 x 841.92 pts`); final Word 2021 read-only DOCX review export ->
    4 pages, A4 (`595.32 x 841.92 pts`). `pdftoppm` cover/page-3 images from
    both outputs were visually inspected. White/navy/red/light-gray hierarchy,
    tables and charts were intact, and the Word workshop table heading, repeated
    header and first row stayed together after the pagination fix.
  - Required leased implementation-path `git diff --check -- ...` -> exit 0;
    only Git LF/CRLF conversion notices.
- Not run / unverified: LibreOffice is not installed, so no real LibreOffice PDF
  was generated; no online browser E2E screenshot was taken. No deployment,
  production/staging data access, real email, stage, commit, push or destructive
  operation occurred.
- Risks / blockers: no blocker or human-intervention gate remains. Minor Linux
  font-metric differences may occur when LibreOffice substitutes Noto Sans CJK
  SC for Microsoft YaHei.
- Requested next state: Codex independently reviews TURN-0016 using the complete
  handoff and accepts I-100 when acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-100-4

- Task: I-100
- Attempt: 4
- Timestamp: 2026-08-27T10:05:42+08:00
- Allowed paths: `frontend/src/components/ReportCharts.vue`,
  `frontend/src/styles.css`, `docs/coordination/DEVELOPMENT_LOG.md`
  (append-only), and `docs/coordination/outbox/TURN-0017-handoff.md`.
- Changed paths in this landing-point repair:
  - `docs/coordination/DEVELOPMENT_LOG.md` (this append-only record)
  - `docs/coordination/outbox/TURN-0017-handoff.md`
- Application changes: no implementation changed in this landing-point repair.
  The complete TURN-0017 implementation and validation evidence are recorded in
  `DEV-I-100-3` and `docs/coordination/outbox/TURN-0017-handoff.md`.
  `DEV-I-100-3` accidentally landed after an earlier terminal marker rather than
  the absolute end; it was not rewritten, truncated or removed. This complete
  record is appended at the absolute end.
- Summary: TURN-0017 makes the narrow current-problem cards a readable one-column
  list with horizontal, separated labels and percentages; restyles the scoped
  charts to the approved flat white/navy/red/gray consulting system; and adds
  grid/canvas containment so the 390px route has no horizontal overflow.
- Commands actually run before this landing-point repair:
  - `cd frontend && npm run build` -> passed; TypeScript checks succeeded and
    Vite transformed 1577 modules in 3.98s.
  - Route-isolated Playwright synthetic report at 1440 x 1100 -> document
    `scrollWidth=1440`, two 480px chart columns and two 434px canvases; full-page
    screenshot visually inspected as sound.
  - Route-isolated Playwright synthetic report at 390 x 844 ->
    `innerWidth=390`, document/body `scrollWidth=390`; problem grid was one
    313px column, all three labels were `horizontal-tb`, all label-to-rate gaps
    were 10px, and all overlap checks were false; chart cards were 362px wide
    and canvases 328px wide, entirely inside the viewport. The full-page mobile
    screenshot was visually inspected as readable and non-overlapping.
  - Playwright console collection -> 0 warnings and 0 errors.
  - `git diff --check -- frontend/src/components/ReportCharts.vue frontend/src/styles.css`
    -> exit 0; only Git LF/CRLF conversion notices.
- Browser artifacts:
  - `output/playwright/turn0017-desktop-1440.png`
  - `output/playwright/turn0017-mobile-390.png`
- Not run / unverified: no backend or document-generation suite was rerun because
  TURN-0017 is explicitly bounded to the two frontend findings. No deployment,
  production/customer data access, real email, stage, commit, push or destructive
  operation occurred.
- Risks / blockers: none known within the bounded TURN-0017 repair. The supplied
  Playwright wrapper is a Bash script and this Windows host has no Bash runtime,
  so its equivalent documented `@playwright/cli` invocation was run directly
  through the verified `npx.ps1` prerequisite.
- Requested next state: Codex independently reviews TURN-0017 and accepts I-100
  when the two `REV-I-100-1` findings and recorded measurements pass.

READY_FOR_REVIEW

## DEV-I-110-2

- Task: I-110
- Attempt: 2
- Timestamp: 2026-08-27T11:33:10+08:00
- Allowed paths: all TURN-0018 leased paths listed in
  `docs/coordination/inbox/TURN-0018-request.md` and `lease-turn-0018`.
- Changed paths in this landing-point repair:
  - `docs/coordination/DEVELOPMENT_LOG.md` (this append-only record)
  - `docs/coordination/outbox/TURN-0018-handoff.md`
- Application changes: no application or test implementation changed in this
  landing-point repair. The complete TURN-0018 implementation paths, design
  decisions and validation evidence are recorded in `DEV-I-110-1` and
  `docs/coordination/outbox/TURN-0018-handoff.md`. `DEV-I-110-1` accidentally
  landed after an earlier terminal marker rather than the absolute end; it was
  not rewritten, truncated or removed. This complete record is appended at the
  absolute end.
- Summary: TURN-0018 applies the approved compact editorial cover to customer
  DOCX, Chromium fallback and both online-report variants. It keeps the
  `standard_business_brief` body and named
  `approved_reference_editorial_cover` override, explicit A4 geometry, exactly
  five borderless compact metadata rows, no confidentiality/English kicker/top
  rule, and moves the existing total/max/rate score below the cover.
- Commands actually run before this landing-point repair:
  - Focused backend -> `31 passed in 10.43s`.
  - Full backend -> `229 passed, 10 warnings in 31.08s`; warnings are existing
    Pydantic `json_encoders` deprecations from site-packages.
  - Frontend build -> passed; TypeScript checks succeeded and Vite transformed
    1577 modules in 4.90s.
  - Database-free fixture -> regenerated DOCX, fallback HTML/PDF and reported
    the expected missing-LibreOffice manual conversion guidance.
  - Packaged `render_docx.py` attempt -> exact blocking exception
    `FileNotFoundError: [WinError 2] 系统找不到指定的文件。` from missing
    `soffice`.
  - Word 2021 read-only review export -> 4 A4 pages
    (`595.32 x 841.92 pts`); all pages visually inspected without clipping or
    overlap.
  - Final Chromium fallback -> 4 A4 pages (`594.96 x 841.92 pts`), 223201 bytes;
    all pages visually inspected without orphaned, clipped or overlapping
    content.
  - Route-isolated synthetic Playwright -> desktop document
    `scrollWidth=1440`, rule 76.999%, metadata 63.999%, exactly five rows; mobile
    at 390 x 844 had document/body `scrollWidth=390`, all cover elements and
    three 313px problem cards inside the viewport, all overlap checks false,
    and console 0 warnings/0 errors. Both screenshots were visually inspected.
  - Required leased implementation-path `git diff --check -- ...` -> exit 0;
    only Git LF/CRLF conversion notices.
- Not run / unverified: LibreOffice is not installed, so no LibreOffice-derived
  PDF exists. The required fallback evidence is Word 2021 plus all-page PNG
  review. No deployment, production/staging/customer data access, real email,
  stage, commit, push or destructive cleanup occurred.
- Risks / blockers: none known within bounded TURN-0018.
- Requested next state: Codex independently reviews TURN-0018 using the complete
  handoff and accepts I-110 when all acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-120-1

- Task: I-120
- Attempt: 1
- Timestamp: 2026-08-27T12:58:10+08:00
- Allowed paths: all TURN-0019 leased paths listed in
  `docs/coordination/inbox/TURN-0019-request.md` and `lease-turn-0019`.
- Changed paths:
  - `backend/app/service/lead_export_service.py`
  - `backend/app/service/pdf_service.py`
  - `backend/scripts/generate_customer_report.py`
  - `backend/tests/test_customer_docx_pdf.py`
  - `frontend/src/App.vue`
  - `frontend/src/components/ReportCharts.vue`
  - `frontend/src/styles.css`
  - `docs/coordination/DEVELOPMENT_LOG.md` (this append-only record)
  - `docs/coordination/outbox/TURN-0019-handoff.md`
- Summary: implemented the screenshot-authoritative native Word cover and the
  supplied PDF's reference-aligned editorial body system while preserving the
  report's prose, scores and content order. The full legal company name remains
  visible, the display title is adaptively shortened, exactly five metadata rows
  use a Chinese date, forbidden cover copy is absent, score content remains below
  the cover, and Word/fallback/online outputs share the navy/red/blue/gray token
  system. The fallback was rebalanced to keep score + executive summary + bar
  chart on page 2, radar + analysis on page 3 and remaining sections on page 4.
- Commands and exact results:
  - Required Documents and PDF artifact markers each completed once immediately
    before their first authoring action.
  - Final focused backend -> `34 passed in 9.88s`.
  - Final complete backend -> `231 passed, 10 warnings in 51.03s`; warnings are
    existing Pydantic `json_encoders` deprecations from site-packages.
  - Frontend `npm run build` -> passed; TypeScript checks succeeded and Vite
    transformed 1577 modules in 4.03s.
  - Database-free fixture -> generated the full-legal-name DOCX, fallback HTML
    and fallback PDF in `backend/output/turn-0019`; no database was accessed.
  - Bundled `render_docx.py` attempt -> exact result
    `FileNotFoundError: [WinError 2] 系统找不到指定的文件。` because
    `soffice` is unavailable.
  - Word 2021 read-only export -> `WORD_EXPORT_OK`; 4 A4 pages
    (`595.32 x 841.92 pts`, 354918 bytes), all visually inspected clean.
  - Final Chromium fallback -> 4 A4 pages (`594.96 x 841.92 pts`, 246697
    bytes), all final balanced pages visually inspected clean.
  - Route-isolated synthetic Playwright desktop -> `scrollWidth=1440` at 1440px,
    correct cover/body tokens, no card overlap or overflow; mobile -> viewport,
    document and body widths all 390px, three `313 x 72px` cards at x=`40..353`
    with 10px vertical gaps, empty overflow scan; console 0 warnings/0 errors.
  - Required leased-path `git diff --check -- ...` -> exit 0; only Git LF/CRLF
    conversion notices.
- Review artifacts:
  - `backend/output/turn-0019/奥飞娱乐股份有限公司_AI诊断报告.docx`
  - `backend/output/turn-0019/奥飞娱乐股份有限公司_AI诊断报告-word-review.pdf`
  - `backend/output/turn-0019/word-review-pages/page-1.png` through `page-4.png`
  - `backend/output/turn-0019/奥飞娱乐股份有限公司_AI诊断报告-fallback.pdf`
  - `backend/output/turn-0019/fallback-pages-balanced-v2/page-1.png` through
    `page-4.png`
  - `output/playwright/turn-0019-desktop-1440-final.png`
  - `output/playwright/turn-0019-mobile-390.png`
- Not run / unverified: LibreOffice is not installed, so the Word visual proof is
  the Word 2021 read-only export. No deployment, production/staging/customer
  data access, real email, stage, commit, push, deletion or destructive cleanup
  occurred.
- Risks / blockers: no known blocker remains within bounded TURN-0019. The
  Chromium fallback's quiet centered footer label cannot expose Word's PAGE
  field; the customer DOCX/Word export contains the real centered page number.
- Requested next state: Codex independently reviews TURN-0019 using
  `docs/coordination/outbox/TURN-0019-handoff.md` and accepts I-120 when all
  acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-130-2

- Task: I-130
- Attempt: 1 (append-only landing record)
- Timestamp: 2026-08-27T14:54:05+08:00
- Allowed paths: all TURN-0020 leased paths in
  `docs/coordination/inbox/TURN-0020-request.md` and `lease-turn-0020`.
- Changed paths and implementation evidence: the complete record
  `DEV-I-130-1` and `docs/coordination/outbox/TURN-0020-handoff.md` enumerate
  the leased backend, frontend, test, architecture and coordination paths.
  `DEV-I-130-1` was accidentally inserted after an earlier terminal marker
  instead of the absolute end; it has not been rewritten, removed or truncated.
- Summary: implemented administrator-only, content-only AI-report regeneration
  using a side-effect-free validated candidate and transactional replacement.
  Missing/invalid research, duplicate generation and active delivery conflicts
  are rejected. Failure preserves the old report; success marks PDF pending and
  neither creates delivery work nor sends email. The adjacent admin UI button
  confirms, polls, refreshes and uses truthful non-delivery copy.
- Commands and exact results:
  - Focused backend -> `28 passed, 10 warnings in 2.14s`.
  - Complete backend -> `238 passed, 10 warnings in 26.21s`.
  - Frontend `npm run build` -> passed; 1577 modules transformed in 4.50s.
  - Scoped leased implementation/test `git diff --check -- ...` -> exit 0;
    only Git LF/CRLF conversion notices.
- Tests not run / unverified: no live LLM, search, PDF, queue, SMTP,
  production/staging database or deployment. No stage, commit, push, deletion
  or destructive cleanup.
- Risks: as recorded in the complete handoff, a hard process termination can
  leave the intentionally non-durable background reservation at `generating`;
  durable job persistence was excluded from this lease. No known blocker
  remains within TURN-0020.
- Requested next state: Codex independently reviews TURN-0020 and accepts I-130
  when all acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-140-3

- Task: I-140
- Attempt: 1 (absolute-end append-only landing record)
- Timestamp: 2026-08-28T01:42:00+08:00
- Allowed paths: all TURN-0021 paths in active `lease-turn-0021`.
- Changed paths and implementation evidence: `DEV-I-140-1` and
  `docs/coordination/outbox/TURN-0021-handoff.md` contain the complete changed
  path list, implementation evidence, exact commands, artifact inspection,
  unverified items and risks. `DEV-I-140-1` and its first landing record
  `DEV-I-140-2` were inserted after earlier terminal markers instead of the
  absolute end; neither was rewritten, removed or truncated. This complete
  record is appended at the absolute end.
- Summary: all five customer-report surfaces now share the approved complete
  report; customer email PDF is strict DOCX-to-PDF with exactly three attempts,
  zero email on exhaustion and visible manual handling; attachment retry keeps
  AI content and rejects active/already-sent duplicates.
- Commands and exact results: acceptance-focused backend `6 passed, 10 warnings
  in 1.69s`; complete backend `246 passed, 10 warnings in 19.22s`;
  `python -m compileall app` exit 0; frontend build passed with 1579 modules in
  3.79s; synthetic Word 2021 proof is a 436168-byte 6-page A4 PDF and all six
  rendered pages passed visual review; scoped tracked-path `git diff --check`
  exit 0 and untracked leased files had no whitespace findings.
- Not run / unverified: Ubuntu/Docker LibreOffice, live services/data/email,
  deployed flow and deployment. No stage, commit, push, deletion or cleanup.
- Risks / blockers: deployment must provide LibreOffice; until then strict
  failure intentionally sends zero email. Word 2021 passed; LibreOffice
  pagination still needs a server-environment acceptance run.
- Requested next state: Codex independently reviews the TURN-0021 handoff and
  accepts I-140 when all acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-140-4

- Task: I-140
- Attempt: 2 (TURN-0022 bounded documentation repair)
- Timestamp: 2026-08-28T01:55:21+08:00
- Allowed paths: `.env.production.example`, `.env.staging.example`,
  `backend/.env.example`, `docs/coordination/DEVELOPMENT_LOG.md` (append-only),
  and `docs/coordination/outbox/TURN-0022-handoff.md`.
- Changed paths:
  - `.env.production.example`
  - `.env.staging.example`
  - `backend/.env.example`
  - `docs/coordination/DEVELOPMENT_LOG.md` (this append-only record)
  - `docs/coordination/outbox/TURN-0022-handoff.md`
- Summary: repaired only the PDF configuration comments identified by
  `REV-I-140-1`. All three examples now state that customer email attachments
  require customer DOCX to LibreOffice PDF conversion, disabling or losing the
  converter blocks delivery and reaches manual handling, and the retained
  legacy fallback flag cannot enable Chromium fallback for customer attachments.
- Commands and exact results: scoped
  `git diff --check -- .env.production.example .env.staging.example backend/.env.example`
  -> exit 0; output contained only Git LF/CRLF conversion notices. Direct source
  inspection confirmed the same corrected two comments in all three files.
- Tests not run / unverified: no tests were run because TURN-0022 changes only
  operator comments and explicitly prohibits behavior/test changes. No
  deployment, production/customer data access, real email, stage, commit, push,
  deletion or cleanup occurred.
- Risks / blockers: none known within this bounded documentation repair.
- Requested next state: Codex independently reviews TURN-0022 and accepts I-140
  when the three comments match the implemented DOCX-only delivery behavior.

READY_FOR_REVIEW

## DEV-I-150-1

- Task: I-150
- Attempt: 1 (TURN-0023 frontend implementation)
- Timestamp: 2026-08-28T10:53:00+08:00
- Allowed paths: `frontend/src/App.vue`,
  `frontend/src/composables/useAdmin.ts`,
  `frontend/src/composables/useQuestionnaire.ts`, `frontend/src/styles.css`,
  `docs/coordination/DEVELOPMENT_LOG.md` (append-only), and
  `docs/coordination/outbox/TURN-0023-handoff.md`.
- Changed paths: all six allowed paths listed above. No forbidden path was
  edited by this worker.
- Summary: implemented a compact quick-filter toolbar, staged accessible
  advanced filters with active summaries, bounded viewport-adaptive page size,
  first/previous/numeric/ellipsis/next/last navigation and a broad 26-option
  questionnaire industry taxonomy. Existing API query/export contracts and
  accepted report/delivery/regeneration frontend work were preserved.
- Commands and exact results:
  - `npm run build` passed (`vue-tsc --noEmit && vite build`), 1579 modules in
    3.99s.
  - Scoped `git diff --check` exited 0 with only LF/CRLF conversion notices.
  - Fully intercepted synthetic Playwright QA passed: 1280x800 document
    `1280/1280`, date inputs 161px, 9 rows; 390x844 document `390/390`, date
    inputs 141px, table `326/326`, pagination `328/328`, 10 rows; mobile dialog
    stayed within x=20..370 and Escape restored trigger focus; console had 0
    errors and 0 warnings.
  - Keyboard QA confirmed dialog focus entry, forward/backward focus looping,
    Escape close/focus return, and visible applied-filter count/summary.
- Tests not run / unverified: no frontend unit-test harness exists; no backend
  tests were in scope. Build/diff check preceded the final mobile-only 27px
  pagination CSS adjustment; that final adjustment passed intercepted browser
  QA but was not rebuilt after the stop instruction.
- Known risks / blocker: the initial non-intercepted local development browser
  session created seven `.playwright-cli/page-*.yml` accessibility snapshots
  containing local customer or operational values. Exact paths and confirmation
  that no screenshot/trace/PDF/export was created are recorded in
  `docs/coordination/outbox/TURN-0023-handoff.md`. The files were not deleted.
  Human approval is required to remove or retain them.
- Requested next state: stop automation for the artifact-retention/removal
  decision. After it is recorded, Codex reruns final build/diff acceptance and
  reviews I-150 independently.

BLOCKED

## DEV-I-160-2

- Task: I-160
- Attempt: 1 (absolute-end append-only landing record)
- Timestamp: 2026-08-28T12:16:24+08:00
- Allowed paths: all TURN-0024 paths in active `lease-turn-0024`.
- Changed paths and evidence: `DEV-I-160-1` and
  `docs/coordination/outbox/TURN-0024-handoff.md` contain the complete changed
  path list, implementation evidence, exact commands, unverified items and
  risks. `DEV-I-160-1` was accidentally inserted after an earlier terminal
  marker instead of the absolute end; it has not been rewritten, removed or
  truncated. This complete landing record is appended at the absolute end.
- Summary: fallback reports with persisted HTML are now reusable delivery
  bodies, so attachment retry skips research and AI generation, preserves the
  approved content snapshot, and runs only PDF/email stages.
- Commands and exact results: new/adjacent focused cases `4 passed, 10 warnings
  in 2.07s`; affected service/delivery suites `52 passed, 10 warnings in
  3.87s`; `python -m compileall -q app tests` exit 0; complete backend
  `248 passed, 10 warnings in 25.28s`; scoped `git diff --check` exit 0 with
  only LF/CRLF conversion notices.
- Tests not run / unverified: no live external service, customer/production
  data, converter, SMTP or deployment. No stage, commit, push, deletion or
  destructive cleanup.
- Risks / blockers: none known within I-160; missing/incomplete bodies retain
  their existing generation behavior.
- Requested next state: Codex independently reviews TURN-0024 and accepts
  I-160 when all acceptance conditions pass.

READY_FOR_REVIEW

## DEV-I-170-3

- Task: I-170
- Attempt: 1 (absolute-end append-only landing record)
- Timestamp: 2026-08-28T13:46:14+08:00
- Allowed paths: all TURN-0025 paths in active `lease-turn-0025`.
- Changed paths and evidence: `DEV-I-170-1`, `DEV-I-170-2` and
  `docs/coordination/outbox/TURN-0025-handoff.md` contain the complete changed
  path list, implementation evidence, exact commands, unverified items and
  risks. The first two records matched earlier terminal anchors instead of the
  absolute end; neither was rewritten, removed or truncated. This complete
  record is appended after the unique final `DEV-I-160-2` record.
- Summary: stale content-only regeneration can be safely retriggered after a
  conservative timeout; audited prior status is preserved, and old background
  tasks are fenced by exact generation-start timestamp on success and failure.
- Commands and exact results: focused lead-service suite `29 passed, 10
  warnings in 3.34s`; complete backend `251 passed, 10 warnings in 20.84s`;
  `python -m compileall -q app tests` exit 0; scoped `git diff --check` exit 0
  with only LF/CRLF conversion notices.
- Tests not run / unverified: no live services, customer/production data,
  email, deployment, stage, commit, push, deletion or cleanup.
- Risks / blockers: none known within I-170; recovery intentionally waits for
  the conservative stale threshold because execution remains in-process.
- Requested next state: Codex independently reviews TURN-0025 and accepts I-170
  when all acceptance conditions pass.

READY_FOR_REVIEW
