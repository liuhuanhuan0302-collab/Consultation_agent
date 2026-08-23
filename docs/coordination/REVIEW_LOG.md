# Review log

Codex is the sole writer. Append only; never modify earlier records.

## Record template

```md
## REV-<task-id>-<attempt>

- Task: <issue ID>
- Reviews: <development record ID>
- Timestamp: <ISO-8601 with timezone>
- Inspected paths: <paths>
- Independent verification: <commands and exact results>
- Findings: <none, or reproducible file/path evidence>
- Next action: <accept, bounded repair instructions, or human decision>

PASS | REWORK | BLOCKED
```

`REWORK` must include a bounded, evidence-based repair request. `BLOCKED` means
automation stops and a human decision is required.

## REV-I-070-1

- Task: I-070
- Reviews: DEV-I-070-1
- Timestamp: 2026-08-23T00:59:00+08:00
- Inspected paths:
  - backend/app/api/v1/endpoints/public.py
  - backend/tests/test_lead_reroll.py
- Independent verification:
  - `python -B -m pytest -p no:cacheprovider -q tests/test_lead_reroll.py` —
    4 passed, 5 warnings.
  - `python -B -m pytest -p no:cacheprovider -q` — 152 passed, 5 warnings.
  - Read-only source inspection confirms `enforce_email_lead_limit` computes its
    cutoff with `utc_now() - timedelta(hours=1)` and no `datetime.utcnow()`
    remains in public.py.
- Findings: none. The helper returns naive UTC, preserving MySQL DATETIME and
  SQLite-fixture compatibility. The test fixes the clock, covers the 429 limit,
  current-lead exclusion, and old-row exclusion.
- Next action: accept I-070. The remaining five warnings are Pydantic v2
  `json_encoders` deprecations in installed dependencies/configuration and are
  outside this bounded fix.

PASS

## REV-I-080-1

- Task: I-080
- Reviews: DEV-I-080-2
- Timestamp: 2026-08-23T21:11:47+08:00
- Inspected paths:
  - backend/app/service/lead_export_service.py
  - backend/app/service/pdf_service.py
  - backend/app/core/config.py
  - backend/Dockerfile
  - backend/scripts/generate_customer_report.py
  - backend/tests/test_customer_docx_pdf.py
  - backend/tests/test_pdf_delivery_gate.py
  - backend/tests/test_lead_export_structure.py
  - backend/app/service/report_queue.py (read only)
- Independent verification:
  - `cd backend && python -B -m pytest -p no:cacheprovider -q tests/test_customer_docx_pdf.py tests/test_pdf_delivery_gate.py tests/test_lead_export_structure.py tests/test_report_queue_claim.py` — 44 passed in 6.01s.
  - `cd backend && python -B -m pytest -p no:cacheprovider -q` — 211 passed, 9 warnings in 21.43s; warnings are existing Pydantic `json_encoders` deprecations.
  - `python -B -m compileall -q app` — exit 0.
  - `docker compose config --no-env-resolution -q` and `docker compose --profile staging config --no-env-resolution -q` — exit 0.
  - `git diff --check` — exit 0 after removal of orchestration-owned trailing whitespace.
  - `python -B scripts/generate_customer_report.py --fixture --output-dir <temporary-directory>` — generated a 157032-byte customer DOCX without database access; PDF conversion was correctly skipped because neither local LibreOffice nor a Docker daemon is available on this host.
- Findings:
  - `lead_export_service.py` currently renders `-` when the persisted score snapshot is absent or malformed, while `pdf_service.py` validates only HTML sections. A formally deliverable customer report can therefore pass through either renderer without trustworthy total, maximum, and rate values. Repair must validate the persisted score snapshot once before renderer selection and fail closed (without entering Chromium fallback) for missing, non-finite, boolean, out-of-range, or inconsistent values.
  - The Docker image installs Noto CJK while the reused DOCX styles declare Microsoft YaHei. A comment is not a deterministic font substitution rule. Repair must add a tracked fontconfig alias from Microsoft YaHei to Noto Sans CJK SC, copy it into the image, refresh the cache, and assert the resolved family during the image build.
  - The new fixture script imports compatibility aggregators (`app.database` and `app.models`) instead of the canonical architecture modules. Repair must use `app.db.database`, `app.models.lead`, and `app.models.report`; new service/test imports should likewise prefer canonical modules.
  - The database-free fixture should use a fixed report date so generated comparison artifacts are repeatable.
- Next action: bounded repair in TURN-0011. Add score fail-closed validation and focused tests, deterministic fontconfig substitution plus build assertion, canonical imports, and a fixed fixture date. Do not change the report content, SMTP, queue business logic, online page, or fallback policy. Re-run the focused and complete backend suites and repository-wide diff check.

REWORK
