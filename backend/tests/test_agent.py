"""Tests for Executive Agent, Query Understanding, Retrieval, and Daily Brief."""

from datetime import date, datetime
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.main import app
from app.models.calendar_event import CalendarEvent
from app.models.commitment import Commitment
from app.models.enums import CommitmentStatus, DeadlinePrecision, OwnershipType
from app.models.person import Person
from app.services.agent.daily_brief import BriefBuilder
from app.services.agent.executive_agent import ExecutiveAgent
from app.services.agent.query_parser import QueryParser
from app.services.extraction.commitment_pipeline import CommitmentPipeline
from app.services.ingestion.ingestion_service import ingest_data_pack
from app.services.retrieval.commitment_retriever import (
    CommitmentFilterCriteria,
    CommitmentRetriever,
)


@pytest.fixture
def agent_db(db_session: Session) -> Session:
    """Fixture with ingested Data Pack and executed commitment pipeline."""
    ingest_data_pack(db_session, settings.data_pack_path)
    pipeline = CommitmentPipeline(db_session)
    pipeline.run()
    return db_session


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestQueryParser:
    """Unit tests for natural-language intent and entity understanding."""

    def test_parse_what_did_i_promise_raghav(self, agent_db: Session):
        parser = QueryParser(agent_db)
        intent = parser.parse("What did I promise Raghav?", as_of_date=date(2026, 9, 23))

        assert intent.intent_type == "PROMISES_MADE"
        assert intent.target_person is not None
        assert intent.target_person.name == "Raghav Sethi"
        assert intent.criteria.ownership_type == OwnershipType.ARJUN
        assert intent.criteria.counterpart_id == intent.target_person.id

    def test_parse_what_am_i_waiting_on(self, agent_db: Session):
        parser = QueryParser(agent_db)
        intent = parser.parse("What am I waiting on?", as_of_date=date(2026, 9, 23))

        assert intent.intent_type == "WAITING_ON"
        assert intent.criteria.ownership_type == OwnershipType.OTHER_PERSON
        assert intent.criteria.status == CommitmentStatus.OPEN

    def test_parse_what_needs_action_today(self, agent_db: Session):
        parser = QueryParser(agent_db)
        intent = parser.parse("What needs action today?", as_of_date=date(2026, 9, 23))

        assert intent.intent_type == "ACTIONS_TODAY"
        assert intent.criteria.status == CommitmentStatus.OPEN
        assert intent.as_of_date == date(2026, 9, 23)

    def test_parse_what_is_unclear(self, agent_db: Session):
        parser = QueryParser(agent_db)
        intent = parser.parse("What is unclear?", as_of_date=date(2026, 9, 23))

        assert intent.intent_type == "UNCLEAR_OWNERSHIP"
        assert intent.criteria.ownership_type == OwnershipType.UNCLEAR

    def test_parse_whats_overdue(self, agent_db: Session):
        parser = QueryParser(agent_db)
        intent = parser.parse("What's overdue?", as_of_date=date(2026, 9, 24))

        assert intent.intent_type == "OVERDUE"
        assert intent.criteria.is_overdue is True
        assert intent.as_of_date == date(2026, 9, 24)


class TestCommitmentRetriever:
    """Unit tests for structured commitment querying."""

    def test_retrieve_by_counterpart(self, agent_db: Session):
        retriever = CommitmentRetriever(agent_db)
        raghav = agent_db.query(Person).filter(Person.name == "Raghav Sethi").first()
        assert raghav is not None

        criteria = CommitmentFilterCriteria(counterpart_id=raghav.id)
        results = retriever.find(criteria)

        assert len(results) == 1
        assert "vendor list" in results[0].action.lower()
        assert results[0].owner.name == "Arjun Malhotra"

    def test_retrieve_unclear_commitments(self, agent_db: Session):
        retriever = CommitmentRetriever(agent_db)
        unclear = retriever.get_unclear_commitments()

        assert len(unclear) == 1
        assert "mumbai" in unclear[0].action.lower()
        assert unclear[0].ownership_type == OwnershipType.UNCLEAR
        assert unclear[0].owner_person_id is None

    def test_retrieve_overdue_temporal_shift(self, agent_db: Session):
        retriever = CommitmentRetriever(agent_db)

        # On 23 Sep 2026: Vendor list is due 23 Sep -> not overdue
        crit_23 = CommitmentFilterCriteria(status=CommitmentStatus.OPEN, is_overdue=True, as_of_date=date(2026, 9, 23))
        assert len(retriever.find(crit_23)) == 0

        # On 24 Sep 2026: Vendor list due date was 23 Sep -> OVERDUE!
        crit_24 = CommitmentFilterCriteria(status=CommitmentStatus.OPEN, is_overdue=True, as_of_date=date(2026, 9, 24))
        overdue_24 = retriever.find(crit_24)
        assert len(overdue_24) >= 1
        assert any("vendor list" in c.action.lower() for c in overdue_24)


