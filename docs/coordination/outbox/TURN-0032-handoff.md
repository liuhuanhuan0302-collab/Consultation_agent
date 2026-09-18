# TURN-0032 repair handoff

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0032
- Issue ID: I-220
- Sender: delegated_org_ui_worker
- Recipient: codex
- Timestamp: 2026-09-16T16:06:58+08:00
- Status: READY_FOR_REVIEW

## Objective completed

Repaired only the mobile bottom-pagination clipping reported by
`REWORK-I-220-1`, without changing desktop or application behavior.

## Changed files

- `frontend/src/components/OrganizationDiagnosisAdmin.vue`
  - In the existing <=640px breakpoint, constrained only the selected-company
    page to `calc(100dvh - 50px)`, matching the measured y=50 mobile content
    origin.
  - Enabled vertical internal scrolling and contained scroll chaining so the
    complete bottom pagination can be reached inside the clipped admin shell.
  - No template, binding, handler, desktop rule, table rule or business logic
    changed in this repair.
- `docs/coordination/DEVELOPMENT_LOG.md`
  - Appended the complete `DEV-I-220-2` record.
- `docs/coordination/outbox/TURN-0032-handoff.md`
  - Added this handoff.

## Commands and exact results

1. Read `TURN-0032-request.md`, `REWORK-I-220-1`, current `STATE.json`, and the
   active TURN-0032 ownership lease: all identified I-220 / TURN-0032 /
   `delegated_org_ui_worker` with the expected three writable paths.
2. `npm run build` from `frontend`: passed; exit 0. `vue-tsc --noEmit && vite
   build`; 1591 modules transformed; Vite completed in 7.97s. Assets:
   `index.html` 2.44 kB, `index-CcGWrT9u.css` 90.93 kB, and
   `index-DwR1jMbv.js` 422.95 kB.
3. Scoped PowerShell source readback: exit 0; confirmed
   `.organization-admin-page.organization-company-selected` has the dvh height,
   max-height and vertical scrolling declarations inside <=640px only.

## Unverified items and risk

- The worker did not have the authenticated browser session used by Codex, so
  the exact 390x844 coordinate/scroll assertion and 1280x720 visual check were
  not rerun. Codex should rerun the same synthetic QA path.
- The 50px subtraction is coupled to the measured mobile content origin from
  the review. A future change to global mobile admin chrome height will require
  a coordinated update.

## Safety and non-goals

- No company-list, submission-detail, application logic, global style, API,
  type, composable, backend or protocol-state change.
- No stage, commit, reset, deletion, deployment, production/customer data
  access, external call or email.

## Requested next state

Codex reruns 390x844 and 1280x720 browser acceptance, then records PASS only
when pagination is fully reachable, document width remains 390px, and desktop
full-height behavior remains intact.
