"""CommitmentSource — many-to-many evidence relationship.

Links a canonical Commitment to the Source records that support it.
This is the answer to "Why does the system believe this commitment exists?"

One commitment may be mentioned in a meeting, an email, and a voice note.
One source may contain references to multiple commitments.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Float, Uuid, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid, utcnow


class CommitmentSource(Base):
    __tablename__ = "commitment_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=new_uuid
    )
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("commitments.id"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sources.id"), nullable=False, index=True
    )

    # The specific snippet from the source that supports this commitment.
    evidence_text: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    # How the evidence was extracted — e.g. "llm_extraction", "manual".
    extraction_method: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    # Optional confidence score from the extraction step (0.0–1.0).
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    # --- Relationships ---
    commitment: Mapped["Commitment"] = relationship(
        "Commitment", back_populates="source_links", lazy="select"
    )
    source: Mapped["Source"] = relationship(
        "Source", back_populates="commitment_links", lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<CommitmentSource commitment={self.commitment_id} "
            f"source={self.source_id}>"
        )
