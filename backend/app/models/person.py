"""Person model — people referenced in the assessment data."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid, utcnow


class Person(Base):
    __tablename__ = "people"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=new_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    # --- Relationships (back-populated from the other side) ---
    authored_sources: Mapped[list["Source"]] = relationship(
        "Source", back_populates="author", lazy="select"
    )
    owned_commitments: Mapped[list["Commitment"]] = relationship(
        "Commitment",
        foreign_keys="Commitment.owner_person_id",
        back_populates="owner",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Person {self.name!r}>"
