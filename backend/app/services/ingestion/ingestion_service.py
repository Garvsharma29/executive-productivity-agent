"""Ingestion Service — persists parsed Data Pack objects into the database.

Responsible ONLY for deterministic persistence and source preservation.
No LLM calls, no commitment extraction, no deduplication, no inferences.

Guarantees:
- Preserves all source evidence verbatim.
- Fully idempotent: running repeatedly produces the exact same DB state.
- Preserves sender/recipient metadata, timestamps, and calendar ownership.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.calendar_event import CalendarEvent
from app.models.enums import SourceType
from app.models.person import Person
from app.models.source import Source
from app.services.ingestion.data_pack_parser import (
    ParsedDataPack,
    parse_data_pack,
)

logger = logging.getLogger(__name__)


class IngestionService:
    """Orchestrates deterministic ingestion of the Data Pack."""

    def __init__(self, db: Session, data_pack_path: Optional[str | Path] = None):
        self.db = db
        self.path = Path(data_pack_path or settings.data_pack_path)

    def run(self) -> dict[str, Any]:
        """Parse and persist the Data Pack idempotently.

        Returns a summary dictionary of ingested and verified counts.
        """
        parsed: ParsedDataPack = parse_data_pack(self.path)

        person_map = self._ingest_people(parsed)
        arjun = person_map.get("arjun.malhotra@veridian-corp.example")

        self._ingest_meeting(parsed, arjun)
        self._ingest_calendars(parsed, person_map)
        self._ingest_emails(parsed, person_map)
        self._ingest_voice_notes(parsed, arjun)

        self.db.commit()

        # Gather final counts from the database
        people_count = self.db.query(Person).count()
        meeting_count = (
            self.db.query(Source)
            .filter(Source.source_type == SourceType.MEETING)
            .count()
        )
        calendar_source_count = (
            self.db.query(Source)
            .filter(Source.source_type == SourceType.CALENDAR)
            .count()
        )
        email_source_count = (
            self.db.query(Source)
            .filter(Source.source_type == SourceType.EMAIL)
            .count()
        )
        voice_note_count = (
            self.db.query(Source)
            .filter(Source.source_type == SourceType.VOICE_NOTE)
            .count()
        )
        total_sources = self.db.query(Source).count()
        calendar_events_count = self.db.query(CalendarEvent).count()

        distinct_threads = len(set(e.thread_subject for e in parsed.emails))

        return {
            "status": "success",
            "people": people_count,
            "meeting": meeting_count,
            "calendar_sources": calendar_source_count,
            "email_sources": email_source_count,
            "email_threads": distinct_threads,
            "voice_notes": voice_note_count,
            "total_sources": total_sources,
            "calendar_events": calendar_events_count,
        }

    # -----------------------------------------------------------------------
    # Ingestion steps
    # -----------------------------------------------------------------------

    def _ingest_people(self, parsed: ParsedDataPack) -> dict[str, Person]:
        """Persist people idempotently. Returns email -> Person mapping."""
        person_map: dict[str, Person] = {}

        for p in parsed.people:
            person = (
                self.db.query(Person)
                .filter(Person.email == p.email)
                .first()
            )
            if not person:
                person = (
                    self.db.query(Person)
                    .filter(Person.name == p.name)
                    .first()
                )

            if person:
                # Update attributes if needed
                person.name = p.name
                person.role = p.role
                person.email = p.email
            else:
                person = Person(name=p.name, role=p.role, email=p.email)
                self.db.add(person)

            self.db.flush()
            person_map[person.email] = person
            person_map[person.name] = person

        return person_map

    def _ingest_meeting(
        self, parsed: ParsedDataPack, arjun: Optional[Person]
    ) -> None:
        """Persist the Leadership Sync meeting as ONE Source record."""
        m = parsed.meeting
        if not m:
            return

        ref = f"Meeting: {m.title} ({m.date.isoformat()})"
        source = (
            self.db.query(Source)
            .filter(
                Source.source_type == SourceType.MEETING,
                Source.source_reference == ref,
            )
            .first()
        )

        occurred_dt = datetime(
            m.date.year, m.date.month, m.date.day,
            m.start_time.hour, m.start_time.minute,
        )

        metadata = {
            "title": m.title,
            "date": m.date.isoformat(),
            "start_time": m.start_time.strftime("%H:%M"),
            "end_time": m.end_time.strftime("%H:%M"),
            "attendees": m.attendees,
        }

        if source:
            source.occurred_at = occurred_dt
            source.content = m.transcript
            source.extra_metadata = metadata
        else:
            source = Source(
                source_type=SourceType.MEETING,
                source_reference=ref,
                occurred_at=occurred_dt,
                author_person_id=arjun.id if arjun else None,
                content=m.transcript,
                extra_metadata=metadata,
            )
            self.db.add(source)

        self.db.flush()

    def _ingest_calendars(
        self, parsed: ParsedDataPack, person_map: dict[str, Person]
    ) -> None:
        """Persist calendar sources and individual CalendarEvent records."""
        # Group events by owner
        events_by_owner: dict[str, list] = {}
        for ev in parsed.calendar_events:
            events_by_owner.setdefault(ev.owner_name, []).append(ev)

        for owner_name, events in events_by_owner.items():
            owner_person = person_map.get(owner_name)
            owner_id = owner_person.id if owner_person else None

            # 1. Source record for this person's calendar
            ref = f"Calendar: {owner_name} (Week of 21–25 Sep 2026)"
            source = (
                self.db.query(Source)
                .filter(
                    Source.source_type == SourceType.CALENDAR,
                    Source.source_reference == ref,
                )
                .first()
            )

            raw_summary = (
                f"Calendar schedule for {owner_name} during the week of "
                f"Monday 21 September 2026 to Friday 25 September 2026.\n"
                f"Total events listed: {len(events)}."
            )
            metadata = {
                "owner": owner_name,
                "week": "2026-09-21 to 2026-09-25",
                "events_count": len(events),
            }

            if source:
                source.content = raw_summary
                source.extra_metadata = metadata
            else:
                source = Source(
                    source_type=SourceType.CALENDAR,
                    source_reference=ref,
                    occurred_at=datetime(2026, 9, 21, 0, 0),
                    author_person_id=owner_id,
                    content=raw_summary,
                    extra_metadata=metadata,
                )
                self.db.add(source)

            self.db.flush()

            # 2. Individual CalendarEvent records
            for ev in events:
                start_dt = datetime(
                    ev.date.year, ev.date.month, ev.date.day,
                    ev.start_time.hour, ev.start_time.minute,
                )
                end_dt = datetime(
                    ev.date.year, ev.date.month, ev.date.day,
                    ev.end_time.hour, ev.end_time.minute,
                )

                cal_event = (
                    self.db.query(CalendarEvent)
                    .filter(
                        CalendarEvent.owner_person_id == owner_id,
                        CalendarEvent.start_time == start_dt,
                        CalendarEvent.title == ev.title,
                    )
                    .first()
                )

                if cal_event:
                    cal_event.end_time = end_dt
                    cal_event.source_id = source.id
                else:
                    cal_event = CalendarEvent(
                        title=ev.title,
                        start_time=start_dt,
                        end_time=end_dt,
                        owner_person_id=owner_id,
                        source_id=source.id,
                    )
                    self.db.add(cal_event)

            self.db.flush()

    def _ingest_emails(
        self, parsed: ParsedDataPack, person_map: dict[str, Person]
    ) -> None:
        """Persist each email individually as a Source record."""
        for e in parsed.emails:
            ref = f"Email: {e.thread_subject} (#{e.sequence})"
            source = (
                self.db.query(Source)
                .filter(
                    Source.source_type == SourceType.EMAIL,
                    Source.source_reference == ref,
                )
                .first()
            )

            sender = person_map.get(e.sender_email)
            sender_id = sender.id if sender else None

            metadata = {
                "thread_subject": e.thread_subject,
                "sequence": e.sequence,
                "timestamp": e.timestamp.isoformat(),
                "sender_email": e.sender_email,
                "recipient_emails": e.recipient_emails,
            }

            if source:
                source.occurred_at = e.timestamp
                source.author_person_id = sender_id
                source.content = e.body
                source.extra_metadata = metadata
            else:
                source = Source(
                    source_type=SourceType.EMAIL,
                    source_reference=ref,
                    occurred_at=e.timestamp,
                    author_person_id=sender_id,
                    content=e.body,
                    extra_metadata=metadata,
                )
                self.db.add(source)

        self.db.flush()

    def _ingest_voice_notes(
        self, parsed: ParsedDataPack, arjun: Optional[Person]
    ) -> None:
        """Persist each voice note transcript individually as a Source record."""
        for idx, vn in enumerate(parsed.voice_notes, start=1):
            time_str = vn.time.strftime("%I:%M %p")
            ref = f"Voice Note {idx} ({vn.date.isoformat()} {time_str})"

            source = (
                self.db.query(Source)
                .filter(
                    Source.source_type == SourceType.VOICE_NOTE,
                    Source.source_reference == ref,
                )
                .first()
            )

            occurred_dt = datetime(
                vn.date.year, vn.date.month, vn.date.day,
                vn.time.hour, vn.time.minute,
            )

            metadata = {
                "date": vn.date.isoformat(),
                "time": time_str,
                "note_index": idx,
                "author": "Arjun Malhotra",
            }

            if source:
                source.occurred_at = occurred_dt
                source.author_person_id = arjun.id if arjun else None
                source.content = vn.transcript
                source.extra_metadata = metadata
            else:
                source = Source(
                    source_type=SourceType.VOICE_NOTE,
                    source_reference=ref,
                    occurred_at=occurred_dt,
                    author_person_id=arjun.id if arjun else None,
                    content=vn.transcript,
                    extra_metadata=metadata,
                )
                self.db.add(source)

        self.db.flush()


def ingest_data_pack(
    db: Session, data_pack_path: Optional[str | Path] = None
) -> dict[str, Any]:
    """Convenience function to run ingestion."""
    service = IngestionService(db, data_pack_path=data_pack_path)
    return service.run()
