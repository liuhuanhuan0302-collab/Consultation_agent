# TURN-0012 completion request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0012
- Issue ID: I-080
- Sender: Codex
- Recipient: audit_pdf_libreoffice
- Previous turn: TURN-0011 ended because the worker hit its tool usage limit after partially writing the score gate.
- Requested next state: review

## Complete and verify the bounded repair

Inspect the partial changes first. Preserve correct score-validation work already present.

1. Complete focused tests for missing/malformed/boolean/non-finite/out-of-range/inconsistent persisted scores. Prove invalid score prevents both LibreOffice conversion and Chromium fallback.
2. Add the leased fontconfig alias file mapping Microsoft YaHei to Noto Sans CJK SC. Copy it into `/etc/fonts/conf.d/` before `fc-cache -f` and add a robust Docker build assertion using `fc-match` that verifies Noto is selected.
3. Confirm canonical imports and fixed fixture date are complete.
4. Fix any test failures caused by strict rate consistency. Do not weaken the gate and do not touch AI content, SMTP, queue business logic, online pages, or non-leased files.
5. Run the focused suite, full backend suite, compile check, and repository-wide `git diff --check`. Docker daemon is unavailable, so inspect Docker syntax but do not wait on Docker.
6. Append a complete DEV-I-080 record at the absolute end of DEVELOPMENT_LOG.md and create TURN-0012-handoff.md.

No stage, commit, deploy, production data, or real email.
