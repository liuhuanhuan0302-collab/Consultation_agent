"""add organization respondent name

Revision ID: f1b7c3d9e5a2
Revises: e8a1c5d7b9f2
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1b7c3d9e5a2"
down_revision: Union[str, Sequence[str], None] = "e8a1c5d7b9f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing organization rows predate the respondent name requirement. Use
    # an empty non-null backfill for those rows; all new API requests validate a
    # non-blank name before persistence.
    with op.batch_alter_table("organization_submissions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "respondent_name",
                sa.String(length=80),
                nullable=False,
                server_default="",
            )
        )
    with op.batch_alter_table("organization_submissions") as batch_op:
        batch_op.alter_column(
            "respondent_name",
            existing_type=sa.String(length=80),
            nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table("organization_submissions") as batch_op:
        batch_op.drop_column("respondent_name")
