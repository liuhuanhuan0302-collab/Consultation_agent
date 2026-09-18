# TURN-0039 implementation handoff

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0039
- Issue ID: I-226
- Sender: delegated_local_launcher_worker
- Recipient: codex
- Timestamp: 2026-09-18T14:38:33+08:00
- Status: READY_FOR_REVIEW

The authoritative terminal development marker is `DEV-I-226-2`. The complete
`DEV-I-226-1` record was accidentally inserted near the start of the append-only
log; it was preserved unchanged, and `DEV-I-226-2` was appended at absolute EOF
as a position correction.

## Objective delivered

Added one local backend launcher command that supervises Uvicorn and the
independent report worker as separate child processes. Production and server
startup behavior remains unchanged.

## Changed files

- `backend/scripts/start_dev.py`
- `backend/tests/test_start_dev.py`
- `README.md`
- `PROJECT_OVERVIEW.md`
- append-only `docs/coordination/DEVELOPMENT_LOG.md`
- `docs/coordination/outbox/TURN-0039-handoff.md`

No forbidden path was written. The pre-existing dirty `docker-compose.yml` was
observed before implementation and was not edited.

## Behavior

- Uses `sys.executable`, so API and worker run with the currently active Python.
- Runs Uvicorn with auto-reload and `scripts/report_worker.py` as separate child
  processes from the backend working directory.
- Prefixes child output as `[api]` and `[worker]`.
- Treats any child exit as unexpected, reports its code, and terminates the
  remaining child; cleanup escalates to kill after a timeout.
- Ctrl+C terminates both children.
- `--dry-run` prints both commands and creates no processes.
- README and project overview use the unified local command, remove the obsolete
  embedded-consumer claim, and explicitly preserve independent production
  Docker services.

## Commands and exact results

From `backend` using `..\.venv\Scripts\python.exe`:

1. `python -m pytest -q tests/test_start_dev.py`
   - Exit 0: `6 passed in 0.04s`.
2. `python -m compileall -q scripts/start_dev.py tests/test_start_dev.py`
   - Exit 0; no output.
3. `python scripts/start_dev.py --dry-run`
   - Exit 0; exact output:

     ```text
     [dev] working directory: E:\Consultation_agent\backend
     [dev] api: E:\Consultation_agent\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
     [dev] worker: E:\Consultation_agent\.venv\Scripts\python.exe scripts/report_worker.py
     [dev] dry run complete; no child processes were started.
     ```

4. Complete `python -m pytest -q`
   - Exit 0: `304 passed, 93 warnings in 36.38s`.
5. `git diff --check -- backend/scripts/start_dev.py backend/tests/test_start_dev.py README.md PROJECT_OVERVIEW.md`
   - Exit 0; only Git LF-to-CRLF working-copy notices for the two Markdown files.

## Unverified items and risks

- Did not run the live launcher because the report worker could consume a real
  queued task. Startup, output prefixing, unexpected-exit cleanup, partial-start
  cleanup and kill escalation are covered with subprocess-boundary unit tests.
- Did not run Docker or deployment checks. The issue deliberately does not alter
  Docker Compose, deployment or environment files.
- Console and signal behavior may vary by operating system; the launcher is a
  local developer convenience, not a replacement for the production process
  manager.

## Safety and requested next state

No real report task, email, Docker service, deployment, production data, stage,
commit, reset, deletion or forbidden-path write occurred. Codex should rerun the
acceptance commands and accept I-226 only after independent diff review.
