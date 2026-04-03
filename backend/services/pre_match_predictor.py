"""
Pre-Match Predictor — Gamble Consultant
========================================
Fetches real H2H (5 years), venue stats, and recent form via GPT-5.4 web search.
Runs algorithm stack: H2H Factor, Venue Factor, Form Factor, Squad Strength.
Combines via logistic model → calibrated probability → confidence %.
Results stored in MongoDB for reuse.
"""
import math
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def compute_prediction(stats: Dict) -> Dict:
    """
    Algorithm stack to compute win confidence from fetched stats.
    
    Factors:
      H2H (0.25) — Head-to-head win ratio last 5 years
      Venue (0.20) — Average score at venue per team
      Form (0.25) — Recent form (last 5 matches win %)
      Squad (0.20) — Squad strength (batting depth + bowling)
      Home (0.10) — Home advantage
    
    Returns calibrated probability and confidence.
    """
    h2h = stats.get("h2h", {})
    venue = stats.get("venue_stats", {})
    form = stats.get("form", {})
    squad = stats.get("squad_strength", {})

    # ── Factor 1: Head-to-Head (last 5 years) ──
    t1_h2h_wins = h2h.get("team1_wins", 0)
    t2_h2h_wins = h2h.get("team2_wins", 0)
    total_h2h = t1_h2h_wins + t2_h2h_wins
    if total_h2h > 0:
        h2h_ratio = t1_h2h_wins / total_h2h
    else:
        h2h_ratio = 0.5
    # Convert to logit component: centered at 0
    h2h_logit = 2.0 * (h2h_ratio - 0.5)  # [-1, 1]

    # ── Factor 2: Venue Performance ──
    t1_venue_avg = venue.get("team1_avg_score", 160)
    t2_venue_avg = venue.get("team2_avg_score", 160)
    venue_diff = (t1_venue_avg - t2_venue_avg) / max(t1_venue_avg, t2_venue_avg, 1)
    venue_logit = 2.5 * venue_diff  # scaled

    t1_venue_win_pct = venue.get("team1_win_pct", 50) / 100
    t2_venue_win_pct = venue.get("team2_win_pct", 50) / 100
    venue_win_logit = 1.5 * (t1_venue_win_pct - t2_venue_win_pct)

    # ── Factor 3: Recent Form (last 5 matches) ──
    t1_form_pct = form.get("team1_last5_win_pct", 50) / 100
    t2_form_pct = form.get("team2_last5_win_pct", 50) / 100
    form_logit = 2.0 * (t1_form_pct - t2_form_pct)

    # ── Factor 4: Squad Strength ──
    t1_bat = squad.get("team1_batting_rating", 50) / 100
    t2_bat = squad.get("team2_batting_rating", 50) / 100
    t1_bowl = squad.get("team1_bowling_rating", 50) / 100
    t2_bowl = squad.get("team2_bowling_rating", 50) / 100
    t1_strength = 0.55 * t1_bat + 0.45 * t1_bowl
    t2_strength = 0.55 * t2_bat + 0.45 * t2_bowl
    squad_logit = 3.0 * (t1_strength - t2_strength)

    # ── Factor 5: Home Advantage ──
    home_logit = 0
    if venue.get("is_team1_home"):
        home_logit = 0.25
    elif venue.get("is_team2_home"):
        home_logit = -0.25

    # ── Weighted Combination ──
    combined_logit = (
        0.25 * h2h_logit +
        0.20 * (venue_logit + venue_win_logit) / 2 +
        0.25 * form_logit +
        0.20 * squad_logit +
        0.10 * home_logit
    )

    # Sigmoid
    raw_prob = 1 / (1 + math.exp(-combined_logit * 3.5))
    raw_prob = max(0.08, min(0.92, raw_prob))

    # Platt calibration (compress toward center slightly)
    cal_prob = 1 / (1 + math.exp(-1.2 * (raw_prob - 0.5) * 4))
    cal_prob = max(0.05, min(0.95, cal_prob))

    # Confidence = how sure the model is (higher when further from 50/50)
    model_confidence = round(50 + abs(cal_prob - 0.5) * 100, 1)

    # Factor breakdown
    factors = {
        "h2h": {
            "weight": 0.25,
            "team1_wins": t1_h2h_wins,
            "team2_wins": t2_h2h_wins,
            "total_matches": total_h2h,
            "no_result": h2h.get("no_result", 0),
            "ratio": round(h2h_ratio, 3),
            "logit_contribution": round(0.25 * h2h_logit, 4),
        },
        "venue": {
            "weight": 0.20,
            "team1_avg_score": t1_venue_avg,
            "team2_avg_score": t2_venue_avg,
            "team1_win_pct": venue.get("team1_win_pct", 50),
            "team2_win_pct": venue.get("team2_win_pct", 50),
            "team1_matches_at_venue": venue.get("team1_matches_at_venue", 0),
            "team2_matches_at_venue": venue.get("team2_matches_at_venue", 0),
            "is_team1_home": venue.get("is_team1_home", False),
            "is_team2_home": venue.get("is_team2_home", False),
            "logit_contribution": round(0.20 * (venue_logit + venue_win_logit) / 2, 4),
        },
        "form": {
            "weight": 0.25,
            "team1_last5_wins": form.get("team1_last5_wins", 0),
            "team1_last5_losses": form.get("team1_last5_losses", 0),
            "team1_last5_win_pct": form.get("team1_last5_win_pct", 50),
            "team2_last5_wins": form.get("team2_last5_wins", 0),
            "team2_last5_losses": form.get("team2_last5_losses", 0),
            "team2_last5_win_pct": form.get("team2_last5_win_pct", 50),
            "logit_contribution": round(0.25 * form_logit, 4),
        },
        "squad": {
            "weight": 0.20,
            "team1_batting_rating": squad.get("team1_batting_rating", 50),
            "team1_bowling_rating": squad.get("team1_bowling_rating", 50),
            "team2_batting_rating": squad.get("team2_batting_rating", 50),
            "team2_bowling_rating": squad.get("team2_bowling_rating", 50),
            "logit_contribution": round(0.20 * squad_logit, 4),
        },
        "home_advantage": {
            "weight": 0.10,
            "logit_contribution": round(0.10 * home_logit, 4),
        },
    }

    return {
        "team1_win_prob": round(cal_prob * 100, 1),
        "team2_win_prob": round((1 - cal_prob) * 100, 1),
        "confidence": model_confidence,
        "raw_probability": round(raw_prob, 4),
        "calibrated_probability": round(cal_prob, 4),
        "combined_logit": round(combined_logit, 4),
        "factors": factors,
    }
