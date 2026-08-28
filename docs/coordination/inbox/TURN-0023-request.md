# TURN-0023 request

- Run ID: `backend-architecture-hardening-20260822`
- Turn ID: `TURN-0023`
- Issue ID: `I-150`
- Sender: Codex
- Recipient: claude_code
- Timestamp: `2026-08-28T10:15:00+08:00`

## Objective

Implement the frontend portion of `ISSUE-I-150.md` within lease-turn-0023.

## Required behavior

- Keep creation date range, processing status and time order in a compact quick
  toolbar. Date inputs must not clip.
- Add a keyboard- and screen-reader-usable advanced filter modal for industry,
  lead level, view and export status, with apply/reset/cancel and active-filter
  count/summary. Preserve the same backend query contract and export filters.
- Remove the page-size selector. Compute a bounded page size from viewport height
  and update on resize without stranding the current page.
- Add first/previous/numeric page window/ellipsis/next/last navigation. Use
  deterministic logic for zero, one, middle and end ranges.
- Expand `industries` in `useQuestionnaire.ts` to a broad, readable taxonomy that
  includes internet/software and keeps other/general choices sensible.
- Preserve all accepted report/delivery/regeneration frontend work.

## Acceptance

- Run frontend production build.
- If no unit-test harness exists, keep pagination logic deterministic and report
  that limitation; perform browser QA at 1440/1280 desktop and 390 mobile with
  no clipping, horizontal overflow or console errors.
- Verify modal keyboard close/focus behavior where practical.
- Run scoped diff check on leased implementation paths.
- Append a complete READY_FOR_REVIEW record and TURN-0023 handoff.

## Non-goals and prohibitions

No backend/API/schema/scoring/report/delivery change; no AGENTS.md edit by the
worker; no deployment, production data, real email, stage, commit, push,
deletion or cleanup.
