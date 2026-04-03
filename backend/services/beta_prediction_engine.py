"""
Beta Prediction Engine — PPL Board
===================================
A. Statistical Models: Poisson Distribution, Enhanced Monte Carlo (10K)
B. Player Prediction Engine (weighted formula)
C. Odds Calculation with house edge
D. Value Bet Alert System
E. Match Context Weighting & Momentum Alerts
"""
import math
import random
from typing import List, Dict, Optional


# ─── POISSON DISTRIBUTION ─────────────────────────────────────

def poisson_pmf(k, lam):
    """P(X=k) = (lambda^k * e^(-lambda)) / k!"""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    try:
        return (lam ** k) * math.exp(-lam) / math.factorial(k)
    except (OverflowError, ValueError):
        return 0.0


def predict_runs_distribution(run_rate, overs_remaining, context=None):
    """
    Predict total remaining runs distribution using Poisson.
    Returns distribution dict {runs: probability} and expected value (lambda).
    """
    lam = run_rate  # base expected runs per over
    if context:
        if context.get("powerplay"):
            lam *= 1.15
        elif context.get("death_overs"):
            lam *= 1.25
        elif context.get("middle_overs"):
            lam *= 0.95
        if context.get("chase") and context.get("pressure") == "high":
            lam *= 0.85  # pressure reduces scoring
    total_lam = max(lam * overs_remaining, 1)
    # Build distribution around expected value
    low = max(0, int(total_lam * 0.4))
    high = int(total_lam * 1.8) + 1
    dist = []
    for runs in range(low, high):
        p = poisson_pmf(runs, total_lam)
        if p > 0.001:
            dist.append({"runs": runs, "probability": round(p, 4)})
    return dist, round(total_lam, 1)


def predict_wickets_distribution(wicket_rate_per_over, overs_remaining):
    """Predict wickets distribution using Poisson."""
    lam = max(wicket_rate_per_over * overs_remaining, 0.1)
    dist = []
    for w in range(11):
        p = poisson_pmf(w, lam)
        if p > 0.001:
            dist.append({"wickets": w, "probability": round(p, 4)})
    return dist, round(lam, 2)


# ─── PLAYER PREDICTION ENGINE ─────────────────────────────────

def predict_player_performance(player_stats):
    """
    Weighted prediction formula:
    Final Score = 0.4 * Last5Avg + 0.3 * VenueAvg + 0.2 * OpponentAdjusted + 0.1 * FormMomentum
    
    Includes "luck biasness" — a random variance factor (+-12%) representing
    unpredictable match-day conditions (dew, toss, pitch behavior, player mood).
    """
    base_runs = (
        0.4 * player_stats.get("last5_avg_runs", 20) +
        0.3 * player_stats.get("venue_avg_runs", 18) +
        0.2 * player_stats.get("opponent_adj_runs", 16) +
        0.1 * player_stats.get("form_momentum_runs", 15)
    )
    base_wickets = (
        0.4 * player_stats.get("last5_avg_wickets", 0.5) +
        0.3 * player_stats.get("venue_avg_wickets", 0.4) +
        0.2 * player_stats.get("opponent_adj_wickets", 0.3) +
        0.1 * player_stats.get("form_momentum_wickets", 0.3)
    )

    # Apply luck biasness — random variance representing unpredictable factors
    luck_bias = random.uniform(0.88, 1.12)
    predicted_runs = round(base_runs * luck_bias, 1)
    predicted_wickets = round(base_wickets * random.uniform(0.85, 1.15), 1)

    # Confidence based on data availability and consistency
    confidence = _calculate_confidence(player_stats)

    return {
        "name": player_stats.get("name", "Unknown"),
        "team": player_stats.get("team", ""),
        "role": player_stats.get("role", "All-rounder"),
        "predicted_runs": max(0, predicted_runs),
        "predicted_wickets": max(0, predicted_wickets),
        "predicted_sr": player_stats.get("predicted_sr", 130),
        "predicted_economy": player_stats.get("predicted_economy", 8.0),
        "confidence": confidence,
        "luck_bias": round(luck_bias, 3),
    }


def _calculate_confidence(stats):
    """Calculate confidence % based on data quality."""
    base = 50
    if stats.get("last5_avg_runs", 0) > 0:
        base += 15
    if stats.get("venue_avg_runs", 0) > 0:
        base += 12
    if stats.get("opponent_adj_runs", 0) > 0:
        base += 10
    if stats.get("form_momentum_runs", 0) > 0:
        base += 8
    # Cap at 95
    consistency = stats.get("consistency", 0.7)
    return min(int(base * consistency), 95)


