"""Pydantic schemas for Commitment — API serialization layer."""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums import (
    OwnershipType,
    CommitmentStatus,
    DeadlinePrecision,
)


class CommitmentBase(BaseModel):
    action: str
    raw_action: str
    ownership_type: OwnershipType
    owner_person_id: Optional[uuid.UUID] = None
    counterpart_person_id: Optional[uuid.UUID] = None
    deadline_date: Optional[date] = None
    deadline_raw: Optional[str] = None
    deadline_precision: DeadlinePrecision = DeadlinePrecision.NONE
    status: CommitmentStatus = CommitmentStatus.OPEN


class CommitmentCreate(CommitmentBase):
    """Payload for creating a new Commitment."""
    pass


class CommitmentSourceRead(BaseModel):
    """Nested read schema for a commitment's source evidence."""
    id: uuid.UUID
    source_id: uuid.UUID
    evidence_text: Optional[str] = None
    extraction_method: Optional[str] = None
    confidence: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CommitmentRead(CommitmentBase):
    """Response schema — includes computed overdue flag placeholder."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    is_overdue: bool = False
    source_links: list[CommitmentSourceRead] = []

    model_config = {"from_attributes": True}
