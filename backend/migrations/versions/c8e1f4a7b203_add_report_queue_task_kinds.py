"""add report queue task kinds

Revision ID: c8e1f4a7b203
Revises: a4d7c9e2f601
Create Date: 2026-08-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8e1f4a7b203"
down_revision: Union[str, Sequence[str], None] = "a4d7c9e2f601"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _columns() -> set[str]:
    return {column["name"] for column in _inspector().get_columns("report_delivery_jobs")}


def upgrade() -> None:
    # A development startup can pre-create these columns through the ORM
    # metadata before Alembic reaches this revision. Adopt that schema and
    # preserve any existing values instead of issuing duplicate DDL.
    if "task_kind" not in _columns():
        op.add_column(
            "report_delivery_jobs",
            sa.Column("task_kind", sa.String(length=32), nullable=False, server_default="full_delivery"),
        )
    if "task_context_json" not in _columns():
        op.add_column(
            "report_delivery_jobs",
            sa.Column("task_context_json", sa.Text(), nullable=True),
        )
    indexes = {index["name"] for index in _inspector().get_indexes("report_delivery_jobs")}
    if "ix_report_delivery_jobs_task_kind" not in indexes:
        op.create_index(
            "ix_report_delivery_jobs_task_kind",
            "report_delivery_jobs",
            ["task_kind"],
            unique=False,
        )


def downgrade() -> None:
    inspector = _inspector()
    if "ix_report_delivery_jobs_task_kind" in {
        index["name"] for index in inspector.get_indexes("report_delivery_jobs")
    }:
        op.drop_index("ix_report_delivery_jobs_task_kind", table_name="report_delivery_jobs")
    for name in ("task_context_json", "task_kind"):
        if name in {column["name"] for column in _inspector().get_columns("report_delivery_jobs")}:
            op.drop_column("report_delivery_jobs", name)
