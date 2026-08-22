# I-030: Add authorization behavior matrix

Status: Accepted  
Priority: P2

## Owned paths

- `backend/tests/test_authorization.py` (new)
- `backend/app/utils/auth.py`

Endpoint changes require a separate lease expansion.

## Acceptance conditions

- Missing, invalid, expired, and disabled-user credentials return 401.
- Authenticated but insufficient roles return 403.
- Admin/operator/sales/consultant allow/deny behavior is tested for every guard.
- Bearer and cookie paths have representative tests.
- At least one real route per guard is tested; tests do not call external services.

## Acceptance evidence

- Authorization matrix: `8 passed, 5 warnings`.
- Full backend regression: `151 passed, 8 warnings`.
- Independent read-only review additionally ran the matrix with seed tests:
  `11 passed, 5 warnings`.
- The review independently reproduced oversized numeric JWT subjects as 401 and
  unknown-role access as 403 on real LeadViewer and ReportViewer routes.
