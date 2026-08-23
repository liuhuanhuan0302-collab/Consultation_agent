# TURN-0011 repair request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0011
- Issue ID: I-080
- Sender: Codex
- Recipient: delegated_customer_pdf_worker
- Development record under review: DEV-I-080-2
- Review record: REV-I-080-1
- Requested next state: review

## Bounded repair

1. Validate the persisted customer score snapshot before choosing Word or browser rendering. Require finite non-boolean numeric `total_score`, `max_score`, and `score_rate`, with `total_score >= 0`, `max_score > 0`, `total_score <= max_score`, and `0 <= score_rate <= 1`. Missing or invalid values must raise a delivery validation error and must not enter Chromium fallback. The customer DOCX builder must not silently render dashes for invalid formal-delivery scores.
2. Add focused tests for missing, boolean, non-finite, and out-of-range scores and prove neither LibreOffice nor browser rendering is attempted after score validation fails.
3. Add `backend/deploy/fontconfig/99-consultation-agent-fonts.conf` with an explicit Microsoft YaHei to Noto Sans CJK SC fontconfig alias. Copy it into the report-worker image, run `fc-cache -f`, and add a build-time `fc-match` assertion showing that a Microsoft YaHei request resolves to Noto Sans CJK SC.
4. Change the fixture script to canonical imports (`app.db.database`, `app.models.lead`, `app.models.report`). Prefer canonical imports in the new PDF service/tests as well. Use a fixed date in the database-free fixture.
5. Update architecture documentation only if necessary to describe the strict score gate or deterministic font substitution.
6. Run the focused customer-PDF acceptance suite, full backend suite, compile check, and repository-wide `git diff --check`. Do not wait on or require the unavailable local Docker daemon.
7. Append a complete development record at the absolute end of `DEVELOPMENT_LOG.md` and write `docs/coordination/outbox/TURN-0011-handoff.md`.

Do not stage, commit, deploy, access production data, send email, or modify any non-leased path.
