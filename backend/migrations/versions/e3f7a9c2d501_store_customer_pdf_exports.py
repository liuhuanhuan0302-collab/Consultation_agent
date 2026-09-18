"""store customer PDF export snapshots

Revision ID: e3f7a9c2d501
Revises: c6f9a2d4e8b1
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f7a9c2d501"
down_revision: Union[str, Sequence[str], None] = "c6f9a2d4e8b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("reports")
    }


def upgrade() -> None:
    # Local metadata bootstrap can create the column before Alembic reaches
    # this revision. Adopt it rather than issuing duplicate DDL.
    if "customer_pdf_bytes" not in _columns():
        op.add_column(
            "reports",
            sa.Column(
                "customer_pdf_bytes",
                sa.LargeBinary(length=16 * 1024 * 1024),
                nullable=True,
            ),
        )


def downgrade() -> None:
    if "customer_pdf_bytes" in _columns():
        op.drop_column("reports", "customer_pdf_bytes")
