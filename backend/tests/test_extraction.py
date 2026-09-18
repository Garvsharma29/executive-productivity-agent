"""Tests for commitment candidate extraction, normalization, deduplication, and pipeline."""

from datetime import date, datetime
import uuid
import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.commitment import Commitment
from app.models.commitment_source import CommitmentSource
from app.models.enums import CommitmentStatus, DeadlinePrecision, OwnershipType, SourceType
from app.models.person import Person
from app.models.source import Source
from app.services.deadline.deadline_resolver import DeadlineResolver
from app.services.deduplication.commitment_deduplicator import CommitmentDeduplicator
from app.services.extraction.commitment_extractor import CommitmentExtractor
from app.services.extraction.commitment_pipeline import CommitmentPipeline
from app.services.extraction.extraction_schema import ExtractedCommitmentCandidate
from app.services.extraction.llm_provider import DeterministicExtractionProvider
from app.services.ingestion.ingestion_service import ingest_data_pack
from app.services.normalization.action_normalizer import ActionNormalizer
from app.services.ownership.ownership_resolver import OwnershipResolver


@pytest.fixture
def populated_db(db_session: Session) -> Session:
    """Fixture with ingested Data Pack sources and people."""
    ingest_data_pack(db_session, settings.data_pack_path)
    return db_session


class TestExtractionSchema:
    """Test 1: Structured extraction schema validation."""

    def test_extracted_commitment_candidate_validation(self):
        cand = ExtractedCommitmentCandidate(
            action="Send updated vendor list to Raghav",
            raw_action="will send by tomorrow morning",
            owner_name_raw="Arjun Malhotra",
            counterpart_name_raw="Raghav Sethi",
            ownership_type=OwnershipType.ARJUN,
            deadline_raw="tomorrow morning",
            deadline_precision=DeadlinePrecision.APPROXIMATE,
            status=CommitmentStatus.OPEN,
            topic="Vendor List",
            source_id=uuid.uuid4(),
            source_type="EMAIL",
            source_reference="Email: Vendor List (#2)",
            evidence_text="will send first thing tomorrow morning instead",
            occurred_at=datetime(2026, 9, 21, 17, 40),
            confidence=0.95,
        )

        assert cand.action == "Send updated vendor list to Raghav"
        assert cand.ownership_type == OwnershipType.ARJUN
        assert cand.deadline_precision == DeadlinePrecision.APPROXIMATE
        assert cand.confidence == 0.95


class TestOwnershipResolution:
    """Test 2 & 3: Known-person resolution and strict unclear ownership safety."""

    def test_known_person_resolution(self, populated_db: Session):
        resolver = OwnershipResolver(populated_db)

        # Arjun
        ot, owner_id = resolver.resolve_ownership("Arjun Malhotra", topic="Vendor List")
        assert ot == OwnershipType.ARJUN
        assert owner_id is not None

        # Colleague
        ot_divya, divya_id = resolver.resolve_ownership("Divya Rao", topic="Expense Variance Report")
        assert ot_divya == OwnershipType.OTHER_PERSON
        assert divya_id is not None
        assert divya_id != owner_id

    def test_mumbai_lease_strictly_unclear_ownership(self, populated_db: Session):
        """Mumbai office lease renewal must remain UNCLEAR regardless of input hints."""
        resolver = OwnershipResolver(populated_db)

        # Even if someone asks Raghav or Facilities
        ot, owner_id = resolver.resolve_ownership(
            "Facilities", topic="Mumbai Office Lease Renewal"
        )
        assert ot == OwnershipType.UNCLEAR
        assert owner_id is None

        ot_arjun, arjun_id = resolver.resolve_ownership(
            "Arjun Malhotra", topic="Mumbai Office Lease Renewal"
        )
        assert ot_arjun == OwnershipType.UNCLEAR
        assert arjun_id is None

        ot_none, none_id = resolver.resolve_ownership(
            None, topic="Mumbai Office Lease Renewal"
        )
        assert ot_none == OwnershipType.UNCLEAR
        assert none_id is None


class TestDeadlineResolution:
    """Test 4, 8 & 9: Evolving deadline resolution, precision, and as_of_date behavior."""

    def test_deadline_precision_exact_vs_approximate(self):
        base_dt = datetime(2026, 9, 21, 9, 0)

        # EXACT: Specific time stated
        res_exact = DeadlineResolver.resolve_deadline("Thursday 9:30 AM", source_occurred_at=base_dt)
        assert res_exact.deadline_date == date(2026, 9, 24)
        assert res_exact.deadline_time is not None
        assert res_exact.deadline_time.hour == 9
        assert res_exact.deadline_time.minute == 30
        assert res_exact.precision == DeadlinePrecision.EXACT

        # APPROXIMATE: Time of day or day only, no clock time fabricated
        res_approx = DeadlineResolver.resolve_deadline("Wednesday morning", source_occurred_at=base_dt)
        assert res_approx.deadline_date == date(2026, 9, 23)
        assert res_approx.deadline_time is None
        assert res_approx.precision == DeadlinePrecision.APPROXIMATE

        res_eod = DeadlineResolver.resolve_deadline("Friday, 25 September end of day", source_occurred_at=base_dt)
        assert res_eod.deadline_date == date(2026, 9, 25)
        assert res_eod.precision == DeadlinePrecision.APPROXIMATE

    def test_overdue_calculation_with_as_of_date(self):
        deadline = date(2026, 9, 23)

        # Before deadline -> not overdue
        assert not DeadlineResolver.is_overdue(deadline, CommitmentStatus.OPEN, as_of_date=date(2026, 9, 22))

        # On deadline day -> not overdue
        assert not DeadlineResolver.is_overdue(deadline, CommitmentStatus.OPEN, as_of_date=date(2026, 9, 23))

        # After deadline day -> overdue!
        assert DeadlineResolver.is_overdue(deadline, CommitmentStatus.OPEN, as_of_date=date(2026, 9, 24))

        # Completed commitments are never overdue
        assert not DeadlineResolver.is_overdue(deadline, CommitmentStatus.COMPLETED, as_of_date=date(2026, 9, 25))


