"""Query Understanding & Intent Parsing for Executive Productivity Agent."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.enums import CommitmentStatus, OwnershipType
from app.models.person import Person
from app.services.retrieval.commitment_retriever import CommitmentFilterCriteria


@dataclass
class ParsedQueryIntent:
    """Structured representation of the user's natural language query intent."""
    raw_query: str
    intent_type: str
    as_of_date: date
    criteria: CommitmentFilterCriteria
    target_person: Optional[Person] = None
    target_person_role: Optional[str] = None  # "counterpart", "owner", "involved"


class QueryParser:
    """Parses natural-language queries into structured retrieval criteria."""

    DEFAULT_DATE = date(2026, 9, 23)

    def __init__(self, db: Session):
        self.db = db
        self._load_people()

    def _load_people(self) -> None:
        """Cache known people from the database for entity resolution."""
        self.people = self.db.query(Person).all()
        self.arjun = next(
            (p for p in self.people if "arjun" in p.name.lower()),
            None,
        )

    def resolve_person(self, query: str) -> Optional[Person]:
        """Match mentioned names in the query against known Person records."""
        q_lower = query.lower()
        for person in self.people:
            # Check first name or full name with word boundaries
            first_name = person.name.split()[0].lower()
            if re.search(rf"\b{re.escape(first_name)}\b", q_lower):
                return person
            if re.search(rf"\b{re.escape(person.name.lower())}\b", q_lower):
                return person
        return None

    def parse(self, query: str, as_of_date: Optional[date] = None) -> ParsedQueryIntent:
        """Analyze query string and return structured intent and criteria."""
        ref_date = as_of_date or self.DEFAULT_DATE
        q_clean = query.strip()
        q_lower = q_clean.lower()

        target_person = self.resolve_person(query)
        arjun_id = self.arjun.id if self.arjun else None

        # 1. Intent: PROMISES_MADE
        # Patterns: "what did I promise...", "what have I promised...", "what do I owe...", "what did I tell X I'd do"
        if re.search(r"\b(?:promise|promised|owe|told\s+\w+\s+i['’]d)\b", q_lower):
            recipient_match = re.search(r"\b(?:promise|promised|owe|to)\s+([A-Za-z]+)\b", q_lower)
            specified_target = None
            if recipient_match:
                candidate_word = recipient_match.group(1)
                if candidate_word not in {"to", "anyone", "someone", "all", "my", "our", "the", "a"}:
                    specified_target = candidate_word

            if target_person and target_person.id != arjun_id:
                counterpart_id = target_person.id
            elif specified_target and not target_person:
                # User asked about a specific unknown person
                counterpart_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            else:
                counterpart_id = None

            criteria = CommitmentFilterCriteria(
                owner_id=arjun_id,
                counterpart_id=counterpart_id,
                ownership_type=OwnershipType.ARJUN,
                as_of_date=ref_date,
            )
            return ParsedQueryIntent(
                raw_query=q_clean,
                intent_type="PROMISES_MADE",
                as_of_date=ref_date,
                criteria=criteria,
                target_person=target_person,
                target_person_role="counterpart",
            )

        # 2. Intent: WAITING_ON
        # Patterns: "what am I waiting on...", "what is waiting on...", "who am I waiting on...", "waiting on Neha"
        if re.search(r"\b(?:waiting\s+on|waiting\s+for|expecting\s+from)\b", q_lower):
            waiting_match = re.search(r"\b(?:waiting\s+(?:on|for)|expecting\s+from)\s+([A-Za-z]+)\b", q_lower)
            specified_target = None
            if waiting_match:
                candidate_word = waiting_match.group(1)
                if candidate_word not in {"anyone", "someone", "all", "my", "our", "the", "a"}:
                    specified_target = candidate_word

            if target_person and target_person.id != arjun_id:
                owner_id = target_person.id
            elif specified_target and not target_person:
                owner_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            else:
                owner_id = None

            criteria = CommitmentFilterCriteria(
                counterpart_id=arjun_id,
                owner_id=owner_id,
                ownership_type=OwnershipType.OTHER_PERSON,
                status=CommitmentStatus.OPEN,
                as_of_date=ref_date,
            )
            return ParsedQueryIntent(
                raw_query=q_clean,
                intent_type="WAITING_ON",
                as_of_date=ref_date,
                criteria=criteria,
                target_person=target_person,
                target_person_role="owner",
            )

        # 3. Intent: OVERDUE
        # Patterns: "what's overdue", "what is overdue", "past due", "missed deadline"
        if re.search(r"\b(?:overdue|past\s+due|missed)\b", q_lower):
            criteria = CommitmentFilterCriteria(
                status=CommitmentStatus.OPEN,
                is_overdue=True,
                as_of_date=ref_date,
            )
            return ParsedQueryIntent(
                raw_query=q_clean,
                intent_type="OVERDUE",
                as_of_date=ref_date,
                criteria=criteria,
            )

        # 4. Intent: UNCLEAR / UNOWNED
        # Patterns: "what is unclear", "unowned", "unassigned", "who owns", "ownership"
        if re.search(r"\b(?:unclear|unowned|unassigned|who\s+owns|ownership|no\s+owner)\b", q_lower):
            criteria = CommitmentFilterCriteria(
                ownership_type=OwnershipType.UNCLEAR,
                status=CommitmentStatus.OPEN,
                as_of_date=ref_date,
            )
            return ParsedQueryIntent(
                raw_query=q_clean,
                intent_type="UNCLEAR_OWNERSHIP",
                as_of_date=ref_date,
                criteria=criteria,
            )

        # 5. Intent: ACTIONS_TODAY
        # Patterns: "what needs action today", "what should I do today", "what's on my plate today", "today's priorities"
        if re.search(r"\b(?:action\s+today|today|due\s+today|my\s+actions|on\s+my\s+plate)\b", q_lower):
            # Look for Arjun's active open commitments due today or overdue
            criteria = CommitmentFilterCriteria(
                owner_id=arjun_id,
                status=CommitmentStatus.OPEN,
                as_of_date=ref_date,
            )
            return ParsedQueryIntent(
                raw_query=q_clean,
                intent_type="ACTIONS_TODAY",
                as_of_date=ref_date,
                criteria=criteria,
            )

        # 6. Intent: PERSON_INVOLVED
        # Patterns: "commitments involving Raghav", "what's going on with Neha"
        if target_person and target_person.id != arjun_id:
            criteria = CommitmentFilterCriteria(
                involved_person_id=target_person.id,
                as_of_date=ref_date,
            )
            return ParsedQueryIntent(
                raw_query=q_clean,
                intent_type="PERSON_INVOLVED",
                as_of_date=ref_date,
                criteria=criteria,
                target_person=target_person,
                target_person_role="involved",
            )

        # 7. Fallback: GENERAL keyword search
        # Extract meaningful search terms (strip common stopwords)
        stopwords = {"what", "are", "is", "the", "my", "our", "all", "commitments", "tasks", "action", "items", "show", "me", "list"}
        tokens = [w for w in re.findall(r"\b\w+\b", q_lower) if w not in stopwords]
        search_query = " ".join(tokens) if tokens else None

        criteria = CommitmentFilterCriteria(
            search_query=search_query,
            as_of_date=ref_date,
        )
        return ParsedQueryIntent(
            raw_query=q_clean,
            intent_type="GENERAL_INQUIRY",
            as_of_date=ref_date,
            criteria=criteria,
        )
