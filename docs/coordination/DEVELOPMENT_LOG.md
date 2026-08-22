# Development log

Claude Code is the sole writer. Append only; never modify earlier records.

## Record template

```md
## DEV-<task-id>-<attempt>

- Task: <issue ID>
- Attempt: <positive integer>
- Timestamp: <ISO-8601 with timezone>
- Allowed paths: <paths>
- Changed paths: <paths, or none>
- Summary: <what changed and why>
- Commands actually run: <commands and exact results; redact secrets>
- Not run / unverified: <items>
- Risks / blockers: <items or none>

READY_FOR_REVIEW
```

Use `BLOCKED` instead of `READY_FOR_REVIEW` only when a protocol human-intervention
gate applies. Do not write a record until all fields are complete.

## DEV-I-070-1

- Task: I-070
- Attempt: 1
- Timestamp: 2026-08-23T00:52:32+08:00
- Allowed paths: backend/app/api/v1/endpoints/public.py, backend/tests/test_lead_reroll.py, docs/coordination/DEVELOPMENT_LOG.md (append-only)
- Changed paths:
  - backend/app/api/v1/endpoints/public.py
  - backend/tests/test_lead_reroll.py
- Summary:
  - Replaced the deprecated naive `datetime.utcnow()` in `enforce_email_lead_limit`
    with the canonical `utc_now()` helper from `app.utils.time_utils`
    (`datetime.now(timezone.utc).replace(tzinfo=None)`), keeping the one-hour
    window, the case-insensitive email match, and the current-lead exclusion
    unchanged. `utc_now()` returns a naive UTC datetime, so the cutoff stays
    compatible with MySQL DATETIME values and SQLite test fixtures.
  - `from datetime import datetime, timedelta` became `from datetime import
    timedelta` (datetime no longer referenced); added
    `from app.utils.time_utils import utc_now`.
  - Added focused regression test
    `test_email_hourly_limit_cutoff_uses_utc_now_helper` in
    backend/tests/test_lead_reroll.py: monkeypatches `public.utc_now` to a fixed
    naive UTC clock (2020-01-01 12:00:00) and asserts (a) 3 leads within the
    hour raise 429, (b) excluding the current lead drops the count to 2 and
    passes, (c) 10 leads older than one hour are not counted. If the
    implementation fell back to `datetime.utcnow()`, the fixed past clock would
    place the "within-hour" leads outside the real cutoff and the test would
    fail, proving the helper is consulted.
  - Note: public.py carried pre-existing uncommitted changes from earlier work;
    this turn only touched the three lines described above.
- Commands actually run:
  - `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_lead_reroll.py`
    -> `4 passed, 5 warnings in 1.32s` (warnings are pre-existing Pydantic
    `json_encoders` deprecations in site-packages).
  - `grep -n "utcnow|datetime" backend/app/api/v1/endpoints/public.py`
    -> only `15:from datetime import timedelta`; no `datetime.utcnow()` remains.
- Not run / unverified:
  - Full backend test suite not run (out of scope; only the required focused
    test was executed).
  - No runtime HTTP check of the endpoint; behavior verified via direct function
    call against an in-memory SQLite engine.
- Risks / blockers: none.

READY_FOR_REVIEW
