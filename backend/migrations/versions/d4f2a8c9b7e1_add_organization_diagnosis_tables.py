"""add standalone organization diagnosis tables

Revision ID: d4f2a8c9b7e1
Revises: c8e1f4a7b203
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f2a8c9b7e1"
down_revision: Union[str, Sequence[str], None] = "c8e1f4a7b203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name_input", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("position", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_organization_submissions_company_name",
        "organization_submissions",
        ["company_name"],
        unique=False,
    )
    op.create_index(
        "ix_organization_submissions_department",
        "organization_submissions",
        ["department"],
        unique=False,
    )
    op.create_index(
        "ix_organization_submissions_status",
        "organization_submissions",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_organization_submissions_company_department",
        "organization_submissions",
        ["company_name", "department"],
        unique=False,
    )

    op.create_table(
        "organization_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_submission_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("answer_value", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_submission_id"],
            ["organization_submissions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_submission_id",
            "question_id",
            name="uq_organization_submission_question",
        ),
    )
    op.create_index(
        "ix_organization_answers_organization_submission_id",
        "organization_answers",
        ["organization_submission_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_answers_question_id",
        "organization_answers",
        ["question_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_organization_answers_question_id", table_name="organization_answers")
    op.drop_index(
        "ix_organization_answers_organization_submission_id",
        table_name="organization_answers",
    )
    op.drop_table("organization_answers")
    op.drop_index(
        "ix_organization_submissions_company_department",
        table_name="organization_submissions",
    )
    op.drop_index("ix_organization_submissions_status", table_name="organization_submissions")
    op.drop_index("ix_organization_submissions_department", table_name="organization_submissions")
    op.drop_index(
        "ix_organization_submissions_company_name",
        table_name="organization_submissions",
    )
    op.drop_table("organization_submissions")
