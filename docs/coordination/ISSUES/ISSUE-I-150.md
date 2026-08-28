# ISSUE I-150: Improve lead filtering, adaptive pagination and industry coverage

## Objective

Make the administrator lead list fit typical desktop viewports without clipped
date controls or a dense row of filters, replace the manual page-size selector
with adaptive pagination and complete page navigation, expand questionnaire
industry choices, and record stable project-maintenance knowledge in AGENTS.md.

## Human decisions and approved interpretation

- Keep the most common quick filters visible: creation date range, processing
  status and time order.
- Put industry, lead level, view status and export status in one accessible
  “更多筛选” modal with apply, reset and cancel behavior.
- Remove the user-facing “每页” selector. Derive page size from available
  viewport height with safe minimum/maximum values and recompute on resize.
- Pagination includes first page, previous page, a compact numeric page window
  with ellipses, next page and last page; it must remain usable on narrow screens.
- Expand industries to a practical broad Chinese business taxonomy including
  internet/software and retain “其他”. No schema/database change is required.
- Windows cannot host a separate case-only `agent.md` beside `AGENTS.md`; update
  the existing authoritative `AGENTS.md` with durable project operating notes
  and a rule to maintain them when important invariants change.

## Scope

- Administrator lead-list component/composable styling and state.
- Questionnaire industry option constants.
- Focused frontend utility tests if the repository has an existing suitable test
  harness; otherwise use deterministic exported helpers plus build/browser QA.
- Responsive browser inspection at representative desktop and mobile widths.
- Codex-owned AGENTS.md project operating notes.

## Non-goals

- No backend filter/API/schema/database change.
- No scoring, lead status, report, delivery, export or authorization behavior
  change.
- No deployment, production/customer data, real email, stage, commit, push,
  deletion or unrelated cleanup.

## Acceptance conditions

1. Both date inputs render completely at common desktop widths.
2. Quick filters remain clear; every advanced filter is available in one modal,
   active advanced filters are visibly summarized, and apply/reset refresh data.
3. There is no page-size selector. Page size adapts to viewport height and stays
   within a sensible bounded range without producing invalid pages.
4. Pagination supports first/previous/numeric/ellipsis/next/last and handles
   zero, one and many pages accessibly.
5. Questionnaire includes a broad industry list with internet/software and no
   regression to form submission.
6. AGENTS.md contains concise durable operating notes and an explicit maintenance
   trigger, without duplicating existing repository rules.
7. Frontend production build, scoped diff checks and responsive browser QA pass.
