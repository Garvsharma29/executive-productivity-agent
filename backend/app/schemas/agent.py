"""Pydantic schemas for Executive Agent interaction and Daily Brief."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.enums import CommitmentStatus, DeadlinePrecision, OwnershipType


class EvidenceItem(BaseModel):
    """Traceable citation pointing back to original source material."""
    source_id: uuid.UUID
    source_type: str
    source_reference: str
    occurred_at: Optional[datetime] = None
    evidence_text: str
    extraction_method: Optional[str] = None
    confidence: Optional[float] = None


class BriefCommitmentItem(BaseModel):
    """UI-ready presentation schema for a commitment in the brief or query answer."""
    id: uuid.UUID
    action: str
    raw_action: str
    topic: Optional[str] = None
    ownership_type: OwnershipType
    owner_name: Optional[str] = None
    counterpart_name: Optional[str] = None
    deadline_raw: Optional[str] = None
    deadline_date: Optional[date] = None
    deadline_precision: DeadlinePrecision = DeadlinePrecision.NONE
    status: CommitmentStatus
    is_overdue: bool = False
    evidence_count: int = 0
    evidence: list[EvidenceItem] = []


class CalendarEventItem(BaseModel):
    """Contextual calendar event representation (never converted into a commitment)."""
    id: uuid.UUID
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    attendees: Optional[list[Any]] = None


class DailyBriefResponse(BaseModel):
    """Structured daily executive action brief for Arjun Malhotra."""
    as_of_date: date
    generated_at: datetime
    executive_name: str = "Arjun Malhotra"
    executive_role: str = "VP Sales"
    summary_counts: dict[str, int] = Field(default_factory=dict)
    my_actions: list[BriefCommitmentItem] = Field(
        default_factory=list,
        description="Open commitments owned by Arjun requiring action."
    )
    waiting_on_others: list[BriefCommitmentItem] = Field(
        default_factory=list,
        description="Open commitments owned by colleagues where Arjun is the counterpart."
    )
    needs_attention: list[BriefCommitmentItem] = Field(
        default_factory=list,
        description="Overdue items, unclear ownership items, or imminent deadlines."
    )
    completed: list[BriefCommitmentItem] = Field(
        default_factory=list,
        description="Recently completed commitments."
    )
    scheduled_today: list[CalendarEventItem] = Field(
        default_factory=list,
        description="Schedule context for the day. Does not represent commitments."
    )


class AgentQueryRequest(BaseModel):
    """Natural language question directed to the Executive Productivity Agent."""
    query: str
    as_of_date: Optional[date] = Field(
        default=None,
        description="Reference date for temporal reasoning (YYYY-MM-DD). Defaults to 2026-09-23 for assessment data."
    )


class AgentQueryResponse(BaseModel):
    """Verifiable, evidence-backed answer produced by the Executive Agent."""
    query: str
    as_of_date: date
    intent: str
    answer: str
    commitments: list[BriefCommitmentItem] = []
    evidence: list[EvidenceItem] = []
