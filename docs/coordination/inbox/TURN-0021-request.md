# TURN-0021 request

- Run ID: `backend-architecture-hardening-20260822`
- Turn ID: `TURN-0021`
- Issue ID: `I-140`
- Sender: Codex
- Recipient: claude_code
- Timestamp: `2026-08-27T23:38:19+08:00`

## Objective

Implement `docs/coordination/ISSUES/ISSUE-I-140.md`, using the approved preview
PDF and `tmp/pdfs/customer-preview-v2/build_preview.py` as exact visual evidence
while integrating the behavior into production renderers and delivery flow.

## Leased paths

Exactly the active `lease-turn-0021` paths in `OWNERSHIP.yaml`, plus the handoff
file and append-only development log entry listed there.

Lease expansion approved at `2026-08-27T23:42:00+08:00`: add
`frontend/src/components/CustomerReportView.vue` so the public and administrator
report surfaces can share one complete presentation component.

Lease expansion approved at `2026-08-28T00:08:00+08:00`: add
`backend/tests/test_system_settings.py` solely to replace two obsolete visual-copy
assertions that conflict with I-140 (old long scene sentence and the removed
`进一步沟通` heading) while preserving contact snapshot coverage.

## Forbidden paths

Exactly the `lease-turn-0021` forbidden paths and all orchestrator-owned
coordination files other than the leased development log and handoff.

## Required behavior

- Preserve all prior accepted changes, including TURN-0020 regeneration.
- Build/reuse a shared presentation/view contract rather than maintaining five
  divergent copies of customer report structure.
- Match every presentation rule in ISSUE-I-140 and the approved 11-page preview.
- Keep persisted AI prose and scores unchanged; derive M01-M09 judgments at
  render time using deterministic module/score rules.
- Preserve historical contact snapshots. New/regenerated reports snapshot the
  then-current centralized setting.
- Make email PDF strictly customer-DOCX -> LibreOffice/Word PDF. Remove or bypass
  Chromium fallback for customer email attachment, without silently changing an
  unrelated browser-preview feature if one exists.
- Implement three bounded conversion attempts and a clear manual-handling state.
  Provide an administrator action labelled/understood as “重新生成附件并发送”,
  safely rejecting duplicates or already-sent delivery.
- Do not couple AI-content regeneration to PDF generation, queue creation or
  email sending.
- Keep endpoints thin and business orchestration in service modules.

## Acceptance and commands

- Add focused tests for full Word embedding, shared section content, exact copy,
  no sixth/management wording, historical snapshots, DOCX-only delivery,
  three-attempt failure/manual state, safe manual retry and regeneration
  non-delivery behavior.
- Run focused backend tests for every changed behavior.
- Run `python -B -m pytest -p no:cacheprovider -q` from `backend`.
- Run `python -m compileall app` from `backend`.
- Run `npm run build` from `frontend`.
- Generate a representative customer DOCX and PDF from synthetic fixture data;
  inspect page count/text and render pages for visual review. Use Word 2021 if
  local LibreOffice is absent and report that fact exactly.
- Run scoped `git diff --check` for every leased implementation/test path.
- Append one complete `READY_FOR_REVIEW` record and write the TURN-0021 handoff
  with exact results, unverified items and risks.

## Non-goals

No prompt/scoring/substantive prose rewrite, production backfill/data, live paid
call, real email, deployment, migration, stage, commit, push, deletion or cleanup.
