# TURN-0022 repair request

- Run ID: `backend-architecture-hardening-20260822`
- Turn ID: `TURN-0022`
- Issue ID: `I-140`
- Sender: Codex
- Recipient: claude_code
- Timestamp: `2026-08-28T01:55:00+08:00`

## Objective

Apply the bounded documentation repair from `REV-I-140-1`.

## Leased paths

- `.env.production.example`
- `.env.staging.example`
- `backend/.env.example`
- `docs/coordination/DEVELOPMENT_LOG.md` (append-only)
- `docs/coordination/outbox/TURN-0022-handoff.md`

## Required repair

Update only the PDF configuration comments so operators cannot infer that a
customer email attachment may fall back to Chromium. State truthfully that
customer delivery requires DOCX/LibreOffice, disabling or failing conversion
blocks delivery and reaches manual handling, and the retained legacy fallback
flag does not affect customer attachments.

## Acceptance

- No application behavior or tests change.
- Run scoped `git diff --check` for the three environment example files.
- Append a complete repair development record and write the TURN-0022 handoff.

## Prohibitions

No other file changes, deployment, production data, real email, stage, commit,
push, deletion or cleanup.
