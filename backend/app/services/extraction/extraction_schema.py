"""Extraction schema — Pydantic models for raw and candidate extracted commitments."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import CommitmentStatus, DeadlinePrecision, OwnershipType


class ExtractedCommitmentCandidate(BaseModel):
    """A raw commitment candidate extracted from a single source."""

    # Action description
    action: str = Field(..., description="Action item description")
    raw_action: str = Field(..., description="Verbatim text from which the action was identified")

    # Ownership clues (raw strings before resolution against Person table)
    owner_name_raw: Optional[str] = Field(None, description="Name or role of the owner as stated in the source")
    counterpart_name_raw: Optional[str] = Field(None, description="Name or role of recipient/requester")
    ownership_type: OwnershipType = Field(default=OwnershipType.UNCLEAR, description="Initial ownership classification")

    # Deadline clues
    deadline_raw: Optional[str] = Field(None, description="Raw deadline phrasing (e.g. 'tomorrow morning')")
    deadline_precision: DeadlinePrecision = Field(default=DeadlinePrecision.NONE)

    # Status & Topic
    status: CommitmentStatus = Field(default=CommitmentStatus.OPEN)
    topic: Optional[str] = Field(None, description="High-level topic cluster (e.g. 'Vendor List')")

    # Evidence traceability
    source_id: uuid.UUID = Field(..., description="ID of the Source record")
    source_type: str = Field(..., description="MEETING, EMAIL, VOICE_NOTE")
    source_reference: str = Field(..., description="Human-readable source reference")
    evidence_text: str = Field(..., description="Verbatim supporting quote from source")
    occurred_at: Optional[datetime] = Field(None, description="When the source occurred")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
