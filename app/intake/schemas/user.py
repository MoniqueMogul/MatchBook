from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserPhoneUpsert(BaseModel):
    phone: str = Field(
        min_length=1,
        max_length=30,
    )


class UserPersonalRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    email: str | None
    phone: str | None
    first_name: str
    last_name: str
    created_at: datetime
    updated_at: datetime