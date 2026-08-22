"""add required city input for new customer leads

Revision ID: 8b22f001
Revises: 5d4f6a2b
Create Date: 2026-08-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b22f001"
down_revision: Union[str, Sequence[str], None] = "5d4f6a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("company_leads", sa.Column("city", sa.String(length=120), nullable=True))
    if "ix_company_leads_city" not in _index_names("company_leads"):
        op.create_index(op.f("ix_company_leads_city"), "company_leads", ["city"], unique=False)

    _add_column_if_missing("reports", sa.Column("research_status", sa.String(length=32), nullable=True))
    _add_column_if_missing("reports", sa.Column("research_started_at", sa.DateTime(), nullable=True))
    _add_column_if_missing("reports", sa.Column("research_completed_at", sa.DateTime(), nullable=True))
    _add_column_if_missing("reports", sa.Column("generation_started_at", sa.DateTime(), nullable=True))
    _add_column_if_missing("reports", sa.Column("generation_completed_at", sa.DateTime(), nullable=True))
    _add_column_if_missing("reports", sa.Column("pdf_status", sa.String(length=32), nullable=True))
    _add_column_if_missing("reports", sa.Column("pdf_started_at", sa.DateTime(), nullable=True))
    _add_column_if_missing("reports", sa.Column("pdf_completed_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE reports SET research_status = 'generated' WHERE company_research_json IS NOT NULL")
    op.execute("UPDATE reports SET research_status = 'pending' WHERE research_status IS NULL")
    op.execute("UPDATE reports SET pdf_status = CASE WHEN pdf_path IS NOT NULL THEN 'generated' ELSE 'pending' END")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("reports") as batch_op:
            batch_op.alter_column("research_status", existing_type=sa.String(length=32), nullable=False)
            batch_op.alter_column("pdf_status", existing_type=sa.String(length=32), nullable=False)
    else:
        op.alter_column("reports", "research_status", existing_type=sa.String(length=32), nullable=False)
        op.alter_column("reports", "pdf_status", existing_type=sa.String(length=32), nullable=False)
    if "ix_reports_research_status" not in _index_names("reports"):
        op.create_index(op.f("ix_reports_research_status"), "reports", ["research_status"], unique=False)
    if "ix_reports_pdf_status" not in _index_names("reports"):
        op.create_index(op.f("ix_reports_pdf_status"), "reports", ["pdf_status"], unique=False)


def downgrade() -> None:
    report_indexes = _index_names("reports")
    if "ix_reports_pdf_status" in report_indexes:
        op.drop_index(op.f("ix_reports_pdf_status"), table_name="reports")
    if "ix_reports_research_status" in report_indexes:
        op.drop_index(op.f("ix_reports_research_status"), table_name="reports")
    for column_name in [
        "pdf_completed_at",
        "pdf_started_at",
        "pdf_status",
        "generation_completed_at",
        "generation_started_at",
        "research_completed_at",
        "research_started_at",
        "research_status",
    ]:
        if column_name in _column_names("reports"):
            op.drop_column("reports", column_name)
    if "ix_company_leads_city" in _index_names("company_leads"):
        op.drop_index(op.f("ix_company_leads_city"), table_name="company_leads")
    if "city" in _column_names("company_leads"):
        op.drop_column("company_leads", "city")
