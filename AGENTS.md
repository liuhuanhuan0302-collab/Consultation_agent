# Repository Engineering Rules

## Backend architecture

All backend changes must follow `backend/ARCHITECTURE.md`.

- API endpoints belong in `backend/app/api/v1/endpoints/` and only handle HTTP concerns.
- Business orchestration belongs in `backend/app/service/`.
- Database queries belong in `backend/app/repositories/`.
- ORM models belong in the matching file under `backend/app/models/`.
- Pydantic request and response models belong in the matching file under `backend/app/schemas/`.
- Configuration and security primitives belong in `backend/app/core/`.
- Database sessions and initialization belong in `backend/app/db/`.
- New schema changes require an Alembic migration. Do not add new runtime `ALTER TABLE` statements.
- Preserve compatibility exports in `app.models` and `app.schemas` when moving existing symbols.
- Add focused tests for behavior changes and run the backend test suite before completion.

## Naming

- Use one domain name consistently across API, service, repository, model, schema and tests.
- This repository uses the singular directory name `service/`; do not introduce a parallel `services/` directory.
- Prefer small domain modules over adding unrelated classes to an existing large file.

## Project operating notes

- `AGENTS.md` is the single authoritative agent-maintenance document for this
  Windows-compatible repository; do not create a parallel `agent.md`/`AGENT.md`.
- Customer report presentation is shared across public/admin HTML, standalone
  customer Word, internal customer-detail Word part three and the email PDF
  source. Preserve five numbered chapters and the snapshotted report content.
- Customer email PDF must come from the customer DOCX. Windows local development
  may use an installed desktop converter; Ubuntu/Docker delivery uses
  LibreOffice. Never silently attach a different Chromium report layout.
- Administrator AI-report regeneration is content-only. PDF generation and email
  delivery require a separate explicit action.
- Content-only regeneration uses a conservative stale timeout plus a persisted
  generation-start lease fence: crashed attempts can be retriggered, while late
  tasks from an older process cannot overwrite a newer reservation.
- When an implementation changes an important architecture boundary, delivery
  safety rule, deployment dependency, authoritative output contract or operator
  recovery path, update this section in the same coordinated issue. Do not add
  temporary debugging facts, customer data, secrets or one-off task history.

## Multi-agent coordination

This repository uses a turn-based, single-writer protocol. The complete protocol is
defined in `docs/coordination/PROTOCOL.md` and is mandatory for Codex, Claude Code,
and any delegated agent.

- Codex is the orchestrator and final reviewer. It owns `AGENTS.md`,
  `docs/coordination/SPEC.md`, `OWNERSHIP.yaml`, `MILESTONES.md`, `DAG.yaml`, and
  `STATE.json` unless an issue explicitly assigns one of those files elsewhere.
- Claude Code is the implementation worker by default. It may edit only files
  leased to it in `OWNERSHIP.yaml` for the active issue.
- Delegated subagents are read-only by default. They may write only when the
  active issue and ownership lease explicitly name them and their file sets do
  not overlap another writer.
- At most one agent may write the shared worktree at a time. Review, planning,
  and test analysis may run in parallel only when they are read-only.
- Before editing, every agent must read `AGENTS.md`, `backend/ARCHITECTURE.md`,
  `docs/coordination/PROTOCOL.md`, `docs/coordination/STATE.json`, the active issue,
  and its ownership lease.
- Agents communicate through `docs/coordination/inbox/` and
  `docs/coordination/outbox/`. Do not treat chat text as the authoritative task
  state when it conflicts with those files.
- Do not use `git add`, `git commit`, `git reset`, delete untracked files, deploy,
  access production data, or send real email unless a human explicitly approves
  that exact action.
- Preserve unrelated dirty-worktree changes. If an assigned file contains
  overlapping user changes, stop and report the conflict instead of overwriting it.
- A worker must finish with a handoff report containing changed files, commands
  and exact results, unverified items, known risks, and the requested next state.
- Codex independently verifies every acceptance condition. A worker's statement
  that work is complete is evidence to inspect, not proof of completion.
- Stop the automatic loop and request human intervention when any condition in
  `docs/coordination/PROTOCOL.md` under "Human intervention gates" is met.

### Dual-log repair loop

The default coordination channel is a dual-log, pseudo-duplex loop:

- Claude Code is the sole writer of application code, tests, migrations, and
  `docs/coordination/DEVELOPMENT_LOG.md`.
- Codex is the sole writer of `docs/coordination/REVIEW_LOG.md`, protocol state,
  leases, and task dispatch records.
- Neither agent may edit the other agent's log. Each log is append-only; do not
  rewrite, truncate, or "clean up" earlier entries.
- Claude may start a review only by appending a complete `READY_FOR_REVIEW`
  record. Codex may request a repair only by appending a `REWORK` record with
  concrete evidence. Chat text is never a completion marker.
- The scheduler wakes at a low frequency and acts only on a new, complete state
  marker. It must not launch another writer while a Claude implementation turn
  is active.
