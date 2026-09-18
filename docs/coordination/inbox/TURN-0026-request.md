# TURN-0026 request

- Issue: I-180
- Lease: lease-turn-0026
- Worker: Claude Code

## Task

Implement ISSUE-I-180 exactly within the lease. Keep this phase disconnected
from HTTP and worker execution. Use repository-owned queries and a service-owned
transaction/orchestration boundary. The settings singleton row must be locked
for placement/promotion/approval mutations. Add a new Alembic revision from the
current head and update migration-chain tests. Preserve unrelated dirty changes.

Run focused tests, complete backend tests, compileall, `alembic heads`, migration
chain checks and scoped diff checks. Append DEVELOPMENT_LOG and write the
TURN-0026 handoff. No live data/services/email/deployment/stage/commit/push.
