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

## DEV-I-080-1

- Task: I-080
- Attempt: 1
- Timestamp: 2026-08-23T20:53:14+08:00
- Allowed paths: backend/app/service/lead_export_service.py, backend/app/service/pdf_service.py, backend/app/core/config.py, backend/Dockerfile, backend/.env.example, .env.production.example, .env.staging.example, backend/ARCHITECTURE.md, backend/scripts/generate_customer_report.py, backend/tests/test_customer_docx_pdf.py, backend/tests/test_pdf_delivery_gate.py, backend/tests/test_lead_export_structure.py, docs/coordination/DEVELOPMENT_LOG.md (append-only), docs/coordination/outbox/TURN-0010-handoff.md
- Changed paths:
  - backend/app/service/lead_export_service.py
  - backend/app/service/pdf_service.py
  - backend/app/core/config.py
  - backend/Dockerfile
  - backend/.env.example
  - .env.production.example
  - .env.staging.example
  - backend/ARCHITECTURE.md
  - backend/scripts/generate_customer_report.py
  - backend/tests/test_customer_docx_pdf.py
  - backend/tests/test_lead_export_structure.py
- Summary:
  - Extracted `build_final_diagnosis_report` as the one Word renderer used by internal Word part three and the customer-only DOCX. The customer document adds a fixed-layout navy/gray business header with persisted report metadata and score snapshot, then reuses the same headings, tables, widths, fonts, spacing, page break and two chart builders.
  - Customer DOCX construction receives only the company name plus final report fields; focused ZIP/XML sentinel tests prove contact, phone, email, WeChat, source, search/research and admin/view sentinels never enter the package.
  - Formal delivery now snapshots ORM-backed report values on the owning thread, builds DOCX/fallback HTML bytes before background conversion, and passes only bytes to `asyncio.to_thread`, avoiding cross-thread SQLAlchemy lazy loads.
  - Added isolated LibreOffice input/output/profile directories, bounded 10-600 second timeout, executable discovery, `pdf:writer_pdf_Export`, stdout/stderr diagnostics, cleanup, and configuration-controlled Chromium fallback that preserves the LibreOffice root error whenever fallback is disabled or browser rendering is unavailable.
  - Added LibreOffice Writer, fontconfig and Noto CJK to the report-worker image; documented the Microsoft YaHei to Noto Sans CJK SC Linux fallback; exposed DOCX/fallback/LibreOffice variables in all three environment templates.
  - Added a database-free `--fixture` command for an 奥飞娱乐 DOCX and optional locally converted PDF, plus fixed-layout, shared-layout-signature, score, isolation, filename, conversion, timeout, cleanup, fallback and ORM-thread-boundary tests.
- Commands actually run:
  - `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py tests/test_pdf_delivery_gate.py tests/test_lead_export_structure.py tests/test_report_queue_claim.py` -> `44 passed in 6.36s`.
  - `cd backend && python -B -m pytest -p no:cacheprovider -q` -> `211 passed, 9 warnings in 18.23s`; warnings are pre-existing Pydantic `json_encoders` deprecations in site-packages.
  - `docker compose config --no-env-resolution -q` -> exit 0.
  - `docker compose --profile staging config --no-env-resolution -q` -> exit 0.
  - Exact `docker compose config` and `docker compose --profile staging config` -> could not resolve because this checkout intentionally has no local `.env.production` / `.env.staging` files; no env files were created or secrets accessed.
  - `git diff --check -- <all leased tracked implementation paths>` -> exit 0 (only line-ending warnings).
  - Exact repository-wide `git diff --check` -> one pre-existing/orchestrator-owned failure at `docs/coordination/MILESTONES.md:29` (`Issues: I-080, I-060` trailing spaces); worker did not modify the forbidden orchestration file.
  - `docker build --check -f backend/Dockerfile backend` -> not executed successfully because Docker Desktop Linux daemon is unavailable (`npipe:////./pipe/dockerDesktopLinuxEngine` missing); no image build was attempted afterward per orchestrator instruction.
- Not run / unverified:
  - No real LibreOffice conversion or visual PDF comparison on this Windows host because LibreOffice is not installed and Docker daemon is unavailable. The subprocess invocation, Writer filter, isolated directories/profile, diagnostics and cleanup are covered with focused tests; fixture DOCX generation is exercised in a subprocess without database queries.
  - No deployment, production/staging data access, real email, commit, stage or push.
- Risks / blockers:
  - Container font substitution uses the distributable Noto Sans CJK SC fallback rather than shipping proprietary Microsoft YaHei; final visual parity should be checked once in the built Linux image.
  - Exact Compose config needs local env files supplied by the human/deployment environment. Repository-wide diff check needs the orchestrator-owned trailing whitespace removed after this writer exits.

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

## DEV-I-080-2

- Task: I-080
- Attempt: 2
- Timestamp: 2026-08-23T20:56:00+08:00
- Allowed paths: backend/app/service/lead_export_service.py, backend/app/service/pdf_service.py, backend/app/core/config.py, backend/Dockerfile, backend/.env.example, .env.production.example, .env.staging.example, backend/ARCHITECTURE.md, backend/scripts/generate_customer_report.py, backend/tests/test_customer_docx_pdf.py, backend/tests/test_pdf_delivery_gate.py, backend/tests/test_lead_export_structure.py, docs/coordination/DEVELOPMENT_LOG.md (append-only), docs/coordination/outbox/TURN-0010-handoff.md
- Changed paths: docs/coordination/DEVELOPMENT_LOG.md only in this attempt; this attempt only repairs the log landing position and makes no additional application-code change. Application changes from TURN-0010 remain in the leased paths listed in `docs/coordination/outbox/TURN-0010-handoff.md`.
- Summary: Only repaired the development-log landing point by appending this complete record at the absolute end of the file. No application code, test, environment template, Dockerfile, architecture document, fixture script, or handoff content was changed in Attempt 2.
- Commands actually run (reused completed TURN-0010 validation evidence; no command was rerun in this log-only attempt):
  - `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py tests/test_pdf_delivery_gate.py tests/test_lead_export_structure.py tests/test_report_queue_claim.py` -> `44 passed in 6.36s`.
  - `cd backend && python -B -m pytest -p no:cacheprovider -q` -> `211 passed, 9 warnings in 18.23s`; warnings are pre-existing Pydantic `json_encoders` deprecations.
  - `docker compose config --no-env-resolution -q` -> exit 0.
  - `docker compose --profile staging config --no-env-resolution -q` -> exit 0.
  - Leased implementation paths passed `git diff --check` (line-ending warnings only).
- Not run / unverified: Exact Compose config remains unavailable because local `.env.production` / `.env.staging` files are absent; Docker daemon remains unavailable, so no image build or real LibreOffice visual conversion was run. No deployment, production/staging data access, real email, stage, commit or push occurred.
- Risks / blockers: Repository-wide `git diff --check` still has only the orchestrator-owned `docs/coordination/MILESTONES.md:29` trailing whitespace. Container font substitution and final PDF visual parity still require verification in a built Linux image.

READY_FOR_REVIEW
