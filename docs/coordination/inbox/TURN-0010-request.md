# TURN-0010 implementation request

- Run ID: backend-architecture-hardening-20260822
- Turn ID: TURN-0010
- Issue ID: I-080
- Sender: Codex
- Recipient: delegated_customer_pdf_worker
- Timestamp: 2026-08-23T20:35:26+08:00

## Objective

Review and complete the existing in-progress Word -> LibreOffice -> customer PDF
implementation against `ISSUES/ISSUE-I-080.md`.

## Scope and ownership

Only edit the active paths in `OWNERSHIP.yaml`. Preserve all existing dirty
changes in those paths and make only bounded corrections. Do not touch forbidden
paths, stage, commit, deploy, access production data, or send email.

## Required review points

- Verify that `build_final_diagnosis_report` is the single rendering component
  used by both internal Word part three and the customer DOCX.
- Verify customer DOCX data-source isolation, real score fields, Word layout and
  charts, and internal Word regression.
- Harden LibreOffice discovery, Writer conversion command, per-job profile/temp
  isolation, timeout, cleanup, and actionable logging.
- Add DOCX/fallback options to all environment templates and keep Chromium as
  fallback only.
- Ensure the Docker image used by `report_worker` contains LibreOffice Writer and
  deterministic CJK font support.
- Verify that PDF validation has no text extraction or size threshold.
- Complete focused tests and the fixture-generation script without database or
  email for its fixture mode.

## Acceptance commands

Run the focused and full test commands, Compose config checks, and `git diff
--check` listed in the issue. Append a complete `READY_FOR_REVIEW` record to
`DEVELOPMENT_LOG.md`, write the handoff file, and then exit.
