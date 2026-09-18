"""Pydantic schemas for Person — API serialization layer."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PersonBase(BaseModel):
    name: str
    role: Optional[str] = None
    email: Optional[str] = None


class PersonCreate(PersonBase):
    """Payload for creating a new Person."""
    pass


class PersonRead(PersonBase):
    """Response schema — what the API returns."""
    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
