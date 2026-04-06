"""
Live Match Prediction Engine — 6-Factor Model

User-defined weights:
  1. Score vs Par Score        (30%) — How the batting team's score compares to phase-adjusted par
  2. Wickets in Hand           (25%) — Remaining batting resources
  3. Recent Over Rate          (15%) — Batting team's scoring rate in recent overs vs required
  4. Bowlers Remaining         (15%) — Bowling team's remaining overs from quality bowlers
  5. Pre-match Base Probability(10%) — Algo pre-match prediction as an anchor
  6. Match Situation Context   (5%)  — Phase of game, new batsman, momentum signals
"""
import math
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Phase-aware par scores per over (cumulative expected score for a strong T20 innings)
PAR_SCORE_TABLE = {
    # Powerplay (1-6): ~7.5 rpo
    1: 7, 2: 14, 3: 22, 4: 29, 5: 36, 6: 44,
    # Middle (7-15): ~8 rpo
    7: 52, 8: 60, 9: 68, 10: 76, 11: 84, 12: 92, 13: 100, 14: 108, 15: 116,
    # Death (16-20): ~10.5 rpo
    16: 127, 17: 138, 18: 149, 19: 160, 20: 172,
}


def _get_par_score(overs: float) -> float:
    """Get expected par score at a given over mark."""
    completed_overs = int(overs)
    fraction = overs - completed_overs
    if completed_overs <= 0:
        return 0
    base = PAR_SCORE_TABLE.get(min(completed_overs, 20), 172)
    # Interpolate for partial overs
    if fraction > 0 and completed_overs < 20:
        next_par = PAR_SCORE_TABLE.get(min(completed_overs + 1, 20), 172)
        base += (next_par - base) * fraction
    return base


