# TURN-0035 implementation request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0035
- Issue ID: I-223
- Sender: codex
- Recipient: delegated_org_ui_worker
- Timestamp: 2026-09-16T16:45:00+08:00
- Objective: implement `ISSUE-I-223.md` exactly as scoped.
- Owned application paths:
  - `frontend/src/components/OrganizationDiagnosisAdmin.vue`
  - `frontend/src/composables/useOrganizationAdmin.ts`
- Additional writable paths: append-only `docs/coordination/DEVELOPMENT_LOG.md`
  and `docs/coordination/outbox/TURN-0035-handoff.md`.
- Forbidden: all other paths, especially backend and lead PDF/export code.
- Use apply_patch, run `npm run build`, inspect fixed request parameters, provide
  the required handoff and end the development log with `READY_FOR_REVIEW` or
  `BLOCKED`.
