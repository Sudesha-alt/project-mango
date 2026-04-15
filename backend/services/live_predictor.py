"""
Live Match Prediction Engine — Historical Structural Score + Phase-Based Weighting

Historical model (team1 perspective):
    H = 0.22 × Squad Strength + 0.10 × H2H + 0.28 × Venue + 0.25 × Form + 0.15 × Toss

Phase-Based Dynamic Weighting (Historical vs Claude):
    Post-Toss:       Algo 70% / Claude 30%
    Mid 1st Innings:  Algo 40% / Claude 60%
    End 1st Innings:  Algo 20% / Claude 80%
    Mid 2nd Innings:  Algo 10% / Claude 90%
    Late game:        Algo 0%  / Claude 100%
"""
import math
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Fix 4: Venue-specific par scores ──
VENUE_PAR_SCORES = {
    "wankhede":     {"par": 178, "bat_first_win_pct": 0.44, "dew_risk": "high"},
    "chinnaswamy":  {"par": 195, "bat_first_win_pct": 0.40, "dew_risk": "medium"},
    "chepauk":      {"par": 158, "bat_first_win_pct": 0.56, "dew_risk": "low"},
    "eden gardens": {"par": 175, "bat_first_win_pct": 0.46, "dew_risk": "high"},
    "eden":         {"par": 175, "bat_first_win_pct": 0.46, "dew_risk": "high"},
    "kotla":        {"par": 168, "bat_first_win_pct": 0.48, "dew_risk": "low"},
    "arun jaitley":  {"par": 168, "bat_first_win_pct": 0.48, "dew_risk": "low"},
    "motera":       {"par": 172, "bat_first_win_pct": 0.52, "dew_risk": "medium"},
    "narendra modi": {"par": 172, "bat_first_win_pct": 0.52, "dew_risk": "medium"},
    "uppal":        {"par": 182, "bat_first_win_pct": 0.45, "dew_risk": "medium"},
    "rajiv gandhi":  {"par": 182, "bat_first_win_pct": 0.45, "dew_risk": "medium"},
    "mohali":       {"par": 170, "bat_first_win_pct": 0.47, "dew_risk": "medium"},
    "sawai":        {"par": 170, "bat_first_win_pct": 0.49, "dew_risk": "medium"},
    "ekana":        {"par": 168, "bat_first_win_pct": 0.50, "dew_risk": "medium"},
    "lucknow":      {"par": 168, "bat_first_win_pct": 0.50, "dew_risk": "medium"},
    "default":      {"par": 170, "bat_first_win_pct": 0.48, "dew_risk": "medium"},
}


def get_venue_profile(venue: str) -> dict:
    """Get venue-specific par score and characteristics."""
    venue_lower = (venue or "").lower()
    for key, profile in VENUE_PAR_SCORES.items():
        if key != "default" and key in venue_lower:
            return profile
    return VENUE_PAR_SCORES["default"]


def _get_venue_par_at_over(venue_par_20: int, overs: float) -> float:
    """Get expected par score at a given over for a specific venue."""
    if overs <= 0:
        return 0
    # Scale the per-over trajectory to the venue's 20-over par
    scale = venue_par_20 / 170  # 170 is our baseline par
    completed = int(overs)
    fraction = overs - completed
    # Base par table (cumulative, baseline 170 par)
    base_table = {
        1: 7, 2: 14, 3: 22, 4: 29, 5: 36, 6: 44,
        7: 52, 8: 60, 9: 68, 10: 76, 11: 84, 12: 92,
        13: 100, 14: 108, 15: 116,
        16: 127, 17: 138, 18: 149, 19: 160, 20: 170,
    }
    base = base_table.get(min(completed, 20), 170)
    if fraction > 0 and completed < 20:
        next_base = base_table.get(min(completed + 1, 20), 170)
        base += (next_base - base) * fraction
    return base * scale


# ── Fix 3: Squad strength differential ──
def compute_squad_strength_differential(xi_data: dict) -> float:
    """
    Returns team1 win probability from squad strength alone (0.0-1.0).
    Aggregates expected_runs + expected_wickets per player into a team score.
    Allrounders get a 1.25x multiplier.
    """
    def team_score(xi_list: list) -> float:
        score = 0.0
        for p in xi_list:
            runs = p.get("expected_runs", 15)
            wkts = p.get("expected_wickets", 0)
            role = (p.get("role") or "").lower()
            is_allrounder = "all" in role or ("bat" in role and "bowl" in role)
            player_score = (runs / 30.0) + (wkts / 1.5)
            if is_allrounder:
                player_score *= 1.25
            score += player_score
        return score

    t1_score = team_score(xi_data.get("team1_xi", []))
    t2_score = team_score(xi_data.get("team2_xi", []))
    total = t1_score + t2_score
    if total == 0:
        return 0.5
    raw = t1_score / total
    return round(1.0 / (1.0 + math.exp(-6 * (raw - 0.5))), 4)


