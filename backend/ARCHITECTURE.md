# Backend Architecture

The backend uses a layered FastAPI architecture with domain-oriented modules.

```text
app/
├── main.py                 # Application assembly and middleware
├── api/v1/endpoints/       # HTTP routes, validation and response mapping
├── service/                # Business workflows and external integrations
├── repositories/           # SQLAlchemy queries and persistence operations
├── models/                 # ORM entities grouped by domain
├── schemas/                # Pydantic contracts grouped by domain
├── core/                   # Environment configuration and security primitives
├── db/                     # Engine, sessions and database initialization
├── utils/                  # Stateless cross-domain helpers
└── data/                   # Versioned static application data
```

## Dependency direction

```text
API -> Service -> Repository -> Model -> Database
 |        |             |
 +------ Schema --------+
```

- API modules translate HTTP requests into application calls. They do not implement scoring, report generation or complex queries.
- Service modules own business workflows, transactions that span several repositories, and third-party integrations.
- Repository modules own reusable database queries. They do not know about FastAPI requests or responses.
- Model modules define persistence only. They do not call services or APIs.
- Schema modules define public contracts only. They do not perform database operations.

Simple read-only CRUD endpoints may call a repository directly when adding a service would provide no business boundary.

## Domain placement

| Domain | ORM model | Pydantic schema | Typical repository/service |
|---|---|---|---|
| Users and roles | `models/user.py` | `schemas/auth.py` | `repositories/user_repo.py` |
| Customer leads | `models/lead.py` | `schemas/lead.py` | `repositories/consult_repo.py` |
| Questionnaires | `models/questionnaire.py` | `schemas/questionnaire.py` | `repositories/questionnaire_repo.py`, `service/diagnosis.py` |
| Reports and delivery | `models/report.py` | `schemas/report.py` | `service/reporting.py`, `service/report_queue.py` |
| Cases | `models/case.py` | `schemas/case.py` | `repositories/case_repo.py` |
| Channels | `models/channel.py` | `schemas/channel.py` | `repositories/qr_code_repo.py` |
| Analytics and audit | `models/audit.py` | `schemas/analytics.py` | admin analytics endpoints |
| API gateway | `models/gateway.py` | `schemas/gateway.py` | `service/api_gateway_service.py` |

## Import conventions

New code should use the canonical paths:

```python
from app.core.config import get_settings
from app.db import get_db
from app.models.lead import CompanyLead
from app.schemas.lead import LeadCreate, LeadResponse
from app.service.diagnosis import score_submission
```

`app.config`, `app.database`, `app.models` and `app.schemas` keep compatibility exports for existing code. Do not add new implementation to the compatibility modules.

## Adding a feature

1. Add or extend the domain schema.
2. Add an ORM model and Alembic migration when persistence changes.
3. Add repository queries.
4. Add service orchestration and external integrations.
5. Add a thin API endpoint.
6. Add focused tests for authorization, validation and business behavior.
7. Run `python -m pytest` and the frontend build when the API contract affects the UI.

## Database changes

Alembic is the source of truth for new schema changes. `db/init_db.py` contains transitional upgrades for old installations only; do not extend that list. Once all deployed environments have migrated, those compatibility upgrades can be removed.
