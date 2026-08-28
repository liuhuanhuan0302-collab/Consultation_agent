# Backend Architecture

The backend uses a layered FastAPI architecture with domain-oriented modules.

```text
backend/app/
├── main.py                 # Application assembly: CORS, rate limiting, exception handlers,
│                           # dev-environment in-process report-queue worker
├── api/v1/
│   ├── router.py           # Aggregates health + public + admin routers
│   └── endpoints/
│       ├── health.py       # GET /api/health
│       ├── public.py       # Public customer endpoints (session, lead, submission, report, QR)
│       └── admin/          # Admin endpoints split by domain
│           ├── _shared.py      # Shared limiter and helpers
│           ├── auth.py         # Login / logout / me / change-password
│           ├── users.py        # User management
│           ├── leads.py        # Lead list/detail/export/email/delete/research
│           ├── questions.py    # Question modules and questions
│           ├── cases.py        # Case studies
│           ├── channels.py     # Channels
│           ├── reports.py      # Report detail
│           ├── analytics.py    # Dashboard and tracking events
│           ├── api_gateway.py  # Search/LLM gateway config and connectivity tests
│           └── system_settings.py # Administrator-managed report contact settings
├── service/                # Business workflows and external integrations
├── repositories/           # SQLAlchemy queries and persistence operations
├── models/                 # ORM entities grouped by domain
├── schemas/                # Pydantic contracts grouped by domain
├── core/                   # Environment configuration and security primitives
├── db/                     # Engine, sessions and database initialization
├── utils/                  # Stateless cross-domain helpers
├── data/                   # Versioned static application data (official questionnaire)
└── seed.py                 # Initial data: admin user, modules, questions, cases, channels
```

`app/config.py` and `app/database.py` are compatibility re-export modules only;
new code must use `app.core.config` and `app.db.database`.

## Dependency direction

```text
API -> Service -> Repository -> Model -> Database
 |        |             |
 +------ Schema --------+
```

- API modules translate HTTP requests into application calls. They do not implement scoring, report generation or complex queries.
- Service modules own business workflows, transactions that span several repositories, and third-party integrations. They do not import or raise FastAPI HTTP exceptions; domain errors are raised as plain service exceptions and mapped to HTTP status codes by the endpoint layer.
- Repository modules own reusable database queries. They do not know about FastAPI requests or responses.
- Model modules define persistence only. They do not call services or APIs.
- Schema modules define public contracts only. They do not perform database operations.

Simple read-only CRUD endpoints may call a repository directly when adding a service would provide no business boundary.

## Domain placement

| Domain | ORM model | Pydantic schema | Typical repository/service |
|---|---|---|---|
| Users and roles | `models/user.py` | `schemas/auth.py` | `repositories/user_repo.py` |
| Customer leads | `models/lead.py` | `schemas/lead.py` | `repositories/lead_repo.py`, `service/lead_service.py`, `service/lead_export_service.py` |
| Questionnaires and scoring | `models/questionnaire.py` | `schemas/questionnaire.py` | `repositories/questionnaire_repo.py`, `repositories/submission_repo.py`, `service/scoring.py`, `service/diagnosis.py`, `service/submission_service.py` |
| Company research evidence | (stored on `Report`) | `schemas/report.py` | `service/company_research.py` |
| Reports and delivery | `models/report.py` | `schemas/report.py` | `service/reporting.py`, `service/report_analysis.py`, `service/report_content.py`, `service/report_queue.py`, `service/pdf_service.py`, `service/email_service.py` |
| Cases | `models/case.py` | `schemas/case.py` | `repositories/case_repo.py` |
| Channels | `models/channel.py` | `schemas/channel.py` | `repositories/qr_code_repo.py` |
| Analytics and audit | `models/audit.py` | `schemas/analytics.py` | admin analytics endpoints |
| API gateway | `models/gateway.py` | `schemas/gateway.py` | `service/api_gateway_service.py` |
| System settings | `models/system_setting.py` | `schemas/system_setting.py` | `repositories/system_setting_repo.py`, `service/system_setting_service.py` |