def _norm_factor(v: Any, default: float = 0.5) -> float:
    """Normalize a 0–1 or 0–100 historical factor to 0–1."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if x > 1.0:
        x = x / 100.0
    return max(0.0, min(1.0, x))


def _standings_win_rate(standings: List, team_name: str) -> Optional[float]:
    if not standings or not team_name:
        return None
    tn = team_name.lower()
    for s in standings:
        if not isinstance(s, dict):
            continue
        name = (s.get("team") or "").lower()
        if not name:
            continue
        if tn in name or name in tn or any(
            len(w) > 3 and w in name for w in tn.split()
        ):
            played = max(1, int(s.get("played", 0) or 0))
            won = int(s.get("won", 0) or 0)
            return won / played
    return None


def _toss_edge_for_team1(sm_data: dict, team1: str, team2: str) -> float:
    toss = (sm_data or {}).get("toss") or {}
    winner = (toss.get("winner") or "").strip()
    if not winner:
        return 0.5
    w = winner.lower()
    t1 = (team1 or "").lower()
    t2 = (team2 or "").lower()
    t1_hit = t1 and (t1 in w or w in t1 or any(len(x) > 3 and x in w for x in t1.split()))
    t2_hit = t2 and (t2 in w or w in t2 or any(len(x) > 3 and x in w for x in t2.split()))
    if t1_hit and not t2_hit:
        return 0.58
    if t2_hit and not t1_hit:
        return 0.42
    return 0.5


def build_historical_factors_from_enrichment(
    enrichment: Optional[Dict],
    match_info: Dict,
    sm_data: Optional[Dict],
) -> Dict[str, float]:
    """
    Derive H-factor inputs from SportMonks enrichment when Claude omits them.
    Values are team1-centric probabilities in [0, 1].
    """
    out = {
        "h2h_win_pct": 0.5,
        "venue_win_pct": 0.5,
        "recent_form_pct": 0.5,
        "toss_advantage_pct": 0.5,
    }
    enrichment = enrichment or {}
    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")

    h2h = enrichment.get("h2h") or {}
    if isinstance(h2h, dict) and h2h.get("matches_played", 0) > 0:
        t1w = float(h2h.get("team1_wins", 0))
        t2w = float(h2h.get("team2_wins", 0))
        dec = t1w + t2w
        if dec > 0:
            out["h2h_win_pct"] = max(0.05, min(0.95, t1w / dec))

    vs = enrichment.get("venue_stats") or {}
    if isinstance(vs, dict):
        bf = vs.get("bat_first_win_pct")
        if bf is not None:
            try:
                out["venue_win_pct"] = max(0.1, min(0.9, float(bf) / 100.0))
            except (TypeError, ValueError):
                pass

    standings = enrichment.get("standings") or []
    r1 = _standings_win_rate(standings, team1)
    r2 = _standings_win_rate(standings, team2)
    if r1 is not None and r2 is not None and (r1 + r2) > 0:
        out["recent_form_pct"] = max(0.05, min(0.95, r1 / (r1 + r2)))

    if sm_data:
        out["toss_advantage_pct"] = _toss_edge_for_team1(sm_data, team1, team2)

    return out


def merge_historical_factors(
    api_defaults: Dict[str, float],
    claude_hf: Optional[Dict],
) -> Dict[str, float]:
    """Claude-provided factors override API-derived defaults when present."""
    keys = ("h2h_win_pct", "venue_win_pct", "recent_form_pct", "toss_advantage_pct")
    merged = dict(api_defaults)
    if not claude_hf:
        return merged
    for k in keys:
        if k not in claude_hf or claude_hf[k] is None:
            continue
        merged[k] = _norm_factor(claude_hf[k], merged.get(k, 0.5))
    return merged


def compute_live_prediction(sm_data: dict, claude_prediction: dict,
                            match_info: dict, pre_match_prob: Optional[float] = None,
                            xi_data: Optional[dict] = None,
                            enrichment: Optional[Dict] = None) -> dict:
    """
    Historical-only live prediction input (team1 perspective).

    P(win) = H

    H = 0.22×Squad + 0.10×H2H + 0.28×Venue + 0.25×Form + 0.15×Toss

    Claude's win % is passed directly as the pre-match base anchor and
    also blended into the final output via phase-based weighting.

    `enrichment` (venue_stats, h2h, standings) fills `historical_factors` when
    the LLM omits them, so H is not stuck at neutral 0.5 for four factors.
    """
    if not sm_data:
        return None

    current_score = sm_data.get("current_score", {})
    runs = current_score.get("runs", 0)
    wickets = current_score.get("wickets", 0)
    overs = current_score.get("overs", 0)
    innings = sm_data.get("current_innings", 1)
    crr = sm_data.get("crr", 0) or 0
    rrr = sm_data.get("rrr") or 0
    recent_balls = sm_data.get("recent_balls", [])
    active_batsmen = sm_data.get("active_batsmen", [])
    active_bowler = sm_data.get("active_bowler")

    target = current_score.get("target") or sm_data.get("target")
    if target and isinstance(target, str):
        try:
            target = int(target)
        except ValueError:
            target = None

    innings_balls_bowled = int(overs) * 6 + round((overs % 1) * 10)
    total_balls_bowled = innings_balls_bowled if innings == 1 else (120 + innings_balls_bowled)
    innings_balls_remaining = max(0, 120 - innings_balls_bowled)
    wickets_remaining = max(0, 10 - wickets)

    # ── Fix 4: Venue-aware par scores ──
    venue = match_info.get("venue", "")
    venue_profile = get_venue_profile(venue)
    venue_par_20 = venue_profile["par"]

    # ━━━━━━ H: Historical/Structural Factors ━━━━━━
    api_hf = build_historical_factors_from_enrichment(enrichment, match_info, sm_data)
    claude_hf = (claude_prediction or {}).get("historical_factors")
    hf = merge_historical_factors(api_hf, claude_hf if isinstance(claude_hf, dict) else None)
    h2h = hf["h2h_win_pct"]
    venue_pct = hf["venue_win_pct"]
    form_pct = hf["recent_form_pct"]
    toss_pct = hf["toss_advantage_pct"]

    # Fix 3: Squad strength from Playing XI
    squad_pct = compute_squad_strength_differential(xi_data) if xi_data else 0.5

    # Fix 2: Research-aligned H weights
    H = (0.22 * squad_pct
         + 0.10 * h2h
         + 0.28 * venue_pct
         + 0.25 * form_pct
         + 0.15 * toss_pct)

    # Keep for transparency/diagnostics in response payload.
    claude_t1_pct = None
    if claude_prediction and not claude_prediction.get("error"):
        claude_t1_pct = claude_prediction.get("team1_win_pct")
        if claude_t1_pct is not None:
            claude_t1_pct = float(claude_t1_pct)

    # ━━━━━━ Final: historical-only score (team1 perspective) ━━━━━━
    # Freeze historical baseline to stored pre-match value when available.
    if pre_match_prob is not None:
        try:
            final_score = float(pre_match_prob)
        except (TypeError, ValueError):
            final_score = H * 100
    else:
        final_score = H * 100
    final_score = round(max(1, min(99, final_score)), 1)

    team1_pct = final_score
    team2_pct = round(100 - final_score, 1)

    active_bat_names = [b.get("name", "?") for b in active_batsmen] if active_batsmen else []
    bowler_name = active_bowler.get("name", "?") if active_bowler else None

    return {
        "team1_pct": team1_pct,
        "team2_pct": team2_pct,
        "H": round(H, 4),
        "historical_base_t1_pct": round(float(pre_match_prob), 1) if pre_match_prob is not None else None,
        "final_score": final_score,
        "model": "historical-only-v1",
        "claude_t1_pct_used": round(claude_t1_pct, 1) if claude_t1_pct is not None else None,
        "venue_profile": {
            "venue": venue,
            "par_20": venue_par_20,
            "bat_first_win_pct": venue_profile["bat_first_win_pct"],
            "dew_risk": venue_profile["dew_risk"],
        },
        "H_breakdown": {
            "squad_strength": round(squad_pct, 3),
            "h2h_win_pct": round(h2h, 3),
            "venue_win_pct": round(venue_pct, 3),
            "recent_form_pct": round(form_pct, 3),
            "toss_advantage_pct": round(toss_pct, 3),
        },
        "live_context": {
            "active_batsmen": active_bat_names,
            "active_bowler": bowler_name,
            "crr": round(crr, 2),
            "rrr": round(rrr, 2) if rrr else None,
            "runs_needed": max(0, target - runs) if (innings == 2 and target) else None,
            "balls_left_innings": innings_balls_remaining,
            "wickets_remaining": wickets_remaining,
            "total_balls_bowled": total_balls_bowled,
        },
        "innings": innings,
    }


# ── Phase Detection & Dynamic Algo/Claude Weighting ──

PHASE_WEIGHTS = {
    "pre_game":       {"algo": 0.70, "claude": 0.30, "label": "Early 1st innings / Post-Toss"},
    "mid_1st_inn":    {"algo": 0.40, "claude": 0.60, "label": "Mid 1st Innings"},
    "end_1st_inn":    {"algo": 0.20, "claude": 0.80, "label": "End 1st Innings"},
    "mid_2nd_inn":    {"algo": 0.10, "claude": 0.90, "label": "Mid 2nd Innings"},
    "late_game":      {"algo": 0.00, "claude": 1.00, "label": "Late Game"},
}


def detect_match_phase(sm_data: dict) -> str:
    """Detect match phase from live data for dynamic weighting."""
    if not sm_data:
        return "pre_game"

    innings = sm_data.get("current_innings", 1)
    current_score = sm_data.get("current_score", {})
    overs = current_score.get("overs", 0)

    if innings == 1:
        if overs <= 0.1:
            return "pre_game"
        elif overs < 12:
            return "mid_1st_inn"
        else:
            return "end_1st_inn"
    else:  # 2nd innings
        if overs < 12:
            return "mid_2nd_inn"
        else:
            return "late_game"


def compute_combined_prediction(
    algo_pred: dict,
    claude_pred: dict,
    sm_data: dict,
    gut_feeling: str = None,
    betting_odds_pct: float = None,
) -> dict:
    """
    Combine Algorithm and Claude predictions using phase-based dynamic weights.
    Optionally integrates gut feeling (3%) and betting odds (7%).

    Weights:
      Post-Toss:       Algo 70% / Claude 30%
      Mid 1st Innings: Algo 40% / Claude 60%
      End 1st Innings: Algo 20% / Claude 80%
      Mid 2nd Innings: Algo 10% / Claude 90%
      Late game:       Algo 0%  / Claude 100%

    If gut_feeling or betting_odds are provided, their combined weight (up to 10%)
    is carved out proportionally from the algo/claude split.
    """
    phase = detect_match_phase(sm_data)
    weights = PHASE_WEIGHTS[phase]
    algo_w = weights["algo"]
    claude_w = weights["claude"]
    phase_label = weights["label"]

    # Get team1 win % from both models
    algo_t1_pct = float(algo_pred.get("team1_pct", 50)) if algo_pred else 50.0
    # Claude now provides adjusted team1_win_pct (algo baseline + contextual adjustment)
    claude_t1_pct = float(claude_pred.get("team1_win_pct", 50)) if claude_pred and not claude_pred.get("error") else 50.0

    # Guardrail: prevent large narrative-only swings away from statistical anchor.
    phase_max_delta = {
        "pre_game": 12.0,
        "mid_1st_inn": 15.0,
        "end_1st_inn": 18.0,
        "mid_2nd_inn": 22.0,
        "late_game": 30.0,
    }
    max_delta = phase_max_delta.get(phase, 15.0)
    claude_delta = claude_t1_pct - algo_t1_pct
    if abs(claude_delta) > max_delta:
        claude_t1_pct = algo_t1_pct + (max_delta if claude_delta > 0 else -max_delta)

    # Gut feeling and betting odds adjustments
    gut_weight = 0.0
    odds_weight = 0.0
    gut_t1_adj = 0.0
    odds_t1_pct = 50.0

    if gut_feeling and gut_feeling.strip():
        gut_weight = 0.03  # 3% weight
        # Parse gut feeling for directional bias
        gut_lower = gut_feeling.lower()
        # Simple sentiment: look for team references or positive/negative words
        # This is passed to Claude for narrative, but for math we apply a small nudge
        positive_words = ["strong", "win", "confident", "dominant", "advantage", "favor", "better"]
        negative_words = ["weak", "lose", "doubt", "struggle", "poor", "collapse", "under pressure"]
        # Check if gut feeling leans toward team1 or team2
        has_positive = any(w in gut_lower for w in positive_words)
        has_negative = any(w in gut_lower for w in negative_words)
        if has_positive and not has_negative:
            gut_t1_adj = 5.0  # Small positive nudge toward team1
        elif has_negative and not has_positive:
            gut_t1_adj = -5.0  # Small negative nudge
        # If both or neither, neutral (0 adj)

    if betting_odds_pct is not None and betting_odds_pct > 0:
        odds_weight = 0.07  # 7% weight
        odds_t1_pct = float(betting_odds_pct)

    # Total user input weight
    user_input_weight = gut_weight + odds_weight

    # Scale down algo/claude proportionally to make room for user inputs
    if user_input_weight > 0:
        scale = 1.0 - user_input_weight
        algo_w *= scale
        claude_w *= scale

    # Compute combined team1 win %
    combined_t1 = (
        algo_w * algo_t1_pct
        + claude_w * claude_t1_pct
        + gut_weight * (50.0 + gut_t1_adj)
        + odds_weight * odds_t1_pct
    )

    combined_t1 = round(max(1, min(99, combined_t1)), 1)
    combined_t2 = round(100 - combined_t1, 1)
    uncertainty_band = round(max(3.0, 18.0 - (algo_w + claude_w) * 10.0), 1)

    # Extract Section 10 data for transparency
    s10 = claude_pred.get("section_10_final_prediction", {}) if claude_pred else {}
    revision_triggers = claude_pred.get("section_11_revision_triggers", []) if claude_pred else []

    return {
        "team1_pct": combined_t1,
        "team2_pct": combined_t2,
        "phase": phase,
        "phase_label": phase_label,
        "algo_weight": round(algo_w, 3),
        "claude_weight": round(claude_w, 3),
        "gut_weight": round(gut_weight, 3),
        "odds_weight": round(odds_weight, 3),
        "algo_t1_pct": round(algo_t1_pct, 1),
        "claude_t1_pct": round(claude_t1_pct, 1),
        "claude_anchor_max_delta": max_delta,
        "claude_source": claude_pred.get("source", "unknown") if claude_pred else "none",
        "claude_section10_t1": s10.get("team1_win_pct") if s10 else None,
        "claude_confidence": s10.get("sentence_4_confidence", "") if s10 else "",
        "revision_triggers": revision_triggers[:3] if revision_triggers else [],
        "gut_feeling": gut_feeling or None,
        "gut_t1_adj": round(gut_t1_adj, 1),
        "betting_odds_t1_pct": round(odds_t1_pct, 1) if betting_odds_pct else None,
        "uncertainty_band_pct": uncertainty_band,
        "model": "phase-weighted-v2",
    }


def _win_pct_side(t1_pct: float, band: float = 0.08) -> int:
    """Which side of a fair coin team1 is on: +1 favored, -1 underdog, 0 toss-up."""
    if t1_pct > 50.0 + band:
        return 1
    if t1_pct < 50.0 - band:
        return -1
    return 0


def stabilize_team1_win_pct(
    new_t1_pct: float,
    prev_t1_pct: Optional[float],
    *,
    ema_alpha: float = 0.42,
    min_lead_past_50_to_flip: float = 3.25,
) -> tuple[float, Dict[str, Any]]:
    """
    Reduce spurious favorite flips when re-running stochastic models (e.g. Claude) on the same state.

    - Exponential blend: display value moves partway toward the new reading (ema_alpha = weight on new).
    - Flip guard: if the raw new pick favors the opposite team vs previous, require
      |new - 50| >= min_lead_past_50_to_flip before trusting that flip; otherwise blend
      the pre-EMA value back toward the previous favorite so small noise does not swap sides.

    Tuning: raise min_lead_past_50_to_flip for stricter flip resistance; lower ema_alpha for stickier display.
    """
    new_t1_pct = max(1.0, min(99.0, float(new_t1_pct)))
    meta: Dict[str, Any] = {
        "raw_team1_pct": round(new_t1_pct, 2),
        "flip_guarded": False,
    }
    if prev_t1_pct is None:
        meta["stabilized_team1_pct"] = round(new_t1_pct, 1)
        return round(new_t1_pct, 1), meta

    prev_t1_pct = max(1.0, min(99.0, float(prev_t1_pct)))
    meta["prev_team1_pct"] = round(prev_t1_pct, 2)

    s_new = _win_pct_side(new_t1_pct)
    s_prev = _win_pct_side(prev_t1_pct)
    adjusted = new_t1_pct

    if s_prev != 0 and s_new != 0 and s_new != s_prev:
        lead = abs(new_t1_pct - 50.0)
        if lead < min_lead_past_50_to_flip:
            # Weak contradictory reading — stay closer to previous favorite
            adjusted = 50.0 + 0.72 * (prev_t1_pct - 50.0) + 0.28 * (new_t1_pct - 50.0)
            adjusted = max(1.0, min(99.0, adjusted))
            meta["flip_guarded"] = True

    blended = ema_alpha * adjusted + (1.0 - ema_alpha) * prev_t1_pct
    blended = max(1.0, min(99.0, blended))
    out = round(blended, 1)
    meta["stabilized_team1_pct"] = out
    return out, meta
