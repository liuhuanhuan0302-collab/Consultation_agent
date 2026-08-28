# ISSUE I-110: Implement the approved compact editorial cover

## Objective

Replace the currently accepted report cover with the human-approved compact
editorial cover derived from page 1 of
`E:/工作/奥飞/直播课程讲解/直播课程/260819-奥飞娱乐Agent ROI评估及大赛具体安排-Final.pdf`.

The approved visual proof is the most recent generated cover in the current
Codex task. It keeps the report content editable and uses the reference only for
typography hierarchy and relative geometry.

## Design authority

- Preserve the existing A4 document/report body geometry; normalize the source
  PDF's Letter-page proportions to A4 rather than changing the entire report.
- Use the existing white/deep-navy/restrained-red/cool-gray palette.
- No top navy rule, logo, gradient, rounded card, shadow, illustration or photo.
- Small centered gray full company name.
- Two centered navy title lines: `<short company> AI 原生转型` and `诊断报告`.
- Centered red regular/medium subtitle: `从诊断共识走向可执行的 AI 转型路径`.
- A thin red rule approximately 76-78% of page width.
- A wide, shallow, borderless light-gray metadata block approximately 62-66%
  of page width. It has compact row spacing and exactly five rows:
  `评估对象`, `报告类型`, `评估范围`, `报告编号`, `出具日期`.
- Do not render `保密级别`, `请妥善保管`, confidentiality wording, or an
  English kicker on the cover.
- Center a modest navy footer statement close below the metadata block:
  `让 AI 从局部工具走向企业级生产力`.
- The lower quarter remains mostly empty.

For DOCX token discipline, retain `standard_business_brief` for the existing
body and use one named first-page override,
`approved_reference_editorial_cover`, following the `editorial_cover` header
pattern. All cover spacing, font sizes, widths, cell margins and colors must be
explicit rather than inherited from Word defaults.

## Scope

- Customer DOCX/Word cover only, plus moving the existing score strip off the
  cover without dropping score content.
- Chromium fallback cover and score placement.
- Online report hero/metadata chrome so it follows the same approved hierarchy
  and remains responsive.
- Database-free fixture and focused structural/style tests.

## Non-goals

- Do not change report prose, prompts, scores, dimensions, snapshots, privacy
  boundaries, API contracts, sanitization, queue behavior, SMTP or delivery
  policy.
- Do not change the shared final-report body renderer or the accepted body,
  chart and table visual system.
- Do not copy logos, the reference report's Agent ROI wording, competition
  content, confidentiality label, or other company-specific source content.
- Do not access customer/production data, send email, deploy, stage, commit or
  push.

## Acceptance conditions

1. Customer DOCX, Word-derived review PDF, Chromium fallback PDF and online
   hero implement the approved cover hierarchy and compact proportions.
2. DOCX cover metadata uses explicit fixed table geometry, five rows, compact
   cell margins and no visible borders; the red rule is wider than the table.
3. No customer cover contains `保密级别`, `请妥善保管`, an English kicker or a
   top navy rule.
4. Existing total/max/rate content remains visible after the cover rather than
   being deleted.
5. The fixture generates a DOCX, fallback HTML/PDF and visual QA artifacts.
6. Packaged `render_docx.py` is attempted. If LibreOffice is unavailable, the
   limitation is recorded and Word 2021 read-only export plus PNG review is used
   as additional local evidence.
7. Focused backend report tests, the complete backend suite, frontend production
   build, responsive browser checks and scoped diff checks pass.
8. No unrelated dirty-worktree changes are overwritten.

