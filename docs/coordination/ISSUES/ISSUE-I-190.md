# ISSUE I-190: Wire HTTP to the persistent dynamic report worker

## Objective

Make every public/admin HTTP report action persist queue work and return without
executing research, AI, PDF conversion or email; make the independent worker the
only executor with database-governed dynamic global concurrency and PDF limits.

## Human-approved runtime contract

- Web/API never starts a queue consumer and never schedules in-process execution.
- All report-related HTTP actions only create/update persistent jobs, including
  public submit, diagnostic-email resume, research, resume delivery, attachment
  retry and AI-content regeneration. The local testing regeneration route must
  not remain an inline AI exception.
- Persist a job kind sufficient to distinguish full delivery, research-only,
  content-only regeneration and attachment-only delivery, plus any recovery
  metadata required by those modes. Add a new Alembic revision if fields are
  required; no runtime DDL.
- The independent worker polls database settings about every two seconds, starts
  up to the configured global processing concurrency, increases immediately when
  raised, does not kill active work when lowered, and claims nothing while paused.
- Multiple accidentally started workers must still respect the single database
  global concurrency limit.
- PDF conversion has a database-enforced global concurrency limit and updates
  `processing_stage` so operators can see research/report/waiting-PDF/PDF/email.
- Existing heartbeat, stale recovery, max-three attempts, incremental backoff,
  lock-token fencing and duplicate-email prevention remain intact.
- Terminal work clears queue state and promotes waiting jobs. Delayed retries
  release processing concurrency and allow other active work to continue; retry
  exhaustion enters manual review and requires explicit approval.

## Scope

- Required job-kind/recovery model fields and migration.
- Queue repository/scheduler integration with enqueue, promotion, claim,
  terminal/retry transitions and PDF slot acquisition.
- Submission and lead services.
- Public/admin report endpoints, FastAPI startup and worker script.
- Focused queue concurrency/mode/HTTP-isolation/retry/PDF tests and migration
  chain updates.

## Non-goals

- No administrator settings/queue-management API or frontend UI in this issue.
- No real model/search/converter/SMTP calls, production/customer data,
  deployment, stage, commit or push.

## Acceptance conditions

1. No HTTP endpoint or FastAPI startup executes/schedules report AI, PDF, email,
   research or queue consumption.
2. New submissions persist tier placement and always return even when first two
   tiers are full; the 251st goes to manual review instead of HTTP 503.
3. Admin research, content regeneration, resume and attachment retry persist the
   correct job kinds and rely solely on the worker.
4. Atomic claim enforces database processing concurrency and pause across
   multiple sessions/workers; settings increases/decreases affect new claims
   without cancelling active jobs.
5. PDF stage enforces database `pdf_concurrency` across workers.
6. Retry/backoff, exhausted manual review, terminal queue clearing/promotion,
   heartbeat/stale recovery and token fencing remain tested.
7. Alembic has one head; focused and full backend suites, compileall and scoped
   diff checks pass.