# ─── ENHANCED MONTE CARLO (10,000 SIMS) ───────────────────────

def monte_carlo_10k(
    team1_players: List[Dict],
    team2_players: List[Dict],
    venue_avg: float = 165,
    pitch_factor: float = 1.0,
    n_simulations: int = 10000,
):
    """
    10,000 match simulations using player-level predictions.
    Each player's score is sampled from normal distribution around their prediction.
    """
    team1_wins = 0
    team1_scores = []
    team2_scores = []

    for _ in range(n_simulations):
        # Simulate team 1 innings
        t1_score = 0
        t1_wickets = 0
        for p in team1_players[:11]:
            if t1_wickets >= 10:
                break
            predicted = p.get("predicted_runs", 15)
            variance = max(predicted * 0.6, 5)  # 60% variance, min 5
            actual = max(0, random.gauss(predicted * pitch_factor, variance))
            # Wicket chance
            if random.random() < 0.15:  # ~15% chance per batsman
                t1_wickets += 1
                actual *= random.uniform(0.1, 0.6)  # Reduced if out early
            t1_score += actual
        t1_score = max(80, min(300, t1_score))

        # Simulate team 2 innings (chasing)
        t2_score = 0
        t2_wickets = 0
        chase_pressure = 1.0 if t1_score <= venue_avg else max(0.75, 1 - (t1_score - venue_avg) / 200)
        for p in team2_players[:11]:
            if t2_wickets >= 10:
                break
            predicted = p.get("predicted_runs", 15) * chase_pressure
            variance = max(predicted * 0.6, 5)
            actual = max(0, random.gauss(predicted * pitch_factor, variance))
            if random.random() < 0.17:  # Slightly higher wicket chance when chasing
                t2_wickets += 1
                actual *= random.uniform(0.1, 0.6)
            t2_score += actual
            if t2_score > t1_score:
                break  # Chase complete
        t2_score = max(60, min(300, t2_score))

        team1_scores.append(round(t1_score))
        team2_scores.append(round(t2_score))
        if t1_score > t2_score:
            team1_wins += 1

    team1_prob = team1_wins / n_simulations
    t1_sorted = sorted(team1_scores)
    t2_sorted = sorted(team2_scores)

    return {
        "team1_win_prob": round(team1_prob, 4),
        "team2_win_prob": round(1 - team1_prob, 4),
        "team1_avg_score": round(sum(team1_scores) / n_simulations, 1),
        "team2_avg_score": round(sum(team2_scores) / n_simulations, 1),
        "team1_median_score": t1_sorted[n_simulations // 2],
        "team2_median_score": t2_sorted[n_simulations // 2],
        "team1_score_range": {
            "p10": t1_sorted[int(n_simulations * 0.1)],
            "p25": t1_sorted[int(n_simulations * 0.25)],
            "p50": t1_sorted[n_simulations // 2],
            "p75": t1_sorted[int(n_simulations * 0.75)],
            "p90": t1_sorted[int(n_simulations * 0.9)],
        },
        "team2_score_range": {
            "p10": t2_sorted[int(n_simulations * 0.1)],
            "p25": t2_sorted[int(n_simulations * 0.25)],
            "p50": t2_sorted[n_simulations // 2],
            "p75": t2_sorted[int(n_simulations * 0.75)],
            "p90": t2_sorted[int(n_simulations * 0.9)],
        },
        "simulations": n_simulations,
    }


# ─── ODDS CALCULATION ENGINE ──────────────────────────────────

def probability_to_decimal_odds(probability):
    """Convert probability to decimal odds."""
    if probability <= 0:
        return 99.0
    if probability >= 1:
        return 1.01
    return round(1 / probability, 2)


def odds_with_house_edge(probability, house_edge=0.10):
    """
    Final Odds = 1 / (Probability * (1 + house_edge))
    Ensures platform stays profitable.
    """
    adjusted = probability * (1 + house_edge)
    if adjusted >= 1:
        return 1.01
    return round(1 / adjusted, 2)


def calculate_odds_bundle(team1_prob, house_edge=0.10):
    """Full odds calculation for both teams."""
    team2_prob = 1 - team1_prob
    return {
        "team1": {
            "true_probability": round(team1_prob * 100, 1),
            "true_odds": probability_to_decimal_odds(team1_prob),
            "house_odds": odds_with_house_edge(team1_prob, house_edge),
            "implied_probability": round((1 / odds_with_house_edge(team1_prob, house_edge)) * 100, 1),
        },
        "team2": {
            "true_probability": round(team2_prob * 100, 1),
            "true_odds": probability_to_decimal_odds(team2_prob),
            "house_odds": odds_with_house_edge(team2_prob, house_edge),
            "implied_probability": round((1 / odds_with_house_edge(team2_prob, house_edge)) * 100, 1),
        },
        "house_edge_pct": house_edge * 100,
        "overround": round(
            (1 / odds_with_house_edge(team1_prob, house_edge) +
             1 / odds_with_house_edge(team2_prob, house_edge)) * 100, 1
        ),
    }


# ─── VALUE BET ALERT SYSTEM ───────────────────────────────────

def detect_value_bet(true_odds, offered_odds, threshold=0.10):
    """
    Trigger when: Offered Odds > True Odds * (1 + threshold)
    This means the market is offering better odds than the model thinks — value!
    """
    if not offered_odds or not true_odds or offered_odds <= 1 or true_odds <= 1:
        return None

    true_implied = 1 / true_odds
    offered_implied = 1 / offered_odds
    edge_pct = round((true_implied - offered_implied) * 100, 1)

    if offered_odds > true_odds * (1 + threshold):
        return {
            "type": "HIGH_VALUE",
            "message": "High value bet detected",
            "true_odds": true_odds,
            "offered_odds": offered_odds,
            "edge_pct": abs(edge_pct),
            "recommendation": "STRONG BET",
        }
    elif offered_odds > true_odds:
        return {
            "type": "MARKET_INEFFICIENCY",
            "message": "Market inefficiency",
            "true_odds": true_odds,
            "offered_odds": offered_odds,
            "edge_pct": abs(edge_pct),
            "recommendation": "CONSIDER",
        }
    return None


# ─── MATCH CONTEXT WEIGHTING ──────────────────────────────────

def get_match_context(overs, innings, wickets, runs=0, target=None):
    """Determine match phase and pressure for dynamic weighting."""
    ctx = {
        "powerplay": overs < 6,
        "middle_overs": 6 <= overs < 15,
        "death_overs": overs >= 15,
        "chase": innings == 2,
        "defend": innings == 1,
        "phase": "powerplay" if overs < 6 else ("middle" if overs < 15 else "death"),
    }

    if innings == 2 and target:
        remaining_overs = max(20 - overs, 0.1)
        rrr = (target - runs) / remaining_overs
        ctx["required_run_rate"] = round(rrr, 2)
        ctx["pressure"] = "critical" if rrr > 15 else "high" if rrr > 12 else "medium" if rrr > 8 else "low"
    else:
        crr = runs / max(overs, 0.1)
        ctx["current_run_rate"] = round(crr, 2)
        ctx["pressure"] = "medium"

    ctx["wickets_pressure"] = "critical" if wickets >= 7 else ("high" if wickets >= 5 else "normal")
    return ctx


# ─── MOMENTUM ALERTS ──────────────────────────────────────────

def generate_alerts(ball_history, match_context, market_odds=None, model_odds=None):
    """Generate real-time alerts based on match events and value bets."""
    alerts = []
    if not ball_history:
        return alerts

    recent = ball_history[-6:]  # Last over

    # Wicket cluster
    recent_wickets = sum(1 for b in recent if b.get("isWicket"))
    if recent_wickets >= 2:
        alerts.append({
            "type": "MOMENTUM_SHIFT",
            "severity": "high",
            "message": f"Momentum shift — {recent_wickets} wickets in last over!",
            "icon": "wicket",
        })

    # Boundary surge
    recent_boundaries = sum(1 for b in recent if b.get("runs", 0) >= 4)
    if recent_boundaries >= 3:
        alerts.append({
            "type": "BOUNDARY_SURGE",
            "severity": "medium",
            "message": f"Boundary surge — {recent_boundaries} boundaries in last over!",
            "icon": "boundary",
        })

    # RRR spike
    rrr = match_context.get("required_run_rate", 0)
    if rrr > 12:
        alerts.append({
            "type": "RRR_SPIKE",
            "severity": "high" if rrr > 15 else "medium",
            "message": f"Required rate at {rrr} RPO",
            "icon": "rate",
        })

    # Pressure index
    if match_context.get("wickets_pressure") == "critical":
        alerts.append({
            "type": "COLLAPSE_RISK",
            "severity": "high",
            "message": "Collapse risk — batting side under severe pressure",
            "icon": "pressure",
        })

    # Value bet alerts
    if market_odds and model_odds:
        for team_key in ["team1", "team2"]:
            market = market_odds.get(team_key)
            model = model_odds.get(team_key)
            if market and model:
                vb = detect_value_bet(model, market)
                if vb:
                    alerts.append({
                        "type": vb["type"],
                        "severity": "high" if vb["type"] == "HIGH_VALUE" else "medium",
                        "message": f"{vb['message']} on {team_key} — {vb['edge_pct']}% edge",
                        "icon": "value_bet",
                        "detail": vb,
                    })

    return alerts


# ─── FULL BETA PREDICTION BUNDLE ──────────────────────────────

def run_beta_prediction(
    player_predictions: List[Dict],
    team1_name: str,
    team2_name: str,
    runs: int = 0,
    wickets: int = 0,
    overs: float = 0,
    target: Optional[int] = None,
    innings: int = 1,
    venue_avg: float = 165,
    ball_history: Optional[List[Dict]] = None,
    market_team1_odds: Optional[float] = None,
    market_team2_odds: Optional[float] = None,
):
    """
    Master function: runs all beta prediction models and returns a complete bundle.
    """
    # Split players by team
    team1_players = [p for p in player_predictions if p.get("team") == team1_name]
    team2_players = [p for p in player_predictions if p.get("team") == team2_name]

    if not team1_players:
        team1_players = player_predictions[:len(player_predictions) // 2]
    if not team2_players:
        team2_players = player_predictions[len(player_predictions) // 2:]

    # 1. Match context
    context = get_match_context(overs, innings, wickets, runs, target)

    # 2. Poisson predictions
    crr = runs / max(overs, 0.1) if overs > 0 else 7.5
    overs_remaining = max(20 - overs, 0)
    runs_dist, expected_runs = predict_runs_distribution(crr, overs_remaining, context)
    wicket_rate = wickets / max(overs, 0.1) if overs > 0 else 0.5
    wickets_dist, expected_wickets = predict_wickets_distribution(wicket_rate, overs_remaining)

    # 3. Player predictions (apply formula)
    player_results = [predict_player_performance(p) for p in player_predictions]

    # 4. Monte Carlo 10K
    mc_result = monte_carlo_10k(
        team1_players, team2_players,
        venue_avg=venue_avg,
        pitch_factor=1.0,
        n_simulations=10000,
    )

    # 5. Odds engine
    odds_bundle = calculate_odds_bundle(mc_result["team1_win_prob"], house_edge=0.10)

    # 6. Alerts
    market_odds_map = {}
    model_odds_map = {}
    if market_team1_odds:
        market_odds_map["team1"] = market_team1_odds
        model_odds_map["team1"] = odds_bundle["team1"]["true_odds"]
    if market_team2_odds:
        market_odds_map["team2"] = market_team2_odds
        model_odds_map["team2"] = odds_bundle["team2"]["true_odds"]

    alerts = generate_alerts(
        ball_history or [],
        context,
        market_odds=market_odds_map,
        model_odds=model_odds_map,
    )

    # 7. Value bet check (direct)
    value_bets = []
    if market_team1_odds:
        vb = detect_value_bet(odds_bundle["team1"]["true_odds"], market_team1_odds)
        if vb:
            vb["team"] = team1_name
            value_bets.append(vb)
    if market_team2_odds:
        vb = detect_value_bet(odds_bundle["team2"]["true_odds"], market_team2_odds)
        if vb:
            vb["team"] = team2_name
            value_bets.append(vb)

    return {
        "match_context": context,
        "poisson": {
            "runs_distribution": runs_dist[:20],
            "expected_remaining_runs": expected_runs,
            "wickets_distribution": wickets_dist,
            "expected_remaining_wickets": expected_wickets,
            "projected_total": round(runs + expected_runs, 0) if innings == 1 else None,
        },
        "player_predictions": player_results,
        "monte_carlo": mc_result,
        "odds": odds_bundle,
        "alerts": alerts,
        "value_bets": value_bets,
    }