## Call chains

### Questionnaire submission

The endpoint owns session ownership, HTTP mapping, response construction, and
scheduling the post-commit background task. Business orchestration and the
transaction boundary live in the submission service.

```text
public.py: submit_questionnaire (HTTP mapping, X-Session-Token ownership, rate limit)
  → service/submission_service.py: submit_questionnaire
      row-lock read (FOR UPDATE) → answer completeness validation
      → pending-job capacity check → answer persistence → rule-engine scoring
      → get-or-create pending report → enqueue delivery job → commit
      (MySQL deadlock 1205/1213 auto-retried up to 3 times)
  → background task process_job_then_next
  → service/report_queue.py: process_report_delivery_job
      → company_research.research_company (fail-closed, see below)
      → reporting.generate_report_content (semaphore-limited, structured template
        validated with up to 3 correction attempts; captures report format version
        and the current global report-contact settings in `summary_json`)
      → pdf_service.render_report_pdf_bytes (客户 DOCX→LibreOffice→PDF，
        单次任务最多转换 3 次；禁止以 Chromium HTML PDF 作为邮件附件)
      → email_service.send_report_pdf_email
```

- Service errors map to HTTP in the endpoint only: 404 not found, 409 already
  submitted, 422 incomplete/invalid answers, 503 queue capacity.
- Draft saving follows the same boundary: `public.py: save_draft` →
  `submission_service.save_submission_draft` → `submission_repo.upsert_answers`.

### Admin lead management

```text
admin/leads.py (role guards, HTTP mapping, background-task scheduling)
  → service/lead_service.py
      → repositories/lead_repo.py   (detail, delivery, queue position, advisor
                                     messages, export audit log, export batches)
      → repositories/consult_repo.py (list, cascade delete)
      → repositories/qr_code_repo.py (channel lookup for Word export)
      → service/lead_export_service.py (Word archive, CSV escaping)
      → service/lead_status.py      (three-dimension tracking status sync)
      → service/company_research.py (async background research task)
      → service/report_queue.py     (re-enqueue on diagnostic-email correction)
```

### Lead tracking: three independent status dimensions

Every `company_leads` row carries three stored status dimensions that never
interfere with each other:

- **View status** (`view_status`: `unviewed` / `viewed`) — flipped to `viewed`
  only on the first admin detail open (`lead_service.get_lead_detail`), which
  records `first_viewed_at` / `first_viewed_by` and writes a `view_lead`
  operation log. Later opens and status polling are no-ops.
- **Processing status** (`processing_status`: `pending` / `processing` /
  `manual_review` / `completed`, plus `processing_note`) — derived, never
  hand-written, by `lead_status.sync_lead_processing_status(db, lead_id)`, the
  single source of truth. It is called at every pipeline transition:
  questionnaire submit (enqueue), report-queue claim / stale recovery /
  success / terminal failure, manual research trigger, background research
  completion, and resume-delivery re-enqueue. Derivation order: delivery
  `sent` → `completed`; queue/research/report still advancing → `processing`
  (in-flight beats stored failures so a manual fix immediately shows 处理中);
  then terminal failures root-cause-first — research `failed`/`review` →
  「企业情报检索失败」, report `failed` → 「AI 报告生成失败」, delivery
  `failed` → 「邮件/PDF 投递失败」; generated report without a delivery job →
  「报告已生成，未创建投递任务」; otherwise `pending`. Failure notes dedupe
  against known upstream prefixes (`公司情报检索失败：` etc.) so the note is
  never double-prefixed. There is no long-lived "fixed" state — repair actions
  live only in the operation log.
- **Export status** (`export_status`: `unexported` / `exported`, plus
  `first_exported_at` / `last_exported_at`) — only the one-click export marks
  rows exported; the filtered CSV export (列表「导出筛选结果」) does not mark
  or create batches.

### Export batches

The one-click export (`POST /api/admin/leads/export-unexported`) runs in a
single transaction: `SELECT ... FOR UPDATE` on unexported leads with a
non-empty company name, builds the CSV snapshot, marks each row exported
(`first_exported_at` set only once), and stores the batch:

