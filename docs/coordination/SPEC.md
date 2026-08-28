# SPEC: Backend architecture hardening and research evidence integrity

Status: Approved for implementation  
Run: `backend-architecture-hardening-20260822`  
Sources: `AGENTS.md`, `backend/ARCHITECTURE.md`, current repository evidence,
and the user's architecture-audit requirements.

## Evidence labels

- **Verified** means Codex directly inspected or executed it in the current
  worktree.
- **Historical** means it came from an earlier handoff and is not current proof.
- **Inference** means tests are still required.

No issue may claim acceptance using only historical evidence or inference.

## Background

The product collects customer information and a 68-question assessment, scores
the submission, researches public company information, generates a DeepSeek
report, renders PDF/Word output, sends email, and provides an admin system. The
same deployment also supports a database- and email-isolated staging environment.

The current worktree has a real layered skeleton but still has business and
database orchestration inside API endpoints. Company-research validation now
rejects missing or empty `sources`, but it does not yet prove that model-provided
URLs came from the real search response or that factual sections bind to sources.

## Current verified baseline

- `backend/app/core/config.py` imports and compiles; the earlier merged-line
  syntax error is no longer present.
- `python -m pytest -q`: **117 passed**, 8 warnings on 2026-08-22.
- `python -m alembic -c alembic.ini heads`: one head, `9c31a760`.
- `public.py` and `admin/leads.py` still directly query/write the database and
  orchestrate multi-step workflows.
- `service/diagnosis.py` still depends on FastAPI `HTTPException`.
- `source_refs` can be missing, empty, incomplete, or contain unknown keys.
- Truthy model `sources` are kept without matching against actual search
  citations/results.
- The dirty worktree contains unrelated edits and untracked debug/PDF artifacts;
  exact leases are mandatory.

## Goals

### G1. Trustworthy company-research evidence

- Treat citations/results returned by the configured search provider as the only
  trusted source set for a generation attempt.
- Normalize and verify model source URLs against that trusted set.
- Require every factual section with content to reference at least one valid
  trusted source.
- Fail closed into the existing retry/manual-review path when evidence cannot be
  proved; do not generate or send a final customer report without evidence.
- Preserve explicit labeling of `challenges`, `ai_opportunities`, and `analysis`
  as AI analysis rather than verified fact.

### G2. Enforce the layered backend architecture

- API handles HTTP input, authentication, application calls, error mapping, and
  response serialization only.
- Service owns business rules, workflow orchestration, and transaction boundaries.
- Repository owns reusable SQLAlchemy queries and persistence operations.
- Service code does not import or throw FastAPI HTTP exceptions.
- Existing API paths, status codes, messages, response fields, scoring behavior,
  and frontend compatibility remain unchanged.

### G3. Prove authorization behavior

- Add representative 401/403/success tests for every role guard and both bearer
  and cookie authentication paths.

### G4. Keep documentation and verification truthful

- Update stale directory and endpoint descriptions from actual code/OpenAPI.
- Run independent full regression; mark Docker or production checks unverified if
  they cannot be executed.

### G5. Unify premium customer-report presentation

- Preserve the accepted AI-generated report content while upgrading presentation.
- Keep internal Word part three, customer DOCX/LibreOffice PDF, Chromium fallback
  PDF, and online report within one restrained executive-consulting design system.
- Use the supplied report only as a visual reference; do not copy company-specific
  content, logos, or confidentiality labels.

### G6. Separate administrator report regeneration from delivery

- Allow administrators to regenerate AI report content from persisted scores and
  company research without re-running research, generating PDF or sending email.
- Replace the current report only after the candidate passes existing V2
  validation; preserve the prior report on failure.

### G7. Lock the approved complete report and safe PDF delivery

- Use one complete customer report-view contract across public/admin HTML,
  standalone Word, internal Word part three, and the emailed PDF source.
- Generate customer email PDF only from the customer DOCX; after three failed
  conversions, send no email and expose an explicit manual retry path.
- Preserve historical report content/contact snapshots and keep AI-content
  regeneration separate from delivery.

### G8. Keep lead administration efficient at real viewport sizes

- Keep only common lead filters visible and move complete advanced filtering to
  one accessible dialog.
- Adapt list page length to viewport height and provide complete compact page
  navigation without a manual page-size selector.
- Maintain a broad questionnaire industry taxonomy and durable project operating
  notes in the authoritative AGENTS.md.

## Non-goals

- A global `{code, message, data}` response rewrite.
- Scoring, questionnaire, risk-level, or UI redesign.
- Changing search/LLM vendors.
- Proving that a public webpage itself is factually correct; this work proves only
  that evidence came from the actual search response and is correctly referenced.
- Automatic production-data backfill, deployment, real email, paid live API tests,
  staging/production secret changes, staging/committing, or cleanup of unrelated
  dirty-worktree files.

## Functional requirements

### FR-01 Trusted sources

- DeepSeek native search trusts only machine-readable citations, annotations, or
  web-search results returned by the response.
- External search providers trust only results returned by `search_company_web()`.
- A model JSON `sources` entry is untrusted until its normalized URL matches the
  trusted set. Unmatched URLs must not be persisted.
- Accepted source metadata should be rebuilt from trusted results, not from model
  claims. Only absolute HTTP/HTTPS URLs with a host are eligible.
- URL matching and deterministic deduplication must have focused tests.

### FR-02 Source references

Factual sections are `company_overview`, `revenue_scale`, `products`,
`industry_characteristics`, and `development_status`.

