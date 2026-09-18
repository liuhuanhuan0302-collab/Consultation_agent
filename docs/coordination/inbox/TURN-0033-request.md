# TURN-0033 implementation request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0033
- Issue ID: I-221
- Sender: codex
- Recipient: delegated_org_ui_worker
- Timestamp: 2026-09-16T16:20:00+08:00
- Objective: implement `ISSUE-I-221.md` exactly as scoped.
- Owned application path: `frontend/src/components/OrganizationDiagnosisAdmin.vue`.
- Additional writable paths: append-only `docs/coordination/DEVELOPMENT_LOG.md`
  and `docs/coordination/outbox/TURN-0033-handoff.md`.
- Forbidden: all other files and all business/interaction changes.
- Use apply_patch, run `npm run build`, provide the required handoff and end the
  development log with `READY_FOR_REVIEW` or `BLOCKED`.
