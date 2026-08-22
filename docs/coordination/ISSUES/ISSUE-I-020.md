# I-020: Extract admin lead workflows

Status: Accepted  
Priority: P1

## Owned paths

- `backend/app/api/v1/endpoints/admin/leads.py`
- `backend/app/service/lead_service.py` (new)
- `backend/app/repositories/lead_repo.py` (new)
- `backend/tests/test_lead_service.py` (new)
- Existing lead delete, delivery, export, and reroll tests

## Acceptance conditions

Move reusable queries and detail/email/reroll/research/export-audit/delivery/delete
orchestration out of the endpoint. Preserve permissions, deletion scope, selected
latest report, filenames, document content, and delivery behavior. Service must not
depend on FastAPI.

Stop for a human if deletion semantics, role access, or the definition of “latest
report” would change.

## Acceptance evidence

- Focused lead workflow validation: `18 passed, 8 warnings`.
- Full backend regression: `143 passed, 8 warnings`.
- Independent read-only review found no behavior regression or human-gate change.
- Latest submission remains delegated to the original `id DESC` repository rule;
  deletion remains delegated to the original cascade implementation.
