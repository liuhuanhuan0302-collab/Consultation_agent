"""Upgrade an empty database or adopt a complete pre-Alembic installation."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import models  # noqa: E402,F401
from app.db.database import Base, engine  # noqa: E402


logger = logging.getLogger(__name__)
BASELINE_REVISION = "2f1c343e7a91"
BASELINE_TABLES = {
    "ai_conversation_messages",
    "case_studies",
    "channel_sources",
    "company_leads",
    "diagnosis_submissions",
    "dimension_scores",
    "export_logs",
    "gateway_api_config",
    "operation_logs",
    "question_answers",
    "question_modules",
    "questions",
    "recommendations",
    "report_delivery_jobs",
    "report_templates",
    "reports",
    "tracking_events",
    "users",
}


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return config


def current_revision() -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def verify_model_schema() -> None:
    inspector = inspect(engine)
    database_tables = set(inspector.get_table_names())
    missing_tables = sorted(set(Base.metadata.tables) - database_tables)
    missing_columns: list[str] = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in database_tables:
            continue
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        missing_columns.extend(
            f"{table_name}.{column.name}"
            for column in table.columns
            if column.name not in actual_columns
        )
    if missing_tables or missing_columns:
        details = []
        if missing_tables:
            details.append("缺少表：" + ", ".join(missing_tables))
        if missing_columns:
            details.append("缺少字段：" + ", ".join(sorted(missing_columns)))
        raise RuntimeError("Alembic 升级后数据库结构仍不完整；" + "；".join(details))


def upgrade_database() -> None:
    config = alembic_config()
    tables = set(inspect(engine).get_table_names())
    application_tables = tables - {"alembic_version"}
    revision = current_revision()

    if revision is None and application_tables:
        missing = sorted(BASELINE_TABLES - application_tables)
        if missing:
            raise RuntimeError(
                "检测到未纳入 Alembic 的残缺数据库，已停止自动升级；缺少基线表："
                + ", ".join(missing)
            )
        logger.warning("检测到完整旧数据库，标记 Alembic 基线 %s 后继续升级", BASELINE_REVISION)
        command.stamp(config, BASELINE_REVISION)

    command.upgrade(config, "head")
    verify_model_schema()
    logger.info("数据库迁移完成，当前版本：%s", current_revision())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    upgrade_database()


if __name__ == "__main__":
    main()
