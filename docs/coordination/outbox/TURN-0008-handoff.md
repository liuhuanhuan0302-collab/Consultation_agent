# TURN-0008 handoff

- Run: `backend-architecture-hardening-20260822`
- Turn: TURN-0008
- Issue: I-050 — Synchronize documentation
- Sender: Claude Code (implementation worker)
- Recipient: Codex (orchestrator / reviewer)
- Timestamp: 2026-08-23

## Objective

Synchronize `backend/ARCHITECTURE.md`, `README.md` and `PROJECT_OVERVIEW.md`
with the actual code: directory layout, questionnaire-submission and
lead-management call chains, role matrix, trusted company-research evidence
rules and fail-closed delivery behavior. Remove stale single-file `models.py` /
`admin.py` descriptions. Do not claim unexecuted checks.

## Non-goals

No code changes, no DEPLOY_SERVER.md edit (no deployment facts changed in the
synced sections), no staging/committing, no deployment, no database access, no
real network/email.

## Leased and forbidden paths

- Leased: `backend/ARCHITECTURE.md`, `README.md`, `PROJECT_OVERVIEW.md`,
  `docs/coordination/outbox/TURN-0008-handoff.md` (per OWNERSHIP.yaml
  lease-turn-0008).
- Forbidden paths (all others, in particular `backend/app/**`,
  `frontend/**`, `backend/migrations/**`, `backend/scripts/**`) were only read.

## Changed files

1. `backend/ARCHITECTURE.md`
   - Replaced directory tree with actual layout (`admin/` endpoint package,
     domain-split `models/` and `schemas/`, `core/`, `db/`, `data/`, compat
     modules `app/config.py` / `app/database.py` marked as re-exports only).
   - Updated domain placement table (lead_repo/lead_service, submission_repo/
     submission_service/scoring, company_research, report_analysis/
     report_content/report_queue, etc.).
   - Added submission and lead-management call chains with transaction
     boundaries and HTTP error mapping (404/409/422/503).
   - Added role matrix (5 guards × 4 roles) and Bearer/Cookie authentication
     behavior (401/403), citing `tests/test_authorization_matrix.py`.
   - Added "Company research evidence" and "Failure behavior (fail closed)"
     sections: trusted-source reconciliation, structural validation rules,
     cache reuse condition, exponential-backoff retry, manual-review terminal
     state, PDF delivery gate, public error redaction, staging isolation.
   - Corrected import-convention examples to `app.core.config` /
     `app.db.database` / service entry points; compat modules noted.

2. `README.md` (preserved pre-existing uncommitted edits: queue-worker
   paragraph and Alembic deploy note)
   - Rewrote backend directory structure (endpoints split, models/schemas by
     domain, core/db, data, compat modules).
   - Added one-paragraph trusted-evidence and fail-closed summary.
   - Corrected scoring description: total score is the dynamic sum of enabled
     module max scores (current bundled data totals 270); removed the stale
     "260-point normalization" claim; rate-based risk thresholds.

3. `PROJECT_OVERVIEW.md`
   - Full directory tree synced to actual files (backend + frontend +
     official-website + docs/coordination).
   - Models section rewritten per domain files (no single `models.py`).
   - Module table synced to `app/data/official_questionnaire.json` (names,
     question counts, max scores; total 270).
   - Scoring section synced to `service/scoring.py` (rate thresholds, dynamic
     max) plus lead-level rule from `service/diagnosis.py`.
   - API inventory replaced with the 43 real routes and per-route guards;
     removed the non-existent `GET /api/public/reports/{token}/pdf` (PDF is
     email-delivered only) and non-existent `admin.py`.
   - Added role-guard table and auth behavior.
   - Added submission and lead call chains.
   - Added company-research evidence rules and fail-closed rules sections.
   - Security section updated (staging DB-suffix + SMTP allowlist, encrypted
     gateway keys, rate limits, session-token ownership, atomic queue claim,
     capacity limits).
   - Deployment section marked as not re-verified in this turn.

## Factual basis (all read directly from code this turn)

- `backend/app/api/v1/endpoints/public.py`, `admin/leads.py`, `admin/auth.py`,
  `admin/reports.py`, `admin/_shared.py`; route inventory from
  `@router.*` grep across `endpoints/`.
- `backend/app/service/submission_service.py`, `lead_service.py`,
  `company_research.py`, `report_queue.py`, `reporting.py`,
  `report_analysis.py`, `report_content.py`, `scoring.py`, `diagnosis.py`,
  `api_gateway_service.py` (partial), `lead_export_service.py` (grep).
- `backend/app/repositories/submission_repo.py`, `lead_repo.py`.
- `backend/app/utils/auth.py`, `backend/app/models/user.py`,
  `backend/app/models/__init__.py`.
- `backend/app/main.py`, `backend/app/api/v1/router.py`,
  `backend/app/core/config.py`, `backend/app/config.py`,
  `backend/app/database.py`.
- `backend/app/data/official_questionnaire.json` (10 modules, 68 questions,
  per-module max scores, total 270).
- `backend/tests/` listing (23 test files) and
  `backend/tests/test_authorization_matrix.py`, `test_pdf_delivery_gate.py`.
- `frontend/src/` structure, `frontend/src/api.ts` (endpoint usage),
  `frontend/Caddyfile`.

## Independent review after implementation

Codex (independent reviewer) executed the following after the documentation
changes were made:

- `python -B -m pytest -p no:cacheprovider -q` — 151 passed, 8 warnings in 17.16s
- `python -B -m compileall -q app` — succeeded
- `python -B -m alembic -c alembic.ini heads` — 9c31a760 (head)
- Read-only enumeration via `app.openapi()` — 43 operations (11 public,
  1 health, 31 admin)

The audit performed no deployment, commits, database writes, real email, or
web/network searches.

## Commands executed and exact results

### This worker

The implementation worker performed read-only code inspection only. It did
not run tests or acceptance commands itself this turn.

## Unverified items

- Frontend production build was not re-run for these documentation-only edits.
- Docker/Compose deployment was not re-verified in this environment.

## Known risks / observations for the reviewer

1. Frontend mismatch (outside this lease): `frontend/src/api.ts` defines
   `POST /api/public/reports/{token}/email` (claim full report) but no such
   backend route exists in `public.py`. Not touched by this issue; may need a
   separate issue if the feature is still wanted.
2. `PROJECT_OVERVIEW.md` previously claimed a public PDF download endpoint and
   a 260-point normalization; both were removed/corrected after code
   verification. If those behaviors are expected product features, they are
   absent from the backend today.
3. `render_fallback_html` still exists in `reporting.py` but the current
   generation path fails closed to manual review instead of delivering the
   fallback; docs describe the current path.

## Requested next state

Codex review of the three doc diffs (`README.md`, `PROJECT_OVERVIEW.md`,
`backend/ARCHITECTURE.md`) against the issue acceptance conditions
(actual-code directory layout, call paths, role matrix, endpoint inventory,
trusted-evidence and failure behavior; no unexecuted checks claimed by the
worker). The independent read-only audit results recorded above (test suite,
compileall, alembic heads) are reviewer evidence, not worker claims.
No state-file change was made by this worker.
