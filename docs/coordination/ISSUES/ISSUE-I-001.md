# I-001: Verify configuration startup gates

Status: Accepted without code changes

## Acceptance evidence

- `python -m py_compile app/core/config.py`: passed.
- Full backend suite: `117 passed`, 8 warnings.
- Alembic: one head, `9c31a760`.
- Existing tests cover staging database-name isolation, staging email allowlist,
  and placeholder environment safeguards.

Do not re-edit `config.py` unless a later test supplies new evidence.
