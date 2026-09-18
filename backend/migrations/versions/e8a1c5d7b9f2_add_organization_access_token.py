"""add organization submission access token

Revision ID: e8a1c5d7b9f2
Revises: d4f2a8c9b7e1
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8a1c5d7b9f2"
down_revision: Union[str, Sequence[str], None] = "d4f2a8c9b7e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_access_tokens() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(
            sa.text(
                "UPDATE organization_submissions "
                "SET access_token = lower(hex(randomblob(16))) "
                "WHERE access_token IS NULL"
            )
        )
    elif bind.dialect.name == "mysql":
        bind.execute(
            sa.text(
                "UPDATE organization_submissions "
                "SET access_token = REPLACE(UUID(), '-', '') "
                "WHERE access_token IS NULL"
            )
        )
    else:
        raise RuntimeError(f"Unsupported database dialect for access token migration: {bind.dialect.name}")


def upgrade() -> None:
    with op.batch_alter_table("organization_submissions") as batch_op:
        batch_op.add_column(sa.Column("access_token", sa.String(length=64), nullable=True))
    _backfill_access_tokens()
    with op.batch_alter_table("organization_submissions") as batch_op:
        batch_op.alter_column("access_token", existing_type=sa.String(length=64), nullable=False)
    op.create_index(
        "ix_organization_submissions_access_token",
        "organization_submissions",
        ["access_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_submissions_access_token",
        table_name="organization_submissions",
    )
    with op.batch_alter_table("organization_submissions") as batch_op:
        batch_op.drop_column("access_token")
