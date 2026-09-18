"""Tests for the domain data model.

Verifies:
- All models can be created (tables exist).
- A Person can be persisted and read back.
- A Source can be persisted and read back.
- A Commitment can be persisted and read back.
- One Commitment can be linked to multiple Sources via CommitmentSource.
- UNCLEAR ownership can be represented.
- Deadline precision/uncertainty can be represented.
- CalendarEvent can be persisted.
- CommitmentAudit can be persisted.
- The is_overdue() method works deterministically.
"""

from datetime import date, datetime, timezone

from app.models import (
    Person,
    Source,
    Commitment,
    CommitmentSource,
    CalendarEvent,
    CommitmentAudit,
    SourceType,
    OwnershipType,
    CommitmentStatus,
    DeadlinePrecision,
    AuditEventType,
)


# ---------------------------------------------------------------------------
# Helper factories — keep tests readable, no fake assessment data
# ---------------------------------------------------------------------------

def _make_person(name="Test Person", role=None, email=None):
    return Person(name=name, role=role, email=email)


def _make_source(source_type=SourceType.MEETING, ref="Test Meeting",
                 content="Some discussion happened.", author=None):
    return Source(
        source_type=source_type,
        source_reference=ref,
        content=content,
        author_person_id=author.id if author else None,
    )