- `export_batches` — immutable CSV byte snapshot (`content`, 16 MB),
  `filters_json`, `rows_count`, `file_name`, exporting user.
- `export_batch_leads` — batch → lead membership (unique pair). Deleting a
  lead removes its membership rows but keeps the batch snapshot downloadable
  (`GET /api/admin/leads/export-batches/{id}/download`).

Concurrent one-click exports cannot double-export: the row locks make the
second transaction see zero unexported rows and return the "没有未导出" message
without creating an empty batch.

### Report format snapshots

`reports.summary_json` is the immutable rendering contract for a generated
report. New reports use `report_format_version = 2` and include a
`report_contact` snapshot copied from the singleton `report_contact_settings`
row. Empty contact fields are omitted. The language model never receives this
renderer-only metadata. HTML is generated from the same payload and persisted;
customer Word, converted PDF, email attachment and later internal export all
render that stored HTML instead of reading live settings. Changing the global
contact therefore affects only new or explicitly regenerated reports.

`service/report_content.py:build_report_presentation_html` is the shared,
non-persistent presentation layer for public HTML, administrator HTML and both
Word exports. It combines the immutable HTML/summary snapshot with deterministic
M01-M09 renderer notes, the approved scene note/numbering and the historical
contact callout without rewriting the AI-authored body. The standalone customer
Word and part three of the internal Word then reuse the same complete customer
document structure: cover, compact score strip, charts, five chapters and
contact callout.

Reports without a format version remain legacy snapshots: their existing
"优先 AI 场景与案例" and "管理层行动建议" sections continue to validate and
export unchanged. Version 2 uses "优先 AI 场景建议", omits management actions,
and appends an unnumbered contact block only when its snapshot has values.

### Administrator report regeneration

`POST /api/admin/leads/{lead_id}/regenerate-report` is an administrator-only,
content-only workflow. The endpoint reserves an existing usable report and
schedules `lead_service.run_report_regeneration_task`; it never enters the
delivery queue. The task reuses the scored submission and the persisted,
evidence-validated company-research snapshot. `reporting.generate_report_candidate`
calls the LLM and runs the existing V2 structural validation without mutating
the stored report. Only a validated candidate is applied in one transaction,
after a second active-delivery conflict check. Success replaces HTML, summary,
recommendations and advisor messages and marks the former PDF snapshot pending;
failure restores the prior usable status and keeps all prior report content.
Neither path generates a PDF, creates or changes a delivery job, or sends email.

`POST /api/admin/leads/{lead_id}/retry-attachment-delivery` is a separate
administrator action for a reviewed, already-generated report. It rejects sent
or active jobs, resets only the PDF/delivery state and queues DOCX→PDF→email;
it never regenerates AI content.

### Legacy data adoption

Migration `6f0a46f68473` adds the columns/tables above and adopts existing rows
as pre-launch customers: all rows get `view_status = 'viewed'` and
`export_status = 'exported'`; `processing_status` is derived per row from the
latest submission → report → delivery job using the same rules as
`lead_status` (sent → completed, terminal failures → manual_review with the
root cause, in-flight → processing, else pending).

## Roles and authorization

Roles: `admin`, `operator`, `sales`, `consultant` (`models/user.py: Role`).
Guards are prebuilt in `utils/auth.py`:

| Guard | Allowed roles | Typical routes |
|---|---|---|
| `AdminOnly` | admin | users, API-gateway config, lead delete / diagnostic-email / manual research |
| `ContentManager` | admin, operator | question/module/case/channel write operations |
| `LeadViewer` | admin, operator, sales, consultant | lead list/detail, question/case/channel lists, analytics, events |
| `LeadExporter` | admin, operator, sales | lead CSV export, lead Word export |
| `ReportViewer` | admin, operator, sales, consultant | report detail |

