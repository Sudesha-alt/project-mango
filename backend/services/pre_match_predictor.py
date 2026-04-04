"""
Pre-Match Predictor — Gamble Consultant
========================================
Fetches real H2H (5 years), venue stats, recent form, and squad strength via GPT-5.4.
Now also incorporates player-level venue performance and individual form from Playing XI.
Combines via logistic model → calibrated probability → confidence %.
"""
import math
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def compute_prediction(stats: Dict, playing_xi: Dict = None) -> Dict:
    """
    Algorithm stack to compute win confidence from fetched stats.
    
    Factors:
      H2H (0.25) — Head-to-head win ratio 2021-2026
      Venue (0.20) — Player-level venue performance + team venue win %
      Form (0.25) — Individual player form + team form
      Squad (0.20) — Squad strength (batting + bowling quality)
      Home (0.10) — Home advantage
    
    If playing_xi is provided, venue and form factors use player-level data.
    """
    h2h = stats.get("h2h", {})
    venue = stats.get("venue_stats", {})
    form = stats.get("form", {})
    squad = stats.get("squad_strength", {})

    # ── Factor 1: Head-to-Head (2021-2026) ──
    t1_h2h_wins = h2h.get("team1_wins", 0)
    t2_h2h_wins = h2h.get("team2_wins", 0)
    total_h2h = t1_h2h_wins + t2_h2h_wins
    h2h_ratio = t1_h2h_wins / total_h2h if total_h2h > 0 else 0.5
    h2h_logit = 2.0 * (h2h_ratio - 0.5)

    # ── Factor 2: Venue Performance ──
    # Start with team-level venue stats
    t1_venue_avg = venue.get("team1_avg_score", 160)
    t2_venue_avg = venue.get("team2_avg_score", 160)
    venue_diff = (t1_venue_avg - t2_venue_avg) / max(t1_venue_avg, t2_venue_avg, 1)
    venue_logit = 2.5 * venue_diff

    t1_venue_win_pct = venue.get("team1_win_pct", 50) / 100
    t2_venue_win_pct = venue.get("team2_win_pct", 50) / 100
    venue_win_logit = 1.5 * (t1_venue_win_pct - t2_venue_win_pct)

    # Player-level venue overlay: if we have Playing XI venue stats, blend them in
    player_venue_logit = 0.0
    if playing_xi:
        t1_xi = playing_xi.get("team1_xi", [])
        t2_xi = playing_xi.get("team2_xi", [])
        t1_venue_score = _calc_player_venue_score(t1_xi)
        t2_venue_score = _calc_player_venue_score(t2_xi)
        if t1_venue_score > 0 or t2_venue_score > 0:
            total_vs = max(t1_venue_score + t2_venue_score, 1)
            player_venue_logit = 2.0 * ((t1_venue_score / total_vs) - 0.5)
            # Blend: 60% player-level, 40% team-level venue
            venue_logit = 0.4 * venue_logit + 0.6 * player_venue_logit
            venue_win_logit = 0.4 * venue_win_logit + 0.6 * player_venue_logit

    # ── Factor 3: Form (Individual + Team) ──
    t1_form_pct = form.get("team1_last5_win_pct", 50) / 100
    t2_form_pct = form.get("team2_last5_win_pct", 50) / 100
    team_form_logit = 2.0 * (t1_form_pct - t2_form_pct)

    # Player-level individual form: use buzz confidence as a proxy for form
    player_form_logit = 0.0
    if playing_xi:
        t1_xi = playing_xi.get("team1_xi", [])
        t2_xi = playing_xi.get("team2_xi", [])
        t1_avg_buzz = _calc_avg_buzz(t1_xi)
        t2_avg_buzz = _calc_avg_buzz(t2_xi)
        if t1_avg_buzz > 0 or t2_avg_buzz > 0:
            player_form_logit = 1.5 * ((t1_avg_buzz - t2_avg_buzz) / 100)
            # Blend: 50% player form, 50% team form
            team_form_logit = 0.5 * team_form_logit + 0.5 * player_form_logit

    form_logit = team_form_logit

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

    # Platt calibration
    cal_prob = 1 / (1 + math.exp(-1.2 * (raw_prob - 0.5) * 4))
    cal_prob = max(0.05, min(0.95, cal_prob))

    # Confidence
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
            "player_venue_logit": round(player_venue_logit, 4),
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
            "player_form_logit": round(player_form_logit, 4),
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
        "uses_player_data": playing_xi is not None,
        "factors": factors,
    }


def _calc_player_venue_score(players: list) -> float:
    """
    Calculate aggregate venue performance score for a team's Playing XI.
    Weights: runs_at_venue (60%) + avg_at_venue (25%) + sr_at_venue (15%)
    """
    if not players:
        return 0
    total = 0
    counted = 0
    for p in players:
        vs = p.get("venue_stats", {})
        matches = vs.get("matches_at_venue", 0)
        if matches > 0:
            runs = vs.get("runs_at_venue", 0)
            avg = vs.get("avg_at_venue", 15)
            sr = vs.get("sr_at_venue", 120)
            # Normalize: runs/100, avg/50, sr/150
            score = 0.60 * min(runs / 100, 2.0) + 0.25 * min(avg / 50, 2.0) + 0.15 * min(sr / 150, 2.0)
            total += score
            counted += 1
        else:
            # No venue data: use expected performance as proxy
            exp_runs = p.get("expected_runs", 15)
            total += 0.3 * min(exp_runs / 30, 1.5)
            counted += 1
    return total / max(counted, 1)


def _calc_avg_buzz(players: list) -> float:
    """Calculate average buzz confidence for a team's Playing XI."""
    if not players:
        return 50
    buzzes = [p.get("buzz_confidence", 50) for p in players]
    return sum(buzzes) / len(buzzes)
