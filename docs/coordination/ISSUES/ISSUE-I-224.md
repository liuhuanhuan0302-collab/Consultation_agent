# I-224: Compact organization diagnosis lists

Status: Accepted
Ownership: leased frontend component only

## Objective

Remove the redundant `组织诊断` page title and eliminate the large empty table
area below short organization-diagnosis result sets.

## Scope and acceptance

- Company list: remove the visible `组织诊断` heading while retaining `刷新`.
- Align `刷新` cleanly without reserving an empty title row.
- Company and submitted-answer list containers shrink to their rendered rows
  instead of filling the remaining viewport with blank space.
- Pagination follows the table content naturally.
- Preserve submitted-only queries/export, all table columns, pagination,
  company/answer navigation, report actions and mobile internal scrolling.
- `npm run build` passes; authenticated desktop and 390x844 checks show compact
  content, reachable actions/pagination and no document-level overflow.
- No backend, schema, database, lead-PDF, commit or deployment work.
