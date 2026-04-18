"""Season anchors and model identifiers for BR / BoR / AR v1."""
from __future__ import annotations

from services.sportmonks_service import IPL_SEASON_IDS

CURRENT_IPL_YEAR: int = max(IPL_SEASON_IDS.keys())

# Spec: current 2.0, N-1 1.4, N-2 0.8, N-3 0.4; all seasons older than N-3 → one pool weight 0.15
RECENCY_OFFSET_WEIGHTS: tuple = (2.0, 1.4, 0.8, 0.4)
RECENCY_OLDER_POOL_WEIGHT: float = 0.15

# CSA recency weights (last 5 innings/spells) — same shape as legacy Option C
CSA_RECENCY_WEIGHTS: tuple = (2.0, 1.5, 1.0, 0.75, 0.5)

IMPACT_MODEL_ID: str = "br_bor_ar_v1"

# Minimum samples (spec)
MIN_BAT_INNINGS_PP_BALLS: int = 30
MIN_BAT_INNINGS_DEATH_BALLS: int = 20
MIN_BOWL_DEATH_OVERS: float = 25.0
MIN_BAT_INNINGS_SR_BLEND: int = 8
