"""Create and secure the Supabase user-creation trigger function.

Revision ID: 2cab85a57c65
Revises: d0caccc3cef8
"""

from typing import Sequence, Union

from alembic import op


revision: str = "2cab85a57c65"
down_revision: Union[str, Sequence[str], None] = "d0caccc3cef8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USER_TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_first_name TEXT;
    v_last_name TEXT;
BEGIN
    v_first_name := NULLIF(
        TRIM(NEW.raw_user_meta_data ->> 'first_name'),
        ''
    );

    v_last_name := NULLIF(
        TRIM(NEW.raw_user_meta_data ->> 'last_name'),
        ''
    );

    IF v_first_name IS NULL OR v_last_name IS NULL THEN
        RAISE EXCEPTION
            'first_name and last_name are required';
    END IF;

    INSERT INTO public.users (
        id,
        email,
        phone,
        first_name,
        last_name,
        status,
        verification_status
    )
    VALUES (
        NEW.id,
        NEW.email,
        NEW.phone,
        v_first_name,
        v_last_name,
        'active',
        'unverified'
    )
    ON CONFLICT (id) DO NOTHING;

    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    """Create the auth trigger function and restrict direct execution."""

    op.execute(USER_TRIGGER_FUNCTION_SQL)

    op.execute(
        "DROP TRIGGER IF EXISTS on_auth_user_created "
        "ON auth.users"
    )

    op.execute(
        "CREATE TRIGGER on_auth_user_created "
        "AFTER INSERT ON auth.users "
        "FOR EACH ROW "
        "EXECUTE FUNCTION public.handle_new_user()"
    )

    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.handle_new_user() "
        "FROM PUBLIC, anon, authenticated"
    )

    op.execute(
        "GRANT EXECUTE ON FUNCTION public.handle_new_user() "
        "TO service_role"
    )


def downgrade() -> None:
    """Remove the user-creation trigger and function."""

    op.execute(
        "DROP TRIGGER IF EXISTS on_auth_user_created "
        "ON auth.users"
    )

    op.execute(
        "DROP FUNCTION IF EXISTS public.handle_new_user()"
    )