"""make DeepSeek the required default search provider

Revision ID: 9c31a760
Revises: 8b22f001
Create Date: 2026-08-22
"""

from typing import Sequence, Union

from alembic import op


revision: str = "9c31a760"
down_revision: Union[str, Sequence[str], None] = "8b22f001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing untouched installations used Bocha with no key and the disabled
    # flag. Move only those defaults to DeepSeek; preserve deliberately saved
    # third-party provider configurations.
    op.execute(
        "UPDATE gateway_api_config "
        "SET search_provider = 'deepseek' "
        "WHERE search_provider = 'bocha' "
        "AND (search_api_key IS NULL OR search_api_key = '')"
    )
    op.execute("UPDATE gateway_api_config SET search_enabled = 1")


def downgrade() -> None:
    # Provider choice is runtime configuration and may have changed after this
    # migration. Do not overwrite an administrator's later selection.
    pass
