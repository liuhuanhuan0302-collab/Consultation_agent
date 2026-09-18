"""allow full organization report HTML to be stored on MySQL

Revision ID: c6f9a2d4e8b1
Revises: b8e2c6d9f1a4
Create Date: 2026-09-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "c6f9a2d4e8b1"
down_revision: Union[str, Sequence[str], None] = "b8e2c6d9f1a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite has no separate MEDIUMTEXT type and already accepts the larger
    # value as TEXT.  The production-relevant MySQL schema is widened here.
    if op.get_bind().dialect.name != "mysql":
        return
    op.alter_column(
        "organization_reports",
        "html_content",
        existing_type=sa.Text(),
        type_=mysql.MEDIUMTEXT(),
        existing_nullable=True,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "mysql":
        return
    op.alter_column(
        "organization_reports",
        "html_content",
        existing_type=mysql.MEDIUMTEXT(),
        type_=sa.Text(),
        existing_nullable=True,
    )
