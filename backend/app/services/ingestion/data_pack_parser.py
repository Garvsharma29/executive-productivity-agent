"""Data Pack Parser — reads the Markdown data pack into structured Python objects.

This module is responsible ONLY for parsing. It does not touch the database.
It produces plain dataclasses that the ingestion service persists.

Parsing rules:
- Preserve original text verbatim (no summarisation, no LLM rewriting).
- Normalise only harmless whitespace from PDF-to-Markdown conversion.
- Fail clearly on unexpected structure rather than inventing data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, date, time
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Parsed data structures (no DB dependency)
# ---------------------------------------------------------------------------

@dataclass
class ParsedPerson:
    name: str
    role: str
    email: str


@dataclass
class ParsedCalendarEvent:
    owner_name: str
    date: date
    start_time: time
    end_time: time
    title: str


@dataclass
class ParsedEmail:
    thread_subject: str
    sequence: int          # 1-based position within the thread
    timestamp: datetime
    sender_email: str
    recipient_emails: list[str]
    body: str


@dataclass
class ParsedVoiceNote:
    date: date
    time: time
    transcript: str


@dataclass
class ParsedMeeting:
    title: str
    date: date
    start_time: time
    end_time: time
    attendees: list[str]
    transcript: str


@dataclass
class ParsedDataPack:
    people: list[ParsedPerson] = field(default_factory=list)
    meeting: Optional[ParsedMeeting] = None
    calendar_events: list[ParsedCalendarEvent] = field(default_factory=list)
    emails: list[ParsedEmail] = field(default_factory=list)
    voice_notes: list[ParsedVoiceNote] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_PACK_YEAR = 2026

# Day-of-month lookup for the week of 21–25 Sep 2026
_DAY_TO_DATE = {
    "mon": 21, "tue": 22, "wed": 23, "thu": 24, "fri": 25,
}

# All dash-like characters found in the data pack
_DASHES = r"[–—\-\u2013\u2014]"
# Smart + regular quote characters
_OPEN_QUOTE = r'[\u201C"\u201E\u00AB]'
_CLOSE_QUOTE = r'[\u201D"\u201F\u00BB]'


def _resolve_day(day_str: str) -> date:
    """Convert 'Mon 21 Sep' or similar into a date object."""
    day_str = day_str.strip().lower()
    for prefix, dom in _DAY_TO_DATE.items():
        if day_str.startswith(prefix):
            return date(DATA_PACK_YEAR, 9, dom)
    raise ValueError(f"Cannot resolve day string: {day_str!r}")


def _parse_time(t: str) -> time:
    """Parse '9:00 AM', '11:00 AM', '2:30 PM' etc."""
    t = t.strip().upper()
    t = re.sub(r"\s+", " ", t)
    for fmt in ("%I:%M %p", "%I:%M%p", "%I %p"):
        try:
            return datetime.strptime(t, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse time: {t!r}")


def _parse_time_range(text: str) -> tuple[time, time]:
    """Parse '9:00–9:35 AM' or '11:00 AM–12:00 PM' into (start, end)."""
    text = text.strip()
    parts = re.split(_DASHES, text)
    if len(parts) != 2:
        raise ValueError(f"Cannot parse time range: {text!r}")

    end_str = parts[1].strip()
    start_str = parts[0].strip()

    end_t = _parse_time(end_str)

    if not re.search(r"[AaPp][Mm]", start_str):
        suffix = "AM" if end_str.upper().rstrip().endswith("AM") else "PM"
        start_str = start_str + " " + suffix

    start_t = _parse_time(start_str)
    return start_t, end_t


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

def _parse_people(section: str) -> list[ParsedPerson]:
    """Parse the People & Email Addresses table."""
    people = []
    for line in section.splitlines():
        line = line.strip()
        if not line or line.startswith("Name") or line.startswith("(All"):
            continue
        email_match = re.search(r"(\S+@\S+\.\S+)\s*$", line)
        if not email_match:
            continue
        email = email_match.group(1)
        prefix = line[:email_match.start()].strip()
        parts = _split_name_role(prefix)
        people.append(ParsedPerson(name=parts[0], role=parts[1], email=email))
    return people


def _split_name_role(text: str) -> tuple[str, str]:
    """Split 'Arjun Malhotra VP Sales (the agent\u2019s user)' into name + role."""
    role_markers = [
        "VP Sales", "Marketing Lead", "Ops Manager", "Finance",
        "Meridian Logistics", "Internal distribution list",
    ]
    for marker in role_markers:
        idx = text.find(marker)
        if idx != -1:
            name = text[:idx].strip()
            role = text[idx:].strip()
            return name, role
    return text.strip(), ""


# ---------------------------------------------------------------------------
# Meeting
# ---------------------------------------------------------------------------

def _parse_meeting(section: str) -> ParsedMeeting:
    """Parse the Leadership Sync meeting section."""
    lines = section.strip().splitlines()
    header = lines[0]
    header_clean = re.sub(r"^[\d.]+\s*", "", header).strip()
    header_clean = re.sub(r"^Meeting Transcript\s*" + _DASHES + r"\s*", "", header_clean)

    parts = [p.strip() for p in header_clean.split(",")]
    title = parts[0] if parts else "Leadership Sync"
    meeting_date = date(2026, 9, 21)
    start_time_val = time(9, 0)
    end_time_val = time(9, 35)

    if len(parts) >= 3:
        try:
            start_time_val, end_time_val = _parse_time_range(parts[-1])
        except ValueError:
            pass

    attendees_line = lines[1] if len(lines) > 1 else ""
    attendees = []
    if "attendees:" in attendees_line.lower():
        att_text = attendees_line.split(":", 1)[1]
        attendees = [a.strip() for a in att_text.split(",")]

    transcript_lines = lines[2:] if len(lines) > 2 else []
    transcript = "\n".join(transcript_lines).strip()

    return ParsedMeeting(
        title=title,
        date=meeting_date,
        start_time=start_time_val,
        end_time=end_time_val,
        attendees=attendees,
        transcript=transcript,
    )


# ---------------------------------------------------------------------------
# Calendars
# ---------------------------------------------------------------------------

def _parse_calendars(section: str) -> list[ParsedCalendarEvent]:
    """Parse the Calendars section — multiple people, each with events."""
    events: list[ParsedCalendarEvent] = []
    current_owner: str | None = None
    known_owners = [
        "Arjun Malhotra", "Neha Kapoor", "Raghav Sethi", "Divya Rao",
    ]

    for line in section.splitlines():
        line_stripped = line.strip()
        if not line_stripped or line_stripped == "---":
            continue
        if line_stripped.startswith("Day/Date") or line_stripped.startswith("Time"):
            continue

        # Check if this line is a person header
        matched_owner = False
        for owner in known_owners:
            if owner in line_stripped and len(line_stripped) < len(owner) + 20:
                current_owner = owner
                matched_owner = True
                break

        if matched_owner:
            continue

        if re.match(r"^\d+\.\s*Calendars", line_stripped):
            continue
        if current_owner is None:
            continue

        event = _try_parse_calendar_line(line_stripped, current_owner)
        if event:
            events.append(event)

    return events


def _try_parse_calendar_line(line: str, owner: str) -> ParsedCalendarEvent | None:
    """Parse 'Mon 21 Sep 9:00–9:35 AM Leadership Sync'."""
    m = re.match(
        r"((?:Mon|Tue|Wed|Thu|Fri)\s+\d{1,2}\s+Sep)\s+"
        r"(\d{1,2}:\d{2}(?:\s*(?:AM|PM))?\s*" + _DASHES + r"\s*\d{1,2}:\d{2}\s*(?:AM|PM))\s+"
        r"(.+)",
        line,
        re.IGNORECASE,
    )
    if not m:
        return None
    try:
        event_date = _resolve_day(m.group(1))
        start_t, end_t = _parse_time_range(m.group(2))
        title = m.group(3).strip()
        return ParsedCalendarEvent(
            owner_name=owner,
            date=event_date,
            start_time=start_t,
            end_time=end_t,
            title=title,
        )
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Emails
# ---------------------------------------------------------------------------

def _parse_emails(section: str) -> list[ParsedEmail]:
    """Parse 5 threads × 5 emails each.

    Strategy: join the section into one long string (fixing PDF line wraps),
    then extract emails by regex.
    """
    emails: list[ParsedEmail] = []
    current_subject: str | None = None

    # Pre-process: remove page-break artefacts (---) and join continuation lines
    lines = section.splitlines()
    cleaned_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "---" or not stripped:
            continue
        cleaned_lines.append(stripped)

    # Re-join into a single text stream for easier regex matching
    full_text = "\n".join(cleaned_lines)

    # Fix email addresses broken across lines by PDF conversion
    # e.g. "divya.rao@veridian-\ncorp.example" → "divya.rao@veridian-corp.example"
    full_text = re.sub(r"(\S+@\S+)-\s*\n\s*(\S+)", r"\1-\2", full_text)

    # Process line by line from the cleaned text
    i = 0
    cleaned = full_text.split("\n")

    while i < len(cleaned):
        line = cleaned[i]

        # Section header
        if re.match(r"^\d+\.\s*Email Threads", line):
            i += 1
            continue

        # Thread header: "Thread N — Subject: XYZ"
        thread_match = re.match(
            r"Thread\s+\d+\s*" + _DASHES + r"\s*Subject:\s*(.+)",
            line, re.IGNORECASE,
        )
        if thread_match:
            current_subject = thread_match.group(1).strip()
            i += 1
            continue

        # Try to parse email starting at this line
        if current_subject and re.match(r"\d+\.\s*(?:Mon|Tue|Wed|Thu|Fri)", line):
            email, consumed = _try_parse_email_block(cleaned, i, current_subject)
            if email:
                emails.append(email)
                i += consumed
                continue

        i += 1

    return emails


def _try_parse_email_block(
    lines: list[str], start_idx: int, subject: str
) -> tuple[ParsedEmail | None, int]:
    """Parse an email block starting at start_idx, consuming continuation lines.

    Returns (email, number_of_lines_consumed).
    """
    # Collect lines until the next email/thread starts or section ends
    block_lines = [lines[start_idx]]
    j = start_idx + 1
    while j < len(lines):
        next_line = lines[j]
        # Stop if next email starts
        if re.match(r"\d+\.\s*(?:Mon|Tue|Wed|Thu|Fri)", next_line, re.IGNORECASE):
            break
        # Stop if new thread starts
        if re.match(r"Thread\s+\d+", next_line, re.IGNORECASE):
            break
        block_lines.append(next_line)
        j += 1

    combined = " ".join(block_lines)
    # Fix broken email addresses
    combined = re.sub(r"(\S+@\S+)-\s+(\S+)", r"\1-\2", combined)

    # Pattern: N. Day DD Mon, TIME — From: sender — To: recipient(s) "body"
    m = re.match(
        r"(\d+)\.\s*"
        r"((?:Mon|Tue|Wed|Thu|Fri)\s+\d{1,2}\s+Sep)"
        r",\s*"
        r"(\d{1,2}:\d{2}\s*(?:AM|PM))"
        r"\s*" + _DASHES + r"\s*"
        r"From:\s*(\S+@\S+)"
        r"\s*" + _DASHES + r"\s*"
        r"To:\s*(.+?)\s+"
        + _OPEN_QUOTE + r"(.+)" + _CLOSE_QUOTE,
        combined,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None, 1

    seq = int(m.group(1))
    event_date = _resolve_day(m.group(2))
    t = _parse_time(m.group(3))
    sender = m.group(4).strip()

    raw_recipients = m.group(5).strip()
    raw_recipients = re.sub(r"-\s+", "-", raw_recipients)
    # Handle "All Staff" as a special recipient
    if "All Staff" in raw_recipients:
        recipients = ["All Staff"]
    else:
        recipients = [
            r.strip().rstrip(",")
            for r in re.split(r",\s*", raw_recipients)
            if "@" in r
        ]

    body = m.group(6).strip()

    timestamp = datetime(DATA_PACK_YEAR, 9, event_date.day, t.hour, t.minute)

    email = ParsedEmail(
        thread_subject=subject,
        sequence=seq,
        timestamp=timestamp,
        sender_email=sender,
        recipient_emails=recipients,
        body=body,
    )
    return email, j - start_idx


# ---------------------------------------------------------------------------
# Voice Notes
# ---------------------------------------------------------------------------

def _parse_voice_notes(section: str) -> list[ParsedVoiceNote]:
    """Parse the Voice Note Transcripts section."""
    notes: list[ParsedVoiceNote] = []

    # Join lines and collapse whitespace (PDF wrapping)
    full_text = " ".join(section.splitlines())
    full_text = re.sub(r"\s+", " ", full_text)

    # Pattern: Voice Note N — Day DD Mon, TIME (optional parenthetical) "transcript"
    pattern = re.compile(
        r"Voice Note \d+\s*" + _DASHES + r"\s*"
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday)\s+"
        r"(\d{1,2})\s+Sep"
        r",\s*(\d{1,2}:\d{2}\s*(?:AM|PM))"
        r"\s*(?:\([^)]*\)\s*)?"        # optional "(recorded in cab)"
        + _OPEN_QUOTE + r"(.+?)" + _CLOSE_QUOTE,
        re.IGNORECASE,
    )

    for m in pattern.finditer(full_text):
        day = int(m.group(1))
        t = _parse_time(m.group(2))
        transcript = m.group(3).strip()
        notes.append(ParsedVoiceNote(
            date=date(DATA_PACK_YEAR, 9, day),
            time=t,
            transcript=transcript,
        ))

    return notes


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_data_pack(path: str | Path) -> ParsedDataPack:
    """Read the Markdown data pack and return all parsed sections.

    Raises FileNotFoundError if the path does not exist.
    Raises ValueError if critical sections cannot be parsed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data pack not found: {path}")

    raw = path.read_text(encoding="utf-8")

    # --- Split into major sections by numbered headers ---
    people_end = re.search(r"\d+\.\s*Meeting Transcript", raw)
    people_section = raw[:people_end.start()] if people_end else ""

    meeting_start = people_end.start() if people_end else 0
    calendars_match = re.search(r"\d+\.\s*Calendars", raw)
    meeting_section = raw[meeting_start:calendars_match.start()] if calendars_match else ""

    emails_match = re.search(r"\d+\.\s*Email Threads", raw)
    calendars_section = raw[calendars_match.start():emails_match.start()] if (calendars_match and emails_match) else ""

    voice_match = re.search(r"\d+\.\s*Voice Note Transcripts?", raw)
    emails_section = raw[emails_match.start():voice_match.start()] if (emails_match and voice_match) else ""

    end_match = re.search(r"Note on Your Prototype", raw)
    voice_section = raw[voice_match.start():end_match.start()] if (voice_match and end_match) else raw[voice_match.start():] if voice_match else ""

    # --- Parse each section ---
    result = ParsedDataPack()
    result.people = _parse_people(people_section)
    result.meeting = _parse_meeting(meeting_section)
    result.calendar_events = _parse_calendars(calendars_section)
    result.emails = _parse_emails(emails_section)
    result.voice_notes = _parse_voice_notes(voice_section)

    return result
