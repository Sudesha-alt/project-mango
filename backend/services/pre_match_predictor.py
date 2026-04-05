"""
Pre-Match Predictor — Baatu - 11
==================================
11-factor prediction model using web-scraped real stats.
Factors: H2H, Venue, Form, Squad, Home, Toss, Pitch, Matchups, Death Overs, Powerplay, Momentum.
"""
import math
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def compute_prediction(stats: Dict, playing_xi: Dict = None, squad_data: Dict = None) -> Dict:
    """
    11-factor algorithm to compute win probability.

    Weights:
      H2H         (0.12) — Head-to-head record 2021-2026
      Venue        (0.10) — Team venue performance + player-level venue stats
      Form         (0.12) — Recent team + player form (sample-size damped)
      Squad        (0.10) — Batting depth + bowling attack quality
      Home         (0.06) — Home ground advantage
      Toss Impact  (0.08) — Historical toss-win correlation at venue
      Pitch/Conds  (0.10) — Pitch type, dew, pace/spin assistance
      Key Matchups (0.10) — Batter vs bowler head-to-head records
      Death Overs  (0.08) — Performance in overs 16-20
      Powerplay    (0.08) — Performance in overs 1-6
      Momentum     (0.06) — Win/loss streaks and extended form
    """
    h2h = stats.get("h2h", {})
    venue = stats.get("venue_stats", {})
    form = stats.get("form", {})
    squad = stats.get("squad_strength", {})
    toss = stats.get("toss", {})
    pitch = stats.get("pitch_conditions", {})
    matchups = stats.get("key_matchups", {})
    death = stats.get("death_overs", {})
    pp = stats.get("powerplay", {})
    momentum = stats.get("momentum", {})

    # ── Squad strength override from actual 2026 roster ──
    if squad_data:
        # squad_data is {team_name: [players]} — remap to {team1: [...], team2: [...]}
        squad_names = list(squad_data.keys())
        remapped_squads = {
            "team1": squad_data.get(squad_names[0], []) if len(squad_names) > 0 else [],
            "team2": squad_data.get(squad_names[1], []) if len(squad_names) > 1 else [],
        }
        t1_rating, t2_rating = _compute_squad_ratings(remapped_squads, playing_xi)
        squad["team1_batting_rating"] = t1_rating["batting"]
        squad["team1_bowling_rating"] = t1_rating["bowling"]
        squad["team2_batting_rating"] = t2_rating["batting"]
        squad["team2_bowling_rating"] = t2_rating["bowling"]

    # ── Factor 1: Head-to-Head (0.12) ──
    t1_h2h_wins = h2h.get("team1_wins", 0)
    t2_h2h_wins = h2h.get("team2_wins", 0)
    total_h2h = t1_h2h_wins + t2_h2h_wins
    h2h_ratio = t1_h2h_wins / total_h2h if total_h2h > 0 else 0.5
    h2h_logit = 2.0 * (h2h_ratio - 0.5)

    # ── Factor 2: Venue Performance (0.10) ──
    t1_venue_avg = venue.get("team1_avg_score", 160)
    t2_venue_avg = venue.get("team2_avg_score", 160)
    venue_diff = (t1_venue_avg - t2_venue_avg) / max(t1_venue_avg, t2_venue_avg, 1)
    venue_logit = 2.5 * venue_diff
    t1_venue_win_pct = venue.get("team1_win_pct", 50) / 100
    t2_venue_win_pct = venue.get("team2_win_pct", 50) / 100
    venue_win_logit = 1.5 * (t1_venue_win_pct - t2_venue_win_pct)
    # Player-level venue overlay
    player_venue_logit = 0.0
    if playing_xi:
        t1_xi = playing_xi.get("team1_xi", [])
        t2_xi = playing_xi.get("team2_xi", [])
        t1_vs = _calc_player_venue_score(t1_xi)
        t2_vs = _calc_player_venue_score(t2_xi)
        if t1_vs > 0 or t2_vs > 0:
            total_vs = max(t1_vs + t2_vs, 1)
            player_venue_logit = 2.0 * ((t1_vs / total_vs) - 0.5)
            venue_logit = 0.4 * venue_logit + 0.6 * player_venue_logit
            venue_win_logit = 0.4 * venue_win_logit + 0.6 * player_venue_logit
    final_venue_logit = (venue_logit + venue_win_logit) / 2

    # ── Factor 3: Form (0.12, sample-size damped) ──
    t1_form_pct = form.get("team1_last5_win_pct", 50) / 100
    t2_form_pct = form.get("team2_last5_win_pct", 50) / 100
    t1_games = form.get("team1_last5_wins", 0) + form.get("team1_last5_losses", 0)
    t2_games = form.get("team2_last5_wins", 0) + form.get("team2_last5_losses", 0)
    min_games = min(t1_games, t2_games)
    damping = min(1.0, min_games / 5.0) if min_games > 0 else 0.0
    t1_form_adj = 0.5 + (t1_form_pct - 0.5) * damping
    t2_form_adj = 0.5 + (t2_form_pct - 0.5) * damping
    team_form_logit = 2.0 * (t1_form_adj - t2_form_adj)
    # Player buzz overlay
    player_form_logit = 0.0
    if playing_xi:
        t1_avg_buzz = _calc_avg_buzz(playing_xi.get("team1_xi", []))
        t2_avg_buzz = _calc_avg_buzz(playing_xi.get("team2_xi", []))
        if t1_avg_buzz > 0 or t2_avg_buzz > 0:
            player_form_logit = 1.5 * ((t1_avg_buzz - t2_avg_buzz) / 100)
            team_form_logit = 0.5 * team_form_logit + 0.5 * player_form_logit
    form_logit = team_form_logit

    # ── Factor 4: Squad Strength (0.10) ──
    t1_bat = squad.get("team1_batting_rating", 50) / 100
    t2_bat = squad.get("team2_batting_rating", 50) / 100
    t1_bowl = squad.get("team1_bowling_rating", 50) / 100
    t2_bowl = squad.get("team2_bowling_rating", 50) / 100
    t1_strength = 0.55 * t1_bat + 0.45 * t1_bowl
    t2_strength = 0.55 * t2_bat + 0.45 * t2_bowl
    squad_logit = 5.0 * (t1_strength - t2_strength)

    # ── Factor 5: Home Advantage (0.06) ──
    home_logit = 0
    if venue.get("is_team1_home"):
        home_logit = 0.3
    elif venue.get("is_team2_home"):
        home_logit = -0.3

    # ── Factor 6: Toss Impact (0.08) ──
    chase_friendly = toss.get("venue_chase_friendly", False)
    bat_first_win_pct = venue.get("bat_first_win_pct", 48) / 100
    toss_logit = 1.0 * (bat_first_win_pct - 0.5)

    # ── Factor 7: Pitch & Conditions (0.10) ──
    pitch_type = pitch.get("pitch_type", "balanced")
    dew_factor = pitch.get("dew_factor", 3) / 10
    # Calculate which team benefits more from pitch conditions based on squad composition
    t1_pace_strength = squad.get("team1_bowling_rating", 50) / 100
    t2_pace_strength = squad.get("team2_bowling_rating", 50) / 100
    # Higher pace/spin assist helps the better bowling side
    pitch_logit = 0.0
    if pitch_type == "bowling":
        pitch_logit = 1.5 * (t1_pace_strength - t2_pace_strength)
    elif pitch_type == "batting":
        pitch_logit = 1.0 * (t1_bat - t2_bat)
    else:
        pitch_logit = 0.5 * ((t1_strength - t2_strength))
    # Dew: high dew benefits chasing team → slight general neutralizer
    dew_logit = -0.2 * dew_factor if dew_factor > 0.4 else 0.0

    # ── Factor 8: Key Matchups (0.10) — filtered to current squad ──
    t1_matchups_raw = matchups.get("team1_batters_vs_team2_bowlers", [])
    t2_matchups_raw = matchups.get("team2_batters_vs_team1_bowlers", [])
    if squad_data:
        squad_names = list(squad_data.keys())
        t1_players = squad_data.get(squad_names[0], []) if len(squad_names) > 0 else []
        t2_players = squad_data.get(squad_names[1], []) if len(squad_names) > 1 else []
        t1_names = {p.get("name", "").lower() for p in t1_players}
        t2_names = {p.get("name", "").lower() for p in t2_players}
        t1_matchups_raw = [m for m in t1_matchups_raw if _name_in_squad(m.get("batter",""), t1_names) and _name_in_squad(m.get("bowler",""), t2_names)]
        t2_matchups_raw = [m for m in t2_matchups_raw if _name_in_squad(m.get("batter",""), t2_names) and _name_in_squad(m.get("bowler",""), t1_names)]
    t1_matchup_score = _calc_matchup_score(t1_matchups_raw)
    t2_matchup_score = _calc_matchup_score(t2_matchups_raw)
    total_matchup = max(t1_matchup_score + t2_matchup_score, 1)
    matchup_logit = 2.0 * ((t1_matchup_score / total_matchup) - 0.5) if total_matchup > 1 else 0.0

    # ── Factor 9: Death Overs (0.08) ──
    t1_death_net = (death.get("team1_avg_death_score", 45) - death.get("team1_avg_death_conceded", 48))
    t2_death_net = (death.get("team2_avg_death_score", 45) - death.get("team2_avg_death_conceded", 48))
    death_logit = 1.5 * ((t1_death_net - t2_death_net) / max(abs(t1_death_net) + abs(t2_death_net), 1))
    # Post-auction: cap stale death overs data influence
    if squad_data:
        death_logit = max(-0.5, min(0.5, death_logit))

    # ── Factor 10: Powerplay (0.08) ──
    t1_pp_score = pp.get("team1_avg_pp_score", 48)
    t2_pp_score = pp.get("team2_avg_pp_score", 48)
    t1_pp_wkts = pp.get("team1_avg_pp_wickets_lost", 1.2)
    t2_pp_wkts = pp.get("team2_avg_pp_wickets_lost", 1.2)
    # Higher score + fewer wickets = better powerplay
    t1_pp_quality = t1_pp_score / max(t1_pp_wkts, 0.5)
    t2_pp_quality = t2_pp_score / max(t2_pp_wkts, 0.5)
    pp_logit = 1.0 * ((t1_pp_quality - t2_pp_quality) / max(t1_pp_quality + t2_pp_quality, 1))

    # ── Factor 11: Momentum (0.06) ──
    t1_streak = momentum.get("team1_current_streak", 0)
    t2_streak = momentum.get("team2_current_streak", 0)
    t1_l10 = momentum.get("team1_last10_wins", 5)
    t2_l10 = momentum.get("team2_last10_wins", 5)
    streak_logit = 0.3 * (t1_streak - t2_streak) / max(abs(t1_streak) + abs(t2_streak), 1)
    long_form_logit = 1.0 * ((t1_l10 - t2_l10) / 10)
    momentum_logit = 0.5 * streak_logit + 0.5 * long_form_logit

    # ── Weighted Combination ──
    # Post mega-auction season: squad composition matters most,
    # historical team-level stats (death, powerplay, form, h2h) are less
    # reliable because squads have changed dramatically.
    is_post_auction = squad_data is not None  # indicates we have actual 2026 roster
    if is_post_auction:
        combined_logit = (
            0.03 * h2h_logit +          # minimal: old squads
            0.07 * final_venue_logit +   # venue still matters
            0.03 * form_logit +          # minimal: old squad results
            0.35 * squad_logit +         # DOMINANT: actual 2026 roster strength
            0.04 * home_logit +
            0.05 * toss_logit +
            0.10 * (pitch_logit + dew_logit) +
            0.15 * matchup_logit +       # current player matchups
            0.03 * death_logit +         # minimal: old squad data
            0.03 * pp_logit +            # minimal: old squad data
            0.12 * momentum_logit        # recent form signal
        )
    else:
        combined_logit = (
            0.12 * h2h_logit +
            0.10 * final_venue_logit +
            0.12 * form_logit +
            0.10 * squad_logit +
            0.06 * home_logit +
            0.08 * toss_logit +
            0.10 * (pitch_logit + dew_logit) +
            0.10 * matchup_logit +
            0.08 * death_logit +
            0.08 * pp_logit +
            0.06 * momentum_logit
        )

    # Sigmoid
    raw_prob = 1 / (1 + math.exp(-combined_logit * 3.5))
    raw_prob = max(0.08, min(0.92, raw_prob))

    # Platt calibration
    cal_prob = 1 / (1 + math.exp(-1.2 * (raw_prob - 0.5) * 4))
    cal_prob = max(0.05, min(0.95, cal_prob))

    model_confidence = round(50 + abs(cal_prob - 0.5) * 100, 1)

    factors = {
        "h2h": {
            "weight": 0.12,
            "team1_wins": t1_h2h_wins,
            "team2_wins": t2_h2h_wins,
            "total_matches": total_h2h,
            "no_result": h2h.get("no_result", 0),
            "ratio": round(h2h_ratio, 3),
            "logit_contribution": round(0.12 * h2h_logit, 4),
        },
        "venue": {
            "weight": 0.10,
            "team1_avg_score": t1_venue_avg,
            "team2_avg_score": t2_venue_avg,
            "team1_win_pct": venue.get("team1_win_pct", 50),
            "team2_win_pct": venue.get("team2_win_pct", 50),
            "team1_matches_at_venue": venue.get("team1_matches_at_venue", 0),
            "team2_matches_at_venue": venue.get("team2_matches_at_venue", 0),
            "is_team1_home": venue.get("is_team1_home", False),
            "is_team2_home": venue.get("is_team2_home", False),
            "player_venue_logit": round(player_venue_logit, 4),
            "logit_contribution": round(0.10 * final_venue_logit, 4),
        },
        "form": {
            "weight": 0.12,
            "team1_last5_wins": form.get("team1_last5_wins", 0),
            "team1_last5_losses": form.get("team1_last5_losses", 0),
            "team1_last5_win_pct": form.get("team1_last5_win_pct", 50),
            "team2_last5_wins": form.get("team2_last5_wins", 0),
            "team2_last5_losses": form.get("team2_last5_losses", 0),
            "team2_last5_win_pct": form.get("team2_last5_win_pct", 50),
            "damping": round(damping, 2),
            "player_form_logit": round(player_form_logit, 4),
            "logit_contribution": round(0.12 * form_logit, 4),
        },
        "squad": {
            "weight": 0.10,
            "team1_batting_rating": squad.get("team1_batting_rating", 50),
            "team1_bowling_rating": squad.get("team1_bowling_rating", 50),
            "team2_batting_rating": squad.get("team2_batting_rating", 50),
            "team2_bowling_rating": squad.get("team2_bowling_rating", 50),
            "logit_contribution": round(0.10 * squad_logit, 4),
        },
        "home_advantage": {
            "weight": 0.06,
            "logit_contribution": round(0.06 * home_logit, 4),
        },
        "toss_impact": {
            "weight": 0.08,
            "toss_winner_win_pct": toss.get("toss_winner_match_win_pct", 52),
            "bat_first_win_pct": venue.get("bat_first_win_pct", 48),
            "chase_friendly": chase_friendly,
            "logit_contribution": round(0.08 * toss_logit, 4),
        },
        "pitch_conditions": {
            "weight": 0.10,
            "pitch_type": pitch_type,
            "pace_assistance": pitch.get("pace_assistance", 5),
            "spin_assistance": pitch.get("spin_assistance", 5),
            "dew_factor": pitch.get("dew_factor", 3),
            "description": pitch.get("description", ""),
            "logit_contribution": round(0.10 * (pitch_logit + dew_logit), 4),
        },
        "key_matchups": {
            "weight": 0.10,
            "team1_matchup_score": round(t1_matchup_score, 2),
            "team2_matchup_score": round(t2_matchup_score, 2),
            "matchups_data": {
                "team1_vs_team2": t1_matchups_raw[:3],
                "team2_vs_team1": t2_matchups_raw[:3],
            },
            "logit_contribution": round(0.10 * matchup_logit, 4),
        },
        "death_overs": {
            "weight": 0.08,
            "team1_avg_score": death.get("team1_avg_death_score", 45),
            "team1_avg_conceded": death.get("team1_avg_death_conceded", 48),
            "team2_avg_score": death.get("team2_avg_death_score", 45),
            "team2_avg_conceded": death.get("team2_avg_death_conceded", 48),
            "team1_net": round(t1_death_net, 1),
            "team2_net": round(t2_death_net, 1),
            "logit_contribution": round(0.08 * death_logit, 4),
        },
        "powerplay": {
            "weight": 0.08,
            "team1_avg_score": pp.get("team1_avg_pp_score", 48),
            "team1_avg_wkts_lost": pp.get("team1_avg_pp_wickets_lost", 1.2),
            "team2_avg_score": pp.get("team2_avg_pp_score", 48),
            "team2_avg_wkts_lost": pp.get("team2_avg_pp_wickets_lost", 1.2),
            "logit_contribution": round(0.08 * pp_logit, 4),
        },
        "momentum": {
            "weight": 0.06,
            "team1_streak": t1_streak,
            "team2_streak": t2_streak,
            "team1_last10_wins": t1_l10,
            "team2_last10_wins": t2_l10,
            "logit_contribution": round(0.06 * momentum_logit, 4),
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


def _calc_matchup_score(matchups_list: list) -> float:
    """Calculate aggregate matchup advantage score from batter-vs-bowler records."""
    if not matchups_list:
        return 0.5  # neutral
    total_score = 0
    for m in matchups_list:
        runs = m.get("runs", 0)
        balls = m.get("balls", 1)
        dismissals = m.get("dismissals", 0)
        sr = m.get("sr", runs / max(balls, 1) * 100)
        # High SR with few dismissals = good for batter
        batter_advantage = (sr / 150) * (1 / max(dismissals + 0.5, 0.5))
        total_score += min(batter_advantage, 3.0)
    return total_score / max(len(matchups_list), 1)


def _calc_player_venue_score(players: list) -> float:
    """Aggregate venue performance score for a team's Playing XI."""
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
            score = 0.60 * min(runs / 100, 2.0) + 0.25 * min(avg / 50, 2.0) + 0.15 * min(sr / 150, 2.0)
            total += score
            counted += 1
        else:
            exp_runs = p.get("expected_runs", 15)
            total += 0.3 * min(exp_runs / 30, 1.5)
            counted += 1
    return total / max(counted, 1)


def _calc_avg_buzz(players: list) -> float:
    """Average buzz for a team's Playing XI."""
    if not players:
        return 50
    buzzes = []
    for p in players:
        bs = p.get("buzz_score")
        if bs is not None:
            buzzes.append((bs + 100) / 2)
        else:
            buzzes.append(p.get("buzz_confidence", 50))
    return sum(buzzes) / len(buzzes)


# ── Role-based squad strength ratings ──

ROLE_WEIGHTS = {
    "Batsman": {"batting": 9, "bowling": 1},
    "Wicketkeeper": {"batting": 7, "bowling": 0},
    "All-rounder": {"batting": 6, "bowling": 6},
    "Bowler": {"batting": 2, "bowling": 9},
}

STAR_PLAYERS = {
    # Batsmen
    "Virat Kohli": 96, "Rohit Sharma": 93, "Suryakumar Yadav": 92, "Shubman Gill": 90,
    "KL Rahul": 89, "Yashasvi Jaiswal": 90, "Rishabh Pant": 91, "Shreyas Iyer": 87,
    "Sanju Samson": 86, "Ruturaj Gaikwad": 87, "Rajat Patidar": 84, "Tilak Varma": 85,
    "Travis Head": 89, "Phil Salt": 88, "Jos Buttler": 90, "Heinrich Klaasen": 89,
    "Nicholas Pooran": 86, "Quinton de Kock": 85, "David Miller": 83,
    "Devdutt Padikkal": 82, "Ishan Kishan": 83, "Karun Nair": 82,
    # All-rounders
    "Hardik Pandya": 90, "Ravindra Jadeja": 89, "Marcus Stoinis": 86,
    "Axar Patel": 85, "Sunil Narine": 87, "Cameron Green": 85,
    "Sam Curran": 84, "Liam Livingstone": 83, "Mitchell Marsh": 84,
    "Venkatesh Iyer": 82, "Nitish Kumar Reddy": 82, "Krunal Pandya": 80,
    "Shivam Dube": 81, "Marco Jansen": 85, "Washington Sundar": 82,
    "Azmatullah Omarzai": 82, "Will Jacks": 83, "Jacob Bethell": 81,
    "Rashid Khan": 92, "Wanindu Hasaranga": 85,
    # Bowlers
    "Jasprit Bumrah": 97, "Mohammed Siraj": 84, "Arshdeep Singh": 86,
    "Yuzvendra Chahal": 85, "Kuldeep Yadav": 86, "Varun Chakaravarthy": 84,
    "Josh Hazlewood": 87, "Mitchell Starc": 89, "Trent Boult": 86,
    "Pat Cummins": 90, "Kagiso Rabada": 88, "Lockie Ferguson": 85,
    "Bhuvneshwar Kumar": 83, "Harshal Patel": 82, "Jofra Archer": 87,
    "Mohammed Shami": 86, "Matheesha Pathirana": 84, "Anrich Nortje": 84,
    "Ravi Bishnoi": 82, "Mayank Yadav": 82,
}


def _compute_squad_ratings(squad_data: dict, playing_xi: dict = None) -> tuple:
    """Compute batting/bowling ratings from actual 2026 squad roster.
    Returns ratings on a 0-100 scale where differences are meaningful."""
    results = {}
    for team_key in ["team1", "team2"]:
        players = squad_data.get(team_key, [])
        if not players:
            results[team_key] = {"batting": 50, "bowling": 50}
            continue

        # If playing XI available, use those 11; otherwise full squad
        xi_names = set()
        if playing_xi:
            xi_key = f"{team_key}_xi"
            for p in playing_xi.get(xi_key, []):
                xi_names.add(p.get("name", "").lower())

        bat_ratings = []
        bowl_ratings = []
        for p in players:
            name = p.get("name", "")
            if xi_names and name.lower() not in xi_names:
                continue
            role = p.get("role", "Batsman")
            base_rating = STAR_PLAYERS.get(name, 65)
            is_overseas = p.get("isOverseas", False)
            is_captain = p.get("isCaptain", False)
            overseas_bonus = 4 if is_overseas and base_rating >= 78 else 0
            captain_bonus = 3 if is_captain else 0
            player_rating = min(99, base_rating + overseas_bonus + captain_bonus)

            weights = ROLE_WEIGHTS.get(role, {"batting": 5, "bowling": 5})
            if weights["batting"] >= 6:
                bat_ratings.append(player_rating)
            if weights["bowling"] >= 6:
                bowl_ratings.append(player_rating)

        # Average of top contributors, scaled to 0-100
        bat_avg = sum(sorted(bat_ratings, reverse=True)[:6]) / min(6, max(len(bat_ratings), 1)) if bat_ratings else 50
        bowl_avg = sum(sorted(bowl_ratings, reverse=True)[:5]) / min(5, max(len(bowl_ratings), 1)) if bowl_ratings else 50

        results[team_key] = {"batting": round(bat_avg, 1), "bowling": round(bowl_avg, 1)}

    return results.get("team1", {"batting": 50, "bowling": 50}), results.get("team2", {"batting": 50, "bowling": 50})


def _get_squad_names(squad_data: dict, team_key: str) -> set:
    """Get set of lowercase player names for a team."""
    players = squad_data.get(team_key, [])
    return {p.get("name", "").lower() for p in players}


def _name_in_squad(name: str, squad_names: set) -> bool:
    """Check if a player name matches any name in the squad (fuzzy last-name match)."""
    name_lower = name.lower().strip()
    if name_lower in squad_names:
        return True
    # Try last name match
    parts = name_lower.split()
    if parts:
        last_name = parts[-1]
        for sn in squad_names:
            if last_name in sn:
                return True
    return False
