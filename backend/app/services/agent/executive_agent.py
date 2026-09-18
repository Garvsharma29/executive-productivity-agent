"""Executive Agent — orchestrates query understanding, retrieval, and grounded response."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.commitment import Commitment
from app.models.commitment_source import CommitmentSource
from app.models.enums import CommitmentStatus
from app.schemas.agent import AgentQueryResponse, BriefCommitmentItem, EvidenceItem
from app.services.agent.query_parser import QueryParser
from app.services.agent.response_generator import ResponseGenerator
from app.services.retrieval.commitment_retriever import CommitmentRetriever


class ExecutiveAgent:
    """Natural-language question answering agent for executive productivity."""

    def __init__(self, db: Session):
        self.db = db
        self.retriever = CommitmentRetriever(db)
        self.parser = QueryParser(db)
        self.generator = ResponseGenerator()

    def _convert_evidence(self, link: CommitmentSource) -> EvidenceItem:
        """Convert a CommitmentSource SQLAlchemy model to EvidenceItem schema."""
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

    def _convert_commitment(self, c: Commitment, as_of_date: date) -> BriefCommitmentItem:
        """Convert a Commitment SQLAlchemy model to BriefCommitmentItem schema."""
        evidence_items = [self._convert_evidence(link) for link in c.source_links]
        eff_status = self._effective_status(c, as_of_date)
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
            status=eff_status,
            is_overdue=c.is_overdue(as_of_date),
            evidence_count=len(evidence_items),
            evidence=evidence_items,
        )

    def answer_query(self, query: str, as_of_date: Optional[date] = None) -> AgentQueryResponse:
        """Process a natural language query and return an evidence-grounded response."""
        ref_date = as_of_date or QueryParser.DEFAULT_DATE

        # 1. Query Understanding
        intent = self.parser.parse(query, as_of_date=ref_date)

        # 2. Structured Retrieval
        commitments = self.retriever.find(intent.criteria)

        # 3. Grounded Response Generation
        answer_text = self.generator.generate(intent, commitments, ref_date)

        # 4. Serialize Commitments and Evidence
        brief_items = [self._convert_commitment(c, ref_date) for c in commitments]
        all_evidence: list[EvidenceItem] = []
        seen_source_ids = set()
        for item in brief_items:
            for ev in item.evidence:
                if ev.source_id not in seen_source_ids:
                    seen_source_ids.add(ev.source_id)
                    all_evidence.append(ev)

        return AgentQueryResponse(
            query=query,
            as_of_date=ref_date,
            intent=intent.intent_type,
            answer=answer_text,
            commitments=brief_items,
            evidence=all_evidence,
        )
