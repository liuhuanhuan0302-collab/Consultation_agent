# I-220: Align organization diagnosis company detail with lead administration

Status: Accepted
Ownership: leased frontend paths only

## Objective

Restyle only the organization-diagnosis company submission-list detail view so
it follows the existing lead-detail/list visual system and uses the available
viewport consistently.

## Scope

- Keep the organization company list unchanged.
- Keep the individual submission detail component unchanged.
- Move the company-detail back action into the right-side header action group.
- Replace the four large metric cards with one compact summary row.
- Preserve all filters, export, pagination, row actions, events and API behavior.
- Let the submission table consume the remaining viewport height and keep its
  pagination at the bottom.
- Preserve responsive behavior: desktop-first, wrapping below 1180px and a
  usable single-column layout below 640px.
- Reuse existing lead-page colors, spacing, radii, controls, table and pagination.

## Non-goals

- No backend, API, schema, data, permission or behavior changes.
- No organization company-list redesign.
- No individual submission-detail redesign.
- No new visual system, dependency or feature.

## Acceptance

- Only leased frontend and handoff/log paths are changed by the worker.
- `npm run build` passes in `frontend`.
- At desktop width, the header, compact summary, filters, table and bottom
  pagination form one stable full-height page without horizontal clipping.
- At <=1180px filters wrap safely; at <=640px controls become a usable single
  column and actions wrap without overflow.
- Existing labels, v-model bindings, handlers and conditional rendering remain
  behaviorally unchanged.
- No commit, deploy, production access, external call or real email.
