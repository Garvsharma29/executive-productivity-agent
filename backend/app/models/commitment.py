"""Commitment model — one canonical action/task after normalization.

A Commitment is the *normalized* representation of an action item.
It may be supported by one or more Source records (via CommitmentSource).

Ownership and deadline precision are designed to preserve uncertainty
rather than invent precision that the source data does not support.
"""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import String, Text, Date, Uuid, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid, utcnow
from app.models.enums import (
    OwnershipType,
    CommitmentStatus,
    DeadlinePrecision,
)


class Commitment(Base):
    __tablename__ = "commitments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=new_uuid
    )

    # --- Action description ---
    # Normalized action text (may be cleaned up / de-duplicated).
    action: Mapped[str] = mapped_column(Text, nullable=False)
    # Original verbatim text before any normalization.
    raw_action: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Ownership ---
    ownership_type: Mapped[OwnershipType] = mapped_column(
        Enum(OwnershipType, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    # FK to the person who owns the action.
    # NULL when ownership_type is UNCLEAR.
    owner_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("people.id"), nullable=True
    )
    # The other party in the commitment (e.g. "send deck to Raghav"
    # → counterpart is Raghav).
    counterpart_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("people.id"), nullable=True
    )

    # --- Deadline ---
    # Resolved calendar date (NULL if no deadline or unresolved).
    deadline_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, index=True
    )
    # Original deadline text verbatim — e.g. "by Wednesday", "tomorrow
    # morning", "end of Q2".  Preserved even after resolution.
    deadline_raw: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    deadline_precision: Mapped[DeadlinePrecision] = mapped_column(
        Enum(DeadlinePrecision, native_enum=False, length=32),
        nullable=False,
        default=DeadlinePrecision.NONE,
    )

    # --- Status ---
    status: Mapped[CommitmentStatus] = mapped_column(
        Enum(CommitmentStatus, native_enum=False, length=32),
        nullable=False,
        default=CommitmentStatus.OPEN,
        index=True,
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, onupdate=utcnow
    )

    # --- Relationships ---
    owner: Mapped[Optional["Person"]] = relationship(
        "Person",
        foreign_keys=[owner_person_id],
        back_populates="owned_commitments",
        lazy="select",
    )
    counterpart: Mapped[Optional["Person"]] = relationship(
        "Person",
        foreign_keys=[counterpart_person_id],
        lazy="select",
    )
    source_links: Mapped[list["CommitmentSource"]] = relationship(
        "CommitmentSource", back_populates="commitment", lazy="select"
    )
    audit_log: Mapped[list["CommitmentAudit"]] = relationship(
        "CommitmentAudit", back_populates="commitment", lazy="select"
    )

    def is_overdue(self, as_of_date: date) -> bool:
        """Deterministic overdue check — no LLM involved.

        A commitment is overdue when:
        1. It has a resolved deadline date.
        2. That date is strictly before *as_of_date*.
        3. The commitment is still open (not completed).
        """
        if self.deadline_date is None:
            return False
        if self.status == CommitmentStatus.COMPLETED:
            return False
        return self.deadline_date < as_of_date

    def __repr__(self) -> str:
        return f"<Commitment {self.action[:60]!r} [{self.status.value}]>"
