"""Secure public tables with row-level security.

Revision ID: 038ab959c33f
Revises: 0eadaaa48810
Create Date: 2026-09-30 00:41:28.182864
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "038ab959c33f"
down_revision: Union[str, Sequence[str], None] = "0eadaaa48810"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PUBLIC_TABLES = (
    "ai_chat_generations",
    "alembic_version",
    "business_financials",
    "businesses",
    "buyer_financials",
    "buyer_preferences",
    "buyer_profiles",
    "conversations",
    "declarations",
    "documents",
    "matches",
    "messages",
    "ndas",
    "notifications",
    "outbox_events",
    "processed_events",
    "seller_profiles",
    "users",
)


def upgrade() -> None:
    """Block direct Data API access and enable RLS."""

    # The frontend uses Supabase Auth but does not query these tables
    # through the Supabase Data API. Application data is accessed
    # through the FastAPI backend using the postgres-owned connection.
    for table_name in PUBLIC_TABLES:
        op.execute(
            f'ALTER TABLE public."{table_name}" '
            "ENABLE ROW LEVEL SECURITY"
        )
        op.execute(
            f'REVOKE ALL PRIVILEGES ON TABLE '
            f'public."{table_name}" '
            "FROM anon, authenticated"
        )

    # Remove browser-role access to supporting database objects.
    op.execute(
        "REVOKE ALL PRIVILEGES ON ALL SEQUENCES "
        "IN SCHEMA public FROM anon, authenticated"
    )
    op.execute(
        "REVOKE ALL PRIVILEGES ON ALL FUNCTIONS "
        "IN SCHEMA public FROM anon, authenticated"
    )

    # Ensure future objects created by application migrations are not
    # automatically exposed to Supabase Data API roles.
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres "
        "IN SCHEMA public "
        "REVOKE ALL PRIVILEGES ON TABLES "
        "FROM anon, authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres "
        "IN SCHEMA public "
        "REVOKE ALL PRIVILEGES ON SEQUENCES "
        "FROM anon, authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres "
        "IN SCHEMA public "
        "REVOKE ALL PRIVILEGES ON FUNCTIONS "
        "FROM anon, authenticated"
    )


def downgrade() -> None:
    """Restore the previous Supabase Data API permissions."""

    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres "
        "IN SCHEMA public "
        "GRANT ALL PRIVILEGES ON TABLES "
        "TO anon, authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres "
        "IN SCHEMA public "
        "GRANT ALL PRIVILEGES ON SEQUENCES "
        "TO anon, authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres "
        "IN SCHEMA public "
        "GRANT ALL PRIVILEGES ON FUNCTIONS "
        "TO anon, authenticated"
    )

    op.execute(
        "GRANT ALL PRIVILEGES ON ALL SEQUENCES "
        "IN SCHEMA public TO anon, authenticated"
    )
    op.execute(
        "GRANT ALL PRIVILEGES ON ALL FUNCTIONS "
        "IN SCHEMA public TO anon, authenticated"
    )

    for table_name in PUBLIC_TABLES:
        op.execute(
            f'GRANT ALL PRIVILEGES ON TABLE '
            f'public."{table_name}" '
            "TO anon, authenticated"
        )
        op.execute(
            f'ALTER TABLE public."{table_name}" '
            "DISABLE ROW LEVEL SECURITY"
        )