class TestActionNormalizer:
    """Test action text normalization."""

    def test_strips_filler_preserves_semantics(self):
        norm1 = ActionNormalizer.normalize_action_text("quick note to self — need to get Raghav that vendor list")
        assert "vendor list" in norm1.lower()
        assert "quick note" not in norm1.lower()

        norm2 = ActionNormalizer.normalize_action_text("will send by tomorrow morning for sure")
        assert "send by tomorrow morning" in norm2.lower()


class TestDataPackIntegrationAndInvariants:
    """Integration tests verifying Data Pack commitments, deduplication, and evidence relationships."""

    def test_pipeline_execution_and_invariants(self, populated_db: Session):
        pipeline = CommitmentPipeline(populated_db)
        result = pipeline.run()

        assert result["status"] == "success"
        commitments = populated_db.query(Commitment).all()

        # There are exactly 6 canonical commitment items
        assert len(commitments) == 6

        # --- Invariant 1: Vendor list evolves to Wednesday morning, owner Arjun ---
        vendor_commitments = [c for c in commitments if "vendor list" in c.action.lower()]
        assert len(vendor_commitments) == 1
        vendor = vendor_commitments[0]
        assert vendor.ownership_type == OwnershipType.ARJUN
        assert vendor.owner is not None
        assert vendor.owner.name == "Arjun Malhotra"
        assert vendor.counterpart is not None
        assert vendor.counterpart.name == "Raghav Sethi"
        assert vendor.deadline_date == date(2026, 9, 23)
        assert "morning" in vendor.deadline_raw.lower()
        assert vendor.status == CommitmentStatus.OPEN
        # Evidence includes meeting, email, voice note
        assert len(vendor.source_links) >= 3

        # --- Invariant 2: Mumbai lease remains unowned / UNCLEAR ---
        mumbai_commitments = [c for c in commitments if "mumbai" in c.action.lower()]
        assert len(mumbai_commitments) == 1
        mumbai = mumbai_commitments[0]
        assert mumbai.ownership_type == OwnershipType.UNCLEAR
        assert mumbai.owner_person_id is None
        assert mumbai.owner is None
        assert mumbai.deadline_date == date(2026, 9, 25)
        assert len(mumbai.source_links) >= 3

        # --- Invariant 3: Expense variance report is COMPLETED ---
        expense_commitments = [c for c in commitments if "expense variance" in c.action.lower()]
        assert len(expense_commitments) == 1
        expense = expense_commitments[0]
        assert expense.ownership_type == OwnershipType.OTHER_PERSON
        assert expense.owner is not None
        assert expense.owner.name == "Divya Rao"
        assert expense.status == CommitmentStatus.COMPLETED
        assert expense.deadline_date == date(2026, 9, 23)

        # --- Invariant 4: Q3 campaign deck has distinct Neha prep & Arjun review ---
        deck_commitments = [c for c in commitments if "campaign deck" in c.action.lower()]
        assert len(deck_commitments) == 2

        neha_deck = next(c for c in deck_commitments if c.owner and c.owner.name == "Neha Kapoor")
        arjun_review = next(c for c in deck_commitments if c.owner and c.owner.name == "Arjun Malhotra")

        assert neha_deck.ownership_type == OwnershipType.OTHER_PERSON
        assert neha_deck.status == CommitmentStatus.COMPLETED
        assert arjun_review.ownership_type == OwnershipType.ARJUN
        assert arjun_review.status == CommitmentStatus.OPEN
        assert arjun_review.deadline_date == date(2026, 9, 24)
        assert arjun_review.deadline_precision == DeadlinePrecision.EXACT

        # --- Invariant 5: Meridian Logistics call is confirmed for Wed 3 PM ---
        meridian_commitments = [c for c in commitments if "meridian" in c.action.lower()]
        assert len(meridian_commitments) == 1
        meridian = meridian_commitments[0]
        assert meridian.ownership_type == OwnershipType.ARJUN
        assert meridian.deadline_date == date(2026, 9, 23)
        assert meridian.deadline_precision == DeadlinePrecision.EXACT
        assert "3:00" in meridian.deadline_raw or "3" in meridian.deadline_raw

    def test_pipeline_idempotency(self, populated_db: Session):
        """Running the pipeline twice produces identical database state and no duplicates."""
        pipeline = CommitmentPipeline(populated_db)

        # Run 1
        res1 = pipeline.run()
        count1 = populated_db.query(Commitment).count()
        links1 = populated_db.query(CommitmentSource).count()

        # Run 2
        res2 = pipeline.run()
        count2 = populated_db.query(Commitment).count()
        links2 = populated_db.query(CommitmentSource).count()

        assert count1 == count2 == 6
        assert links1 == links2
        assert res1["canonical_commitments_count"] == res2["canonical_commitments_count"]
