"""Repair missing NDA electronic-signature columns."""

from typing import Sequence, Union

from alembic import op


revision: str = "1b04d6887e20"
down_revision: Union[str, Sequence[str], None] = "2cab85a57c65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reconcile NDA schema in databases stamped past older migrations."""

    op.execute(
        """
        ALTER TABLE public.ndas
            ADD COLUMN IF NOT EXISTS signature_provider VARCHAR(50),
            ADD COLUMN IF NOT EXISTS provider_document_id VARCHAR(255),
            ADD COLUMN IF NOT EXISTS provider_template_id VARCHAR(255),
            ADD COLUMN IF NOT EXISTS signing_initialization_status VARCHAR(30),
            ADD COLUMN IF NOT EXISTS signing_initialization_started_at TIMESTAMPTZ
        """
    )

    op.execute(
        """
        UPDATE public.ndas
        SET signing_initialization_status = 'not_started'
        WHERE signing_initialization_status IS NULL
        """
    )

    op.execute(
        """
        ALTER TABLE public.ndas
        ALTER COLUMN signing_initialization_status SET NOT NULL
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ndas_signature_provider
        ON public.ndas (signature_provider)
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_ndas_provider_document_id
        ON public.ndas (provider_document_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ndas_signing_initialization_status
        ON public.ndas (signing_initialization_status)
        """
    )


def downgrade() -> None:
    """Do not restore the known-invalid schema state."""

    pass