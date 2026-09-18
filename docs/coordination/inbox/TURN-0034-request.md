# TURN-0034 implementation request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0034
- Issue ID: I-222
- Sender: codex
- Recipient: delegated_org_ui_worker
- Timestamp: 2026-09-16T16:30:00+08:00
- Objective: implement `ISSUE-I-222.md` exactly as scoped.
- Owned application paths:
  - `frontend/src/components/OrganizationDiagnosisAdmin.vue`
  - `frontend/src/components/OrganizationSubmissionDetail.vue`
- Additional writable paths: append-only `docs/coordination/DEVELOPMENT_LOG.md`
  and `docs/coordination/outbox/TURN-0034-handoff.md`.
- Forbidden: all other paths and all backend/report-generation behavior changes.
- Use apply_patch, run `npm run build`, inspect the event wiring, provide the
  required handoff and end the development log with `READY_FOR_REVIEW` or
  `BLOCKED`.
