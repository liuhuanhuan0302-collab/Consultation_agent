from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_kwargs = {
    "pool_pre_ping": True,
    "connect_args": connect_args,
}
if not settings.database_url.startswith("sqlite"):
    engine_kwargs.update(
        {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
        }
    )
engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrades()


def ensure_schema_upgrades() -> None:
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

    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
