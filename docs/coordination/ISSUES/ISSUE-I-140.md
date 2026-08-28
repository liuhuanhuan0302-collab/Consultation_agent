# ISSUE I-140: Lock the approved customer report across all outputs

## Objective

Promote the human-approved 11-page preview style into the production report
rendering pipeline and make the same complete customer report structure appear
in public HTML, administrator HTML preview, standalone customer Word, part three
of the internal customer-detail Word, and the customer email PDF.

## Human decisions

- The approved baseline is
  `output/pdf/北京五八到家信息技术集团有限公司_AI诊断报告_场景间距调整预览.pdf`.
- All five output locations contain the complete customer report: cover, compact
  score overview, charts, exactly five numbered chapters, and contact callout.
- Internal customer-detail Word retains its first two internal sections; part
  three embeds the complete customer report and places its internal part label
  as a small marker on the customer cover instead of a separate page.
- Existing AI prose and scores are not regenerated or materially rewritten.
- M01-M09 receive renderer-derived, restrained dark-red judgment sentences that
  are not written back into the stored AI body.
- Report contact information is snapshotted at report generation/regeneration;
  historical reports retain their original snapshot.
- Customer email PDF is produced only from the customer DOCX. Browser/HTML PDF
  fallback is forbidden for email delivery.
- DOCX-to-PDF conversion retries three times. Exhaustion sends no email, exposes
  a manual-handling failure, and the admin can explicitly retry attachment
  generation and sending.
- AI-content regeneration remains content-only and never creates a PDF or sends
  email. Sending is a separate administrator action.
- Ubuntu 22.04 Docker LibreOffice output is the deployment path. This local turn
  may use Word 2021 for visual proof and must report LibreOffice as unverified if
  it is unavailable.

## Presentation contract

- Header: `<company name> | AI 原生转型诊断报告`.
- Compact neutral score strip: `诊断得分 <score> / <max>` and
  `综合得分率 <rate>%`, with a thin progress line; avoid an accusatory visual.
- No red sentence between `一、执行摘要` and its table.
- The maturity-analysis introduction is dark red. Each M01-M09 module has one
  gentle dark-red renderer-derived judgment before its detail table.
- The key-contradictions table is full width, uses 25%/45%/30% columns, and
  vertically centers cell content.
- The AI-scene introduction is exactly
  `以下场景仅供决策参考，具体需入企调研后给出更详细的建议。` in dark red.
- AI-scene headings are numbered `1.` through `5.`; scene blocks have restrained
  separation, while `预期收益` uses ordinary paragraph spacing and is not red.
- No numbered sixth chapter and no visible `管理层` wording.
- The contact block has no `进一步沟通` heading. It uses a pale-red background,
  dark-red left rule and dark-navy bold text with the approved two-line wording.

## Scope

- Shared backend report-view/snapshot construction and Word rendering.
- Public and administrator HTML report view models/components/styles.
- Customer-detail Word part-three composition.
- DOCX-only email-PDF generation, bounded conversion retries, failure/manual
  state, and explicit administrator attachment-regenerate/send path.
- Focused rendering, export, delivery-gate, retry, endpoint and UI tests.
- Architecture/configuration documentation needed to describe the real path.

## Non-goals

- Do not change questionnaire scoring, AI prompts or substantive diagnosis prose.
- Do not regenerate historical AI content or perform a production backfill.
- Do not deploy, access production/customer data, call paid/live model/search,
  send real email, stage, commit, push, delete or clean unrelated files.

## Acceptance conditions

1. All five output locations use one complete report-view contract and match the
   approved content order and presentation rules.
2. Persisted historical HTML remains readable; renderer-derived additions do not
   mutate the stored AI body, and contact snapshots remain historically stable.
3. Standalone customer Word and internal Word part three include cover, compact
   score, both charts, five complete chapters and the contact callout.
4. Email attachment generation never returns a Chromium/HTML fallback PDF.
5. Conversion failure performs three bounded attempts, sends no email, reaches a
   visible manual-handling state, and supports explicit admin retry without
   duplicating an already-sent delivery.
6. AI-content regeneration still produces no PDF/job/email side effect.
7. Focused tests, full backend suite, frontend production build, compile checks
   and scoped diff checks pass.
8. Generate and visually inspect a representative DOCX and PDF. If LibreOffice
   is unavailable locally, use Word 2021 for local proof and record server
   LibreOffice acceptance as a deployment verification item.
