"""
Live Match Prediction Engine — Alpha-Blended H×L Model + Phase-Based Weighting

Formula: P(win) = alpha × H + (1 - alpha) × L

H = Historical/Structural factors (decays as match progresses):
    0.22 × Squad Strength + 0.10 × H2H + 0.28 × Venue + 0.25 × Form + 0.15 × Toss

L = Live factors (6-factor model):
    0.30 × Score vs Par + 0.25 × Wickets + 0.15 × Recent Rate
    + 0.15 × Bowlers Remaining + 0.10 × Pre-match Base + 0.05 × Context

Alpha = Stage-aware non-linear decay:
    Pre-game: 0.85 → End inn1: 0.20 → End inn2: 0.05

Phase-Based Dynamic Weighting (Algorithm vs Claude):
    Post-Toss:       Algo 70% / Claude 30%
    Mid 1st Innings:  Algo 40% / Claude 60%
    End 1st Innings:  Algo 20% / Claude 80%
    Mid 2nd Innings:  Algo 10% / Claude 90%
    Late game:        Algo 0%  / Claude 100%
"""
import math
import logging
from typing import Dict, Optional, List

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


# ── Fix 1: Non-linear alpha curve ──
def compute_alpha(balls_bowled_total: int, innings: int) -> float:
    """
    Research-calibrated alpha: historical weight drops fast once live data arrives.
    Stage boundaries (total match balls):
      0      = pre-game   -> alpha = 0.85
      120    = end inn1   -> alpha = 0.20
      240    = end inn2   -> alpha = 0.05
    """
    if innings == 1:
        progress = min(1.0, balls_bowled_total / 120)
        alpha = 0.85 - (0.65 * progress)
    else:
        inn2_balls = max(0, balls_bowled_total - 120)
        progress = min(1.0, inn2_balls / 120)
        alpha = 0.20 - (0.15 * progress)
    return round(max(0.05, min(0.85, alpha)), 3)


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


