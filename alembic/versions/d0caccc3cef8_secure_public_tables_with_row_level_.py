"""Secure public tables with row-level security.

Revision ID: d0caccc3cef8
Revises: f37c9021ab41
Create Date: 2026-09-30 12:38:38.286597
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d0caccc3cef8"
down_revision: Union[str, Sequence[str], None] = "f37c9021ab41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PUBLIC_TABLES = (
    "ai_chat_generations",
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


TABLE_PRIVILEGES = (
    "SELECT, INSERT, UPDATE, DELETE, "
    "TRUNCATE, REFERENCES, TRIGGER"
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

    # alembic_version is an internal Alembic bookkeeping table, not
    # application data. It does not require application-level RLS,
    # but browser-facing Supabase roles should not have access to it.
    op.execute(
        'REVOKE ALL PRIVILEGES ON TABLE '
        'public."alembic_version" '
        'FROM anon, authenticated'
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

    # Restore the previous default table privileges.
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres "
        "IN SCHEMA public "
        f"GRANT {TABLE_PRIVILEGES} ON TABLES "
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

    # Restore access to existing supporting database objects.
    op.execute(
        "GRANT ALL PRIVILEGES ON ALL SEQUENCES "
        "IN SCHEMA public TO anon, authenticated"
    )
    op.execute(
        "GRANT ALL PRIVILEGES ON ALL FUNCTIONS "
        "IN SCHEMA public TO anon, authenticated"
    )

    # Restore the previous application-table privileges and RLS state.
    for table_name in PUBLIC_TABLES:
        op.execute(
            f"GRANT {TABLE_PRIVILEGES} ON TABLE "
            f'public."{table_name}" '
            "TO anon, authenticated"
        )
        op.execute(
            f'ALTER TABLE public."{table_name}" '
            "DISABLE ROW LEVEL SECURITY"
        )

    # alembic_version was protected only through permissions,
    # so restore its previous privileges without changing RLS.
    op.execute(
        f"GRANT {TABLE_PRIVILEGES} ON TABLE "
        'public."alembic_version" '
        "TO anon, authenticated"
    )