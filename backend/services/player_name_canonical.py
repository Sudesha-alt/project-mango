"""
Canonical display names for players who appear under multiple spellings in SportMonks / Mongo / squads.

All IPL-facing code should run names through ``canonical_player_display_name`` when *writing*
lineups or ``player_performance`` so the Players directory, pre-match XI, and Mongo stay aligned.
"""
from __future__ import annotations

import re
from typing import Dict

# Normalized key (letters + spaces only, lower) -> single display name used everywhere.
_CANONICAL_BY_NORMALIZED: Dict[str, str] = {
    "kl rahul": "KL Rahul",
    "lokesh rahul": "KL Rahul",
    "k l rahul": "KL Rahul",
}


def _norm_key(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def canonical_player_display_name(name: str) -> str:
    """Return the app-wide display name for this player, or the stripped original if unknown."""
    if not name or not str(name).strip():
        return (name or "").strip()
    raw = str(name).strip()
    key = _norm_key(raw)
    return _CANONICAL_BY_NORMALIZED.get(key, raw)