class TestExecutiveAgentQA:
    """End-to-end question answering tests against actual Data Pack."""

    def test_query_what_did_i_promise_raghav(self, agent_db: Session):
        agent = ExecutiveAgent(agent_db)
        res = agent.answer_query("What did I promise Raghav?", as_of_date=date(2026, 9, 23))

        assert res.intent == "PROMISES_MADE"
        assert len(res.commitments) == 1
        comm = res.commitments[0]
        assert "vendor list" in comm.action.lower()
        assert comm.owner_name == "Arjun Malhotra"
        assert comm.counterpart_name == "Raghav Sethi"
        assert comm.status == CommitmentStatus.OPEN
        assert "vendor list" in res.answer.lower()
        # Verify evidence links are included
        assert len(res.evidence) >= 3

    def test_query_what_needs_action_today(self, agent_db: Session):
        agent = ExecutiveAgent(agent_db)
        res = agent.answer_query("What needs action today?", as_of_date=date(2026, 9, 23))

        assert res.intent == "ACTIONS_TODAY"
        # On 23 Sep, Arjun has actions: Vendor list and Meridian call coordination
        actions = [c.action.lower() for c in res.commitments]
        assert any("vendor list" in a for a in actions)
        assert any("meridian" in a for a in actions)
        assert len(res.evidence) > 0

    def test_query_what_is_unclear(self, agent_db: Session):
        agent = ExecutiveAgent(agent_db)
        res = agent.answer_query("What is unclear?", as_of_date=date(2026, 9, 23))

        assert res.intent == "UNCLEAR_OWNERSHIP"
        assert len(res.commitments) == 1
        comm = res.commitments[0]
        assert "mumbai" in comm.action.lower()
        assert comm.ownership_type == OwnershipType.UNCLEAR
        assert comm.owner_name is None
        assert "unclear" in res.answer.lower() or "unassigned" in res.answer.lower()

    def test_query_what_am_i_waiting_on(self, agent_db: Session):
        agent = ExecutiveAgent(agent_db)
        res = agent.answer_query("What am I waiting on?", as_of_date=date(2026, 9, 23))

        assert res.intent == "WAITING_ON"
        # Completed items (Expense report, Neha deck prep) must NOT appear as active waiting
        for c in res.commitments:
            assert c.status == CommitmentStatus.OPEN
            assert c.ownership_type == OwnershipType.OTHER_PERSON

    def test_empty_or_unknown_query(self, agent_db: Session):
        agent = ExecutiveAgent(agent_db)
        res = agent.answer_query("What did I promise nonexistingperson?", as_of_date=date(2026, 9, 23))
        assert "no" in res.answer.lower() or "not found" in res.answer.lower()

    def test_evidence_tracing_in_agent_response(self, agent_db: Session):
        agent = ExecutiveAgent(agent_db)
        res = agent.answer_query("What did I promise Raghav?", as_of_date=date(2026, 9, 23))

        for ev in res.evidence:
            assert ev.source_id is not None
            assert ev.source_type in ["MEETING", "EMAIL", "VOICE_NOTE"]
            assert ev.source_reference is not None
            assert len(ev.evidence_text) > 0


class TestDailyExecutiveBrief:
    """Tests for Daily Executive Brief structure, categories, and calendar separation."""

    def test_daily_brief_structure_and_categories(self, agent_db: Session):
        builder = BriefBuilder(agent_db)
        brief = builder.build_brief(as_of_date=date(2026, 9, 23))

        assert brief.as_of_date == date(2026, 9, 23)
        assert brief.executive_name == "Arjun Malhotra"

        # 1. My Actions: Open commitments owned by Arjun
        for action in brief.my_actions:
            assert action.ownership_type == OwnershipType.ARJUN
            assert action.status == CommitmentStatus.OPEN
            assert action.owner_name == "Arjun Malhotra"

        # 2. Waiting on Others: Open commitments owned by others
        for waiting in brief.waiting_on_others:
            assert waiting.ownership_type == OwnershipType.OTHER_PERSON
            assert waiting.status == CommitmentStatus.OPEN
            assert waiting.counterpart_name == "Arjun Malhotra"

        # 3. Needs Attention: Unclear ownership or imminent/overdue
        unclear_items = [item for item in brief.needs_attention if item.ownership_type == OwnershipType.UNCLEAR]
        assert len(unclear_items) == 1
        assert "mumbai" in unclear_items[0].action.lower()

        # 4. Completed: Expense report and Neha deck prep
        completed_actions = [item.action.lower() for item in brief.completed]
        assert any("expense variance" in a for a in completed_actions)

        # Completed commitments must NOT appear in my_actions
        my_action_ids = {item.id for item in brief.my_actions}
        for comp in brief.completed:
            assert comp.id not in my_action_ids

    def test_daily_brief_calendar_separation(self, agent_db: Session):
        """Calendar events must appear under scheduled_today and NOT as commitments."""
        builder = BriefBuilder(agent_db)
        brief = builder.build_brief(as_of_date=date(2026, 9, 23))

        # On Wed 23 Sep, Arjun has calendar events (Call - Meridian Logistics, Blocked)
        assert len(brief.scheduled_today) >= 1
        event_titles = [ev.title for ev in brief.scheduled_today]
        assert any("Meridian Logistics" in t for t in event_titles)

        # None of the calendar event IDs are commitment IDs
        commitment_ids = {c.id for c in agent_db.query(Commitment).all()}
        for ev in brief.scheduled_today:
            assert ev.id not in commitment_ids


