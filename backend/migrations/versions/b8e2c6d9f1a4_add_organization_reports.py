"""add independent organization report analysis tables

Revision ID: b8e2c6d9f1a4
Revises: f1b7c3d9e5a2
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8e2c6d9f1a4"
down_revision: Union[str, Sequence[str], None] = "f1b7c3d9e5a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("organization_submissions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "analysis_status",
                sa.String(length=32),
                nullable=False,
                server_default="not_eligible",
            )
        )
        batch_op.add_column(sa.Column("analysis_note", sa.Text(), nullable=True))
        batch_op.create_index(
            "ix_organization_submissions_analysis_status",
            ["analysis_status"],
            unique=False,
        )

    op.create_table(
        "organization_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_submission_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("report_format_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("analysis_json", sa.Text(), nullable=True),
        sa.Column("html_content", sa.Text(), nullable=True),
        sa.Column("pdf_content", sa.LargeBinary(length=16777215), nullable=True),
        sa.Column("source_enterprise_report_id", sa.Integer(), nullable=True),
        sa.Column("model_vendor", sa.String(length=80), server_default="deepseek", nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("generation_error", sa.Text(), nullable=True),
        sa.Column("generation_started_at", sa.DateTime(), nullable=True),
        sa.Column("generation_completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_submission_id"],
            ["organization_submissions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_submission_id",
            "version",
            name="uq_organization_report_submission_version",
        ),
    )
    op.create_index(
        "ix_organization_reports_organization_submission_id",
        "organization_reports",
        ["organization_submission_id"],
        unique=False,
    )
    op.create_index("ix_organization_reports_status", "organization_reports", ["status"], unique=False)
    op.create_index(
        "ix_organization_reports_source_enterprise_report_id",
        "organization_reports",
        ["source_enterprise_report_id"],
        unique=False,
    )
    op.create_index("ix_organization_reports_created_at", "organization_reports", ["created_at"], unique=False)

    op.create_table(
        "organization_report_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_submission_id", sa.Integer(), nullable=False),
        sa.Column("organization_report_id", sa.Integer(), nullable=False),
        sa.Column("task_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("lock_token", sa.String(length=64), nullable=True),
        sa.Column("run_after", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_submission_id"],
            ["organization_submissions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_report_id"],
            ["organization_reports.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, column in (
        ("organization_submission_id", "organization_submission_id"),
        ("organization_report_id", "organization_report_id"),
        ("task_kind", "task_kind"),
        ("status", "status"),
        ("run_after", "run_after"),
        ("created_at", "created_at"),
    ):
        op.create_index(
            f"ix_organization_report_tasks_{name}",
            "organization_report_tasks",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for name in (
        "ix_organization_report_tasks_created_at",
        "ix_organization_report_tasks_run_after",
        "ix_organization_report_tasks_status",
        "ix_organization_report_tasks_task_kind",
        "ix_organization_report_tasks_organization_report_id",
        "ix_organization_report_tasks_organization_submission_id",
    ):
        op.drop_index(name, table_name="organization_report_tasks")
    op.drop_table("organization_report_tasks")
    op.drop_index("ix_organization_reports_created_at", table_name="organization_reports")
    op.drop_index("ix_organization_reports_source_enterprise_report_id", table_name="organization_reports")
    op.drop_index("ix_organization_reports_status", table_name="organization_reports")
    op.drop_index("ix_organization_reports_organization_submission_id", table_name="organization_reports")
    op.drop_table("organization_reports")
    with op.batch_alter_table("organization_submissions") as batch_op:
        batch_op.drop_index("ix_organization_submissions_analysis_status")
        batch_op.drop_column("analysis_note")
        batch_op.drop_column("analysis_status")
