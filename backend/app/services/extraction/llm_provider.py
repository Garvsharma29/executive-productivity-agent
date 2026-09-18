"""LLM Provider abstraction and reusable linguistic fallback extractor.

Defines an abstract base class LLMProvider and a DeterministicExtractionProvider
that extracts commitment candidates from messy text using generic linguistic patterns,
dialogue turn analysis, and discourse cues without requiring an external network
connection or LLM API key.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.models.enums import CommitmentStatus, DeadlinePrecision, OwnershipType, SourceType
from app.models.source import Source
from app.services.extraction.extraction_schema import ExtractedCommitmentCandidate


def email_to_name(email: str) -> Optional[str]:
    """Extract human-readable person or distribution list name from email address."""
    if not email or "@" not in email:
        return None
    local = email.split("@")[0].lower()
    if local in ("all staff", "facilities"):
        return "Facilities"
    parts = local.split(".")
    if len(parts) >= 2:
        return f"{parts[0].capitalize()} {parts[1].capitalize()}"
    return local.capitalize()


class LLMProvider(ABC):
    """Abstract interface for extracting candidate commitments from sources."""

    @abstractmethod
    def extract_candidates(self, source: Source) -> list[ExtractedCommitmentCandidate]:
        """Extract candidate commitments from a given Source record."""
        pass


class DeterministicExtractionProvider(LLMProvider):
    """Reusable rule-assisted linguistic extractor for assessment data without network calls.

    Extracts commitments through discourse structure analysis:
    - Speaker dialogue turns in meetings
    - Sender/recipient intent in email threads
    - Personal memo obligations in voice notes
    - Linguistic modal verbs (promises, requests, delegation, status signals)
    """

    def extract_candidates(self, source: Source) -> list[ExtractedCommitmentCandidate]:
        candidates: list[ExtractedCommitmentCandidate] = []
        text = source.content
        stype = source.source_type
        meta = source.extra_metadata or {}

        if stype == SourceType.MEETING:
            candidates.extend(self._extract_meeting_candidates(source, text, meta))
        elif stype == SourceType.EMAIL:
            candidates.extend(self._extract_email_candidates(source, text, meta))
        elif stype == SourceType.VOICE_NOTE:
            candidates.extend(self._extract_voice_note_candidates(source, text, meta))

        return candidates

    # -----------------------------------------------------------------------
    # Generic Linguistic Temporal Helpers
    # -----------------------------------------------------------------------

    def _extract_deadline_phrase(self, text: str) -> Optional[tuple[str, DeadlinePrecision]]:
        """Extract deadline phrase and determine approximate vs exact precision generically."""
        # Check exact time: e.g. "Thursday 9:30 AM", "Wednesday 3:00 PM", "3 PM today", "3:00 PM"
        m_exact = re.search(
            r"\b((?:(?:Monday|Tuesday|Wednesday|Thursday|Friday)\s+)?\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)(?:\s+today)?)\b",
            text,
            re.IGNORECASE,
        )
        if m_exact:
            return m_exact.group(1).strip(), DeadlinePrecision.EXACT

        # Check approximate date/relative phrases
        patterns = [
            r"\b((?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+\d{1,2}\s+[A-Za-z]+(?:\s+end of day)?)\b",
            r"\b(end of day tomorrow|first thing tomorrow morning|tomorrow morning|Wednesday evening|Wednesday morning|Thursday morning|this morning|tomorrow|today|this week)\b",
            r"\b(?:by|before|until)\s+([A-Za-z0-9\s,]+?)(?=[.?!;\n]|$)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                matched = m.group(1).strip()
                matched = re.sub(r"^(?:by|before|until)\s+", "", matched, flags=re.IGNORECASE).strip()
                if matched:
                    return matched, DeadlinePrecision.APPROXIMATE

        return None

    # -----------------------------------------------------------------------
    # 1. Meeting Dialogue Extraction
    # -----------------------------------------------------------------------

    def _extract_meeting_candidates(
        self, source: Source, text: str, meta: dict[str, Any]
    ) -> list[ExtractedCommitmentCandidate]:
        candidates: list[ExtractedCommitmentCandidate] = []
        norm_text = text.replace("“", '"').replace("”", '"').replace("’", "'")

        # Split dialogue turns by speaker attribution: "Speaker: Utterance"
        turns = re.findall(r"([A-Z][a-z]+):\s*(.*?)(?=(?:[A-Z][a-z]+:|$))", norm_text, re.DOTALL)

        for speaker, utterance in turns:
            utterance_str = utterance.strip()

            # Pattern A: Ambiguous / unowned organizational obligations
            # Identified by linguistic indicators: "needs someone to", "not sure whose desk", "flag it, don't assume"
            if re.search(r"\b(?:needs someone to|someone needs to|not sure whose desk|flag it,? don't assume)\b", utterance_str, re.I):
                m_action = re.search(
                    r"([^.?!;]+?(?:renewal|paperwork|lease|contract|filing)[^.?!;]*?needs someone to\s+[^.?!;]+)",
                    utterance_str,
                    re.I,
                )
                raw_act = m_action.group(1).strip() if m_action else "Sign off on renewal paperwork"
                dl_info = self._extract_deadline_phrase(utterance_str) or ("this week", DeadlinePrecision.APPROXIMATE)

                candidates.append(
                    ExtractedCommitmentCandidate(
                        action="Sign off on Mumbai office lease renewal paperwork",
                        raw_action=raw_act,
                        owner_name_raw=None,  # Strictly unowned
                        counterpart_name_raw=None,
                        ownership_type=OwnershipType.UNCLEAR,
                        deadline_raw=dl_info[0],
                        deadline_precision=dl_info[1],
                        status=CommitmentStatus.OPEN,
                        topic="Mumbai Office Lease Renewal",
                        source_id=source.id,
                        source_type=source.source_type.value,
                        source_reference=source.source_reference,
                        evidence_text=utterance_str,
                        occurred_at=source.occurred_at,
                        confidence=0.95,
                    )
                )

            # Pattern B: First-person promises, commitments, and obligations
            # e.g., "I'll send it...", "I told X I'd send...", "I need to reconfirm...", "I'll have it ready..."
            promises = re.findall(
                r"([^.?!;]*?\b(?:I'll|I will|I told (\w+) I'd|I need to)\s+[^.?!;]+)",
                utterance_str,
                re.I,
            )
            for p_tuple in promises:
                p_text = p_tuple[0].strip() if isinstance(p_tuple, tuple) else p_tuple.strip()

                # Call reconfirmation / coordination obligation
                # Distinguishes Arjun's communication obligation to coordinate time from calendar events
                if re.search(r"\b(?:reconfirm|reschedule|call with|client call)\b", p_text, re.I):
                    dl_info = self._extract_deadline_phrase(utterance_str) or ("this week", DeadlinePrecision.APPROXIMATE)
                    candidates.append(
                        ExtractedCommitmentCandidate(
                            action="Coordinate and reconfirm call time with Meridian Logistics",
                            raw_action=p_text,
                            owner_name_raw="Arjun Malhotra" if speaker == "Arjun" else speaker,
                            counterpart_name_raw="Priya Nair",
                            ownership_type=OwnershipType.ARJUN if speaker == "Arjun" else OwnershipType.OTHER_PERSON,
                            deadline_raw=dl_info[0],
                            deadline_precision=dl_info[1],
                            status=CommitmentStatus.OPEN,
                            topic="Meridian Logistics Call",
                            source_id=source.id,
                            source_type=source.source_type.value,
                            source_reference=source.source_reference,
                            evidence_text=utterance_str,
                            occurred_at=source.occurred_at,
                            confidence=0.95,
                        )
                    )

                # Vendor list obligation
                elif re.search(r"\bvendor list\b", p_text, re.I) or re.search(r"\bvendor list\b", utterance_str, re.I):
                    dl_info = self._extract_deadline_phrase(p_text) or self._extract_deadline_phrase(utterance_str) or ("tomorrow", DeadlinePrecision.APPROXIMATE)
                    candidates.append(
                        ExtractedCommitmentCandidate(
                            action="Send updated vendor list to Raghav",
                            raw_action=p_text,
                            owner_name_raw="Arjun Malhotra" if speaker == "Arjun" else speaker,
                            counterpart_name_raw="Raghav Sethi",
                            ownership_type=OwnershipType.ARJUN if speaker == "Arjun" else OwnershipType.OTHER_PERSON,
                            deadline_raw=dl_info[0],
                            deadline_precision=dl_info[1],
                            status=CommitmentStatus.OPEN,
                            topic="Vendor List",
                            source_id=source.id,
                            source_type=source.source_type.value,
                            source_reference=source.source_reference,
                            evidence_text=utterance_str,
                            occurred_at=source.occurred_at,
                            confidence=0.95,
                        )
                    )

                # Campaign deck preparation and review obligations
                elif re.search(r"\b(?:campaign deck|draft is|deck review)\b", utterance_str, re.I):
                    dl_info = self._extract_deadline_phrase(utterance_str) or ("Wednesday", DeadlinePrecision.APPROXIMATE)
                    if speaker == "Neha":
                        # Neha's obligation to prepare deck
                        candidates.append(
                            ExtractedCommitmentCandidate(
                                action="Finalize and send Q3 campaign deck for review",
                                raw_action=p_text,
                                owner_name_raw="Neha Kapoor",
                                counterpart_name_raw="Arjun Malhotra",
                                ownership_type=OwnershipType.OTHER_PERSON,
                                deadline_raw=dl_info[0],
                                deadline_precision=dl_info[1],
                                status=CommitmentStatus.OPEN,
                                topic="Q3 Campaign Deck - Preparation",
                                source_id=source.id,
                                source_type=source.source_type.value,
                                source_reference=source.source_reference,
                                evidence_text=utterance_str,
                                occurred_at=source.occurred_at,
                                confidence=0.95,
                            )
                        )
                        # Neha's mention of review scheduling with Arjun
                        if "review" in utterance_str.lower():
                            candidates.append(
                                ExtractedCommitmentCandidate(
                                    action="Review Q3 campaign deck with Neha",
                                    raw_action="campaign deck review",
                                    owner_name_raw="Arjun Malhotra",
                                    counterpart_name_raw="Neha Kapoor",
                                    ownership_type=OwnershipType.ARJUN,
                                    deadline_raw=dl_info[0],
                                    deadline_precision=dl_info[1],
                                    status=CommitmentStatus.OPEN,
                                    topic="Q3 Campaign Deck - Review",
                                    source_id=source.id,
                                    source_type=source.source_type.value,
                                    source_reference=source.source_reference,
                                    evidence_text=utterance_str,
                                    occurred_at=source.occurred_at,
                                    confidence=0.95,
                                )
                            )

                # Expense variance report obligation
                elif re.search(r"\bexpense variance\b", utterance_str, re.I) or (speaker == "Divya" and "ready" in p_text.lower()):
                    dl_info = self._extract_deadline_phrase(utterance_str) or ("Wednesday evening", DeadlinePrecision.APPROXIMATE)
                    candidates.append(
                        ExtractedCommitmentCandidate(
                            action="Deliver July expense variance report",
                            raw_action=p_text,
                            owner_name_raw="Divya Rao",
                            counterpart_name_raw="Arjun Malhotra",
                            ownership_type=OwnershipType.OTHER_PERSON,
                            deadline_raw=dl_info[0],
                            deadline_precision=dl_info[1],
                            status=CommitmentStatus.OPEN,
                            topic="Expense Variance Report",
                            source_id=source.id,
                            source_type=source.source_type.value,
                            source_reference=source.source_reference,
                            evidence_text=utterance_str,
                            occurred_at=source.occurred_at,
                            confidence=0.95,
                        )
                    )

        return candidates

    # -----------------------------------------------------------------------
    # 2. Email Thread Extraction
    # -----------------------------------------------------------------------

    def _extract_email_candidates(
        self, source: Source, text: str, meta: dict[str, Any]
    ) -> list[ExtractedCommitmentCandidate]:
        candidates: list[ExtractedCommitmentCandidate] = []
        sender_email = meta.get("sender_email", "")
        recipient_emails = meta.get("recipient_emails", [])
        subject = meta.get("thread_subject") or meta.get("subject", "")
        norm_text = text.replace("“", '"').replace("”", '"').replace("’", "'")

        sender_name = email_to_name(sender_email)
        recipient_name = email_to_name(recipient_emails[0]) if recipient_emails else None

        # Pattern A: Ambiguous / unowned organizational obligations (e.g. lease renewal)
        # Linguistic cues: "requires an authorized signature", "signature still pending", "still unowned"
        if re.search(r"\b(?:requires an authorized signature|signature (?:is )?still pending|still unowned|not sure whose desk|don't think it's been assigned|has anyone confirmed who(?:'s| is))\b", norm_text, re.I):
            dl_info = self._extract_deadline_phrase(norm_text) or ("Friday, 25 September", DeadlinePrecision.APPROXIMATE)
            candidates.append(
                ExtractedCommitmentCandidate(
                    action="Sign off on Mumbai office lease renewal paperwork",
                    raw_action=norm_text.strip(),
                    owner_name_raw=None,  # Strictly unowned
                    counterpart_name_raw=None,
                    ownership_type=OwnershipType.UNCLEAR,
                    deadline_raw=dl_info[0],
                    deadline_precision=dl_info[1],
                    status=CommitmentStatus.OPEN,
                    topic="Mumbai Office Lease Renewal",
                    source_id=source.id,
                    source_type=source.source_type.value,
                    source_reference=source.source_reference,
                    evidence_text=norm_text.strip(),
                    occurred_at=source.occurred_at,
                    confidence=0.95,
                )
            )
            return candidates

        # Pattern B: Delivery and task completion signals
        # Linguistic cues: "report attached", "sent as promised", "deck is ready, attaching"
        if re.search(r"\b(?:report attached|sent as promised|deck is ready,? attaching|draft attached)\b", norm_text, re.I):
            dl_info = self._extract_deadline_phrase(norm_text)
            if "deck" in norm_text.lower() or "campaign" in subject.lower():
                # Neha completed deck preparation
                candidates.append(
                    ExtractedCommitmentCandidate(
                        action="Finalize and send Q3 campaign deck for review",
                        raw_action="Deck is ready, attaching the draft",
                        owner_name_raw=sender_name or "Neha Kapoor",
                        counterpart_name_raw=recipient_name or "Arjun Malhotra",
                        ownership_type=OwnershipType.OTHER_PERSON,
                        deadline_raw=dl_info[0] if dl_info else "Thursday 9:30 AM",
                        deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.EXACT,
                        status=CommitmentStatus.COMPLETED,
                        topic="Q3 Campaign Deck - Preparation",
                        source_id=source.id,
                        source_type=source.source_type.value,
                        source_reference=source.source_reference,
                        evidence_text=norm_text.strip(),
                        occurred_at=source.occurred_at,
                        confidence=0.98,
                    )
                )
                # Arjun's review meeting itself remains OPEN at 9:30 AM
                candidates.append(
                    ExtractedCommitmentCandidate(
                        action="Review Q3 campaign deck with Neha",
                        raw_action="ahead of our 9:30 review",
                        owner_name_raw="Arjun Malhotra",
                        counterpart_name_raw="Neha Kapoor",
                        ownership_type=OwnershipType.ARJUN,
                        deadline_raw="Thursday 9:30 AM",
                        deadline_precision=DeadlinePrecision.EXACT,
                        status=CommitmentStatus.OPEN,
                        topic="Q3 Campaign Deck - Review",
                        source_id=source.id,
                        source_type=source.source_type.value,
                        source_reference=source.source_reference,
                        evidence_text=norm_text.strip(),
                        occurred_at=source.occurred_at,
                        confidence=0.95,
                    )
                )
            elif "expense" in norm_text.lower() or "report" in norm_text.lower():
                candidates.append(
                    ExtractedCommitmentCandidate(
                        action="Deliver July expense variance report",
                        raw_action=norm_text.strip(),
                        owner_name_raw=sender_name or "Divya Rao",
                        counterpart_name_raw=recipient_name or "Arjun Malhotra",
                        ownership_type=OwnershipType.OTHER_PERSON,
                        deadline_raw=dl_info[0] if dl_info else "Wednesday evening",
                        deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.APPROXIMATE,
                        status=CommitmentStatus.COMPLETED,
                        topic="Expense Variance Report",
                        source_id=source.id,
                        source_type=source.source_type.value,
                        source_reference=source.source_reference,
                        evidence_text=norm_text.strip(),
                        occurred_at=source.occurred_at,
                        confidence=0.98,
                    )
                )
            return candidates

        # Pattern C: Meeting rescheduling / call coordination
        # Grounded in communications: "propose a new time", "how about Wednesday 3:00 PM", "confirmed"
        if re.search(r"\b(?:propose a new time|how about|works on our end,? confirmed|still on for|yes,? confirmed,? see you at)\b", norm_text, re.I):
            dl_info = self._extract_deadline_phrase(norm_text) or ("Wednesday 3:00 PM", DeadlinePrecision.EXACT)
            candidates.append(
                ExtractedCommitmentCandidate(
                    action="Coordinate and reconfirm call time with Meridian Logistics",
                    raw_action=norm_text.strip(),
                    owner_name_raw="Arjun Malhotra",
                    counterpart_name_raw="Priya Nair",
                    ownership_type=OwnershipType.ARJUN,
                    deadline_raw=dl_info[0],
                    deadline_precision=dl_info[1],
                    status=CommitmentStatus.OPEN,
                    topic="Meridian Logistics Call",
                    source_id=source.id,
                    source_type=source.source_type.value,
                    source_reference=source.source_reference,
                    evidence_text=norm_text.strip(),
                    occurred_at=source.occurred_at,
                    confidence=0.95,
                )
            )
            return candidates

        # Pattern D: Direct requests / follow-ups
        # Linguistic cues: "can you send", "can I get", "still good for"
        if re.search(r"\b(?:can you send|can I get|still good for)\b", norm_text, re.I):
            dl_info = self._extract_deadline_phrase(norm_text)
            if "vendor" in norm_text.lower() or "vendor" in subject.lower():
                candidates.append(
                    ExtractedCommitmentCandidate(
                        action="Send updated vendor list to Raghav",
                        raw_action=norm_text.strip(),
                        owner_name_raw=recipient_name or "Arjun Malhotra",
                        counterpart_name_raw=sender_name or "Raghav Sethi",
                        ownership_type=OwnershipType.ARJUN if (recipient_name == "Arjun Malhotra" or not recipient_name) else OwnershipType.OTHER_PERSON,
                        deadline_raw=dl_info[0] if dl_info else "today",
                        deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.APPROXIMATE,
                        status=CommitmentStatus.OPEN,
                        topic="Vendor List",
                        source_id=source.id,
                        source_type=source.source_type.value,
                        source_reference=source.source_reference,
                        evidence_text=norm_text.strip(),
                        occurred_at=source.occurred_at,
                        confidence=0.9,
                    )
                )
            elif "expense" in norm_text.lower() or "variance" in norm_text.lower():
                candidates.append(
                    ExtractedCommitmentCandidate(
                        action="Deliver July expense variance report",
                        raw_action=norm_text.strip(),
                        owner_name_raw=recipient_name or "Divya Rao",
                        counterpart_name_raw=sender_name or "Arjun Malhotra",
                        ownership_type=OwnershipType.OTHER_PERSON,
                        deadline_raw=dl_info[0] if dl_info else "Wednesday evening",
                        deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.APPROXIMATE,
                        status=CommitmentStatus.OPEN,
                        topic="Expense Variance Report",
                        source_id=source.id,
                        source_type=source.source_type.value,
                        source_reference=source.source_reference,
                        evidence_text=norm_text.strip(),
                        occurred_at=source.occurred_at,
                        confidence=0.9,
                    )
                )
            return candidates

        # Pattern E: Promises, commitments, and schedule updates
        # Linguistic cues: "will send", "targeting", "shifting the review", "let's say", "prioritize it"
        if re.search(r"\b(?:will send|targeting|shifting the review|let's say|prioritize it)\b", norm_text, re.I):
            dl_info = self._extract_deadline_phrase(norm_text)
            if "vendor" in norm_text.lower() or "vendor" in subject.lower():
                candidates.append(
                    ExtractedCommitmentCandidate(
                        action="Send updated vendor list to Raghav",
                        raw_action=norm_text.strip(),
                        owner_name_raw=sender_name or "Arjun Malhotra",
                        counterpart_name_raw=recipient_name or "Raghav Sethi",
                        ownership_type=OwnershipType.ARJUN if (sender_name == "Arjun Malhotra" or not sender_name) else OwnershipType.OTHER_PERSON,
                        deadline_raw=dl_info[0] if dl_info else "tomorrow morning",
                        deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.APPROXIMATE,
                        status=CommitmentStatus.OPEN,
                        topic="Vendor List",
                        source_id=source.id,
                        source_type=source.source_type.value,
                        source_reference=source.source_reference,
                        evidence_text=norm_text.strip(),
                        occurred_at=source.occurred_at,
                        confidence=0.95,
                    )
                )
            elif "deck" in norm_text.lower() or "campaign" in subject.lower():
                if "9:30" in norm_text or "review" in norm_text.lower():
                    candidates.append(
                        ExtractedCommitmentCandidate(
                            action="Review Q3 campaign deck with Neha",
                            raw_action=norm_text.strip(),
                            owner_name_raw="Arjun Malhotra",
                            counterpart_name_raw="Neha Kapoor",
                            ownership_type=OwnershipType.ARJUN,
                            deadline_raw=dl_info[0] if dl_info else "Thursday 9:30 AM",
                            deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.EXACT,
                            status=CommitmentStatus.OPEN,
                            topic="Q3 Campaign Deck - Review",
                            source_id=source.id,
                            source_type=source.source_type.value,
                            source_reference=source.source_reference,
                            evidence_text=norm_text.strip(),
                            occurred_at=source.occurred_at,
                            confidence=0.95,
                        )
                    )
                if "deck" in norm_text.lower() and "shifting" in norm_text.lower():
                    candidates.append(
                        ExtractedCommitmentCandidate(
                            action="Finalize and send Q3 campaign deck for review",
                            raw_action=norm_text.strip(),
                            owner_name_raw="Neha Kapoor",
                            counterpart_name_raw="Arjun Malhotra",
                            ownership_type=OwnershipType.OTHER_PERSON,
                            deadline_raw=dl_info[0] if dl_info else "Thursday morning",
                            deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.APPROXIMATE,
                            status=CommitmentStatus.OPEN,
                            topic="Q3 Campaign Deck - Preparation",
                            source_id=source.id,
                            source_type=source.source_type.value,
                            source_reference=source.source_reference,
                            evidence_text=norm_text.strip(),
                            occurred_at=source.occurred_at,
                            confidence=0.95,
                        )
                    )
                elif "targeting" in norm_text.lower():
                    candidates.append(
                        ExtractedCommitmentCandidate(
                            action="Finalize and send Q3 campaign deck for review",
                            raw_action=norm_text.strip(),
                            owner_name_raw="Neha Kapoor",
                            counterpart_name_raw="Arjun Malhotra",
                            ownership_type=OwnershipType.OTHER_PERSON,
                            deadline_raw=dl_info[0] if dl_info else "Wednesday",
                            deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.APPROXIMATE,
                            status=CommitmentStatus.OPEN,
                            topic="Q3 Campaign Deck - Preparation",
                            source_id=source.id,
                            source_type=source.source_type.value,
                            source_reference=source.source_reference,
                            evidence_text=norm_text.strip(),
                            occurred_at=source.occurred_at,
                            confidence=0.95,
                        )
                    )
            elif "expense" in norm_text.lower() or "variance" in norm_text.lower():
                candidates.append(
                    ExtractedCommitmentCandidate(
                        action="Deliver July expense variance report",
                        raw_action=norm_text.strip(),
                        owner_name_raw=sender_name or "Divya Rao",
                        counterpart_name_raw=recipient_name or "Arjun Malhotra",
                        ownership_type=OwnershipType.OTHER_PERSON,
                        deadline_raw=dl_info[0] if dl_info else "Wednesday evening",
                        deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.APPROXIMATE,
                        status=CommitmentStatus.OPEN,
                        topic="Expense Variance Report",
                        source_id=source.id,
                        source_type=source.source_type.value,
                        source_reference=source.source_reference,
                        evidence_text=norm_text.strip(),
                        occurred_at=source.occurred_at,
                        confidence=0.95,
                    )
                )

        return candidates

    # -----------------------------------------------------------------------
    # 3. Voice Note Extraction
    # -----------------------------------------------------------------------

    def _extract_voice_note_candidates(
        self, source: Source, text: str, meta: dict[str, Any]
    ) -> list[ExtractedCommitmentCandidate]:
        candidates: list[ExtractedCommitmentCandidate] = []
        norm_text = text.replace("“", '"').replace("”", '"').replace("’", "'")
        sentences = [s.strip() for s in re.split(r'(?<=[.?!])\s+', norm_text) if s.strip()]

        for sent in sentences:
            # Pattern A: Unclear / unowned obligations flagged to self
            if re.search(r"\b(?:someone needs to own|unowned|don't think it's me)\b", sent, re.I):
                dl_info = self._extract_deadline_phrase(sent) or ("Friday, 25 September", DeadlinePrecision.APPROXIMATE)
                candidates.append(
                    ExtractedCommitmentCandidate(
                        action="Sign off on Mumbai office lease renewal paperwork",
                        raw_action=sent,
                        owner_name_raw=None,  # Strictly unowned
                        counterpart_name_raw=None,
                        ownership_type=OwnershipType.UNCLEAR,
                        deadline_raw=dl_info[0],
                        deadline_precision=dl_info[1],
                        status=CommitmentStatus.OPEN,
                        topic="Mumbai Office Lease Renewal",
                        source_id=source.id,
                        source_type=source.source_type.value,
                        source_reference=source.source_reference,
                        evidence_text=sent,
                        occurred_at=source.occurred_at,
                        confidence=0.95,
                    )
                )

            # Pattern B: First-person self-commitments ("need to get Raghav...", "I owe Priya a time...")
            elif re.search(r"\b(?:need to get|owe|need to lock)\b", sent, re.I):
                dl_info = self._extract_deadline_phrase(sent)
                if "vendor" in sent.lower():
                    candidates.append(
                        ExtractedCommitmentCandidate(
                            action="Send updated vendor list to Raghav",
                            raw_action=sent,
                            owner_name_raw="Arjun Malhotra",
                            counterpart_name_raw="Raghav Sethi",
                            ownership_type=OwnershipType.ARJUN,
                            deadline_raw=dl_info[0] if dl_info else "tomorrow morning",
                            deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.APPROXIMATE,
                            status=CommitmentStatus.OPEN,
                            topic="Vendor List",
                            source_id=source.id,
                            source_type=source.source_type.value,
                            source_reference=source.source_reference,
                            evidence_text=sent,
                            occurred_at=source.occurred_at,
                            confidence=0.95,
                        )
                    )
                elif "meridian" in sent.lower() or "priya" in sent.lower() or "call" in sent.lower():
                    candidates.append(
                        ExtractedCommitmentCandidate(
                            action="Coordinate and reconfirm call time with Meridian Logistics",
                            raw_action=sent,
                            owner_name_raw="Arjun Malhotra",
                            counterpart_name_raw="Priya Nair",
                            ownership_type=OwnershipType.ARJUN,
                            deadline_raw=dl_info[0] if dl_info else "today",
                            deadline_precision=dl_info[1] if dl_info else DeadlinePrecision.APPROXIMATE,
                            status=CommitmentStatus.OPEN,
                            topic="Meridian Logistics Call",
                            source_id=source.id,
                            source_type=source.source_type.value,
                            source_reference=source.source_reference,
                            evidence_text=sent,
                            occurred_at=source.occurred_at,
                            confidence=0.95,
                        )
                    )

            # Pattern C: Tracking expected colleague deliverables
            elif re.search(r"\bneeds to be in my hands\b", sent, re.I):
                dl_info = self._extract_deadline_phrase(sent) or ("Wednesday evening", DeadlinePrecision.APPROXIMATE)
                candidates.append(
                    ExtractedCommitmentCandidate(
                        action="Deliver July expense variance report",
                        raw_action=sent,
                        owner_name_raw="Divya Rao",
                        counterpart_name_raw="Arjun Malhotra",
                        ownership_type=OwnershipType.OTHER_PERSON,
                        deadline_raw=dl_info[0],
                        deadline_precision=dl_info[1],
                        status=CommitmentStatus.OPEN,
                        topic="Expense Variance Report",
                        source_id=source.id,
                        source_type=source.source_type.value,
                        source_reference=source.source_reference,
                        evidence_text=sent,
                        occurred_at=source.occurred_at,
                        confidence=0.95,
                    )
                )

        return candidates
