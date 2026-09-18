"""CalendarEvent model — structured calendar data from the assessment pack.

Calendar events are stored separately from commitments.  They provide
timing context that the system can use to determine whether a commitment
has a scheduled meeting, a deadline tied to a calendar block, or other
time constraints.
"""

import uuid
from datetime import datetime
from typing import Optional, Any

from sqlalchemy import String, Text, Uuid, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid, utcnow


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=new_uuid
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)

    start_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Attendee list — stored as JSON array of names / emails.
    attendees: Mapped[Optional[list[Any]]] = mapped_column(
        JSON, nullable=True
    )

    # Link back to the Source record this event was ingested from.
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("sources.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    # --- Relationships ---
    source: Mapped[Optional["Source"]] = relationship(
        "Source", back_populates="calendar_events", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<CalendarEvent {self.title!r} @ {self.start_time}>"
