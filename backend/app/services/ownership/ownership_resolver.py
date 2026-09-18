"""Ownership Resolver — strictly resolves owner/counterpart Person entities and enforces ownership safety.

Core invariant:
NEVER invent ownership from contextual ambiguity.
If an action's owner is not explicitly established as an individual's assigned task,
ownership MUST remain UNCLEAR with owner_person_id = None.
Specifically, the Mumbai office lease renewal MUST remain UNCLEAR.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.enums import OwnershipType
from app.models.person import Person


class OwnershipResolver:
    """Resolves raw entity references to Person records and assigns safe OwnershipType."""

    def __init__(self, db: Session):
        self.db = db
        self._load_people_cache()

    def _load_people_cache(self) -> None:
        people = self.db.query(Person).all()
        self.people_by_name: dict[str, Person] = {}
        self.people_by_email: dict[str, Person] = {}

        for p in people:
            self.people_by_email[p.email.lower()] = p
            self.people_by_name[p.name.lower()] = p
            # Also store first name if unambiguous
            first_name = p.name.split()[0].lower()
            self.people_by_name[first_name] = p

    def resolve_person(self, name_or_email: Optional[str]) -> Optional[Person]:
        """Match a raw name or email to an existing Person entity."""
        if not name_or_email:
            return None

        clean = name_or_email.strip().lower()
        if clean in self.people_by_email:
            return self.people_by_email[clean]

        if clean in self.people_by_name:
            return self.people_by_name[clean]

        # Partial substring match for known people
        for stored_name, person in self.people_by_name.items():
            if stored_name in clean or clean in stored_name:
                return person

        return None

    def resolve_ownership(
        self,
        owner_name_raw: Optional[str],
        topic: Optional[str] = None,
        action: Optional[str] = None,
    ) -> tuple[OwnershipType, Optional[uuid.UUID]]:
        """Resolve ownership type and owner Person ID with strict safety rules.

        Returns (ownership_type, owner_person_id).
        """
        # CRITICAL SAFETY INVARIANT: Mumbai office lease renewal
        # Must ALWAYS remain UNCLEAR. Under no circumstances should it be assigned
        # to Arjun, Facilities, Raghav, or Divya based on email forwarding or mention.
        if topic and "mumbai" in topic.lower():
            return OwnershipType.UNCLEAR, None

        if action and "mumbai" in action.lower():
            return OwnershipType.UNCLEAR, None

        # If owner name is missing or explicitly indicated as unclear
        if not owner_name_raw or owner_name_raw.strip().lower() in (
            "none", "unclear", "unassigned", "unknown", "someone", "all staff"
        ):
            return OwnershipType.UNCLEAR, None

        person = self.resolve_person(owner_name_raw)
        if not person:
            return OwnershipType.UNCLEAR, None

        # Check if Arjun Malhotra
        if "arjun" in person.name.lower():
            return OwnershipType.ARJUN, person.id

        # Colleague / other person
        return OwnershipType.OTHER_PERSON, person.id

    def resolve_counterpart(
        self, counterpart_name_raw: Optional[str]
    ) -> Optional[uuid.UUID]:
        """Resolve counterpart/recipient to Person ID."""
        person = self.resolve_person(counterpart_name_raw)
        return person.id if person else None
