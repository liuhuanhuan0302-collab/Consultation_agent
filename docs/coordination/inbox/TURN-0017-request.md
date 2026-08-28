# TURN-0017 bounded repair request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0017
- Issue ID: I-100
- Sender: Codex
- Recipient: delegated_report_visual_worker
- Timestamp: 2026-08-27T09:51:51+08:00

## Objective

Repair exactly the two mobile/online findings in `REV-I-100-1` without changing
the accepted Word, PDF, backend, report content, or desktop information structure.

## Required changes

1. Add a mobile override for `.ai-problem-list` so the three findings become a
   readable one-column list at narrow widths. Labels and percentages must remain
   horizontal, separated, and non-overlapping.
2. Update the scoped `ReportCharts.vue` visual system from rounded
   blue/purple/orange dashboard cards to the approved flat white/navy/red/gray
   consulting style.
3. Add the necessary grid-item/canvas containment (`min-width: 0`, max-width or
   equivalent) so a 390px viewport has no horizontal page overflow.

## Leased paths

- `frontend/src/components/ReportCharts.vue`
- `frontend/src/styles.css`
- `docs/coordination/DEVELOPMENT_LOG.md` (append only)
- `docs/coordination/outbox/TURN-0017-handoff.md`

All other paths are forbidden.

## Acceptance

- `cd frontend && npm run build` passes.
- Playwright synthetic report at 1440px remains visually sound.
- At 390px: `document.documentElement.scrollWidth <= window.innerWidth`;
  problem labels are horizontal and do not overlap percentages; charts fit the
  viewport; console has no warnings/errors.
- `git diff --check -- frontend/src/components/ReportCharts.vue frontend/src/styles.css`
  exits 0.
- Append a complete `READY_FOR_REVIEW` record and TURN-0017 handoff, then exit.

