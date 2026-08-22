# I-040: Bind company research to trusted sources

Status: Accepted  
Priority: P0

## Owned paths

- `backend/app/service/company_research.py`
- `backend/tests/test_company_research.py`
- `backend/app/service/lead_export_service.py`
- `backend/tests/test_lead_export_structure.py`

## Forbidden paths

API endpoints, gateway configuration, report queue, models, schemas, migrations,
production scripts, and all unrelated dirty files.

## Acceptance conditions

- Trusted sources come only from the actual search provider response.
- Model URLs must normalize-match trusted URLs; invented URLs cannot persist.
- `source_refs` is required; unknown keys and invalid indices fail.
- Every factual section with content has at least one valid trusted reference.
- Missing evidence retries and ultimately enters manual review rather than
  producing a deliverable.
- Word/HTML factual sections use concrete source numbers, not a generic fallback.
- Add tests for invented URLs, valid normalized matches, missing/empty/incomplete
  refs, unknown keys, booleans, duplicates, unsafe schemes, and display behavior.

## Validation

```powershell
cd E:\Consultation_agent\backend
python -B -m pytest -p no:cacheprovider tests/test_company_research.py tests/test_lead_export_structure.py -q
```

## Human gate

Stop if the provider has no machine-verifiable citations and delivery would
require a policy exception, or if historical production backfill is proposed.

## Acceptance evidence

- Focused validation: `41 passed, 5 warnings`.
- Full backend regression: `122 passed, 8 warnings`.
- Independent read-only review confirmed the model-URL, duplicate-reference,
  missing-display, and unsafe historical-link bypasses are closed.
- No network search, email, deployment, production database operation, staging,
  commit, or staging-area mutation was performed.
