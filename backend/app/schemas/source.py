"""Pydantic schemas for Source — API serialization layer."""

import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel

from app.models.enums import SourceType


class SourceBase(BaseModel):
    source_type: SourceType
    source_reference: str
    occurred_at: Optional[datetime] = None
    author_person_id: Optional[uuid.UUID] = None
    content: str
    extra_metadata: Optional[dict[str, Any]] = None


class SourceCreate(SourceBase):
    """Payload for creating a new Source."""
    pass


class SourceRead(SourceBase):
    """Response schema — what the API returns."""
    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
