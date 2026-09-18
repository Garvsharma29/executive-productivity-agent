"""Source model — original evidence from the assessment data pack.

A Source is an immutable record of supplied evidence.  Its content must
never be overwritten during normalization or extraction.  Normalized /
extracted data lives in Commitment and CommitmentSource.
"""

import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import String, Text, Uuid, Enum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid, utcnow
from app.models.enums import SourceType


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=new_uuid
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    # Human-readable reference, e.g. "Q2 Planning Meeting", "Thread: Budget Review"
    source_reference: Mapped[str] = mapped_column(
        String(512), nullable=False
    )
    occurred_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Who created / sent this source (nullable — calendar entries may not
    # have a single author).
    author_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("people.id"), nullable=True
    )

    # Full original content — never modified after ingestion.
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional structured metadata (participants list, email headers, etc.)
    extra_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    # --- Relationships ---
    author: Mapped[Optional["Person"]] = relationship(
        "Person", back_populates="authored_sources", lazy="select"
    )
    commitment_links: Mapped[list["CommitmentSource"]] = relationship(
        "CommitmentSource", back_populates="source", lazy="select"
    )
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(
        "CalendarEvent", back_populates="source", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Source {self.source_type.value}: {self.source_reference!r}>"
