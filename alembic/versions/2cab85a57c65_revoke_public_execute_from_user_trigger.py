"""Revoke public execution of the user-creation trigger function."""

from typing import Sequence, Union

from alembic import op


revision: str = "2cab85a57c65"
down_revision: Union[str, Sequence[str], None] = "d0caccc3cef8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Prevent browser-facing roles from directly invoking the function."""

    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.handle_new_user() "
        "FROM PUBLIC, anon, authenticated"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.handle_new_user() "
        "TO service_role"
    )


def downgrade() -> None:
    """Restore the original inherited PUBLIC execution permission."""

    op.execute(
        "GRANT EXECUTE ON FUNCTION public.handle_new_user() "
        "TO PUBLIC"
    )