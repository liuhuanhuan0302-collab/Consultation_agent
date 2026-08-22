# TURN-0003 focused implementation request

- Run: `backend-architecture-hardening-20260822`
- Issue: `I-040`
- Sender: Codex
- Recipient: Claude Code
- Permission: unattended bypass approved for this lease only

Read the active rules and implement only these two files:

- `backend/app/service/company_research.py`
- `backend/tests/test_company_research.py`

Required outcome:

1. Add failing tests for missing/empty/incomplete/unknown `source_refs`, invalid or
   duplicate indices, unsafe source URLs, invented model sources, and one valid
   normalized match to trusted citations.
2. Implement URL validation/normalization and trusted-source reconciliation.
3. Require at least one valid trusted reference for each of the five factual
   sections that contains research.
4. Analytical sections remain optional references and explicitly analytical.
5. Existing retry/manual-review behavior must fail closed when reconciliation or
   validation fails.

Run:

```powershell
cd E:\Consultation_agent\backend
python -B -m pytest -p no:cacheprovider tests/test_company_research.py -q
```

Write `docs/coordination/outbox/TURN-0003-handoff.md` and exit. Do not edit any
other file, stage, commit, deploy, access production data, invoke live external
APIs, or send email.
