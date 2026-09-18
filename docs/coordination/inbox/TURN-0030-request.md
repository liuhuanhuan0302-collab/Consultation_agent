# TURN-0030 request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0030
- Issue ID: I-210
- Sender: Codex orchestrator
- Recipient: Claude Code implementation worker
- Timestamp: 2026-09-04T18:38:00+08:00

Repair only the migration adoption edge found in review. The existing local
database is already at `c8e1f4a7b203`; do not downgrade it. Update the leased c8
migration to inspect and adopt pre-created `task_kind` and
`task_context_json` columns/index, preserving values and adding only missing
pieces. Add deterministic migration-chain coverage using a pre-created task
column table. Do not alter frontend or detail behavior already fixed. Run the
focused/full backend tests, compileall, diff-check and leave a complete
READY_FOR_REVIEW handoff.

