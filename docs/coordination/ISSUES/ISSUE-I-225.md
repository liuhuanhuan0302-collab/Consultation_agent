# I-225: Export customer PDF from lead detail

Status: Accepted
Ownership: leased lead-report backend/frontend paths

## Objective

Add an administrator `导出 PDF` action to lead detail that downloads the same
customer-facing pure diagnosis PDF contract used by email delivery.

## Architecture and product boundaries

- The PDF source is always the snapshotted customer DOCX converted by
  LibreOffice through the existing customer attachment renderer.
- Never export the internal lead Word, administrator detail HTML, organization
  report, or a Chromium/browser-layout substitute.
- HTTP endpoints only persist a typed PDF-export task or stream an already
  persisted artifact. Only the independent report worker may run DOCX-to-PDF.
- PDF export is content-preserving and email-free: no AI regeneration, research,
  delivery retry, recipient update or real email.
- Preserve the five customer report chapters and snapshotted contact/report
  content. Regeneration must invalidate an older stored PDF artifact.

## Required behavior

- Persist the generated customer PDF bytes on the lead report via an Alembic
  migration; do not add runtime DDL.
- Add a non-delivery `pdf_export` report task kind. It must use the existing
  global processing/PDF concurrency, lease fencing, retries and queue tiers.
- A successful normal email-delivery conversion stores the exact PDF bytes that
  are passed to email. A PDF-export task stores the same renderer output and
  finishes without sending email.
- Add LeadExporter-authorized prepare and download endpoints. Prepare deduplicates
  active work and returns ready/queued state; download streams only a validated
  stored PDF with the customer-readable filename and writes export/operation audit.
- Lead detail exposes artifact readiness and sufficient queue state for polling.
- Add `导出 PDF` beside `导出 Word`. If ready, download immediately; otherwise
  queue once, poll until ready/failed/timeout, then automatically download or
  show a clear error. Prevent duplicate clicks and clean up polling timers.
- Preserve Word export, report regeneration, retry-delivery and all unrelated UI.

## Acceptance

- Focused service/queue/API/authorization/migration tests cover no report,
  not-ready report, ready download, task deduplication, email-free worker path,
  exact persisted/email byte equality, stale-artifact invalidation and roles.
- Complete backend test suite, compileall, Alembic single-head check and frontend
  build pass.
- Authenticated browser QA verifies the button, queued-to-download behavior with
  mocked or local safe data, error state and no desktop/mobile overflow.
- If a real local PDF artifact is produced for QA, validate its PDF structure,
  render representative pages and inspect them before completion.
- No production data, real email, deployment, stage, commit, reset or deletion.