- `source_refs` is required and must be a dictionary.
- Keys must be recognized structured-section keys.
- Every factual section not equal to `MISSING_RESEARCH` must have a non-empty list
  of unique integer references.
- Boolean, string, zero, negative, duplicate, and out-of-range references fail.
- A factual section marked `MISSING_RESEARCH` must not invent a reference.
- Analytical sections may reference sources but are not required to do so; their
  presentation must continue to identify them as analysis/inference.

### FR-03 Failure and cache behavior

- New and regenerated research must pass strict evidence validation.
- Missing or empty model sources may be reconciled only when section references
  can still be mapped deterministically to trusted results; otherwise retry.
- Invalid research must not be marked `generated`, rendered into a new final
  deliverable, or emailed.
- Existing retry behavior remains; exhausted retries lead to manual review.
- Previously sent historical reports remain readable. Production backfill is a
  separate human-approved operation.

### FR-04 Evidence display

- Word/HTML output for factual company-research sections must show concrete source
  numbers when the section is included.
- Do not use a generic “see source list” message to hide a missing mapping.
- Keep a deduplicated source list at the end and safely escape display content.

### FR-05 Questionnaire submission service

Move completeness validation, capacity checking, answer persistence, scoring,
report creation/update, delivery-job creation, transaction handling, and deadlock
retry to a submission service/repository boundary. Keep the endpoint responsible
for session ownership, HTTP mapping, response construction, and scheduling the
post-commit background task.

### FR-06 Admin lead service

Move lead detail, email correction, reroll/research workflow, export audit,
delivery-state selection, deletion orchestration, and reusable SQL out of
`admin/leads.py` while preserving permissions and output formats.

### FR-07 Customer report visual contract

- Word and customer DOCX continue to share the same final-report body renderer.
- Chromium fallback must use explicit A4 print rules and the same navy, restrained
  red, light-gray, typography, table, and callout hierarchy as Word output.
- Online presentation must use the same visual vocabulary while remaining
  responsive.
- Visual changes must not alter report text, score data, snapshot semantics,
  sanitization, privacy boundaries, API behavior, or delivery behavior.
- The customer cover uses the human-approved compact editorial hierarchy:
  centered gray company line, two-line navy title, restrained red subtitle,
  wide red rule, wide/shallow five-row gray metadata block, and a small navy
  closing statement. It contains no confidentiality label or English kicker.
- The cover is built from editable Word-native elements and follows the approved
  screenshot, with a dynamic full legal company line, derived short company
  title, report number and Chinese-formatted date.
- The report body preserves substantive content while following the supplied
  reference PDF's restrained consulting system: muted header/red rule, compact
  footer, navy/red/blue heading ladder, navy-header tables with pale blue-gray
  rows, pale-red left-rule decision callouts and disciplined whitespace.

### FR-08 Safe report regeneration

- A dedicated administrator action regenerates AI report content only and never
  reuses the delivery-resume endpoint.
- Active generation or queued/processing delivery conflicts are rejected.
- Failed candidate generation leaves the prior HTML, summary and recommendations
  usable; successful generation invalidates only the derived PDF status.
- The action records an audit event and does not create or mutate delivery jobs.

### FR-09 Complete report consistency and delivery gate

- Every report surface contains the customer cover, compact score overview,
  charts, exactly five numbered chapters and the approved contact callout.
- Renderer-derived maturity judgments may enrich presentation but must not
  rewrite persisted AI body content.
- Internal Word preserves its first two sections and embeds the complete customer
  report as part three with a small internal cover marker.
- Email delivery accepts only a successful customer-DOCX conversion. Browser PDF
  fallback must never be attached to customer email.
- DOCX conversion retries three times; exhaustion produces a visible manual state
  and an administrator-controlled regenerate-attachment-and-send retry.
- Regenerate-attachment-and-send must reuse any complete persisted approved body
  (`generated` or historical `fallback`) and must never re-enter research or AI
  content generation.
- Content-only AI regeneration must recover stale in-process reservations after
  crashes and fence late tasks so an older attempt cannot replace a newer one.

## Architecture and safety requirements

- Follow `API -> Service -> Repository -> Model -> Database`.
- Keep the singular `service/` directory.
- Do not add new runtime `ALTER TABLE`; schema changes require Alembic.
- Preserve compatibility exports in `app.models` and `app.schemas`.
- Mock search, DeepSeek, SMTP, and other paid/external calls in automated tests.
- Do not read or print real secrets or customer data.
- Preserve staging database-suffix and email-allowlist guards.
- Preserve public error redaction and safe HTML/URL handling.

## Global acceptance conditions

- Baseline behavior remains covered and all tests pass.
- Company research rejects untrusted model URLs and incomplete/invalid references.
- Evidence failure prevents PDF/email delivery and reaches retry/manual review.
- Submission and lead endpoints no longer own complex queries or cross-table
  transactions for the refactored workflows.
- Services under this scope do not depend on FastAPI HTTP exceptions.
- Representative role-authorization behavior is tested.
- Alembic has exactly one head.
- Frontend build passes if an API contract or frontend consumer changes.
- Compose files parse if Docker is available; otherwise this is reported as
  unverified.
- No unrelated dirty changes are overwritten, staged, deleted, or committed.

## Human decisions reserved

- Whether to backfill or regenerate historical production reports.
- Any policy change that permits delivery when the search provider supplies no
  machine-verifiable citations.
- Any change to role permissions, deletion semantics, API contracts, or production
  deployment behavior.
- Any paid live-search test budget.
