# TURN-0037 repair handoff

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0037
- Issue ID: I-224
- Sender: delegated_org_ui_worker
- Recipient: codex
- Timestamp: 2026-09-16T22:03:31+08:00
- Status: READY_FOR_REVIEW

## Objective completed

Removed the remaining desktop detail-card flex fill identified by
`REWORK-I-224-1-LANDING`, so the selected-company card now shrinks to its
content instead of retaining roughly 430px of bordered blank space.

## Changed files

- `frontend/src/components/OrganizationDiagnosisAdmin.vue`
  - Deleted `.organization-company-selected > .organization-company-detail {
    flex: 1 1 auto; overflow: hidden; }`.
  - The card now inherits the existing base `flex: 0 0 auto`.
  - Preserved table-wrapper max height, mobile dvh/page scrolling, mobile
    overflow, navigation, pagination and every business binding.
- `docs/coordination/DEVELOPMENT_LOG.md`
  - Appended `DEV-I-224-2` without rewriting earlier records.
- `docs/coordination/outbox/TURN-0037-handoff.md`
  - Added this handoff.

## Commands and exact results

1. Read current `STATE.json`, TURN-0037 ownership lease,
   `REWORK-I-224-1-LANDING`, and `TURN-0037-request.md`; all matched I-224 /
   TURN-0037 / `delegated_org_ui_worker` and the three writable paths.
2. Scoped source readback: exit 0. Confirmed the desktop detail-card fill
   selector is absent, the base section rule supplies `flex: 0 0 auto`, long
   tables retain `max-height: min(560px, calc(100vh - 190px))`, and mobile keeps
   `height/max-height: calc(100dvh - 50px)` plus visible detail overflow.
3. `npm run build` from `frontend`: passed; exit 0. `vue-tsc --noEmit && vite
   build`; 1591 modules transformed; Vite completed in 3.93s. Assets:
   `index.html` 2.44 kB, `index-w2nrgJnp.css` 87.04 kB, and
   `index-BEh5kUZZ.js` 416.65 kB.

## Unverified items and risk

- No authenticated browser session was available to the worker. Codex should
  repeat the exact 1280x720 one-row card/table/pagination measurement and the
  390x844 scroll-to-pagination check.
- No known functional risk: the repair deletes one layout override and does not
  alter template or script behavior.

## Safety and non-goals

- No navigation/business binding, composable, API/type, global style, backend,
  schema, database, lead PDF/export or protocol-state change.
- No stage, commit, reset, deletion, deployment, production/customer data
  access, external call or email.

## Requested next state

Codex independently reviews TURN-0037 and records PASS for I-224 only after
desktop compact-card and mobile reachability acceptance succeed.
