# I-080: Reuse the internal Word final report for customer PDF delivery

Status: Repairing  
Owner: audit_pdf_libreoffice  
Turn: TURN-0012

## Objective

Make the formal customer PDF reuse the exact Word rendering component used by
part three of the internal lead export. Generate a customer-only DOCX, convert
it with LibreOffice Headless, validate the resulting PDF, and keep the existing
Chromium HTML renderer as a configuration-controlled fallback.

## Allowed paths

- `backend/app/service/lead_export_service.py`
- `backend/app/service/pdf_service.py`
- `backend/app/core/config.py`
- `backend/Dockerfile`
- `backend/deploy/fontconfig/99-consultation-agent-fonts.conf`
- `backend/.env.example`
- `.env.production.example`
- `.env.staging.example`
- `backend/ARCHITECTURE.md`
- `backend/scripts/generate_customer_report.py`
- `backend/tests/test_customer_docx_pdf.py`
- `backend/tests/test_pdf_delivery_gate.py`
- `backend/tests/test_lead_export_structure.py`
- `docs/coordination/DEVELOPMENT_LOG.md` (append-only)
- `docs/coordination/outbox/TURN-0012-handoff.md`

## Existing dirty changes

The allowed application paths already contain an in-progress implementation
for this exact customer request. Treat it as user-owned work to review and
complete. Preserve it; do not replace or revert it wholesale.

## Acceptance conditions

- Internal Word export still renders its three sections and its third section
  through one shared final-diagnosis Word component.
- Customer DOCX contains only a customer report header, real persisted score
  fields, and the shared final diagnosis content; it never loads or renders
  contact, source, research, search-source, view, or admin-operation fields.
- Customer DOCX includes the existing navy headers, fixed table widths, fonts,
  spacing, maturity ranking chart, radar chart, and report pagination behavior.
- Formal customer PDF uses DOCX -> LibreOffice Headless first, with an isolated
  temporary directory/profile, bounded timeout, cleanup, and actionable errors.
- PDF validation checks only `%PDF-`, parseability, and at least one page. It
  does not extract Chinese chapter text and has no 10 KB threshold.
- Chromium remains a configuration-controlled fallback and is not called when
  LibreOffice succeeds.
- The report-worker image installs LibreOffice Writer and CJK fonts. Production,
  staging, and local environment templates expose the DOCX/fallback settings.
- Attachment filename remains `{company_name}_AI诊断报告.pdf`, with invalid
  filename characters sanitized and a safe empty-name fallback.
- Focused tests prove data isolation, final section presence, score fidelity,
  filename behavior, LibreOffice invocation/failure/timeout, configurable
  fallback, and unchanged internal Word output.
- Add a local fixture command that generates an 奥飞娱乐 DOCX and, when
  LibreOffice is installed, PDF without database access or email.
- `python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py tests/test_pdf_delivery_gate.py tests/test_lead_export_structure.py tests/test_report_queue_claim.py`
  passes.
- `python -B -m pytest -p no:cacheprovider -q` passes.
- `docker compose config`, `docker compose --profile staging config`, and
  `git diff --check` pass.
- Do not stage, commit, deploy, access production data, or send email.

## Non-goals

No AI prompt/content change, `report.html_content` generation change, scoring or
schema change, SMTP or queue-business change, online Vue change, or real email.
