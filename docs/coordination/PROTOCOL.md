# Multi-agent coordination protocol

## Purpose

This protocol provides pseudo-duplex communication between Codex, Claude Code,
and delegated agents without allowing concurrent edits to the shared worktree.
Communication is asynchronous; code writing is strictly turn-based.

## Roles

### Human owner

- Owns product decisions and production authority.
- Approves destructive operations, commits when requested, deployments,
  production database access, real email delivery, and material scope changes.

### Codex orchestrator and reviewer

- Maintains the SPEC, milestones, issues, DAG, state, and ownership leases.
- Selects the next ready issue from the DAG.
- Writes requests to `inbox/`, starts one implementation worker, and waits for it
  to exit before reviewing.
- Reviews the diff and runs acceptance commands independently.
- Marks an issue accepted, creates a bounded repair turn, or stops for a human.

### Claude Code implementation worker

- Implements only the active issue.
- Edits only leased paths and preserves unrelated changes.
- Adds focused tests and runs issue-level validation.
- Appends one structured completion record to `DEVELOPMENT_LOG.md`, releases the
  turn by exiting, and does not self-approve.

### Delegated subagents

- Are read-only unless a non-overlapping write lease explicitly assigns them.
- May inspect architecture, tests, security, migrations, or documentation in
  parallel and report findings to Codex.

## Authoritative files

- `SPEC.md`: stable scope, requirements, and global acceptance conditions.
- `MILESTONES.md`: ordered delivery outcomes.
- `ISSUES/ISSUE-*.md`: bounded implementation contracts.
- `DAG.yaml`: issue dependencies and scheduling state.
- `OWNERSHIP.yaml`: active file leases.
- `STATE.json`: current run, turn, writer, and loop counters.
- `inbox/TURN-*-request.md`: orchestrator-to-worker request.
- `outbox/TURN-*-handoff.md`: worker-to-orchestrator result.
- `DEVELOPMENT_LOG.md`: append-only Claude-to-Codex implementation evidence.
- `REVIEW_LOG.md`: append-only Codex-to-Claude review verdicts and repair
  evidence.
- `decisions/DECISION-*.md`: human decisions and approvals.

## Turn lifecycle

1. Codex selects a DAG node whose dependencies are accepted.
2. Codex checks the dirty worktree and creates a non-overlapping lease.
3. Codex updates `STATE.json` and writes a request to `inbox/`.
4. Exactly one implementation worker edits leased files and runs tests.
5. The worker appends a `READY_FOR_REVIEW` development record and exits.
6. Codex confirms the worker process has stopped, reviews the diff, and reruns
   acceptance commands.
7. Codex appends `PASS`, `REWORK`, or `BLOCKED` to the review log, then either
   accepts the issue, creates a repair turn for the same issue, or records a
   human-intervention decision.
8. Codex releases the lease before scheduling the next writer.

## Message contract

Every request and handoff must include:

- run ID, turn ID, issue ID, sender, recipient, and timestamp;
- objective and explicit non-goals;
- leased and forbidden paths;
- dependencies and relevant evidence;
- acceptance conditions and commands;
- changed files and exact command results for handoffs;
- unverified items, residual risks, and requested next state.

## Dual-log protocol

`DEVELOPMENT_LOG.md` belongs only to Claude Code and `REVIEW_LOG.md` belongs
only to Codex. Both files are append-only. A complete record is a Markdown
heading followed by metadata and a terminal status marker on its own line; a
partially written record must be ignored.

### Development record

Claude appends one record per implementation attempt containing: task ID and
attempt number; permitted and changed paths; a concise description; commands it
actually ran with exact results (secrets redacted); tests not run; known risks;
and exactly one terminal marker: `READY_FOR_REVIEW` or `BLOCKED`.

### Review record

Codex appends one record per completed review containing: task ID and the
development-record ID; changed paths actually inspected; independent commands
and results; a verdict; and next action. `REWORK` must give reproducible
findings with file paths and acceptance conditions. Valid terminal verdicts are
`PASS`, `REWORK`, and `BLOCKED`.

### Scheduler rules

- On a new `READY_FOR_REVIEW`, Codex runs the specified read-only audit and
  appends a review verdict.
- On a new `REWORK`, Claude receives one bounded repair request with the quoted
  evidence, then exits after appending its next development record.
- `PASS` ends the issue. `BLOCKED` ends automation and requires a human.
- Ignore duplicate IDs, incomplete records, and records whose task ID does not
  equal `STATE.json.active_issue`.
- Never dispatch while a previous Claude process is alive or a lease is active
  for another writer.

## File ownership rules

- Ownership is an exclusive lease, not permanent authorship.
- Only Codex edits protocol state files unless an issue explicitly says otherwise.
- A worker may read the repository but may write only `owned_paths`, its handoff
  file, and test-generated ignored caches.
- Shared files such as `public.py`, repository exports, schema exports, and
  architecture documents must never be leased to two writers in one turn.
- If the actual fix requires an unleased file, the worker must stop and request a
  lease expansion; it must not silently broaden scope.

## Automatic repair loop

- Maximum repair turns per issue: 3.
- Maximum consecutive turns with the same root failure: 3.
- Maximum consecutive turns with no material diff or test improvement: 2.
- Each repair request must quote concrete reviewer evidence and remain within the
  issue's scope.
- Passing worker tests does not end the loop; independent Codex verification does.

## Human intervention gates

Stop automation and write a decision request when any of these occurs:

- a product ambiguity could change user-visible behavior or stored customer data;
- production database access, deployment, real email, external publication,
  staging/production secrets, or a paid-call budget increase is required;
- a destructive command, migration with data-loss risk, deletion, reset, force
  operation, or rollback of user changes is proposed;
- ownership paths overlap another active writer or unrelated user changes cannot
  be preserved safely;
- the same root failure occurs in 3 consecutive turns;
- 2 consecutive turns produce no material progress;
- acceptance cannot be executed in the available environment;
- architecture rules and product requirements conflict;
- requested scope expands beyond the active issue or changes more than the leased
  domain boundary;
- credentials, external services, or required infrastructure are unavailable;
- tests reveal possible exposure of customer data, secrets, or internal errors.

## Default prohibitions

Without explicit human approval, agents must not stage or commit changes, push,
open or merge pull requests, deploy, alter production infrastructure, access or
copy real customer data, send real messages or email, or delete repository files.
