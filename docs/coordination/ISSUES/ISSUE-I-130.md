# ISSUE I-130: Add safe administrator AI-report regeneration

## Objective

Add an administrator-only "重新生成 AI 报告" action beside the AI report in
the lead detail view. Regeneration reuses the persisted questionnaire scores and
validated company-research snapshot, replaces the current report only after a
new V2 report passes the existing structural validation, and never creates a
PDF, queues delivery, or sends email.

## Human decisions

- The button regenerates AI report content only.
- It does not re-run company research.
- It does not generate PDF or send/re-send email.
- The current report remains intact when the new candidate fails.
- A successful candidate may replace the stored HTML/summary and marks the PDF
  snapshot stale/pending for any later, separately authorized delivery flow.

## Scope

- Administrator endpoint and HTTP-to-service error mapping.
- Lead-domain orchestration and isolated background generation task.
- Safe transactional candidate generation using the existing report generator.
- Admin UI button, progress state, polling/refresh and error feedback.
- Focused service/endpoint/UI tests and architecture documentation.

## Non-goals

- Do not change prompts, report prose, scoring, research, PDF rendering, delivery
  queue, SMTP, Word export or customer-facing report layout.
- Do not automatically resend a report or alter an already-sent delivery record.
- Do not add a migration or persistence model unless Codex explicitly expands
  the issue and lease after evidence proves it necessary.
- Do not access production/customer data, invoke a live LLM, send email, deploy,
  stage, commit, push, delete or clean unrelated files.

## Acceptance conditions

1. Only `admin` can invoke a dedicated regenerate-report endpoint.
2. The action requires a current report and persisted company research, rejects
   duplicate generation and conflicts with queued/processing delivery work.
3. The background task reuses current questionnaire/research data and existing
   V2 validation; tests mock all external model calls.
4. Success atomically replaces report content, resets PDF status to pending,
   records an operation log, and creates no delivery job or email action.
5. Failure preserves prior HTML, summary, recommendations and usable report
   status while exposing a bounded failure message for administrators.
6. The admin button is adjacent to "AI 分析报告", disables while running,
   refreshes the displayed report, and never claims that email was sent.
7. Existing resume-delivery and diagnostic-email behavior remains unchanged.
8. Focused backend tests, the complete backend suite, frontend production build
   and scoped diff checks pass without touching unrelated dirty changes.

