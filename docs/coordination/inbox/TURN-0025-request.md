# TURN-0025 request

- Issue: I-170
- Lease: lease-turn-0025
- Worker: Claude Code

## Task

Implement the approved stale-timeout recovery and generation-timestamp fencing
described in ISSUE-I-170. Keep the HTTP response contract unchanged. Repository
code owns the operation-log lookup; service code owns orchestration; endpoint
code only schedules the returned lease-aware background task. Add deterministic
tests with fixed timestamps and mocked model generation; no live services.

Run focused tests, the complete backend suite, compileall and scoped diff checks.
Append a complete DEVELOPMENT_LOG record and write the TURN-0025 handoff. Do not
access production/customer data, send email, deploy, stage, commit or push.
