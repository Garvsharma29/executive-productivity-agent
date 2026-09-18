"""Deadline Resolver — anchors temporal expressions to calendar dates and precision.

Exercise reference week:
Monday 21 September 2026 – Friday 25 September 2026.

Rules:
- Preserve raw deadline text verbatim.
- Distinguish EXACT (explicit time stated) from APPROXIMATE (e.g. morning, EOD).
- Do not invent arbitrary clock times for approximate deadlines.
- Deterministic overdue check relative to an explicit as_of_date.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

from app.models.enums import CommitmentStatus, DeadlinePrecision

DATA_PACK_YEAR = 2026
DATA_PACK_MONTH = 9

_DAY_MAP = {
    "mon": 21,
    "monday": 21,
    "tue": 22,
    "tuesday": 22,
    "wed": 23,
    "wednesday": 23,
    "thu": 24,
    "thursday": 24,
    "fri": 25,
    "friday": 25,
}


@dataclass
class ResolvedDeadline:
    deadline_date: Optional[date]
    deadline_time: Optional[time]
    precision: DeadlinePrecision
    deadline_raw: Optional[str]


class DeadlineResolver:
    """Resolves natural language deadline expressions relative to source context."""

    @classmethod
    def resolve_deadline(
        cls,
        deadline_raw: Optional[str],
        source_occurred_at: Optional[datetime] = None,
        as_of_date: Optional[date] = None,
    ) -> ResolvedDeadline:
        """Resolve a raw deadline string into structured date, time, and precision."""
        if not deadline_raw or not deadline_raw.strip():
            return ResolvedDeadline(
                deadline_date=None,
                deadline_time=None,
                precision=DeadlinePrecision.NONE,
                deadline_raw=None,
            )

        raw = deadline_raw.strip()
        raw_lower = raw.lower()

        base_date = as_of_date or (
            source_occurred_at.date()
            if source_occurred_at
            else date(DATA_PACK_YEAR, DATA_PACK_MONTH, 21)
        )

        # 1. Check for explicit time (e.g. "9:30 AM", "3:00 PM")
        time_match = re.search(r"(\d{1,2}:\d{2})\s*(AM|PM)?", raw, re.IGNORECASE)
        resolved_time: Optional[time] = None
        if time_match:
            time_str = time_match.group(1)
            ampm = time_match.group(2)
            try:
                if ampm:
                    dt = datetime.strptime(f"{time_str} {ampm.upper()}", "%I:%M %p")
                else:
                    dt = datetime.strptime(time_str, "%H:%M")
                resolved_time = dt.time()
            except ValueError:
                pass

        # 2. Check for explicit day mentions ("Wednesday", "Thursday 9:30 AM", "Friday, 25 September")
        target_day: Optional[int] = None
        for day_name, dom in _DAY_MAP.items():
            if re.search(rf"\b{day_name}\b", raw_lower):
                target_day = dom
                break

        # Check explicit day of month digits ("25 September", "Sep 25", "25th")
        if target_day is None:
            dom_match = re.search(r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s*(?:Sep|September)?\b", raw_lower)
            if dom_match:
                d = int(dom_match.group(1))
                if 21 <= d <= 25:
                    target_day = d

        # 3. Handle relative terms ("today", "tomorrow", "this week")
        if target_day is None:
            if "today" in raw_lower or "this morning" in raw_lower or "tonight" in raw_lower:
                target_day = base_date.day
            elif "tomorrow" in raw_lower:
                tomorrow = base_date + timedelta(days=1)
                target_day = tomorrow.day
            elif "this week" in raw_lower or "end of week" in raw_lower:
                target_day = 25  # Friday of the exercise week

        resolved_date: Optional[date] = None
        if target_day is not None:
            resolved_date = date(DATA_PACK_YEAR, DATA_PACK_MONTH, target_day)

        # 4. Determine precision
        if resolved_time is not None:
            precision = DeadlinePrecision.EXACT
        elif resolved_date is not None:
            precision = DeadlinePrecision.APPROXIMATE
        else:
            precision = DeadlinePrecision.RELATIVE_UNRESOLVED

        return ResolvedDeadline(
            deadline_date=resolved_date,
            deadline_time=resolved_time,
            precision=precision,
            deadline_raw=raw,
        )

    @classmethod
    def is_overdue(
        cls,
        deadline_date: Optional[date],
        status: CommitmentStatus,
        as_of_date: date,
    ) -> bool:
        """Deterministic check for overdue commitments."""
        if deadline_date is None:
            return False
        if status == CommitmentStatus.COMPLETED:
            return False
        return deadline_date < as_of_date
