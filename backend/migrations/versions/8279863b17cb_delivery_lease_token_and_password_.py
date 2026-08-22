"""delivery lease token and password revocation

Revision ID: 8279863b17cb
Revises: 6f0a46f68473
Create Date: 2026-08-23 04:36:20.239938

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8279863b17cb'
down_revision: Union[str, Sequence[str], None] = '6f0a46f68473'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """报告任务租约 token 与用户密码撤销时间。

    lock_token：队列任务认领时签发的一次性租约。超时回收与终态写入都
    以它为条件，杜绝仍在执行的任务被重新入队后重复生成、重复发邮件。
    password_changed_at：修改密码后拒绝此前签发的 JWT（现有行留 NULL，
    不追溯作废存量 token）。
    """
    op.add_column("report_delivery_jobs", sa.Column("lock_token", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "password_changed_at")
    op.drop_column("report_delivery_jobs", "lock_token")
