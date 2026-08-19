# Repository Engineering Rules

## Backend architecture

All backend changes must follow `backend/ARCHITECTURE.md`.

- API endpoints belong in `backend/app/api/v1/endpoints/` and only handle HTTP concerns.
- Business orchestration belongs in `backend/app/service/`.
- Database queries belong in `backend/app/repositories/`.
- ORM models belong in the matching file under `backend/app/models/`.
- Pydantic request and response models belong in the matching file under `backend/app/schemas/`.
- Configuration and security primitives belong in `backend/app/core/`.
- Database sessions and initialization belong in `backend/app/db/`.
- New schema changes require an Alembic migration. Do not add new runtime `ALTER TABLE` statements.
- Preserve compatibility exports in `app.models` and `app.schemas` when moving existing symbols.
- Add focused tests for behavior changes and run the backend test suite before completion.

## Naming

- Use one domain name consistently across API, service, repository, model, schema and tests.
- This repository uses the singular directory name `service/`; do not introduce a parallel `services/` directory.
- Prefer small domain modules over adding unrelated classes to an existing large file.
