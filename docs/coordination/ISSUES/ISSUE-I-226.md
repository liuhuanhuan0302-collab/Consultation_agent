# I-226: Add unified local backend launcher

Status: Accepted
Ownership: leased local-development launcher and documentation paths

## Objective

Provide one local backend command that starts the FastAPI development server and
the independent report worker together, while preserving separate processes and
leaving all production/server startup behavior unchanged.

## Required behavior

- Add a local-development launcher under `backend/scripts/` that uses the active
  Python interpreter to run both Uvicorn and `scripts/report_worker.py`.
- Keep API and worker as separate child processes; do not embed a queue consumer
  into `app.main`.
- Prefix or otherwise distinguish child output, fail visibly if either child
  exits unexpectedly, and terminate the remaining child when the launcher exits.
- Provide a non-mutating dry-run mode suitable for focused automated validation.
- Correct local-startup documentation that currently claims the development API
  starts an embedded consumer.
- Do not modify Docker Compose, production/staging environment files, application
  queue behavior, database schema, HTTP APIs or frontend behavior.

## Acceptance

- Focused launcher tests cover command construction/dry-run and child cleanup or
  failure handling at the unit boundary.
- Python compile/check and focused tests pass; the complete backend suite passes.
- Documentation presents the unified local command and retains the separate
  production Docker worker contract.
- No Docker service, production configuration, deployment, real email, stage,
  commit, reset or deletion.