def compute_live_prediction(sm_data: dict, claude_prediction: dict,
                            match_info: dict, pre_match_prob: Optional[float] = None) -> dict:
    """
    6-Factor Live Win Prediction.

    Weights:
      Score vs Par Score          0.30
      Wickets in Hand             0.25
      Recent Over Rate            0.15
      Bowlers Remaining           0.15
      Pre-match Base Probability  0.10
      Match Situation Context     0.05
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

    # Parse target
    target = current_score.get("target") or sm_data.get("target")
    if target and isinstance(target, str):
        try:
            target = int(target)
        except ValueError:
            target = None

    innings_balls_bowled = int(overs) * 6 + round((overs % 1) * 10)
    innings_balls_remaining = max(0, 120 - innings_balls_bowled)
    wickets_remaining = max(0, 10 - wickets)

    # ━━━━━━ Factor 1: Score vs Par Score (30%) ━━━━━━
    if innings == 2 and target and target > 0:
        # 2nd innings: compare actual progress to required trajectory
        runs_needed = max(0, target - runs)
        if innings_balls_remaining > 0:
            actual_rrr = (runs_needed / innings_balls_remaining) * 6
        else:
            actual_rrr = 99 if runs_needed > 0 else 0
        # Sigmoid mapping: rrr around 8 = neutral, lower = ahead, higher = behind
        # ratio = how comfortable the chase is (crr/rrr or progress-based)
        if actual_rrr > 0:
            ratio = crr / actual_rrr if actual_rrr < 50 else 0
        else:
            ratio = 2.0  # already won or no runs needed
        score_vs_par = 1.0 / (1.0 + math.exp(-6 * (ratio - 1.0)))
    else:
        # 1st innings: compare score to par at this stage
        par = _get_par_score(overs) if overs > 0 else 1
        if par > 0:
            score_ratio = runs / par
            score_vs_par = 1.0 / (1.0 + math.exp(-5 * (score_ratio - 1.0)))
        else:
            score_vs_par = 0.5

    # ━━━━━━ Factor 2: Wickets in Hand (25%) ━━━━━━
    # Non-linear: losing early wickets is worse; 8+ in hand late is very strong
    wick_ratio = wickets_remaining / 10
    # Apply phase context: wickets matter more as innings progresses
    phase_factor = min(1.0, innings_balls_bowled / 72)  # peaks at over 12
    wickets_in_hand = wick_ratio ** (0.7 + 0.3 * phase_factor)
    # In 2nd innings with high RRR and few wickets, compress further
    if innings == 2 and rrr and rrr > 10 and wickets_remaining <= 4:
        wickets_in_hand *= max(0.2, wickets_remaining / 6)

    # ━━━━━━ Factor 3: Recent Over Rate (15%) ━━━━━━
    # Batting team's scoring in recent balls vs what's needed
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
        recent_rpo = (recent_runs / len(last_12)) * 6  # runs per over equivalent
        if innings == 2 and rrr and rrr > 0:
            target_rpo = rrr
        else:
            # 1st innings: compare to phase par
            if overs <= 6:
                target_rpo = 7.5
            elif overs <= 15:
                target_rpo = 8.0
            else:
                target_rpo = 10.5
        ratio = recent_rpo / max(1, target_rpo)
        recent_over_rate = 1.0 / (1.0 + math.exp(-4 * (ratio - 1.0)))
        # Penalize if wickets fell in recent balls
        if recent_wickets >= 2:
            recent_over_rate *= 0.5
        elif recent_wickets == 1:
            recent_over_rate *= 0.75
    else:
        recent_over_rate = 0.5  # no data = neutral

    # ━━━━━━ Factor 4: Bowlers Remaining (15%) ━━━━━━
    # From the BOWLING team's perspective (inverted for batting team)
    # Check how many overs the current bowler has left, and quality of options
    bowling_card = sm_data.get("bowling_card", [])
    yet_to_bowl = sm_data.get("yet_to_bowl", [])

    if bowling_card or yet_to_bowl:
        # Count bowlers who haven't completed their 4 overs
        bowlers_with_overs = 0
        total_remaining_overs = 0
        for bwl in bowling_card:
            bowled = bwl.get("overs", 0) or 0
            if bowled < 4:
                bowlers_with_overs += 1
                total_remaining_overs += (4 - bowled)
        bowlers_with_overs += len(yet_to_bowl)
        total_remaining_overs += len(yet_to_bowl) * 4

        # More bowling options remaining = harder for batting team
        # Normalize: 5+ bowlers with overs = strong; 2 or less = weak
        bowling_depth = min(1.0, bowlers_with_overs / 5)
        # Invert for batting team perspective
        bowlers_remaining = 1.0 - (bowling_depth * 0.6 + 0.2)
        # If active bowler is expensive, boost batting team's factor
        if active_bowler:
            econ = active_bowler.get("economy", 8) or 8
            if econ > 10:
                bowlers_remaining = min(1.0, bowlers_remaining + 0.15)
            elif econ < 6:
                bowlers_remaining = max(0, bowlers_remaining - 0.15)
    else:
        bowlers_remaining = 0.5  # neutral when no data

    # ━━━━━━ Factor 5: Pre-match Base Probability (10%) ━━━━━━
    # Anchor from pre-match algorithm; 0.5 default if unavailable
    if pre_match_prob is not None:
        pre_match_base = max(0, min(1.0, pre_match_prob / 100))
    else:
        pre_match_base = 0.5

    # ━━━━━━ Factor 6: Match Situation Context (5%) ━━━━━━
    # Combines: phase of game, new batsman vulnerability, momentum signals
    context_score = 0.5  # neutral base

    # New batsman penalty
    if active_batsmen:
        min_balls = min((bat.get("balls", 0) or 0) for bat in active_batsmen)
        if min_balls < 3:
            context_score -= 0.15
        elif min_balls < 8:
            context_score -= 0.08

    # Phase pressure: death overs in chase amplify context
    if innings == 2 and overs >= 15 and rrr and rrr > 10:
        context_score -= 0.10  # death overs + high rrr = pressure
    elif innings == 1 and overs >= 15 and crr > 10:
        context_score += 0.10  # big death over hitting in 1st innings = good

    # Recent momentum from last 6 balls
    last_6 = recent_balls[-6:] if recent_balls else []
    last6_runs = sum(int(b) if isinstance(b, str) and b.isdigit() else (b if isinstance(b, (int, float)) else 0) for b in last_6)
    if last_6 and len(last_6) >= 4:
        if last6_runs >= 12:
            context_score += 0.10  # strong hitting
        elif last6_runs <= 3:
            context_score -= 0.08  # dot ball pressure

    context_score = max(0, min(1.0, context_score))

    # ━━━━━━ Compose Weighted Score ━━━━━━
    L = (0.30 * score_vs_par
         + 0.25 * wickets_in_hand
         + 0.15 * recent_over_rate
         + 0.15 * bowlers_remaining
         + 0.10 * pre_match_base
         + 0.05 * context_score)

    # L is from BATTING team's perspective
    # Normalize to team1's perspective
    team1 = match_info.get("team1", "Team A")
    batting_team = sm_data.get("batting_team", team1)

    if batting_team.lower() in team1.lower() or team1.lower() in batting_team.lower():
        L_team1 = L
    else:
        L_team1 = 1.0 - L

    team1_pct = round(max(1, min(99, L_team1 * 100)), 1)
    team2_pct = round(100 - team1_pct, 1)

    # Context strings for UI
    active_bat_names = [b.get("name", "?") for b in active_batsmen] if active_batsmen else []
    bowler_name = active_bowler.get("name", "?") if active_bowler else None

    return {
        "team1_pct": team1_pct,
        "team2_pct": team2_pct,
        "L": round(L, 4),
        "final_score": team1_pct,
        "model": "6-factor-live",
        "weights": {
            "score_vs_par": 0.30,
            "wickets_in_hand": 0.25,
            "recent_over_rate": 0.15,
            "bowlers_remaining": 0.15,
            "pre_match_base": 0.10,
            "match_situation_context": 0.05,
        },
        "breakdown": {
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
        },
        "innings": innings,
    }
