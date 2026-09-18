# TURN-0031 implementation request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0031
- Issue ID: I-220
- Sender: codex
- Recipient: delegated_org_ui_worker
- Timestamp: 2026-09-16T00:00:00+08:00
- Objective: implement `ISSUE-I-220.md` exactly as scoped.
- Owned application path: `frontend/src/components/OrganizationDiagnosisAdmin.vue`.
- Additional writable paths: `docs/coordination/DEVELOPMENT_LOG.md` (append
  only) and `docs/coordination/outbox/TURN-0031-handoff.md`.
- Forbidden: every other repository path, especially backend files,
  `frontend/src/App.vue`, `frontend/src/styles.css`, API/types/composables,
  protocol state files, the company-list behavior and
  `OrganizationSubmissionDetail.vue`.
- Preserve the existing untracked component as user work; make the smallest
  in-place template/scoped-style changes needed and do not recreate the file.
- Acceptance commands: `npm run build` from `frontend`; a scoped diff/readback
  of the owned component; report any visual check that could not be run.
- Handoff: append one complete `READY_FOR_REVIEW` or `BLOCKED` development-log
  record and write the requested outbox report with changed files, commands and
  exact results, unverified items, risks and requested next state.
- Safety: do not stage, commit, reset, delete files, deploy, access production
  data, or send real email.
