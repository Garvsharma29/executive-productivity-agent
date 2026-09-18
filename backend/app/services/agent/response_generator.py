"""Grounded Response Generator — produces verifiable, citation-backed answers."""

from __future__ import annotations

from datetime import date
from typing import Optional

from app.models.commitment import Commitment
from app.models.enums import CommitmentStatus, OwnershipType
from app.services.agent.query_parser import ParsedQueryIntent


class ResponseGenerator:
    """Deterministic, factual response generator strictly grounded in retrieved commitments."""

    @staticmethod
    def generate(
        intent: ParsedQueryIntent,
        commitments: list[Commitment],
        as_of_date: date,
    ) -> str:
        """Synthesize natural-language answer without inventing facts."""
        if not commitments:
            if intent.intent_type == "PROMISES_MADE" and intent.target_person:
                return (
                    f"You have no recorded commitments made to {intent.target_person.name} "
                    f"as of {as_of_date.strftime('%A, %d %B %Y')}."
                )
            elif intent.intent_type == "OVERDUE":
                return (
                    f"Great news — you have no overdue commitments as of "
                    f"{as_of_date.strftime('%A, %d %B %Y')}."
                )
            elif intent.intent_type == "UNCLEAR_OWNERSHIP":
                return (
                    f"There are no commitments with unclear ownership flagged as of "
                    f"{as_of_date.strftime('%A, %d %B %Y')}."
                )
            return (
                f"No commitments were found matching your inquiry as of "
                f"{as_of_date.strftime('%A, %d %B %Y')}."
            )

        # 1. Intent: PROMISES_MADE
        if intent.intent_type == "PROMISES_MADE":
            target_name = intent.target_person.name if intent.target_person else "your colleagues"
            lines = [f"Here {'is the commitment' if len(commitments) == 1 else 'are the commitments'} you made to {target_name}:"]
            for i, c in enumerate(commitments, 1):
                dl_str = c.deadline_raw or (c.deadline_date.strftime('%Y-%m-%d') if c.deadline_date else "No deadline set")
                status_str = "OPEN" if c.status == CommitmentStatus.OPEN else "COMPLETED"
                overdue_str = " (OVERDUE)" if c.is_overdue(as_of_date) else ""
                lines.append(
                    f"{i}. \"{c.action}\" — Deadline: {dl_str} | Status: {status_str}{overdue_str}."
                )
            return "\n".join(lines)

        # 2. Intent: WAITING_ON
        if intent.intent_type == "WAITING_ON":
            lines = ["Here are the commitments involving colleagues you are waiting on:"]
            for i, c in enumerate(commitments, 1):
                owner_name = c.owner.name if c.owner else "Unassigned"
                dl_str = c.deadline_raw or (c.deadline_date.strftime('%Y-%m-%d') if c.deadline_date else "No deadline set")
                lines.append(
                    f"{i}. \"{c.action}\" (Owner: {owner_name}) — Deadline: {dl_str} [Status: {c.status.value}]."
                )
            return "\n".join(lines)

        # 3. Intent: ACTIONS_TODAY
        if intent.intent_type == "ACTIONS_TODAY":
            # Filter active actions relevant to today
            lines = [f"Here are your active commitments requiring action as of {as_of_date.strftime('%A, %d %B %Y')}:"]
            for i, c in enumerate(commitments, 1):
                dl_str = c.deadline_raw or (c.deadline_date.strftime('%Y-%m-%d') if c.deadline_date else "No deadline set")
                overdue_str = " [OVERDUE]" if c.is_overdue(as_of_date) else ""
                lines.append(
                    f"{i}. \"{c.action}\" — Deadline: {dl_str}{overdue_str} (Status: {c.status.value})."
                )
            return "\n".join(lines)

        # 4. Intent: OVERDUE
        if intent.intent_type == "OVERDUE":
            lines = [f"Attention required: {len(commitments)} commitment{' is' if len(commitments) == 1 else 's are'} overdue as of {as_of_date.strftime('%A, %d %B %Y')}:"]
            for i, c in enumerate(commitments, 1):
                dl_str = c.deadline_raw or (c.deadline_date.strftime('%Y-%m-%d') if c.deadline_date else "unknown")
                owner_str = c.owner.name if c.owner else "Unassigned"
                lines.append(
                    f"{i}. \"{c.action}\" (Owner: {owner_str}) — Was due: {dl_str}."
                )
            return "\n".join(lines)

        # 5. Intent: UNCLEAR_OWNERSHIP
        if intent.intent_type == "UNCLEAR_OWNERSHIP":
            lines = ["Here are the commitments with UNCLEAR or disputed ownership requiring executive alignment:"]
            for i, c in enumerate(commitments, 1):
                dl_str = c.deadline_raw or (c.deadline_date.strftime('%Y-%m-%d') if c.deadline_date else "No deadline set")
                lines.append(
                    f"{i}. \"{c.action}\" — Deadline: {dl_str} | Ownership: UNCLEAR (Unassigned). Needs an owner assigned."
                )
            return "\n".join(lines)

        # 6. Default / General inquiry
        lines = [f"Found {len(commitments)} relevant commitment{'s' if len(commitments) != 1 else ''}:"]
        for i, c in enumerate(commitments, 1):
            owner_str = c.owner.name if c.owner else ("UNCLEAR" if c.ownership_type == OwnershipType.UNCLEAR else "Unknown")
            dl_str = c.deadline_raw or (c.deadline_date.strftime('%Y-%m-%d') if c.deadline_date else "No deadline")
            lines.append(
                f"{i}. \"{c.action}\" (Owner: {owner_str}) — Deadline: {dl_str} [Status: {c.status.value}]."
            )
        return "\n".join(lines)
