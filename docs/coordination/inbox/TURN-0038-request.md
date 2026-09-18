# TURN-0038 implementation request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0038
- Issue ID: I-225
- Sender: codex
- Recipient: delegated_org_ui_worker
- Timestamp: 2026-09-17T00:00:00+08:00

Implement `ISSUE-I-225.md` exactly within the active lease. Read all mandatory
repository/protocol files first. Preserve existing dirty-worktree content and
do not rewrite unrelated changes.

Use a nullable persisted customer-PDF byte snapshot on `reports`, a new typed
non-delivery `pdf_export` queue task, thin prepare/download HTTP endpoints, and
frontend prepare/poll/download behavior. The report worker is the sole converter;
the export task must never send email or regenerate research/AI content. Normal
delivery must store the exact bytes it emails. Content regeneration must clear
the stored artifact. Include focused tests and architecture documentation.

Run focused tests, the full backend suite, compileall, Alembic heads and frontend
build. Append a complete READY_FOR_REVIEW record at the absolute end of the
development log and write the TURN-0038 handoff with exact results and risks.
