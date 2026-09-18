"""Action Normalizer — standardizes action text while preserving raw text verbatim."""

from __future__ import annotations

import re


class ActionNormalizer:
    """Cleans and standardizes action descriptions."""

    _FILLER_PREFIXES = [
        r"^quick note to self\s*[-—:]*\s*",
        r"^reminder\s*[-—:]*\s*",
        r"^just checking\s*[-—:]*\s*",
        r"^i need to\s+",
        r"^need to\s+",
        r"^will\s+",
        r"^i told \w+ i['’]d\s+",
        r"^can you\s+",
    ]

    @classmethod
    def normalize_action_text(cls, text: str) -> str:
        """Strip conversational filler while preserving meaningful semantic terms."""
        cleaned = text.strip()

        for pattern in cls._FILLER_PREFIXES:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

        # Capitalize first letter
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]

        return cleaned