class TestAPIEndpoints:
    """Integration tests for FastAPI endpoints."""

    def test_get_daily_brief_endpoint(self, agent_db: Session, client: TestClient):
        response = client.get("/api/brief?as_of_date=2026-09-23")
        assert response.status_code == 200
        data = response.json()

        assert data["as_of_date"] == "2026-09-23"
        assert "my_actions" in data
        assert "waiting_on_others" in data
        assert "needs_attention" in data
        assert "completed" in data
        assert "scheduled_today" in data

    def test_post_agent_query_endpoint(self, agent_db: Session, client: TestClient):
        payload = {
            "query": "What did I promise Raghav?",
            "as_of_date": "2026-09-23",
        }
        response = client.post("/api/agent/query", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["query"] == payload["query"]
        assert data["intent"] == "PROMISES_MADE"
        assert "vendor list" in data["answer"].lower()
        assert len(data["commitments"]) == 1
        assert len(data["evidence"]) >= 3

    def test_post_agent_query_all_key_questions(self, agent_db: Session, client: TestClient):
        # 1. Action today
        r1 = client.post("/api/agent/query", json={"query": "What needs action today?", "as_of_date": "2026-09-23"})
        assert r1.status_code == 200
        assert r1.json()["intent"] == "ACTIONS_TODAY"
        assert len(r1.json()["commitments"]) >= 2

        # 2. What is unclear
        r2 = client.post("/api/agent/query", json={"query": "What is unclear?", "as_of_date": "2026-09-23"})
        assert r2.status_code == 200
        assert r2.json()["intent"] == "UNCLEAR_OWNERSHIP"
        assert "mumbai" in r2.json()["answer"].lower()
        assert r2.json()["commitments"][0]["ownership_type"] == "UNCLEAR"

        # 3. What am I waiting on
        r3 = client.post("/api/agent/query", json={"query": "What am I waiting on?", "as_of_date": "2026-09-23"})
        assert r3.status_code == 200
        assert r3.json()["intent"] == "WAITING_ON"
        assert len(r3.json()["commitments"]) >= 1

        # 4. Overdue check on 24 Sep
        r4 = client.post("/api/agent/query", json={"query": "What's overdue?", "as_of_date": "2026-09-24"})
        assert r4.status_code == 200
        assert r4.json()["intent"] == "OVERDUE"
        assert len(r4.json()["commitments"]) >= 1
        assert any("vendor list" in c["action"].lower() for c in r4.json()["commitments"])

    def test_daily_brief_temporal_shifts_across_week(self, agent_db: Session):
        """Verify daily brief adjusts categories as the assessment week progresses."""
        builder = BriefBuilder(agent_db)

        # Wednesday 23 Sep: Vendor list due today, Neha deck waiting
        brief_23 = builder.build_brief(as_of_date=date(2026, 9, 23))
        assert any("vendor list" in a.action.lower() for a in brief_23.my_actions)
        assert any("campaign deck" in a.action.lower() for a in brief_23.waiting_on_others)

        # Thursday 24 Sep: Vendor list becomes OVERDUE, Neha deck completes
        brief_24 = builder.build_brief(as_of_date=date(2026, 9, 24))
        vendor_24 = next(a for a in brief_24.my_actions if "vendor list" in a.action.lower())
        assert vendor_24.is_overdue is True
        assert any(a.id == vendor_24.id for a in brief_24.needs_attention)
        # Neha deck is completed
        assert any("campaign deck" in a.action.lower() for a in brief_24.completed)

        # Friday 25 Sep: Both vendor list and deck review are overdue; Mumbai lease due today
        brief_25 = builder.build_brief(as_of_date=date(2026, 9, 25))
        mumbai_25 = next(a for a in brief_25.needs_attention if "mumbai" in a.action.lower())
        assert mumbai_25.deadline_date == date(2026, 9, 25)

