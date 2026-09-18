# TURN-0027 request

- Issue: I-190
- Lease: lease-turn-0027
- Worker: Claude Code

## Task

Implement ISSUE-I-190 within the lease. Reuse the accepted I-180 scheduler
domain. Prefer a unified persistent report job with a clear task kind over any
new in-process BackgroundTask exception. The worker must use settings-row locking
for global claims and PDF slots, keep lease fencing/heartbeats, and record stages.
HTTP contracts should remain compatible except capacity exhaustion now persists
manual-review work instead of returning 503. Remove development in-Web consumer.

Add deterministic tests with mocked external stages and multiple DB sessions.
Run focused/full backend tests, compileall, Alembic heads/migration chain, and
scoped/global diff checks. Append DEVELOPMENT_LOG and handoff. No live data,
services, email, deployment, stage, commit or push.
