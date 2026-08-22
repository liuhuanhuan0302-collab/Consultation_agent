"""Database bootstrap and transitional schema upgrades."""

from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.db.database import Base, SessionLocal, engine


def init_db() -> None:
    from app import models  # noqa: F401

    if get_settings().environment == "development":
        # Local development remains easy to bootstrap. Production schema is
        # migrated before Uvicorn starts by scripts/migrate_database.py.
        Base.metadata.create_all(bind=engine)
        ensure_schema_upgrades()

    from app.service.api_gateway_service import migrate_gateway_secrets

    db = SessionLocal()
    try:
        migrate_gateway_secrets(db)
    finally:
        db.close()


def ensure_schema_upgrades() -> None:
    """Apply legacy upgrades until all environments use Alembic exclusively."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "questions" not in table_names:
        return

    statements: list[str] = []
    question_columns = {column["name"] for column in inspector.get_columns("questions")}
    if "dimension" not in question_columns:
        statements.append("ALTER TABLE questions ADD COLUMN dimension VARCHAR(120)")
    if "option_text" not in question_columns:
        statements.append("ALTER TABLE questions ADD COLUMN option_text TEXT")

    if "company_leads" in table_names:
        lead_columns = {column["name"] for column in inspector.get_columns("company_leads")}
        if "email" not in lead_columns:
            statements.append("ALTER TABLE company_leads ADD COLUMN email VARCHAR(255)")
        if "priority_strategy" not in lead_columns:
            statements.append("ALTER TABLE company_leads ADD COLUMN priority_strategy VARCHAR(40)")
        if "demand_summary" not in lead_columns:
            statements.append("ALTER TABLE company_leads ADD COLUMN demand_summary TEXT")

    if "reports" in table_names:
        report_columns = {column["name"] for column in inspector.get_columns("reports")}
        if "company_research_json" not in report_columns:
            statements.append("ALTER TABLE reports ADD COLUMN company_research_json TEXT")

    if "gateway_api_config" in table_names:
        gateway_columns = {column["name"] for column in inspector.get_columns("gateway_api_config")}
        if "search_model" not in gateway_columns:
            statements.append("ALTER TABLE gateway_api_config ADD COLUMN search_model VARCHAR(120)")

    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
