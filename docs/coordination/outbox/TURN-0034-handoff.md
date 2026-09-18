# TURN-0034 implementation handoff

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0034
- Issue ID: I-222
- Sender: delegated_org_ui_worker
- Recipient: codex
- Timestamp: 2026-09-16T16:21:03+08:00
- Status: READY_FOR_REVIEW

## Objective completed

An opened organization submission is now a dedicated view with a visible
top-level `返回答卷列表` action. Returning reuses the existing state action and
restores the same company answer list without resetting its filters or page.

## Changed files

- `frontend/src/components/OrganizationDiagnosisAdmin.vue`
  - Changed the selected-company list branch to render only while
    `selectedSubmission` is absent.
  - Added a mutually exclusive selected-submission branch.
  - Wired the child's `close` event to existing `closeSubmission`.
  - Preserved report generation/download props and event bindings.
- `frontend/src/components/OrganizationSubmissionDetail.vue`
  - Added an `ArrowLeft` top-header `返回答卷列表` button.
  - Added the typed `close` emit.
  - Added bounded header/button wrapping styles so the action stays reachable
    at desktop and narrow widths.
- `docs/coordination/DEVELOPMENT_LOG.md`
  - Appended `DEV-I-222-1` without rewriting earlier records.
- `docs/coordination/outbox/TURN-0034-handoff.md`
  - Added this handoff.

Both application components were already untracked user-owned files and were
edited in place.

## State preservation evidence

The existing unmodified `closeSubmission()` performs only:

```text
selectedSubmission.value = null
submissionDetailError.value = ""
```

It does not mutate `selectedCompany`, `submissionFilters`, `companyDetail` or
`submissionPage`, so returning preserves the company, filter values, loaded
answer list and current page.

## Commands and exact results

1. Read required repository, architecture, protocol, state, issue, ownership
   and TURN-0034 request files: active state and lease matched I-222 /
   TURN-0034 / `delegated_org_ui_worker` and the four writable paths.
2. `npm run build` from `frontend`: passed; exit 0. `vue-tsc --noEmit && vite
   build`; 1591 modules transformed; Vite completed in 4.94s. Assets:
   `index.html` 2.44 kB, `index-9xBBafd8.css` 89.47 kB, and
   `index-BMSt4hfq.js` 422.54 kB.
3. Scoped PowerShell wiring readback: exit 0. Confirmed parent
   `v-else-if="!selectedSubmission"`, child `close: []`, child
   `emit('close')`, parent `@close="closeSubmission"`, preserved
   `generate-report` / `download-report`, and unchanged close-state behavior.

## Unverified items and risk

- No authenticated browser session was available to the worker. Codex should
  verify open → dedicated detail → return at 1280x720 and 390x844, including
  filter/page retention and absence of document overflow.
- No known API/report-action regression after compile and static wiring checks.

## Safety and non-goals

- No composable, API/type, global style, backend, report generation, migration,
  database or protocol-state change.
- No stage, commit, reset, deletion, deployment, production/customer data
  access, external call or email.

## Requested next state

Codex independently reviews TURN-0034 and records PASS for I-222 only after
build and desktop/mobile interaction acceptance succeed.
