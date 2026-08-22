# DECISION-001: Claude CLI unattended permission mode

Status: approved

Human approval: The user authorized automatic repair with permission to modify
coordination documents, backend code, and tests, while explicitly prohibiting
commits, deployment, production database operations, and real email. Codex
interprets this as approval to use bypass permissions only for the active leased
issue under those restrictions.

## Evidence

- TURN-0001 ran for approximately eight minutes with CPU activity but produced no
  output, file change, permission prompt, or handoff.
- TURN-0002 reduced scope to two files and again produced no output or file change
  in the observation window.
- Both CLI processes were started and stopped by Codex; no leased business file
  changed in either turn.
- A minimal no-tool DeepSeek diagnostic returned `OK` in 8.7 seconds, so API
  connectivity is available.

## Likely cause

The non-interactive Claude CLI can reach the configured model but its current
`auto` permission/tool workflow does not complete unattended in this environment.
Claude Desktop visibly uses bypass permissions. Matching that behavior requires
starting CLI with `--dangerously-skip-permissions`, which grants the worker broad
local command authority and therefore requires explicit human approval.

## Approved controls

- Exact file lease for every turn.
- No staging, commit, reset, deletion, deployment, production data, live external
  calls, or real email.
- Independent Codex diff review and test execution after the worker exits.
- The third no-progress turn ends external-Claude automation for this issue.
