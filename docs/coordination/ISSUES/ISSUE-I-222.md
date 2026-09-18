# I-222: Add navigable organization submission detail

Status: Accepted
Ownership: leased frontend paths only

## Objective

Make an opened organization submission a dedicated detail view with an explicit
`返回答卷列表` action instead of appending the detail below the company list.

## Scope and acceptance

- Reuse the existing `closeSubmission()` state action.
- When `selectedSubmission` exists, replace the company submission list with the
  individual detail component.
- Add a visible top-level `返回答卷列表` button to the individual detail and emit
  a close event to the parent.
- Returning restores the same selected company, filters, list data and page.
- Preserve report generation/download actions and all API behavior.
- Desktop and mobile layouts have no document overflow; the return action is
  reachable without scrolling to the bottom.
- `npm run build` passes.
- No backend, migration, database, report-content, commit or deployment change.
