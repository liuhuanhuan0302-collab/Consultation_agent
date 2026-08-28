# ISSUE I-100: Unify and elevate customer report presentation

## Objective

Make the customer-facing report materially more polished and ensure that the
online report, customer DOCX, LibreOffice PDF, Chromium fallback PDF, and the
internal Word export's third section use one coherent executive-consulting
visual system.

The visual reference is:
`E:/工作/奥飞/直播课程讲解/直播课程/260819-奥飞娱乐Agent ROI评估及大赛具体安排-Final.pdf`.

## Verified problem

- `build_final_diagnosis_report` already shares Word body content between the
  internal export and customer DOCX.
- The local environment has no LibreOffice, so customer delivery falls back to
  `render_report_html_attachment`, which currently uses an unrelated dark
  gradient/card design. This is why the returned PDF does not visually align
  with the Word third section.
- The online report has a third, partially overlapping CSS treatment.

## Required design direction

- White A4-like canvas with generous whitespace and strict alignment.
- Deep navy for hierarchy and table headers.
- Restrained red for judgment, key conclusions, and hairline accents.
- Cool light gray for metadata and alternating table rows.
- Clear executive hierarchy, restrained decoration, and evidence-first tables.
- The result should feel like a premium management-consulting deliverable, not
  a dark technology dashboard or a marketing landing page.

## Scope

- Refine Word/DOCX cover, metadata, score block, headings, callouts, tables,
  chart colors, header/footer, spacing, and pagination.
- Make Chromium fallback HTML/PDF visually mirror the Word design language and
  use deterministic A4 print rules.
- Align the online report body and outer report chrome with the same visual
  system while preserving responsive behavior.
- Extend the fixture path so a database-free browser-fallback HTML/PDF artifact
  can be produced for visual comparison.
- Add focused structural/style tests for the shared design contract.

## Non-goals

- Do not change AI prompts, generated report sections, wording, scoring, data,
  report snapshots, API contracts, queue behavior, SMTP, or delivery policy.
- Do not access production/customer data or send email.
- Do not require a schema migration.
- Do not copy logos, confidential wording, or company-specific content from the
  reference PDF.

## Acceptance conditions

1. Internal Word part three and customer DOCX still call the same
   `build_final_diagnosis_report` body renderer.
2. Customer DOCX and Chromium fallback use the same navy/red/light-gray visual
   vocabulary for cover/meta/score/headings/tables/callouts/charts.
3. Fallback HTML includes explicit A4 print/page-break rules and no dark
   gradient hero or rounded dashboard-card treatment.
4. Online report adopts the same consulting-report hierarchy without changing
   sanitized report HTML or application behavior.
5. A database-free fixture generates DOCX plus fallback HTML/PDF artifacts, and
   the worker records a visual inspection result.
6. Existing privacy boundaries remain: customer artifacts contain no internal
   contact, research, admin, or audit fields.
7. Focused backend report tests pass, the complete backend suite passes, and the
   frontend production build passes.
8. No unrelated changes are overwritten, staged, committed, deployed, or sent.

