# I-010: Extract questionnaire submission workflow

Status: Accepted  
Priority: P1

## Owned paths

- `backend/app/api/v1/endpoints/public.py`
- `backend/app/service/submission_service.py` (new)
- `backend/app/repositories/submission_repo.py` (new)
- `backend/app/service/diagnosis.py`
- `backend/tests/test_submission_session.py`
- `backend/tests/test_submission_service.py` (new)

## Acceptance conditions

- Endpoint retains only HTTP/session concerns, service call, error mapping,
  response serialization, and post-commit background scheduling.
- Completeness, capacity, persistence, scoring, report/job creation, transaction,
  rollback, and MySQL deadlock retry live in Service/Repository.
- Service does not import FastAPI or throw `HTTPException`.
- Existing status codes, messages, response fields, retry behavior, no-email
  behavior, and idempotency remain unchanged.
- Focused tests prove rollback and no duplicate report/delivery job on retry.

## Validation

```powershell
python -B -m pytest -p no:cacheprovider tests/test_submission_service.py tests/test_submission_session.py tests/test_scoring.py tests/test_report_queue_claim.py tests/test_lead_reroll.py -q
```

## Acceptance evidence

- Focused validation: `42 passed, 8 warnings`.
- Full backend regression: `135 passed, 8 warnings`.
- `git diff --check` and `python -B -m compileall -q app` completed without
  errors (line-ending warnings only).
- Independent read-only review reproduced and verified fixes for post-commit
  retry and late-draft consistency defects.
- Real MySQL two-request locking remains unverified because this run did not
  connect to a production or staging database; SQLite ignores `FOR UPDATE`.
