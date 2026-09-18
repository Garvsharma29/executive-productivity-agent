"""Commitment Pipeline — orchestrates end-to-end extraction, normalization, deduplication, and persistence.

Guarantees:
- Fully idempotent: running repeatedly updates/refreshes without duplicating commitments or links.
- Strictly safe ownership: unassigned tasks (e.g. Mumbai lease) remain UNCLEAR with owner=None.
- Complete traceability: all supporting sources bridged via CommitmentSource.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit import CommitmentAudit
from app.models.commitment import Commitment
from app.models.commitment_source import CommitmentSource
from app.models.enums import AuditEventType
from app.services.deduplication.commitment_deduplicator import CommitmentDeduplicator
from app.services.extraction.commitment_extractor import CommitmentExtractor
from app.services.extraction.llm_provider import LLMProvider
from app.services.ownership.ownership_resolver import OwnershipResolver

logger = logging.getLogger(__name__)


class CommitmentPipeline:
    """Orchestrates candidate extraction, deduplication, and database persistence."""

    def __init__(self, db: Session, provider: Optional[LLMProvider] = None):
        self.db = db
        self.extractor = CommitmentExtractor(provider=provider)
        self.ownership_resolver = OwnershipResolver(db)
        self.deduplicator = CommitmentDeduplicator(self.ownership_resolver)

    def run(self) -> dict[str, Any]:
        """Execute the full commitment intelligence pipeline idempotently."""
        # 1. Extract candidates across all sources
        candidates = self.extractor.extract_from_all_sources(self.db)

        # 2. Deduplicate and merge candidates into canonical payloads
        canonical_payloads = self.deduplicator.deduplicate_and_merge(candidates)

        persisted_commitments: list[Commitment] = []

        # 3. Persist canonical commitments and evidence links idempotently
        for payload in canonical_payloads:
            # Query existing commitment by unique canonical signature
            # (action, ownership_type, owner_person_id)
            query = self.db.query(Commitment).filter(
                Commitment.action == payload.action,
                Commitment.ownership_type == payload.ownership_type,
            )
            if payload.owner_person_id is not None:
                query = query.filter(Commitment.owner_person_id == payload.owner_person_id)
            else:
                query = query.filter(Commitment.owner_person_id.is_(None))

            commitment = query.first()

            if commitment:
                # Update existing commitment state
                if commitment.status != payload.status:
                    self.db.add(
                        CommitmentAudit(
                            commitment_id=commitment.id,
                            event_type=AuditEventType.STATUS_CHANGED,
                            field_name="status",
                            old_value=commitment.status.value,
                            new_value=payload.status.value,
                        )
                    )
                    commitment.status = payload.status

                if commitment.deadline_date != payload.deadline_date:
                    self.db.add(
                        CommitmentAudit(
                            commitment_id=commitment.id,
                            event_type=AuditEventType.DEADLINE_UPDATED,
                            field_name="deadline_date",
                            old_value=commitment.deadline_date.isoformat() if commitment.deadline_date else None,
                            new_value=payload.deadline_date.isoformat() if payload.deadline_date else None,
                        )
                    )
                    commitment.deadline_date = payload.deadline_date
                    commitment.deadline_raw = payload.deadline_raw
                    commitment.deadline_precision = payload.deadline_precision

                commitment.counterpart_person_id = payload.counterpart_person_id
            else:
                # Create new canonical commitment
                commitment = Commitment(
                    action=payload.action,
                    raw_action=payload.raw_action,
                    ownership_type=payload.ownership_type,
                    owner_person_id=payload.owner_person_id,
                    counterpart_person_id=payload.counterpart_person_id,
                    deadline_date=payload.deadline_date,
                    deadline_raw=payload.deadline_raw,
                    deadline_precision=payload.deadline_precision,
                    status=payload.status,
                )
                self.db.add(commitment)
                self.db.flush()

                self.db.add(
                    CommitmentAudit(
                        commitment_id=commitment.id,
                        event_type=AuditEventType.CREATED,
                        field_name="status",
                        new_value=commitment.status.value,
                    )
                )

            self.db.flush()

            # 4. Bridge evidence sources idempotently
            existing_links = {
                link.source_id
                for link in self.db.query(CommitmentSource)
                .filter(CommitmentSource.commitment_id == commitment.id)
                .all()
            }

            for ev in payload.evidence_links:
                if ev.source_id not in existing_links:
                    link = CommitmentSource(
                        commitment_id=commitment.id,
                        source_id=ev.source_id,
                        evidence_text=ev.evidence_text,
                        extraction_method="llm_extraction",
                        confidence=ev.confidence,
                    )
                    self.db.add(link)
                    existing_links.add(ev.source_id)

            persisted_commitments.append(commitment)

        self.db.commit()

        # Summary for API and CLI callers
        total_links = self.db.query(CommitmentSource).count()
        return {
            "status": "success",
            "candidates_extracted": len(candidates),
            "canonical_commitments_count": len(persisted_commitments),
            "total_evidence_links": total_links,
            "commitments": [
                {
                    "id": str(c.id),
                    "action": c.action,
                    "ownership_type": c.ownership_type.value,
                    "owner": c.owner.name if c.owner else None,
                    "counterpart": c.counterpart.name if c.counterpart else None,
                    "deadline_raw": c.deadline_raw,
                    "deadline_date": c.deadline_date.isoformat() if c.deadline_date else None,
                    "deadline_precision": c.deadline_precision.value,
                    "status": c.status.value,
                    "sources_count": len(c.source_links),
                }
                for c in persisted_commitments
            ],
        }
