"""Make the legacy NDA R2 document link optional.

Revision ID: 54f1c3a9b7e2
Revises: 1b04d6887e20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "54f1c3a9b7e2"
down_revision: Union[str, Sequence[str], None] = "1b04d6887e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Permit provider-managed NDAs without an unrelated R2 document."""

    op.alter_column(
        "ndas",
        "document_id",
        existing_type=sa.UUID(),
        nullable=True,
        schema="public",
    )


def downgrade() -> None:
    """Keep the corrected nullable state to avoid destructive data loss."""

    pass
