from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.db_enum import NDAStatus


class NDABase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )


class NDACreate(NDABase):
    """
    Internal/application input for creating an NDA.

    The client should not decide buyer/seller IDs.
    Those come from the Match.
    """

    match_id: UUID
    document_id: UUID
    version: str


class NDASignRequest(NDABase):
    """
    The authenticated user is the signer.

    We intentionally do not accept signer_user_id or signer_role
    from the frontend.
    """

    pass


class NDAResponse(NDABase):
    id: UUID
    match_id: UUID
    document_id: UUID

    status: NDAStatus
    version: str

    buyer_signed_at: datetime | None
    seller_signed_at: datetime | None

    created_at: datetime
    completed_at: datetime | None


class NDAAccessResponse(NDABase):
    """
    Useful response for the frontend NDA screen.
    """

    nda: NDAResponse

    current_user_has_signed: bool
    buyer_has_signed: bool
    seller_has_signed: bool
    completed: bool