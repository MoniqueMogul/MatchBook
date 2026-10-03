"""repair stale profile verification columns

Revision ID: cb02a841f41f
Revises: 54f1c3a9b7e2
Create Date: 2026-10-03 16:06:42.163391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb02a841f41f'
down_revision: Union[str, Sequence[str], None] = '54f1c3a9b7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS ix_buyer_profiles_verification_status
    """)

    op.execute("""
        ALTER TABLE buyer_profiles
        DROP COLUMN IF EXISTS verification_status
    """)

    op.execute("""
        DROP INDEX IF EXISTS ix_seller_profiles_verification_status
    """)

    op.execute("""
        ALTER TABLE seller_profiles
        DROP COLUMN IF EXISTS verification_status
    """)


def downgrade() -> None:
    op.add_column(
        "buyer_profiles",
        sa.Column(
            "verification_status",
            sa.String(length=30),
            nullable=False,
            server_default="unverified",
        ),
    )

    op.create_index(
        "ix_buyer_profiles_verification_status",
        "buyer_profiles",
        ["verification_status"],
        unique=False,
    )

    op.add_column(
        "seller_profiles",
        sa.Column(
            "verification_status",
            sa.String(length=30),
            nullable=False,
            server_default="unverified",
        ),
    )

    op.create_index(
        "ix_seller_profiles_verification_status",
        "seller_profiles",
        ["verification_status"],
        unique=False,
    )
