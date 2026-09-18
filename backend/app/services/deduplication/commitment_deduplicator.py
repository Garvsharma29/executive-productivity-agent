"""Commitment Deduplicator & Merger — aggregates multi-source candidate commitments.

Resolves temporal evolution:
- Tracks shifting deadlines across meeting transcripts, email threads, and voice notes.
- Captures the latest supported deadline and status (e.g. COMPLETED for delivered items).
- Merges all supporting evidence into multi-source references without duplicating commitments.
- Strictly keeps distinct obligations separate (e.g. Neha deck prep vs Arjun deck review).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from app.models.enums import CommitmentStatus, DeadlinePrecision, OwnershipType
from app.services.deadline.deadline_resolver import DeadlineResolver, ResolvedDeadline
from app.services.extraction.extraction_schema import ExtractedCommitmentCandidate
from app.services.ownership.ownership_resolver import OwnershipResolver


@dataclass
class EvidenceLink:
    source_id: uuid.UUID
    source_type: str
    source_reference: str
    evidence_text: str
    confidence: float
    occurred_at: Optional[datetime]


@dataclass
class CanonicalCommitmentPayload:
    topic: str
    action: str
    raw_action: str
    ownership_type: OwnershipType
    owner_person_id: Optional[uuid.UUID]
    counterpart_person_id: Optional[uuid.UUID]
    deadline_date: Optional[date]
    deadline_raw: Optional[str]
    deadline_precision: DeadlinePrecision
    status: CommitmentStatus
    evidence_links: list[EvidenceLink] = field(default_factory=list)


class CommitmentDeduplicator:
    """Merges candidate extractions into deduplicated canonical commitments."""

    def __init__(self, ownership_resolver: OwnershipResolver):
        self.ownership_resolver = ownership_resolver

    def deduplicate_and_merge(
        self, candidates: list[ExtractedCommitmentCandidate]
    ) -> list[CanonicalCommitmentPayload]:
        """Group candidates by topic and distinct owner, merging temporal evolution."""
        if not candidates:
            return []

        # Group candidates by (canonical_topic, ownership_type, owner_person_id)
        # Note: Keeps Neha's preparation and Arjun's review separate because their owner is different.
        clusters: dict[tuple[str, OwnershipType, Optional[uuid.UUID]], list[ExtractedCommitmentCandidate]] = {}

        for cand in candidates:
            # Resolve owner and counterpart
            ownership_type, owner_id = self.ownership_resolver.resolve_ownership(
                owner_name_raw=cand.owner_name_raw,
                topic=cand.topic,
                action=cand.action,
            )
            counterpart_id = self.ownership_resolver.resolve_counterpart(cand.counterpart_name_raw)

            # Store resolved IDs on the candidate instance
            cand.ownership_type = ownership_type

            # Cluster key distinguishes distinct topics and distinct owners
            cluster_topic = cand.topic or cand.action
            key = (cluster_topic, ownership_type, owner_id)
            clusters.setdefault(key, []).append((cand, owner_id, counterpart_id))

        canonical_results: list[CanonicalCommitmentPayload] = []

        for (topic, ownership_type, owner_id), cand_entries in clusters.items():
            # Sort candidates chronologically by occurred_at
            cand_entries.sort(key=lambda item: item[0].occurred_at or datetime.min)

            # Extract latest candidate for current state / deadline
            latest_cand, _, latest_counterpart_id = cand_entries[-1]

            # Find counterpart from any candidate if latest missed it
            resolved_counterpart_id = latest_counterpart_id
            if not resolved_counterpart_id:
                for _, _, c_id in cand_entries:
                    if c_id:
                        resolved_counterpart_id = c_id
                        break

            # Find latest deadline among all candidates in this cluster
            # (Earlier statements may have had older deadlines, later statements update it)
            latest_deadline_info = None
            for cand, _, _ in cand_entries:
                if cand.deadline_raw:
                    resolved_dl = DeadlineResolver.resolve_deadline(
                        cand.deadline_raw, source_occurred_at=cand.occurred_at
                    )
                    latest_deadline_info = resolved_dl

            if not latest_deadline_info:
                latest_deadline_info = DeadlineResolver.resolve_deadline(
                    latest_cand.deadline_raw, source_occurred_at=latest_cand.occurred_at
                )

            # Determine final status: if any message confirms completion, mark COMPLETED
            # (e.g. Divya attached report and Arjun acknowledged receipt)
            final_status = CommitmentStatus.OPEN
            for cand, _, _ in cand_entries:
                if cand.status == CommitmentStatus.COMPLETED:
                    final_status = CommitmentStatus.COMPLETED

            # Merge all evidence sources, deduplicating by source_id
            seen_sources: set[uuid.UUID] = set()
            evidence_links: list[EvidenceLink] = []

            for cand, _, _ in cand_entries:
                if cand.source_id not in seen_sources:
                    seen_sources.add(cand.source_id)
                    evidence_links.append(
                        EvidenceLink(
                            source_id=cand.source_id,
                            source_type=cand.source_type,
                            source_reference=cand.source_reference,
                            evidence_text=cand.evidence_text,
                            confidence=cand.confidence,
                            occurred_at=cand.occurred_at,
                        )
                    )

            canonical_results.append(
                CanonicalCommitmentPayload(
                    topic=topic,
                    action=latest_cand.action,
                    raw_action=latest_cand.raw_action,
                    ownership_type=ownership_type,
                    owner_person_id=owner_id,
                    counterpart_person_id=resolved_counterpart_id,
                    deadline_date=latest_deadline_info.deadline_date,
                    deadline_raw=latest_deadline_info.deadline_raw,
                    deadline_precision=latest_deadline_info.precision,
                    status=final_status,
                    evidence_links=evidence_links,
                )
            )

        return canonical_results
