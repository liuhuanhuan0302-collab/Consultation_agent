"""add persistent report queue scheduler

Revision ID: a4d7c9e2f601
Revises: 3e7d1b9c5a20
Create Date: 2026-08-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4d7c9e2f601"
down_revision: Union[str, Sequence[str], None] = "3e7d1b9c5a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _ensure_settings_table() -> None:
    inspector = _inspector()
    if not _table_exists(inspector, "report_queue_settings"):
        op.create_table(
            "report_queue_settings",
            sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
            sa.Column("processing_concurrency", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("active_queue_capacity", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("automatic_wait_capacity", sa.Integer(), nullable=False, server_default="200"),
            sa.Column("pdf_concurrency", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("processing_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("promotion_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("updated_by", sa.String(length=120), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("id = 1", name="ck_report_queue_settings_singleton"),
            sa.CheckConstraint("processing_concurrency >= 1", name="ck_report_queue_processing_positive"),
            sa.CheckConstraint("active_queue_capacity >= processing_concurrency", name="ck_report_queue_active_capacity"),
            sa.CheckConstraint("automatic_wait_capacity >= 0", name="ck_report_queue_automatic_capacity"),
            sa.CheckConstraint("pdf_concurrency >= 1", name="ck_report_queue_pdf_positive"),
            sa.CheckConstraint("pdf_concurrency <= processing_concurrency", name="ck_report_queue_pdf_concurrency"),
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        # Development startup may have created an intermediate table with
        # create_all. Adopt it and add only columns that are missing.
        columns = _column_names(inspector, "report_queue_settings")
        definitions = (
            sa.Column("processing_concurrency", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("active_queue_capacity", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("automatic_wait_capacity", sa.Integer(), nullable=False, server_default="200"),
            sa.Column("pdf_concurrency", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("processing_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("promotion_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("updated_by", sa.String(length=120), nullable=True),
            # SQLite rejects a non-constant default when adding a column to an
            # existing table.  Add it nullable, backfill, and keep the model's
            # normal default for future rows.
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        for column in definitions:
            if column.name not in columns:
                op.add_column("report_queue_settings", column)

        if "updated_at" not in columns:
            op.execute(sa.text("UPDATE report_queue_settings SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"))

    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM report_queue_settings WHERE id = 1")).first() is None:
        bind.execute(
            sa.text(
                "INSERT INTO report_queue_settings "
                "(id, processing_concurrency, active_queue_capacity, automatic_wait_capacity, "
                "pdf_concurrency, processing_paused, promotion_paused, updated_at) "
                "VALUES (1, 2, 50, 200, 1, :processing_paused, :promotion_paused, CURRENT_TIMESTAMP)"
            ),
            {"processing_paused": False, "promotion_paused": False},
        )


def _ensure_job_column(column: sa.Column) -> None:
    if column.name not in _column_names(_inspector(), "report_delivery_jobs"):
        op.add_column("report_delivery_jobs", column)


def _ensure_job_index(name: str, columns: list[str]) -> None:
    if name not in _index_names(_inspector(), "report_delivery_jobs"):
        op.create_index(name, "report_delivery_jobs", columns, unique=False)


def upgrade() -> None:
    _ensure_settings_table()
    _ensure_job_column(sa.Column("queue_state", sa.String(length=32), nullable=True))
    _ensure_job_column(sa.Column("processing_stage", sa.String(length=64), nullable=True))
    _ensure_job_column(sa.Column("approved_at", sa.DateTime(), nullable=True))
    _ensure_job_column(sa.Column("approved_by", sa.String(length=120), nullable=True))
    _ensure_job_index("ix_report_delivery_jobs_queue_state", ["queue_state"])
    _ensure_job_index("ix_report_delivery_jobs_queue_schedule", ["queue_state", "status", "run_after", "created_at"])
    _ensure_job_index("ix_report_delivery_jobs_approved_waiting", ["queue_state", "approved_at", "id"])

    # Preserve an explicitly assigned state while adopting legacy runnable jobs.
    op.execute(
        sa.text(
            "UPDATE report_delivery_jobs SET queue_state = 'active' "
            "WHERE queue_state IS NULL AND status IN ('queued', 'processing')"
        )
    )


def downgrade() -> None:
    inspector = _inspector()
    indexes = _index_names(inspector, "report_delivery_jobs")
    for name in (
        "ix_report_delivery_jobs_approved_waiting",
        "ix_report_delivery_jobs_queue_schedule",
        "ix_report_delivery_jobs_queue_state",
    ):
        if name in indexes:
            op.drop_index(name, table_name="report_delivery_jobs")
    for column in ("approved_by", "approved_at", "processing_stage", "queue_state"):
        if column in _column_names(_inspector(), "report_delivery_jobs"):
            op.drop_column("report_delivery_jobs", column)
    if _table_exists(_inspector(), "report_queue_settings"):
        op.drop_table("report_queue_settings")
