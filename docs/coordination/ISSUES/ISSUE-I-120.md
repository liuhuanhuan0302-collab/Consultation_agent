# ISSUE I-120: Produce the reference-aligned report body preview

## Objective

Generate a new customer-report preview that combines two independently approved
visual authorities:

- the user-provided screenshot controls the cover layout; and
- pages 2-6 of
  `E:/工作/奥飞/直播课程讲解/直播课程/260819-奥飞娱乐Agent ROI评估及大赛具体安排-Final.pdf`
  control the body typography, page furniture, tables, callouts and whitespace.

Preserve the current diagnostic report's prose, section order, scores, charts
and factual content except for minimal fixture wording needed to demonstrate the
layout.

## Human decisions

- Keep A4 output; normalize the reference PDF's Letter proportions to A4.
- Build the cover from editable Word-native elements, never a screenshot image.
- Use one reusable template for all customers. The full legal company name,
  report number and date remain dynamic.
- The cover top line uses the full legal company name. The title uses a short
  name derived by removing common legal suffixes, with bounded font reduction
  for unusually long names.
- Long metadata stays on one line when possible; preserve the compact block by
  reducing type only to a readable minimum.
- Apply the same cover/body visual system to Word, customer PDF fallback and
  online report output.

## Cover authority

Rebuild the cover to match
`E:/CodexData/.codex/generated_images/01a03d7f-61bb-7813-8c3c-d8af6f850e45/exec-4f0b3dbc-f758-443b-9e43-831f52fa8357.png`:

- small centered gray full legal company name;
- two-line centered navy title, `<short company> AI 原生转型` and `诊断报告`;
- centered restrained-red subtitle;
- wide thin red rule;
- wide, shallow, borderless five-row metadata block;
- centered small navy closing statement;
- no confidentiality label, English kicker, top rule, logo or decoration.

The current Word cover is not a design authority and must not be retained by
accident. The new fixture must use `奥飞娱乐股份有限公司` so the full-name and
short-name behavior is visible in review artifacts.

## Body authority

Use the source PDF body as a restrained consulting system rather than copying
its business content:

- small muted-gray running header with a thin red rule;
- compact footer with a quiet report label/date and centered page number;
- large deep-navy section titles, restrained-red lead statements and smaller
  blue subsection headings;
- 10.5-11 pt dark body copy with deliberate paragraph rhythm;
- deep-navy table headers with white text, pale blue-gray body fills or
  alternating rows, thin cool-gray borders and compact but readable cell
  padding;
- pale-red decision/callout bands with a red left rule and navy bold text;
- generous whitespace and disciplined page breaks;
- retain existing charts and their data, but align labels, gridlines, caption
  treatment and surrounding spacing with the same palette.

Keep `standard_business_brief` as the base preset and record a named body
override, `reference_consulting_body_v2`, plus the already approved native cover
override. All page, type, spacing, table and color tokens must be explicit.

## Scope

- Customer DOCX generation and database-free preview fixture.
- Customer Chromium fallback PDF.
- Online public/active report presentation.
- Focused structural/style regression tests.
- A new preview output directory; do not overwrite TURN-0018 artifacts.

## Non-goals

- Do not rewrite report analysis, prompts, scores, dimensions or section order.
- Do not copy the source PDF's ROI, competition, logo or confidential content.
- Do not change API contracts, persistence, authorization, sanitization, queue,
  SMTP or delivery behavior.
- Do not access customer/production data, send email, deploy, stage, commit,
  push, delete or clean unrelated files.

## Acceptance conditions

1. The new Word cover visually follows the screenshot rather than TURN-0018's
   rendered cover, while remaining editable and A4.
2. The fixture visibly demonstrates a full legal company line and short company
   title, five compact metadata rows, Chinese date formatting and no forbidden
   confidentiality/kicker text.
3. Body content remains materially unchanged while page furniture, hierarchy,
   tables, callouts, charts and whitespace follow the reference PDF system.
4. Word, fallback PDF and online report use the same vocabulary and remain
   readable without clipping, overlap or orphan pages.
5. Generate new DOCX, Word-review PDF and fallback PDF artifacts under a new
   TURN-0019 output directory and inspect every rendered page.
6. Attempt the packaged `render_docx.py`; if LibreOffice is unavailable, record
   the exact failure and use Word 2021 read-only export plus PNG inspection.
7. Focused backend tests, complete backend suite, frontend production build,
   responsive browser checks and scoped diff checks pass.
8. No unrelated dirty-worktree changes are overwritten.