Authentication accepts a Bearer token or the admin HttpOnly session cookie
(either one). Missing, invalid, expired, disabled-user, malformed or
out-of-range-subject credentials return 401; a valid user outside the allowed
role list returns 403. Changing a password sets `users.password_changed_at`;
any JWT issued before that moment is rejected with 401, so a leaked token dies
with the next password change instead of living up to 720 minutes. Both paths
and all guards are covered by `tests/test_authorization_matrix.py` against
real routes.

## Company research evidence

Search-provider citations are the only trusted source set for one generation
attempt. Everything the model returns is untrusted until reconciled:

- External search (`bocha` / `serpapi` / `custom`) trusts only results from
  `search_company_web()`; `deepseek` native search trusts only machine-readable
  `web_search_tool_result` blocks returned by the official Anthropic protocol
  endpoint (`/anthropic/v1/messages` with the `web_search_20250305` tool).
  Text-block URLs, `thinking` / `server_tool_use` blocks and model self-reported
  URLs are never trusted.
- Model `sources` entries are kept only when their normalized URL
  (absolute HTTP/HTTPS with a host, no credentials) exactly matches the trusted
  set; `reconcile_research_sources` remaps `source_refs` accordingly. Unmatched
  URLs are never persisted. Normalization strips the query string and fragment
  (`scheme://host[:port]/path`), since search links routinely carry tracking
  parameters that a model cannot be required to reproduce verbatim.
- `validate_structured_research` requires a non-empty `sources` list (each entry
  with title and URL), a `source_refs` dictionary restricted to known structured
  section keys, and a non-empty list of unique in-range integer references for
  every factual section (`company_overview`, `revenue_scale`, `products`,
  `industry_characteristics`, `development_status`). Sections marked
  `MISSING_RESEARCH` must not invent references. Analytical sections
  (`challenges`, `ai_opportunities`, `analysis`) may reference sources but are
  always presented as AI analysis, not verified fact.
- JSON parse or structural validation failure triggers exactly one correction
  call that reuses the already-obtained search results (no re-search); a model
  that returns an empty `sources` list gets the same correction and fails
  closed if it still cannot map `source_refs` to real citations.
- Cached research is reused only when it carries `evidence_version == 1` and
  passes validation; otherwise it is regenerated.

### Retry semantics (no amplification)

- API / network errors are not retried inside `research_company`; the exception
  is recorded in `generation_error` and the report queue requeues the job with
  backoff up to `max_attempts` (default 3) total queue attempts.
- JSON / structure failures are corrected at most once per queue attempt,
  reusing the existing conversation and machine citations with the search tool
  disabled — they never trigger a new web search.
- `pause_turn` is a protocol continuation, not a failure: the assistant content
  blocks are appended as-is and the call resumes, at most
  `MAX_PAUSE_CONTINUATIONS` (2) times; exhaustion raises and is handled like an
  API error (queue retry).

### Report queue lease and heartbeat

Every `report_delivery_jobs` claim issues a one-time `lock_token`. While a job
runs, a heartbeat loop renews `locked_at` every 30 seconds via a conditional
UPDATE (`WHERE status=processing AND lock_token=<mine>`); a job whose lease is
lost aborts at the next checkpoint — the pre-send ownership check and the
conditional final status write make duplicate emails impossible. Stale
recovery re-queues (or fails) only jobs whose lease expired without renewal,
via one conditional UPDATE that also acts as the mutual-exclusion between
concurrent reclaimers; it clears `lock_token` so the old executor can never
overwrite the new one. `STALE_PROCESSING_TIMEOUT` is the maximum of 15
minutes and `DEEPSEEK_TIMEOUT_SECONDS × 10 / 60` — always longer than the
worst-case pipeline (research 2 + report 1 + 3 corrections + 2 pause
continuations ≈ 8 LLM calls, plus search/PDF/SMTP).

Report-generation failure (incomplete/structurally invalid content after the
in-model correction attempts) is retried at queue level with `2 × attempts`
minute backoff like research failure, instead of failing terminal on the
first attempt; only after `max_attempts` does the job go to manual review.

## Failure behavior (fail closed)

