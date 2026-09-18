# I-221: Remove organization detail eyebrow and summary

Status: Accepted
Ownership: leased frontend paths only

## Objective

Remove the two user-marked presentation blocks from the organization company
submission-list detail: the `企业组织答卷` eyebrow and the complete compact
statistics summary row.

## Scope and acceptance

- Keep the company name and right-side export/back actions.
- Remove the four-value summary row entirely.
- Remove CSS that is used only by the deleted summary.
- Preserve filters, table, pagination, responsive scrolling and all behavior.
- `npm run build` passes and browser inspection confirms the filter moves up
  without desktop/mobile overflow.
- No other application path, commit, deploy, production access or real email.
