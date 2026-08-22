"""normalize columns previously maintained by runtime upgrades

Revision ID: 5d4f6a2b
Revises: 2f1c343e7a91
Create Date: 2026-08-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5d4f6a2b"
down_revision: Union[str, Sequence[str], None] = "2f1c343e7a91"
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
    _add_column_if_missing("questions", sa.Column("dimension", sa.String(length=120), nullable=True))
    _add_column_if_missing("questions", sa.Column("option_text", sa.Text(), nullable=True))

    _add_column_if_missing("company_leads", sa.Column("email", sa.String(length=255), nullable=True))
    _add_column_if_missing("company_leads", sa.Column("priority_strategy", sa.String(length=40), nullable=True))
    _add_column_if_missing("company_leads", sa.Column("demand_summary", sa.Text(), nullable=True))
    if "ix_company_leads_priority_strategy" not in _index_names("company_leads"):
        op.create_index("ix_company_leads_priority_strategy", "company_leads", ["priority_strategy"], unique=False)

    _add_column_if_missing("reports", sa.Column("company_research_json", sa.Text(), nullable=True))
    _add_column_if_missing("gateway_api_config", sa.Column("search_model", sa.String(length=120), nullable=True))


def downgrade() -> None:
    # These columns may predate Alembic and contain production data. A downgrade
    # must not guess which installation originally created them.
    pass