- Research failure or validation failure returns no research data, marks
  `research_status = failed`, and records the reason in `generation_error`.
  Starting processing clears any previous `generation_error` and sets
  `research_status = processing`. The delivery job is requeued with exponential
  backoff (`2 × attempts` minutes); after `max_attempts` the report becomes
  `failed` with `research_status = review` for manual review. No final
  deliverable is generated or emailed without evidence.
- Report generation validates the fixed six-section template and retries up to
  3 times with the previous validation feedback; an incomplete report is marked
  `failed` and goes to manual review instead of being delivered.
- The PDF delivery gate validates the final HTML snapshot before rendering,
  then checks only the `%PDF-` header, parser readability and a positive page
  count. It deliberately does not use byte-size thresholds or extracted Chinese
  text because neither is a reliable proxy for visual report completeness.
- Customer email PDF rendering requires Word → LibreOffice Headless conversion
  (`pdf_service.convert_customer_docx_to_pdf`, Writer filter
  `pdf:writer_pdf_Export`), reusing the Word layout
  components of the internal lead export so both documents share fonts,
  navy table headers, column widths, line spacing and charts. Conversion and PDF
  validation are attempted exactly three times. Exhaustion marks the delivery
  failed/manual, sends no email and exposes the explicit administrator retry
  action. `PDF_DOCX_FALLBACK_TO_BROWSER` is retained only as a legacy/browser
  preview compatibility setting and cannot affect customer attachments. ORM
  report values are snapshotted before worker-thread conversion; each
  LibreOffice process gets an isolated temporary input/output directory and user
  profile with a bounded timeout.
- Container PDF rendering: Docker services run with `no-new-privileges` and
  `cap_drop: ALL`, so the Chromium sandbox cannot start (setuid helper is
  blocked and Ubuntu 23.10+ hosts restrict unprivileged user namespaces).
  `PDF_BROWSER_NO_SANDBOX=true` (set in `docker-compose.yml` and the
  production/staging env examples) launches Chromium with `--no-sandbox` —
  the container is the isolation boundary and the rendered HTML is generated
  and sanitized by the system itself. Outside containers the flag stays off
  and a sandbox startup failure reports an actionable hint.
- Public endpoints redact internal failure details and return the same generic
  message the frontend shows; detailed errors are visible in the admin system
  only.
- Staging isolation: `staging` must use a database name ending in `_test` or
  `_staging` and must configure `SMTP_RECIPIENT_ALLOWLIST`; both are enforced
  at settings load.
- Production HTTPS: `production` rejects `http://` values for
  `PUBLIC_WEB_BASE_URL` and `CORS_ORIGINS` at settings load — the session
  cookie is `Secure` in production and plaintext customer data / report
  tokens / admin credentials are never acceptable. Nginx serves 80 → 443
  redirect, TLS and HSTS (`deploy/nginx/consultation-agent.conf`).
- Anonymous session credentials travel only in the `X-Session-Token` header
  (`submissions/{id}/report`, `sessions/report`); they never appear in URL
  query parameters, browser history or access logs.

## Import conventions

New code should use the canonical paths:

```python
from app.core.config import get_settings
from app.db.database import get_db
from app.models.lead import CompanyLead
from app.schemas.lead import LeadCreate, LeadResponse
from app.service.submission_service import submit_questionnaire
from app.service.lead_service import list_admin_leads
```

`app.config`, `app.database`, `app.models` and `app.schemas` keep compatibility
exports for existing code. Do not add new implementation to the compatibility
modules.

## Adding a feature

1. Add or extend the domain schema.
2. Add an ORM model and Alembic migration when persistence changes.
3. Add repository queries.
4. Add service orchestration and external integrations.
5. Add a thin API endpoint.
6. Add focused tests for authorization, validation and business behavior.
7. Run `python -m pytest` and the frontend build when the API contract affects the UI.

## Database changes

Alembic is the source of truth for new schema changes. `db/init_db.py` contains
transitional upgrades for old installations only; do not extend that list. Once
all deployed environments have migrated, those compatibility upgrades can be
removed.
