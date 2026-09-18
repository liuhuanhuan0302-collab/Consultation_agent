# TURN-0037 repair request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0037
- Issue ID: I-224
- Sender: codex
- Recipient: delegated_org_ui_worker

Repair the remaining visual blank area found during independent review. At
1280x720 with one submitted answer, `.organization-submission-list-wrap` is
correctly 86px and pagination starts at y=190, but
`.organization-company-detail` remains 672px tall because the selected detail
section still uses `flex: 1 1 auto`. The resulting bordered white card contains
roughly 430px of empty space below pagination. Make the selected company detail
card shrink to its content on desktop while preserving the previous mobile
scrolling/reachability, long-table max-height scrolling, navigation and all
business bindings. Run the build and produce a fresh READY_FOR_REVIEW handoff.
