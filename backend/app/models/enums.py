"""Domain enums shared across models and schemas.

Design decisions documented in docs/architecture/domain-model.md.
"""

import enum


class SourceType(str, enum.Enum):
    """Type of original evidence supplied in the assessment data pack."""

    MEETING = "MEETING"
    EMAIL = "EMAIL"
    CALENDAR = "CALENDAR"
    VOICE_NOTE = "VOICE_NOTE"


class OwnershipType(str, enum.Enum):
    """Who owns the commitment.

    ARJUN         – Arjun Malhotra is the owner (his action).
    OTHER_PERSON  – Another named person owns the action (Arjun is waiting).
    UNCLEAR       – The source does not establish clear ownership.
                    The system flags this rather than inventing an answer.
    """

    ARJUN = "ARJUN"
    OTHER_PERSON = "OTHER_PERSON"
    UNCLEAR = "UNCLEAR"


class CommitmentStatus(str, enum.Enum):
    """Stored status of a commitment.

    Only states that represent *persisted* workflow stages are included here.

    OVERDUE is intentionally excluded — it is a *computed* property derived
    deterministically from (deadline_date, as_of_date) at query time.
    Storing it would create stale data the moment the clock ticks.

    UNCLEAR_OWNER is also excluded as a status — unclear ownership is
    captured by OwnershipType.UNCLEAR on the commitment.  A commitment
    with unclear ownership is still OPEN (it needs attention precisely
    *because* ownership is unresolved).
    """

    OPEN = "OPEN"
    WAITING_ON_OTHERS = "WAITING_ON_OTHERS"
    COMPLETED = "COMPLETED"


class DeadlinePrecision(str, enum.Enum):
    """How precisely the deadline is known.

    EXACT               – A concrete date was stated ("by June 15").
    APPROXIMATE         – A rough window was stated ("early next week").
    RELATIVE_UNRESOLVED – A relative reference that has not been anchored
                          to a calendar date yet ("tomorrow", "Wednesday
                          morning").  The raw text is preserved; the system
                          will resolve it when given an as_of_date.
    NONE                – No deadline was mentioned.
    """

    EXACT = "EXACT"
    APPROXIMATE = "APPROXIMATE"
    RELATIVE_UNRESOLVED = "RELATIVE_UNRESOLVED"
    NONE = "NONE"


class AuditEventType(str, enum.Enum):
    """Categories of auditable changes on a commitment."""

    CREATED = "CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    DEADLINE_UPDATED = "DEADLINE_UPDATED"
    OWNERSHIP_CHANGED = "OWNERSHIP_CHANGED"
    SOURCE_LINKED = "SOURCE_LINKED"
