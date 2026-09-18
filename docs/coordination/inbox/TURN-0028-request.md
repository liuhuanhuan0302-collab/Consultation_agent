# TURN-0028 request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0028
- Issue ID: I-200
- Sender: Codex orchestrator
- Recipient: Claude Code implementation worker
- Timestamp: 2026-08-28T18:40:00+08:00

## Objective

Implement ISSUE-I-200 exactly: administrator queue settings, queue overview and
manual review actions in the existing System Settings backend/frontend.

## Required implementation notes

- Keep HTTP handlers thin; repository queries in the repository layer and
  orchestration/audit in services.
- Reuse `ReportQueueSetting`, `report_queue_scheduler` and existing operation-log
  machinery. Do not duplicate queue transition rules in endpoints.
- Return count breakdowns for all four queue states, lifecycle states and known
  processing stages. ETA must be clearly approximate/null when no defensible
  throughput estimate exists; do not invent precision.
- Manual rows need stable IDs, company/report identifiers safe for admins,
  task kind, attempts/error/timestamps and approval state.
- Require an explicit boolean confirmation only when processing concurrency is
  increased. Validate all bounds before commit.
- UI must remain usable at desktop and narrow widths. Batch selection must clear
  safely after successful action and show request errors through existing toast
  handling.
- Run browser QA only with synthetic/intercepted API data; do not access or
  capture real customer data.

## Lease and forbidden paths

The authoritative lease is `lease-turn-0028` in `OWNERSHIP.yaml`. Do not edit
outside its owned paths. In particular, do not modify queue claim/execution
semantics, migrations, AGENTS/protocol state, deployment files, or send email.

## Acceptance commands

- Focused backend tests for settings/overview/auth/actions/audit.
- Complete backend pytest suite and compileall.
- `npm run build` in `frontend`.
- Scoped/global `git diff --check`.
- Playwright CLI synthetic API-intercept QA at desktop and narrow viewport,
  including save validation, increase-risk confirmation, refresh, batch approve
  and reject, responsive layout and console errors.

End with a complete READY_FOR_REVIEW handoff and append-only development record.