def _make_commitment(action="Follow up on item", raw_action="follow up on that item",
                     ownership=OwnershipType.ARJUN, owner=None,
                     deadline_date=None, deadline_raw=None,
                     precision=DeadlinePrecision.NONE,
                     status=CommitmentStatus.OPEN):
    return Commitment(
        action=action,
        raw_action=raw_action,
        ownership_type=ownership,
        owner_person_id=owner.id if owner else None,
        deadline_date=deadline_date,
        deadline_raw=deadline_raw,
        deadline_precision=precision,
        status=status,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTablesCreated:
    """Verify that all ORM models produce valid tables."""

    def test_all_tables_exist(self, db_engine):
        """Base.metadata.create_all should create all 6 tables without error."""
        table_names = set(db_engine.dialect.get_table_names(
            db_engine.connect()
        ))
        expected = {
            "people",
            "sources",
            "commitments",
            "commitment_sources",
            "calendar_events",
            "commitment_audit",
        }
        assert expected.issubset(table_names), (
            f"Missing tables: {expected - table_names}"
        )


class TestPersonModel:
    def test_persist_and_read(self, db_session):
        person = _make_person(
            name="Arjun Malhotra",
            role="CEO",
            email="arjun@example.com",
        )
        db_session.add(person)
        db_session.commit()

        loaded = db_session.query(Person).filter_by(name="Arjun Malhotra").one()
        assert loaded.id is not None
        assert loaded.role == "CEO"
        assert loaded.email == "arjun@example.com"

    def test_nullable_fields(self, db_session):
        """Role and email can be null."""
        person = _make_person(name="Unknown Person")
        db_session.add(person)
        db_session.commit()

        loaded = db_session.query(Person).one()
        assert loaded.role is None
        assert loaded.email is None


class TestSourceModel:
    def test_persist_and_read(self, db_session):
        source = _make_source(
            source_type=SourceType.EMAIL,
            ref="Thread: Budget Review",
            content="Please review the budget by Friday.",
        )
        db_session.add(source)
        db_session.commit()

        loaded = db_session.query(Source).one()
        assert loaded.source_type == SourceType.EMAIL
        assert loaded.source_reference == "Thread: Budget Review"
        assert loaded.content == "Please review the budget by Friday."

    def test_source_with_author(self, db_session):
        person = _make_person(name="Author Person", email="author@test.com")
        db_session.add(person)
        db_session.flush()

        source = _make_source(author=person)
        db_session.add(source)
        db_session.commit()

        loaded = db_session.query(Source).one()
        assert loaded.author_person_id == person.id

    def test_all_source_types(self, db_session):
        """Every SourceType enum value can be persisted."""
        for stype in SourceType:
            source = Source(
                source_type=stype,
                source_reference=f"Test {stype.value}",
                content="content",
            )
            db_session.add(source)
        db_session.commit()
        assert db_session.query(Source).count() == len(SourceType)


class TestCommitmentModel:
    def test_persist_and_read(self, db_session):
        person = _make_person(name="Arjun", email="arjun@test.com")
        db_session.add(person)
        db_session.flush()

        commitment = _make_commitment(
            action="Send proposal to client",
            raw_action="I'll send the proposal",
            ownership=OwnershipType.ARJUN,
            owner=person,
            deadline_date=date(2025, 6, 15),
            deadline_raw="by June 15",
            precision=DeadlinePrecision.EXACT,
        )
        db_session.add(commitment)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.action == "Send proposal to client"
        assert loaded.raw_action == "I'll send the proposal"
        assert loaded.ownership_type == OwnershipType.ARJUN
        assert loaded.owner_person_id == person.id
        assert loaded.deadline_date == date(2025, 6, 15)
        assert loaded.deadline_raw == "by June 15"
        assert loaded.deadline_precision == DeadlinePrecision.EXACT
        assert loaded.status == CommitmentStatus.OPEN

    def test_unclear_ownership(self, db_session):
        """UNCLEAR ownership: owner_person_id is NULL, system flags ambiguity."""
        commitment = _make_commitment(
            action="Someone needs to handle compliance review",
            raw_action="the compliance review needs to happen",
            ownership=OwnershipType.UNCLEAR,
            owner=None,
        )
        db_session.add(commitment)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.ownership_type == OwnershipType.UNCLEAR
        assert loaded.owner_person_id is None

    def test_waiting_on_others(self, db_session):
        other = _make_person(name="Raghav", email="raghav@test.com")
        db_session.add(other)
        db_session.flush()

        commitment = _make_commitment(
            action="Raghav to send financials",
            raw_action="Raghav said he'd send the financials",
            ownership=OwnershipType.OTHER_PERSON,
            owner=other,
            status=CommitmentStatus.WAITING_ON_OTHERS,
        )
        db_session.add(commitment)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.ownership_type == OwnershipType.OTHER_PERSON
        assert loaded.status == CommitmentStatus.WAITING_ON_OTHERS
        assert loaded.owner_person_id == other.id


class TestDeadlinePrecision:
    """Verify that deadline uncertainty is properly representable."""

    def test_exact_deadline(self, db_session):
        c = _make_commitment(
            deadline_date=date(2025, 7, 1),
            deadline_raw="by July 1st",
            precision=DeadlinePrecision.EXACT,
        )
        db_session.add(c)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.deadline_precision == DeadlinePrecision.EXACT
        assert loaded.deadline_date == date(2025, 7, 1)
        assert loaded.deadline_raw == "by July 1st"

    def test_approximate_deadline(self, db_session):
        c = _make_commitment(
            deadline_date=None,
            deadline_raw="early next week",
            precision=DeadlinePrecision.APPROXIMATE,
        )
        db_session.add(c)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.deadline_precision == DeadlinePrecision.APPROXIMATE
        assert loaded.deadline_date is None
        assert loaded.deadline_raw == "early next week"

    def test_relative_unresolved_deadline(self, db_session):
        """'tomorrow' or 'Wednesday morning' — raw text preserved, no date yet."""
        c = _make_commitment(
            deadline_date=None,
            deadline_raw="tomorrow morning",
            precision=DeadlinePrecision.RELATIVE_UNRESOLVED,
        )
        db_session.add(c)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.deadline_precision == DeadlinePrecision.RELATIVE_UNRESOLVED
        assert loaded.deadline_date is None
        assert loaded.deadline_raw == "tomorrow morning"

    def test_no_deadline(self, db_session):
        c = _make_commitment(precision=DeadlinePrecision.NONE)
        db_session.add(c)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.deadline_precision == DeadlinePrecision.NONE
        assert loaded.deadline_date is None
        assert loaded.deadline_raw is None


class TestIsOverdue:
    """Verify is_overdue() deterministic computation."""

    def test_overdue_when_past_deadline(self, db_session):
        c = _make_commitment(
            deadline_date=date(2025, 6, 1),
            precision=DeadlinePrecision.EXACT,
            status=CommitmentStatus.OPEN,
        )
        db_session.add(c)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.is_overdue(as_of_date=date(2025, 6, 2)) is True

    def test_not_overdue_when_before_deadline(self, db_session):
        c = _make_commitment(
            deadline_date=date(2025, 6, 15),
            precision=DeadlinePrecision.EXACT,
            status=CommitmentStatus.OPEN,
        )
        db_session.add(c)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.is_overdue(as_of_date=date(2025, 6, 10)) is False

    def test_not_overdue_when_completed(self, db_session):
        """Completed commitments are never overdue, even if past deadline."""
        c = _make_commitment(
            deadline_date=date(2025, 6, 1),
            precision=DeadlinePrecision.EXACT,
            status=CommitmentStatus.COMPLETED,
        )
        db_session.add(c)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.is_overdue(as_of_date=date(2025, 6, 15)) is False

    def test_not_overdue_when_no_deadline(self, db_session):
        c = _make_commitment(precision=DeadlinePrecision.NONE)
        db_session.add(c)
        db_session.commit()

        loaded = db_session.query(Commitment).one()
        assert loaded.is_overdue(as_of_date=date(2025, 12, 31)) is False


class TestCommitmentSourceLink:
    """One commitment can be linked to multiple sources (and vice versa)."""

    def test_one_commitment_multiple_sources(self, db_session):
        # Create two distinct sources
        src_meeting = _make_source(
            source_type=SourceType.MEETING,
            ref="Q2 Planning",
            content="Arjun agreed to send the deck.",
        )
        src_email = _make_source(
            source_type=SourceType.EMAIL,
            ref="Thread: Deck Follow-up",
            content="As discussed, I will send the deck.",
        )
        db_session.add_all([src_meeting, src_email])
        db_session.flush()

        commitment = _make_commitment(
            action="Send the deck",
            raw_action="I will send the deck",
        )
        db_session.add(commitment)
        db_session.flush()

        # Link both sources to the same commitment
        link1 = CommitmentSource(
            commitment_id=commitment.id,
            source_id=src_meeting.id,
            evidence_text="Arjun agreed to send the deck.",
            extraction_method="llm_extraction",
            confidence=0.92,
        )
        link2 = CommitmentSource(
            commitment_id=commitment.id,
            source_id=src_email.id,
            evidence_text="I will send the deck.",
            extraction_method="llm_extraction",
            confidence=0.88,
        )
        db_session.add_all([link1, link2])
        db_session.commit()

        # Verify
        loaded = db_session.query(Commitment).one()
        assert len(loaded.source_links) == 2

        source_types = {link.source.source_type for link in loaded.source_links}
        assert source_types == {SourceType.MEETING, SourceType.EMAIL}

    def test_one_source_multiple_commitments(self, db_session):
        """A single source can contain references to multiple commitments."""
        source = _make_source(
            content="Arjun will send the deck. Raghav to share financials.",
        )
        db_session.add(source)
        db_session.flush()

        c1 = _make_commitment(action="Send the deck", raw_action="send the deck")
        c2 = _make_commitment(action="Share financials", raw_action="share financials")
        db_session.add_all([c1, c2])
        db_session.flush()

        link1 = CommitmentSource(
            commitment_id=c1.id,
            source_id=source.id,
            evidence_text="Arjun will send the deck.",
        )
        link2 = CommitmentSource(
            commitment_id=c2.id,
            source_id=source.id,
            evidence_text="Raghav to share financials.",
        )
        db_session.add_all([link1, link2])
        db_session.commit()

        loaded_source = db_session.query(Source).one()
        assert len(loaded_source.commitment_links) == 2


class TestCalendarEventModel:
    def test_persist_and_read(self, db_session):
        event = CalendarEvent(
            title="Q2 Strategy Review",
            start_time=datetime(2025, 6, 10, 14, 0, tzinfo=timezone.utc),
            end_time=datetime(2025, 6, 10, 15, 30, tzinfo=timezone.utc),
            description="Review Q2 goals and deliverables",
            attendees=["arjun@example.com", "raghav@example.com"],
        )
        db_session.add(event)
        db_session.commit()

        loaded = db_session.query(CalendarEvent).one()
        assert loaded.title == "Q2 Strategy Review"
        assert loaded.attendees is not None
        assert len(loaded.attendees) == 2


class TestCommitmentAuditModel:
    def test_persist_audit_event(self, db_session):
        commitment = _make_commitment()
        db_session.add(commitment)
        db_session.flush()

        audit = CommitmentAudit(
            commitment_id=commitment.id,
            event_type=AuditEventType.CREATED,
            field_name=None,
            old_value=None,
            new_value=None,
        )
        db_session.add(audit)
        db_session.commit()

        loaded = db_session.query(CommitmentAudit).one()
        assert loaded.event_type == AuditEventType.CREATED
        assert loaded.commitment_id == commitment.id

    def test_status_change_audit(self, db_session):
        commitment = _make_commitment()
        db_session.add(commitment)
        db_session.flush()

        audit = CommitmentAudit(
            commitment_id=commitment.id,
            event_type=AuditEventType.STATUS_CHANGED,
            field_name="status",
            old_value="OPEN",
            new_value="COMPLETED",
        )
        db_session.add(audit)
        db_session.commit()

        loaded = db_session.query(CommitmentAudit).one()
        assert loaded.field_name == "status"
        assert loaded.old_value == "OPEN"
        assert loaded.new_value == "COMPLETED"
