# TURN-0039 implementation request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0039
- Issue ID: I-226
- Sender: codex
- Recipient: delegated_local_launcher_worker
- Timestamp: 2026-09-18T14:32:05+08:00
- Status: REQUESTED

## Objective

Implement `ISSUE-I-226.md`: one local backend command must supervise Uvicorn and
the independent report worker as separate child processes. Production/server
startup must remain unchanged.

## Leased paths

- `backend/scripts/start_dev.py`
- `backend/tests/test_start_dev.py`
- `README.md`
- `PROJECT_OVERVIEW.md`
- append-only `docs/coordination/DEVELOPMENT_LOG.md`
- `docs/coordination/outbox/TURN-0039-handoff.md`

## Forbidden paths and non-goals

- Do not edit `docker-compose.yml`, deployment files, environment files,
  `backend/app/**`, migrations, frontend code, protocol state files or AGENTS.md.
- Do not start Docker, send email, process a real queued task, deploy, stage,
  commit, reset, delete files or access production data.
- Preserve all unrelated dirty-worktree changes.

## Acceptance commands

- Focused launcher tests.
- `python -m compileall -q scripts/start_dev.py tests/test_start_dev.py`.
- Complete backend `pytest -q`.
- Dry-run the launcher and record exact commands/output.
- Confirm production Docker files are unchanged.

Finish with a complete append-only `READY_FOR_REVIEW` record and handoff.
