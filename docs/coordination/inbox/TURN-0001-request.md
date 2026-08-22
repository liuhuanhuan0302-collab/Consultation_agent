# TURN-0001 implementation request

- Run: `backend-architecture-hardening-20260822`
- Issue: `I-040`
- Sender: Codex
- Recipient: Claude Code
- State: implementation requested

## Objective

Implement `docs/coordination/ISSUES/ISSUE-I-040.md` completely and only within
the active lease in `OWNERSHIP.yaml`.

## Required behavior

1. Treat actual provider citations/results as the only trusted source set.
2. Normalize-match model source URLs to trusted URLs; never persist an invented
   or unsafe URL.
3. Require valid `source_refs` for every factual section with content. Reject
   missing, empty, unknown, duplicate, boolean, non-integer, negative, zero, and
   out-of-range references.
4. Preserve analytical sections as explicitly non-factual analysis.
5. Fail closed through the existing retry/manual-review path when evidence cannot
   be mapped.
6. Replace generic source fallbacks in leased output code with concrete references.
7. Preserve existing external behavior outside stricter evidence rejection.

## Constraints

- Read `AGENTS.md`, `CLAUDE.md`, `backend/ARCHITECTURE.md`, the SPEC, protocol,
  state, issue, and ownership lease before editing.
- Do not edit outside `owned_paths`; request lease expansion instead.
- Do not run live DeepSeek/search/SMTP calls. Tests must mock external services.
- Do not stage, commit, reset, delete files, deploy, or access production data.
- Preserve all unrelated dirty-worktree changes in leased files.

## Acceptance command

```powershell
cd E:\Consultation_agent\backend
python -B -m pytest -p no:cacheprovider tests/test_company_research.py tests/test_lead_export_structure.py -q
```

After the focused command passes, run the complete backend suite if time permits.

## Handoff

Write `docs/coordination/outbox/TURN-0001-handoff.md` with changed files, exact
commands/results, unverified items, known risks, and requested next state. Then
exit. Do not declare the issue accepted; Codex reviews independently.
