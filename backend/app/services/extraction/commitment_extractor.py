"""Commitment Extractor — extracts candidate commitments across sources."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.enums import SourceType
from app.models.source import Source
from app.services.extraction.extraction_schema import ExtractedCommitmentCandidate
from app.services.extraction.llm_provider import DeterministicExtractionProvider, LLMProvider


class CommitmentExtractor:
    """Service that coordinates commitment candidate extraction from stored sources."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or DeterministicExtractionProvider()

    def extract_from_source(self, source: Source) -> list[ExtractedCommitmentCandidate]:
        """Extract candidate commitments from a single Source record."""
        return self.provider.extract_candidates(source)

    def extract_from_all_sources(self, db: Session) -> list[ExtractedCommitmentCandidate]:
        """Extract candidate commitments from all action-bearing sources in the database.

        Calendar sources are timing context/constraints, while MEETING, EMAIL,
        and VOICE_NOTE sources contain human commitments and actions.
        """
        sources = (
            db.query(Source)
            .filter(Source.source_type.in_([
                SourceType.MEETING,
                SourceType.EMAIL,
                SourceType.VOICE_NOTE,
            ]))
            .order_by(Source.occurred_at.asc())
            .all()
        )

        all_candidates: list[ExtractedCommitmentCandidate] = []
        for src in sources:
            candidates = self.extract_from_source(src)
            all_candidates.extend(candidates)

        return all_candidates
