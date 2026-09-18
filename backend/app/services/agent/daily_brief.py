"""Daily Executive Brief Builder — categorizes executive workflow and schedule context."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.base import utcnow
from app.models.calendar_event import CalendarEvent
from app.models.commitment import Commitment
from app.models.commitment_source import CommitmentSource
from app.models.enums import CommitmentStatus, OwnershipType
from app.models.person import Person
from app.schemas.agent import (
    BriefCommitmentItem,
    CalendarEventItem,
    DailyBriefResponse,
    EvidenceItem,
)
from app.services.agent.query_parser import QueryParser


class BriefBuilder:
    """Constructs the daily executive action brief for Arjun Malhotra."""

    def __init__(self, db: Session):
        self.db = db
        self.arjun = self.db.query(Person).filter(Person.name.ilike("%arjun%")).first()

    def _convert_evidence(self, link: CommitmentSource) -> EvidenceItem:
        src = link.source
        return EvidenceItem(
            source_id=link.source_id,
            source_type=src.source_type.value if src else "UNKNOWN",
            source_reference=src.source_reference if src else "Unknown Source",
            occurred_at=src.occurred_at if src else None,
            evidence_text=link.evidence_text or (src.content[:300] if src else ""),
            extraction_method=link.extraction_method,
            confidence=link.confidence,
        )

    def _convert_commitment(self, c: Commitment, as_of_date: date) -> BriefCommitmentItem:
        evidence_items = [self._convert_evidence(link) for link in c.source_links]
        return BriefCommitmentItem(
            id=c.id,
            action=c.action,
            raw_action=c.raw_action,
            ownership_type=c.ownership_type,
            owner_name=c.owner.name if c.owner else None,
            counterpart_name=c.counterpart.name if c.counterpart else None,
            deadline_raw=c.deadline_raw,
            deadline_date=c.deadline_date,
            deadline_precision=c.deadline_precision,
            status=c.status,
            is_overdue=c.is_overdue(as_of_date),
            evidence_count=len(evidence_items),
            evidence=evidence_items,
        )

    def _convert_calendar_event(self, ev: CalendarEvent) -> CalendarEventItem:
        return CalendarEventItem(
            id=ev.id,
            title=ev.title,
            start_time=ev.start_time,
            end_time=ev.end_time,
            description=ev.description,
            attendees=ev.attendees,
        )

    def _effective_status(self, c: Commitment, as_of_date: date) -> CommitmentStatus:
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

    def build_brief(self, as_of_date: Optional[date] = None) -> DailyBriefResponse:
        """Assemble the complete executive daily brief for the specified date."""
        ref_date = as_of_date or QueryParser.DEFAULT_DATE

        # 1. Fetch all canonical commitments with eager-loaded relations
        commitments = (
            self.db.query(Commitment)
            .options(
                joinedload(Commitment.owner),
                joinedload(Commitment.counterpart),
                joinedload(Commitment.source_links).joinedload(CommitmentSource.source),
            )
            .order_by(Commitment.deadline_date.asc().nulls_last())
            .all()
        )

        # 2. Fetch Arjun's calendar events for as_of_date
        arjun_id = self.arjun.id if self.arjun else None
        calendar_events = []
        if arjun_id:
            # Query calendar events occurring on ref_date
            calendar_events = (
                self.db.query(CalendarEvent)
                .filter(
                    CalendarEvent.owner_person_id == arjun_id,
                    func.date(CalendarEvent.start_time) == ref_date,
                )
                .order_by(CalendarEvent.start_time.asc())
                .all()
            )

        # 3. Categorization logic
        my_actions: list[BriefCommitmentItem] = []
        waiting_on_others: list[BriefCommitmentItem] = []
        needs_attention_dict: dict[str, BriefCommitmentItem] = {}
        completed: list[BriefCommitmentItem] = []

        for c in commitments:
            eff_status = self._effective_status(c, ref_date)
            item = self._convert_commitment(c, ref_date)
            item.status = eff_status

            # A. Completed as of ref_date
            if eff_status == CommitmentStatus.COMPLETED:
                completed.append(item)
                continue

            # B. My Actions: Owned by Arjun & Open
            if c.ownership_type == OwnershipType.ARJUN:
                my_actions.append(item)

            # C. Waiting on Others: Colleague owned & Arjun counterpart & Open
            elif c.ownership_type == OwnershipType.OTHER_PERSON:
                waiting_on_others.append(item)

            # D. Needs Attention criteria:
            # - Overdue
            # - Unclear ownership
            # - Imminent deadline (due today)
            is_overdue = c.is_overdue(ref_date)
            is_unclear = c.ownership_type == OwnershipType.UNCLEAR
            is_due_today = c.deadline_date == ref_date

            if is_overdue or is_unclear or is_due_today:
                needs_attention_dict[str(c.id)] = item

        scheduled_today = [self._convert_calendar_event(ev) for ev in calendar_events]

        return DailyBriefResponse(
            as_of_date=ref_date,
            generated_at=utcnow(),
            summary_counts={
                "my_actions": len(my_actions),
                "waiting_on_others": len(waiting_on_others),
                "needs_attention": len(needs_attention_dict),
                "completed": len(completed),
                "scheduled_today": len(scheduled_today),
            },
            my_actions=my_actions,
            waiting_on_others=waiting_on_others,
            needs_attention=list(needs_attention_dict.values()),
            completed=completed,
            scheduled_today=scheduled_today,
        )