def compute_live_prediction(sm_data: dict, claude_prediction: dict,
                            match_info: dict, pre_match_prob: Optional[float] = None,
                            xi_data: Optional[dict] = None) -> dict:
    """
    Alpha-blended H×L Live Prediction.

    P(win) = alpha × H + (1-alpha) × L

    H = 0.22×Squad + 0.10×H2H + 0.28×Venue + 0.25×Form + 0.15×Toss
    L = 6-factor live model
    Alpha = stage-aware non-linear decay (0.85 → 0.05)

    Claude's win % is passed directly as the pre-match base anchor and
    also blended into the final output via phase-based weighting.
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
    innings_balls_remaining = max(0, 120 - innings_balls_bowled)
    wickets_remaining = max(0, 10 - wickets)

    # Total match balls for alpha
    total_balls_bowled = innings_balls_bowled if innings == 1 else (120 + innings_balls_bowled)

    # ── Fix 4: Venue-aware par scores ──
    venue = match_info.get("venue", "")
    venue_profile = get_venue_profile(venue)
    venue_par_20 = venue_profile["par"]

    # ━━━━━━ Fix 1: Alpha (non-linear) ━━━━━━
    alpha = compute_alpha(total_balls_bowled, innings)

    # ━━━━━━ H: Historical/Structural Factors ━━━━━━
    hf = claude_prediction.get("historical_factors", {}) if claude_prediction else {}
    h2h = float(hf.get("h2h_win_pct", 0.5))
    venue_pct = float(hf.get("venue_win_pct", 0.5))
    form_pct = float(hf.get("recent_form_pct", 0.5))
    toss_pct = float(hf.get("toss_advantage_pct", 0.5))

    # Fix 3: Squad strength from Playing XI
    squad_pct = compute_squad_strength_differential(xi_data) if xi_data else 0.5

    # Fix 2: Research-aligned H weights
    H = (0.22 * squad_pct
         + 0.10 * h2h
         + 0.28 * venue_pct
         + 0.25 * form_pct
         + 0.15 * toss_pct)

    # ━━━━━━ L: Live Factors (6-Factor Model) ━━━━━━

    # Factor 1: Score vs Par Score (30%) — venue-aware
    if innings == 2 and target and target > 0:
        runs_needed = max(0, target - runs)
        if innings_balls_remaining > 0:
            actual_rrr = (runs_needed / innings_balls_remaining) * 6
        else:
            actual_rrr = 99 if runs_needed > 0 else 0
        if actual_rrr > 0:
            ratio = crr / actual_rrr if actual_rrr < 50 else 0
        else:
            ratio = 2.0
        score_vs_par = 1.0 / (1.0 + math.exp(-6 * (ratio - 1.0)))
    else:
        # 1st innings: compare score to venue-specific par
        par = _get_venue_par_at_over(venue_par_20, overs) if overs > 0 else 1
        if par > 0:
            score_ratio = runs / par
            score_vs_par = 1.0 / (1.0 + math.exp(-5 * (score_ratio - 1.0)))
        else:
            score_vs_par = 0.5

    # Factor 2: Wickets in Hand (25%)
    wick_ratio = wickets_remaining / 10
    phase_factor = min(1.0, innings_balls_bowled / 72)
    wickets_in_hand = wick_ratio ** (0.7 + 0.3 * phase_factor)
    if innings == 2 and rrr and rrr > 10 and wickets_remaining <= 4:
        wickets_in_hand *= max(0.2, wickets_remaining / 6)

    # Factor 3: Recent Over Rate (15%)
    last_12 = recent_balls[-12:] if recent_balls else []
    recent_runs = 0
    recent_wickets = 0
    for b in last_12:
        if isinstance(b, (int, float)):
            recent_runs += b
        elif isinstance(b, str):
            if b.isdigit():
                recent_runs += int(b)
            elif b.upper() == "W":
                recent_wickets += 1

    if last_12:
        recent_rpo = (recent_runs / len(last_12)) * 6
        if innings == 2 and rrr and rrr > 0:
            target_rpo = rrr
        else:
            if overs <= 6:
                target_rpo = venue_par_20 / 20 * 0.85   # Powerplay: ~85% of avg RPO
            elif overs <= 15:
                target_rpo = venue_par_20 / 20 * 0.95   # Middle: ~95% of avg RPO
            else:
                target_rpo = venue_par_20 / 20 * 1.25    # Death: ~125% of avg RPO
        ratio = recent_rpo / max(1, target_rpo)
        recent_over_rate = 1.0 / (1.0 + math.exp(-4 * (ratio - 1.0)))
        if recent_wickets >= 2:
            recent_over_rate *= 0.5
        elif recent_wickets == 1:
            recent_over_rate *= 0.75
    else:
        recent_over_rate = 0.5

    # Factor 4: Bowlers Remaining (15%)
    bowling_card = sm_data.get("bowling_card", [])
    yet_to_bowl = sm_data.get("yet_to_bowl", [])
    if bowling_card or yet_to_bowl:
        bowlers_with_overs = 0
        for bwl in bowling_card:
            bowled = bwl.get("overs", 0) or 0
            if bowled < 4:
                bowlers_with_overs += 1
        bowlers_with_overs += len(yet_to_bowl)
        bowling_depth = min(1.0, bowlers_with_overs / 5)
        bowlers_remaining = 1.0 - (bowling_depth * 0.6 + 0.2)
        if active_bowler:
            econ = active_bowler.get("economy", 8) or 8
            if econ > 10:
                bowlers_remaining = min(1.0, bowlers_remaining + 0.15)
            elif econ < 6:
                bowlers_remaining = max(0, bowlers_remaining - 0.15)
    else:
        bowlers_remaining = 0.5

    # Factor 5: Pre-match Base Probability (10%)
    # Prefer the algo+claude adjusted probability (contextual adjustment applied)
    claude_t1_pct = None
    if claude_prediction and not claude_prediction.get("error"):
        claude_t1_pct = claude_prediction.get("team1_win_pct")
        if claude_t1_pct is not None:
            claude_t1_pct = float(claude_t1_pct)

    if claude_t1_pct is not None:
        pre_match_base = max(0.01, min(0.99, claude_t1_pct / 100))
    elif pre_match_prob is not None:
        pre_match_base = max(0, min(1.0, pre_match_prob / 100))
    else:
        pre_match_base = 0.5

    # Factor 6: Match Situation Context (5%)
    context_score = 0.5
    if active_batsmen:
        min_balls = min((bat.get("balls", 0) or 0) for bat in active_batsmen)
        if min_balls < 3:
            context_score -= 0.15
        elif min_balls < 8:
            context_score -= 0.08

    if innings == 2 and overs >= 15 and rrr and rrr > 10:
        context_score -= 0.10
    elif innings == 1 and overs >= 15 and crr > 10:
        context_score += 0.10

    last_6 = recent_balls[-6:] if recent_balls else []
    last6_runs = sum(int(b) if isinstance(b, str) and b.isdigit() else (b if isinstance(b, (int, float)) else 0) for b in last_6)
    if last_6 and len(last_6) >= 4:
        if last6_runs >= 12:
            context_score += 0.10
        elif last6_runs <= 3:
            context_score -= 0.08
    context_score = max(0, min(1.0, context_score))

    # ━━━━━━ Compose L (from BATTING team's perspective) ━━━━━━
    L = (0.30 * score_vs_par
         + 0.25 * wickets_in_hand
         + 0.15 * recent_over_rate
         + 0.15 * bowlers_remaining
         + 0.10 * pre_match_base
         + 0.05 * context_score)

    # ━━━━━━ Normalize L to team1's perspective ━━━━━━
    team1 = match_info.get("team1", "Team A")
    batting_team = sm_data.get("batting_team", team1)

    if batting_team.lower() in team1.lower() or team1.lower() in batting_team.lower():
        L_team1 = L
    else:
        L_team1 = 1.0 - L

    # ━━━━━━ Final: alpha × H + (1-alpha) × L ━━━━━━
    # H is already from team1's perspective (Claude historical factors are team1-centric)
    final_score = (alpha * H + (1 - alpha) * L_team1) * 100
    final_score = round(max(1, min(99, final_score)), 1)

    team1_pct = final_score
    team2_pct = round(100 - final_score, 1)

    active_bat_names = [b.get("name", "?") for b in active_batsmen] if active_batsmen else []
    bowler_name = active_bowler.get("name", "?") if active_bowler else None

    return {
        "team1_pct": team1_pct,
        "team2_pct": team2_pct,
        "alpha": alpha,
        "H": round(H, 4),
        "L": round(L, 4),
        "L_team1": round(L_team1, 4),
        "final_score": final_score,
        "model": "alpha-HL-v2",
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
        "L_breakdown": {
            "score_vs_par": round(score_vs_par, 3),
            "wickets_in_hand": round(wickets_in_hand, 3),
            "recent_over_rate": round(recent_over_rate, 3),
            "bowlers_remaining": round(bowlers_remaining, 3),
            "pre_match_base": round(pre_match_base, 3),
            "match_situation_context": round(context_score, 3),
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
    "pre_game":       {"algo": 0.70, "claude": 0.30, "label": "Post-Toss"},
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
        "claude_source": claude_pred.get("source", "unknown") if claude_pred else "none",
        "claude_section10_t1": s10.get("team1_win_pct") if s10 else None,
        "claude_confidence": s10.get("sentence_4_confidence", "") if s10 else "",
        "revision_triggers": revision_triggers[:3] if revision_triggers else [],
        "gut_feeling": gut_feeling or None,
        "gut_t1_adj": round(gut_t1_adj, 1),
        "betting_odds_t1_pct": round(odds_t1_pct, 1) if betting_odds_pct else None,
        "model": "phase-weighted-v2",
    }
