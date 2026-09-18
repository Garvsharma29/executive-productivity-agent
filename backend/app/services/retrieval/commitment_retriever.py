"""Commitment Retrieval Service — structured and explainable query layer.

Retrieves canonical commitments from PostgreSQL with eager-loaded owners,
counterparts, and source evidence links without requiring a vector database.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.commitment import Commitment
from app.models.commitment_source import CommitmentSource
from app.models.enums import CommitmentStatus, OwnershipType
from app.models.person import Person


@dataclass
class CommitmentFilterCriteria:
    """Structured search criteria for querying canonical commitments."""
    owner_id: Optional[uuid.UUID] = None
    counterpart_id: Optional[uuid.UUID] = None
    involved_person_id: Optional[uuid.UUID] = None
    ownership_type: Optional[OwnershipType] = None
    status: Optional[CommitmentStatus] = None
    status_in: Optional[list[CommitmentStatus]] = None
    due_date: Optional[date] = None
    due_before: Optional[date] = None
    due_after: Optional[date] = None
    is_overdue: Optional[bool] = None
    search_query: Optional[str] = None
    as_of_date: Optional[date] = None


def get_effective_status(c: Commitment, as_of_date: date) -> CommitmentStatus:
    """Determine effective status of commitment relative to as_of_date."""
    if c.status != CommitmentStatus.COMPLETED:
        return c.status

    completion_dates = []
    for link in c.source_links:
        if link.source and link.source.occurred_at:
            txt = (link.evidence_text or link.source.content).lower()
            if any(w in txt for w in ["attached", "sent as promised", "is ready"]):
                completion_dates.append(link.source.occurred_at.date())

    if completion_dates and max(completion_dates) > as_of_date:
        return CommitmentStatus.OPEN

    return CommitmentStatus.COMPLETED


class CommitmentRetriever:
    """Service for querying and retrieving canonical commitments with evidence."""

    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        """Base SQLAlchemy query eager-loading relationships and evidence."""
        return (
            self.db.query(Commitment)
            .options(
                joinedload(Commitment.owner),
                joinedload(Commitment.counterpart),
                joinedload(Commitment.source_links).joinedload(CommitmentSource.source),
            )
        )

    def get_by_id(self, commitment_id: uuid.UUID) -> Optional[Commitment]:
        """Fetch a single commitment by ID with all evidence."""
        return self._base_query().filter(Commitment.id == commitment_id).first()

    def find(self, criteria: CommitmentFilterCriteria) -> list[Commitment]:
        """Execute a structured search based on CommitmentFilterCriteria."""
        query = self._base_query()

        # Ownership filter
        if criteria.ownership_type is not None:
            query = query.filter(Commitment.ownership_type == criteria.ownership_type)

        # Owner person ID
        if criteria.owner_id is not None:
            query = query.filter(Commitment.owner_person_id == criteria.owner_id)

        # Counterpart person ID
        if criteria.counterpart_id is not None:
            query = query.filter(Commitment.counterpart_person_id == criteria.counterpart_id)

        # Involved person (either owner OR counterpart)
        if criteria.involved_person_id is not None:
            query = query.filter(
                or_(
                    Commitment.owner_person_id == criteria.involved_person_id,
                    Commitment.counterpart_person_id == criteria.involved_person_id,
                )
            )

        # Status filter — if as_of_date is provided, evaluate effective status on that date
        # (e.g. commitments completed on Thursday were still OPEN on Wednesday)
        filter_status_in_python = False
        if criteria.status is not None:
            if criteria.as_of_date is not None:
                filter_status_in_python = True
            else:
                query = query.filter(Commitment.status == criteria.status)
        elif criteria.status_in:
            query = query.filter(Commitment.status.in_(criteria.status_in))

        # Deadline date filter
        if criteria.due_date is not None:
            query = query.filter(Commitment.deadline_date == criteria.due_date)
        if criteria.due_before is not None:
            query = query.filter(Commitment.deadline_date <= criteria.due_before)
        if criteria.due_after is not None:
            query = query.filter(Commitment.deadline_date >= criteria.due_after)

        # Keyword / search query filter (case-insensitive on action or raw_action)
        if criteria.search_query:
            term = f"%{criteria.search_query.strip()}%"
            query = query.filter(
                or_(
                    Commitment.action.ilike(term),
                    Commitment.raw_action.ilike(term),
                )
            )

        results = query.order_by(Commitment.deadline_date.asc().nulls_last()).all()

        # Effective status filtering when as_of_date is specified
        if filter_status_in_python and criteria.as_of_date is not None:
            results = [
                c for c in results
                if get_effective_status(c, criteria.as_of_date) == criteria.status
            ]

        # Overdue filtering evaluated in Python using deterministic is_overdue(as_of_date)
        if criteria.is_overdue is not None and criteria.as_of_date is not None:
            results = [
                c for c in results
                if c.is_overdue(criteria.as_of_date) == criteria.is_overdue
            ]

        return results

    def get_arjun_commitments(
        self, as_of_date: date, status: Optional[CommitmentStatus] = None
    ) -> list[Commitment]:
        """Fetch commitments owned by Arjun Malhotra."""
        criteria = CommitmentFilterCriteria(
            ownership_type=OwnershipType.ARJUN,
            status=status,
            as_of_date=as_of_date,
        )
        return self.find(criteria)

    def get_waiting_on_others(
        self, arjun_id: uuid.UUID, as_of_date: date
    ) -> list[Commitment]:
        """Fetch open commitments where Arjun is waiting on a colleague."""
        criteria = CommitmentFilterCriteria(
            counterpart_id=arjun_id,
            ownership_type=OwnershipType.OTHER_PERSON,
            status=CommitmentStatus.OPEN,
            as_of_date=as_of_date,
        )
        return self.find(criteria)

    def get_unclear_commitments(self) -> list[Commitment]:
        """Fetch commitments where ownership is explicitly UNCLEAR."""
        criteria = CommitmentFilterCriteria(
            ownership_type=OwnershipType.UNCLEAR,
            status=CommitmentStatus.OPEN,
        )
        return self.find(criteria)
