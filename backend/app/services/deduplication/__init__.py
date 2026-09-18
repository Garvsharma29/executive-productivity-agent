"""Commitment deduplication package."""

from app.services.deduplication.commitment_deduplicator import (
    CanonicalCommitmentPayload,
    CommitmentDeduplicator,
    EvidenceLink,
)

__all__ = [
    "CanonicalCommitmentPayload",
    "CommitmentDeduplicator",
    "EvidenceLink",
]
