# ISSUE I-160: Make attachment retry content-preserving for fallback reports

## Objective

Ensure the administrator “重新生成附件并发送” path never performs company
research or AI report generation when an approved persisted report body already
exists, including historical reports whose status is `fallback`.

## Confirmed defect

- `retry_report_attachment_delivery` accepts both `generated` and `fallback`
  reports with non-empty `html_content`.
- `process_report_delivery_job` currently recognizes only `generated` as an
  existing body, so an accepted `fallback` report re-enters research and model
  generation before PDF/email delivery.
- This can replace reviewed content and violates the attachment-only contract.

## Scope

- Align the queue's reusable-body predicate with the administrator retry gate.
- Preserve `report.status`, `html_content`, and existing report content metadata
  throughout attachment-only processing.
- Add focused regression coverage proving a `fallback` report skips research and
  AI generation and proceeds only through PDF/email delivery.

## Non-goals

- No API, schema, migration, frontend, prompt, report-layout or delivery-policy
  change.
- No production access, real email, external/paid calls, deployment, stage,
  commit, push or unrelated cleanup.

## Acceptance conditions

1. A `fallback` report with non-empty persisted HTML is delivery-ready in the
   same way as a `generated` report.
2. Attachment retry for that report calls neither company research nor AI report
   generation.
3. The original status and HTML remain byte-for-byte unchanged while the mocked
   PDF and email stages execute once.
4. Missing/incomplete report bodies retain existing generation/retry behavior.
5. Focused tests and the complete backend test suite pass.
