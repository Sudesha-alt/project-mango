"""
Player impact entrypoint: default BR/BoR v1 or classic BPR+CSA (Players directory).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from services.player_impact_br_bor import compute_player_impact_profile as compute_br_bor_profile
from services.player_impact_classic_bpr import compute_classic_player_impact_profile

__all__ = ["compute_player_impact_profile", "claude_impact_fallback_allowed", "IMPACT_FORMULAS"]

IMPACT_FORMULAS = frozenset({"br_bor_v1", "classic_bpr_csa"})


def compute_player_impact_profile(
    perf_row: Optional[dict],
    role_code: str,
    star_rating: float,
    *,
    batting_position: Optional[int] = None,
    bowling_style: Optional[str] = None,
    formula: str = "br_bor_v1",
) -> Dict[str, Any]:
    f = (formula or "br_bor_v1").strip()
    if f not in IMPACT_FORMULAS:
        f = "br_bor_v1"
    if f == "classic_bpr_csa":
        return compute_classic_player_impact_profile(
            perf_row,
            role_code,
            star_rating,
            batting_position=batting_position,
            bowling_style=bowling_style,
        )
    return compute_br_bor_profile(
        perf_row,
        role_code,
        star_rating,
        batting_position=batting_position,
        bowling_style=bowling_style,
    )


def claude_impact_fallback_allowed() -> bool:
    return os.environ.get("ALLOW_CLAUDE_PLAYER_IMPACT_FALLBACK", "").lower() in (
        "1",
        "true",
        "yes",
    )
