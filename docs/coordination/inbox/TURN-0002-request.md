# TURN-0002 focused implementation request

- Run: `backend-architecture-hardening-20260822`
- Issue: `I-040`
- Sender: Codex
- Recipient: Claude Code

Implement only the core research-evidence validation in:

- `backend/app/service/company_research.py`
- `backend/tests/test_company_research.py`

Do not modify the other leased files during this focused turn.

## Required changes

1. Add focused tests first for missing/empty `source_refs`, unknown keys,
   incomplete factual-section coverage, invalid/duplicate indices, unsafe URL
   schemes, an invented model URL, and a valid normalized trusted URL match.
2. Implement small pure helpers for URL validation/normalization and trusted-source
   reconciliation.
3. Require references for the five factual sections with content; analytical
   sections remain optional and explicitly analytical.
4. Reconcile model sources with the actual citations/results supplied to
   `research_company()`. Never persist an unmatched model URL.
5. If model evidence cannot be mapped, let existing retries fail closed rather
   than silently creating references.

## Constraints

Follow the active lease and all repository rules. Preserve unrelated changes. No
live API, email, production data, staging, commit, reset, delete, or deployment.

## Validation

```powershell
cd E:\Consultation_agent\backend
python -B -m pytest -p no:cacheprovider tests/test_company_research.py -q
```

Write `docs/coordination/outbox/TURN-0002-handoff.md` and exit. Do not perform
Word/HTML display changes in this turn; Codex will schedule those after review.
