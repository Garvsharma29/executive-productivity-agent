"""CommitmentAudit — lightweight change log for commitments.

Records meaningful state transitions so the system can explain
*when* and *how* a commitment's status, deadline, or ownership changed.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Uuid, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid, utcnow
from app.models.enums import AuditEventType


class CommitmentAudit(Base):
    __tablename__ = "commitment_audit"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=new_uuid
    )
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("commitments.id"), nullable=False, index=True
    )

    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, native_enum=False, length=32), nullable=False
    )

    # Which field changed (e.g. "status", "deadline_date", "ownership_type").
    field_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    changed_at: Mapped[datetime] = mapped_column(default=utcnow)

    # --- Relationships ---
    commitment: Mapped["Commitment"] = relationship(
        "Commitment", back_populates="audit_log", lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<CommitmentAudit {self.event_type.value} "
            f"on {self.commitment_id}>"
        )
