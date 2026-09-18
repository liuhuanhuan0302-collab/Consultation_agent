# TURN-0032 repair request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0032
- Issue ID: I-220
- Sender: codex
- Recipient: delegated_org_ui_worker
- Timestamp: 2026-09-16T16:04:00+08:00
- Objective: repair the 390x844 bottom-clipping finding in
  `REWORK-I-220-1`, without changing desktop behavior or application logic.
- Owned application path: `frontend/src/components/OrganizationDiagnosisAdmin.vue`.
- Additional writable paths: append-only `docs/coordination/DEVELOPMENT_LOG.md`
  and `docs/coordination/outbox/TURN-0032-handoff.md`.
- Forbidden: all other paths and all feature/business changes.
- Acceptance: at 390x844, internal scrolling must reach the complete pagination;
  document width must remain 390px; 1280x720 behavior remains full-height;
  `npm run build` passes.
- Finish with a complete handoff and absolute-end `READY_FOR_REVIEW` or
  `BLOCKED` development marker. Do not stage, commit, reset, delete or deploy.
