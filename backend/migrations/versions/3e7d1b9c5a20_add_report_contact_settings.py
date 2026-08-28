"""add report contact settings

Revision ID: 3e7d1b9c5a20
Revises: 8279863b17cb
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3e7d1b9c5a20"
down_revision: Union[str, Sequence[str], None] = "8279863b17cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_contact_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contact_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("wechat", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=254), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(length=120), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("report_contact_settings")
