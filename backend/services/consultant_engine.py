"""
Gamble Consultant — Layered Decision Engine
=============================================
Layer 1: Feature Engine
Layer 2: Pre-match Model (Logistic)
Layer 3: Live Win Probability (Feature-driven)
Layer 4: Score Simulation (Negative Binomial, 10K sims)
Layer 5: Calibration (Platt scaling)
Layer 6: Odds & Edge (overround removal, value signals)
"""
import math
import random
from typing import List, Dict, Optional
from scipy.stats import nbinom  # negative binomial


# ═══════════════════════════════════════════════════════════════
# LAYER 1: FEATURE ENGINE
# ═══════════════════════════════════════════════════════════════

def build_features(snapshot: Dict) -> Dict:
    """
    Generate all derived features from a raw match state snapshot.
    Phase-aware, role-aware features for model consumption.
    """
    innings = snapshot.get("innings", 1)
    score = snapshot.get("score", 0)
    wickets = snapshot.get("wickets_lost", 0)
    overs = snapshot.get("over", 0) + snapshot.get("ball", 0) / 6
    target = snapshot.get("target")
    balls_remaining = snapshot.get("balls_remaining", max(int((20 - overs) * 6), 0))
    venue = snapshot.get("venue", "")
    venue_par = snapshot.get("venue_par_score", 165)

    crr = score / max(overs, 0.1)
    rrr = 0
    if innings == 2 and target and balls_remaining > 0:
        required_runs = target - score
        rrr = (required_runs / balls_remaining) * 6

    # Phase flags
    phase_powerplay = 1 if overs < 6 else 0
    phase_middle = 1 if 6 <= overs < 15 else 0
    phase_death = 1 if overs >= 15 else 0

    # Wicket/resource ratios
    wickets_in_hand = 10 - wickets
    wickets_in_hand_ratio = wickets_in_hand / 10
    balls_per_wicket_remaining = balls_remaining / max(wickets_in_hand, 1)

    # Run rate delta
    rr_delta = crr - rrr if innings == 2 else crr - (venue_par / 20)

    # Pressure index (composite)
    pressure = 0
    if innings == 2 and target:
        if rrr > 0:
            pressure = min(rrr / crr, 3.0) if crr > 0 else 2.5
        if wickets >= 5:
            pressure *= 1.3
        if wickets >= 7:
            pressure *= 1.5
    else:
        # 1st innings pressure is about setting a good total
        if wickets >= 5 and overs < 15:
            pressure = 1.5
        elif wickets >= 3 and overs < 10:
            pressure = 1.2

    # Collapse risk
    collapse_risk = 0
    if wickets >= 5 and overs < 15:
        collapse_risk = 0.7
    elif wickets >= 7:
        collapse_risk = 0.9
    elif wickets >= 3 and overs < 8:
        collapse_risk = 0.4

    # Score deviation from par
    if innings == 1:
        expected_at_this_point = venue_par * (overs / 20)
        score_diff_to_par = score - expected_at_this_point
    else:
        if target:
            par_at_this_point = target * (1 - balls_remaining / 120)
            score_diff_to_par = score - par_at_this_point
        else:
            score_diff_to_par = 0

    # Batting depth index (simplified — higher wickets = less depth)
    batting_depth_index = max(0, (wickets_in_hand - 3) / 7)  # 0-1 scale

    # Momentum features (from ball history if available)
    ball_history = snapshot.get("ball_history", [])
    momentum_5 = _calc_momentum(ball_history, 5)
    momentum_10 = _calc_momentum(ball_history, 10)

    # Striker/bowler quality from snapshot
    striker = snapshot.get("striker", {})
    bowler = snapshot.get("bowler", {})
    striker_quality = striker.get("phase_sr", 125) / 150  # normalized
    bowler_quality = 1 - (bowler.get("economy", 8) / 15)  # lower economy = higher quality

    # Chase difficulty
    chase_difficulty = 0
    if innings == 2 and target:
        chase_difficulty = max(0, min(1, (rrr - 6) / 12))  # 0 at RRR=6, 1 at RRR=18

    return {
        "innings": innings,
        "score": score,
        "wickets_lost": wickets,
        "overs": round(overs, 1),
        "target": target,
        "balls_remaining": balls_remaining,
        "current_run_rate": round(crr, 2),
        "required_run_rate": round(rrr, 2),
        "run_rate_delta": round(rr_delta, 2),
        "wickets_in_hand": wickets_in_hand,
        "wickets_in_hand_ratio": round(wickets_in_hand_ratio, 2),
        "balls_per_wicket_remaining": round(balls_per_wicket_remaining, 1),
        "phase_powerplay": phase_powerplay,
        "phase_middle": phase_middle,
        "phase_death": phase_death,
        "phase": "powerplay" if phase_powerplay else ("middle" if phase_middle else "death"),
        "batting_depth_index": round(batting_depth_index, 2),
        "pressure_index": round(min(pressure, 3.0), 2),
        "collapse_risk": round(collapse_risk, 2),
        "score_diff_to_par": round(score_diff_to_par, 1),
        "venue_par_score": venue_par,
        "momentum_5_ball": momentum_5,
        "momentum_10_ball": momentum_10,
        "striker_quality_index": round(striker_quality, 2),
        "bowler_quality_index": round(bowler_quality, 2),
        "chase_difficulty": round(chase_difficulty, 2),
        "dew_indicator": 1 if snapshot.get("dew") else 0,
    }


def _calc_momentum(ball_history, window):
    if not ball_history or len(ball_history) < 2:
        return 0
    recent = ball_history[-window:]
    runs = sum(b.get("runs", 0) for b in recent)
    wickets = sum(1 for b in recent if b.get("isWicket"))
    boundaries = sum(1 for b in recent if b.get("runs", 0) >= 4)
    raw = runs - wickets * 10 + boundaries * 3
    return round(max(-1, min(1, raw / (window * 3))), 2)


# ═══════════════════════════════════════════════════════════════
# LAYER 2: PRE-MATCH MODEL (Logistic)
# ═══════════════════════════════════════════════════════════════

def pre_match_probability(
    team_strength: float = 0.0,       # T: [-1, 1] team rating difference
    venue_advantage: float = 0.0,     # V: [-0.5, 0.5] home/away
    toss_effect: float = 0.0,         # X: [-0.3, 0.3] toss + batting first/second
    lineup_depth: float = 0.0,        # L: [-1, 1] batting depth diff
    bowling_strength: float = 0.0,    # B: [-1, 1] bowling attack diff
    alpha: float = 0.0,               # intercept
) -> float:
    """P(win) = σ(α + T + V + X + L + B)"""
    logit = alpha + team_strength + venue_advantage + toss_effect + lineup_depth + bowling_strength
    prob = 1 / (1 + math.exp(-logit))
    return round(max(0.05, min(0.95, prob)), 4)


def compute_team_factors(team_data: Dict, opponent_data: Dict, venue: str, toss_winner: str = None) -> Dict:
    """Compute T, V, X, L, B from team data for the pre-match model."""
    # Team strength from squad quality (simplified)
    t1_rating = team_data.get("rating", 50)
    t2_rating = opponent_data.get("rating", 50)
    T = (t1_rating - t2_rating) / 50  # normalized [-1, 1]

    # Venue advantage (home teams get a boost)
    V = 0.15 if team_data.get("home_venue") == venue else -0.05

    # Toss effect
    X = 0.1 if toss_winner == team_data.get("name") else -0.05

    # Lineup depth (count of quality batsmen)
    t1_depth = team_data.get("batting_depth", 6)
    t2_depth = opponent_data.get("batting_depth", 6)
    L = (t1_depth - t2_depth) / 5  # normalized

    # Bowling strength
    t1_bowl = team_data.get("bowling_rating", 50)
    t2_bowl = opponent_data.get("bowling_rating", 50)
    B = (t1_bowl - t2_bowl) / 50

    return {"T": round(T, 3), "V": round(V, 3), "X": round(X, 3),
            "L": round(L, 3), "B": round(B, 3)}


# ═══════════════════════════════════════════════════════════════
# LAYER 3: LIVE WIN PROBABILITY (Feature-driven)
# ═══════════════════════════════════════════════════════════════

def live_win_probability(features: Dict) -> float:
    """
    Feature-driven live probability using logistic combination.
    Replaces hardcoded sigmoid. Uses all computed features.
    """
    innings = features.get("innings", 1)

    if innings == 1:
        return _live_prob_first_innings(features)
    return _live_prob_chase(features)


def _live_prob_first_innings(f: Dict) -> float:
    """1st innings: probability of setting a winning total."""
    score_par = f.get("score_diff_to_par", 0)
    depth = f.get("batting_depth_index", 0.5)
    phase_death = f.get("phase_death", 0)
    crr = f.get("current_run_rate", 7.5)
    collapse = f.get("collapse_risk", 0)
    momentum = f.get("momentum_10_ball", 0)
    venue_par = f.get("venue_par_score", 165)

    # Logistic combination of features
    logit = (
        0.0 +                                    # intercept
        0.012 * score_par +                       # ahead of par = good
        0.8 * depth +                             # more depth = good
        0.3 * (crr - 8) / 4 +                   # high run rate = good
        -1.2 * collapse +                         # collapse = bad
        0.4 * momentum +                          # positive momentum = good
        0.15 * phase_death * (crr - 10) / 5      # death overs scoring
    )
    prob = 1 / (1 + math.exp(-logit))
    return round(max(0.05, min(0.95, prob)), 4)


def _live_prob_chase(f: Dict) -> float:
    """2nd innings: probability of successful chase."""
    rrr = f.get("required_run_rate", 8)
    crr = f.get("current_run_rate", 7)
    wk_ratio = f.get("wickets_in_hand_ratio", 0.8)
    balls_left = f.get("balls_remaining", 60)
    pressure = f.get("pressure_index", 1.0)
    depth = f.get("batting_depth_index", 0.5)
    chase_diff = f.get("chase_difficulty", 0.3)
    momentum = f.get("momentum_10_ball", 0)
    collapse = f.get("collapse_risk", 0)
    dew = f.get("dew_indicator", 0)
    score = f.get("score", 0)
    target = f.get("target", 170)

    if score >= target:
        return 1.0
    if wk_ratio <= 0 or balls_left <= 0:
        return 0.0

    # Rate comparison
    rate_advantage = (crr - rrr) / max(rrr, 1) if rrr > 0 else 0.5

    logit = (
        0.0 +
        1.5 * rate_advantage +                    # ahead of rate = good
        1.8 * wk_ratio +                          # wickets in hand
        0.003 * balls_left +                      # more balls = good
        -0.6 * pressure +                         # high pressure = bad
        0.5 * depth +                             # batting depth
        -1.0 * chase_diff +                       # harder chase = bad
        0.5 * momentum +                          # momentum
        -1.5 * collapse +                         # collapse risk
        0.2 * dew                                 # dew helps chasing
    )
    prob = 1 / (1 + math.exp(-logit))
    return round(max(0.03, min(0.97, prob)), 4)


# ═══════════════════════════════════════════════════════════════
# LAYER 4: SCORE SIMULATION (Negative Binomial, 10K sims)
# ═══════════════════════════════════════════════════════════════

def negative_binomial_innings(
    mean_score: float,
    variance_factor: float = 1.4,
    n_samples: int = 10000,
) -> List[int]:
    """
    Sample innings totals from negative binomial distribution.
    NB is right-skewed, matching real cricket score distributions.
    Mean = mean_score, Variance = mean_score * variance_factor
    """
    if mean_score <= 0:
        return [0] * n_samples

    var = mean_score * variance_factor
    # NB parameterization: n = mean^2 / (var - mean), p = mean / var
    if var <= mean_score:
        var = mean_score * 1.1  # ensure var > mean for NB
    n_param = (mean_score ** 2) / (var - mean_score)
    p_param = mean_score / var
    n_param = max(n_param, 1)
    p_param = max(0.01, min(p_param, 0.99))

    samples = nbinom.rvs(n_param, 1 - p_param, size=n_samples).tolist()
    # Clamp to reasonable cricket range
    return [max(50, min(300, s)) for s in samples]


def simulate_match(
    team1_mean: float,
    team2_mean: float,
    team1_var_factor: float = 1.4,
    team2_var_factor: float = 1.5,  # chasing has more variance
    venue_par: float = 165,
    n_sims: int = 10000,
    phase_adj: Dict = None,
) -> Dict:
    """
    Full match simulation using negative binomial per innings.
    Returns win probabilities, score ranges, and distributions.
    """
    t1_scores = negative_binomial_innings(team1_mean, team1_var_factor, n_sims)
    t2_base_scores = negative_binomial_innings(team2_mean, team2_var_factor, n_sims)

    # Chase adjustment: team 2 is affected by team 1's score
    team1_wins = 0
    t2_adjusted = []
    for i in range(n_sims):
        t1 = t1_scores[i]
        t2_base = t2_base_scores[i]
        # Chase pressure: if target is high, slightly reduce expected score
        if t1 > venue_par * 1.1:
            chase_penalty = 1 - (t1 - venue_par) / (venue_par * 3)
            t2 = int(t2_base * max(0.7, chase_penalty))
        else:
            chase_bonus = 1 + (venue_par - t1) / (venue_par * 4)
            t2 = int(t2_base * min(1.15, chase_bonus))
        t2 = max(50, min(300, t2))
        t2_adjusted.append(t2)
        if t1 > t2:
            team1_wins += 1

    t1_sorted = sorted(t1_scores)
    t2_sorted = sorted(t2_adjusted)
    prob = team1_wins / n_sims

    return {
        "team1_win_prob": round(prob, 4),
        "team2_win_prob": round(1 - prob, 4),
        "simulations": n_sims,
        "team1_scores": {
            "mean": round(sum(t1_scores) / n_sims, 1),
            "median": t1_sorted[n_sims // 2],
            "p10": t1_sorted[int(n_sims * 0.1)],
            "p25": t1_sorted[int(n_sims * 0.25)],
            "p50": t1_sorted[n_sims // 2],
            "p75": t1_sorted[int(n_sims * 0.75)],
            "p90": t1_sorted[int(n_sims * 0.9)],
        },
        "team2_scores": {
            "mean": round(sum(t2_adjusted) / n_sims, 1),
            "median": t2_sorted[n_sims // 2],
            "p10": t2_sorted[int(n_sims * 0.1)],
            "p25": t2_sorted[int(n_sims * 0.25)],
            "p50": t2_sorted[n_sims // 2],
            "p75": t2_sorted[int(n_sims * 0.75)],
            "p90": t2_sorted[int(n_sims * 0.9)],
        },
    }


# ═══════════════════════════════════════════════════════════════
# LAYER 5: CALIBRATION (Platt Scaling)
# ═══════════════════════════════════════════════════════════════

def platt_calibrate(raw_prob: float, a: float = -1.2, b: float = 0.1) -> float:
    """
    Platt scaling: P_cal = 1 / (1 + exp(a * raw + b))
    Parameters a, b should be fit on holdout data.
    Defaults provide mild compression toward 0.5 (reduces overconfidence).
    """
    logit = a * raw_prob + b
    cal = 1 / (1 + math.exp(logit))
    return round(max(0.03, min(0.97, cal)), 4)


def calibrate_probability(raw_prob: float) -> Dict:
    """Apply calibration and compute uncertainty band."""
    calibrated = platt_calibrate(raw_prob)
    # Uncertainty band: wider when probability is near 0.5, narrower at extremes
    base_uncertainty = 0.08
    uncertainty = base_uncertainty * (1 - abs(calibrated - 0.5) * 2)
    uncertainty = max(0.02, uncertainty)

    confidence = 1 - uncertainty * 2
    return {
        "raw": round(raw_prob, 4),
        "calibrated": calibrated,
        "uncertainty_band": {
            "low": round(max(0.01, calibrated - uncertainty), 4),
            "high": round(min(0.99, calibrated + uncertainty), 4),
        },
        "confidence": round(max(0.3, min(0.95, confidence)), 2),
    }


# ═══════════════════════════════════════════════════════════════
# LAYER 6: ODDS & EDGE
# ═══════════════════════════════════════════════════════════════

def remove_overround(odds_list: List[float]) -> List[float]:
    """
    Remove bookmaker overround to get true implied probabilities.
    Sum of implied probs > 1 means there's margin built in.
    """
    implied = [1 / o for o in odds_list if o > 0]
    total = sum(implied)
    if total <= 0:
        return implied
    return [round(p / total, 4) for p in implied]


def compute_odds_and_edge(
    calibrated_prob: float,
    market_odds: float = None,
    market_odds_opponent: float = None,
) -> Dict:
    """Full odds computation with overround removal and edge detection."""
    fair_odds = round(1 / calibrated_prob, 2) if calibrated_prob > 0 else 99.0
    opponent_prob = 1 - calibrated_prob
    fair_odds_opponent = round(1 / opponent_prob, 2) if opponent_prob > 0 else 99.0

    result = {
        "fair_probability": round(calibrated_prob * 100, 1),
        "fair_decimal_odds": fair_odds,
        "fair_odds_opponent": fair_odds_opponent,
    }

    if market_odds and market_odds > 1:
        raw_implied = 1 / market_odds

        # If we have both sides, remove overround
        if market_odds_opponent and market_odds_opponent > 1:
            normalized = remove_overround([market_odds, market_odds_opponent])
            market_prob = normalized[0]
            overround = round((1 / market_odds + 1 / market_odds_opponent) * 100, 1)
        else:
            market_prob = raw_implied
            overround = None

        edge = round((calibrated_prob - market_prob) * 100, 1)

        result.update({
            "market_decimal_odds": market_odds,
            "market_implied_probability": round(raw_implied * 100, 1),
            "normalized_market_probability": round(market_prob * 100, 1),
            "overround": overround,
            "edge_pct": edge,
        })

    return result


def classify_signal(
    edge_pct: float,
    confidence: float,
    calibrated_prob: float,
) -> Dict:
    """
    Classify the betting signal based on edge, confidence, and probability.
    Returns signal label and recommendation.
    """
    if confidence < 0.4:
        return {
            "signal": "WAIT_FOR_MORE_DATA",
            "recommendation": "Model confidence too low. Wait for more match data.",
            "color": "gray",
        }

    if edge_pct is None:
        return {
            "signal": "NO_MARKET",
            "recommendation": "No market odds provided. Enter bookmaker odds to compare.",
            "color": "gray",
        }

    if edge_pct >= 8:
        return {
            "signal": "STRONG_VALUE",
            "recommendation": "Strong edge detected. Model significantly disagrees with market.",
            "color": "green",
        }
    elif edge_pct >= 4:
        return {
            "signal": "VALUE",
            "recommendation": "Positive edge exists. Worth considering based on risk appetite.",
            "color": "lime",
        }
    elif edge_pct >= 1:
        return {
            "signal": "SMALL_EDGE",
            "recommendation": "Marginal edge. Proceed with caution.",
            "color": "yellow",
        }
    elif edge_pct >= -2:
        return {
            "signal": "NO_BET",
            "recommendation": "No meaningful edge. Market is fairly priced.",
            "color": "gray",
        }
    else:
        return {
            "signal": "AVOID",
            "recommendation": "Market is offering worse odds than fair value. Do not bet.",
            "color": "red",
        }


# ═══════════════════════════════════════════════════════════════
# MASTER: FULL CONSULTATION
# ═══════════════════════════════════════════════════════════════

def run_consultation(
    snapshot: Dict,
    player_predictions: List[Dict] = None,
    team1_data: Dict = None,
    team2_data: Dict = None,
    market_odds_team1: float = None,
    market_odds_team2: float = None,
    risk_tolerance: str = "balanced",  # "safe", "balanced", "aggressive"
) -> Dict:
    """
    Master function: runs the full layered decision engine.
    Returns structured output as specified in the blueprint.
    """
    team1 = snapshot.get("batting_team", snapshot.get("team1", "Team A"))
    team2 = snapshot.get("bowling_team", snapshot.get("team2", "Team B"))
    match_id = snapshot.get("match_id", "")

    # Layer 1: Features
    features = build_features(snapshot)

    # Layer 2 + 3: Probability
    if features["overs"] == 0 and features["score"] == 0:
        # Pre-match
        factors = compute_team_factors(
            team1_data or {}, team2_data or {},
            snapshot.get("venue", ""), snapshot.get("toss_winner")
        )
        raw_prob = pre_match_probability(**factors)
        model_source = "pre_match_logistic"
    else:
        raw_prob = live_win_probability(features)
        factors = None
        model_source = "live_feature_model"

    # Layer 4: Simulation
    venue_par = features.get("venue_par_score", 165)
    t1_mean = venue_par
    t2_mean = venue_par
    if player_predictions:
        t1_preds = [p for p in player_predictions if p.get("team") == team1]
        t2_preds = [p for p in player_predictions if p.get("team") == team2]
        if t1_preds:
            t1_mean = sum(p.get("predicted_runs", 15) for p in t1_preds[:11])
        if t2_preds:
            t2_mean = sum(p.get("predicted_runs", 15) for p in t2_preds[:11])

    sim = simulate_match(t1_mean, t2_mean, venue_par=venue_par, n_sims=10000)

    # Blend simulation probability with feature model
    sim_prob = sim["team1_win_prob"]
    blended_raw = raw_prob * 0.6 + sim_prob * 0.4

    # Layer 5: Calibration
    cal = calibrate_probability(blended_raw)

    # Layer 6: Odds & Edge
    odds_edge = compute_odds_and_edge(
        cal["calibrated"], market_odds_team1, market_odds_team2
    )

    # Signal classification
    edge = odds_edge.get("edge_pct")
    signal = classify_signal(edge or 0, cal["confidence"], cal["calibrated"])

    # Risk-adjusted recommendation
    if risk_tolerance == "safe" and signal["signal"] in ("SMALL_EDGE", "VALUE"):
        signal["recommendation"] += " But given your safe profile, consider skipping."
    elif risk_tolerance == "aggressive" and signal["signal"] == "SMALL_EDGE":
        signal["recommendation"] = "Small edge, but your aggressive profile suggests it could be worth a calculated punt."

    # Top drivers
    drivers = _identify_top_drivers(features, cal["calibrated"])

    # Player impact (if available)
    player_impact = []
    if player_predictions:
        for p in sorted(player_predictions, key=lambda x: x.get("predicted_runs", 0), reverse=True)[:8]:
            player_impact.append({
                "name": p.get("name"),
                "team": p.get("team"),
                "role": p.get("role"),
                "predicted_runs": p.get("predicted_runs", 0),
                "predicted_wickets": p.get("predicted_wickets", 0),
                "confidence": p.get("confidence", 50),
            })

    from datetime import datetime, timezone
    return {
        "match_id": match_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "team": team1,
        "opponent": team2,
        "win_probability": round(cal["calibrated"] * 100, 1),
        "odds_0_100": round(cal["calibrated"] * 100),
        "fair_decimal_odds": odds_edge["fair_decimal_odds"],
        "market_decimal_odds": odds_edge.get("market_decimal_odds"),
        "market_implied_probability": odds_edge.get("market_implied_probability"),
        "normalized_market_probability": odds_edge.get("normalized_market_probability"),
        "edge_pct": odds_edge.get("edge_pct"),
        "overround": odds_edge.get("overround"),
        "confidence": cal["confidence"],
        "calibration": cal,
        "value_signal": signal["signal"],
        "signal_color": signal["color"],
        "bet_recommendation": signal["recommendation"],
        "risk_tolerance": risk_tolerance,
        "uncertainty_band": cal["uncertainty_band"],
        "top_drivers": drivers,
        "features": features,
        "simulation": sim,
        "player_impact": player_impact,
        "model_source": model_source,
        "pre_match_factors": factors,
        "odds_detail": odds_edge,
    }


def _identify_top_drivers(features: Dict, prob: float) -> List[str]:
    """Identify the top factors driving the current prediction."""
    drivers = []
    f = features

    if f["innings"] == 2:
        if f["wickets_in_hand_ratio"] > 0.7:
            drivers.append("Wickets in hand — strong batting resources remaining")
        elif f["wickets_in_hand_ratio"] < 0.4:
            drivers.append("Low wickets — batting side under pressure")

        if f["required_run_rate"] > 12:
            drivers.append(f"Required rate at {f['required_run_rate']} RPO — very demanding")
        elif f["required_run_rate"] > 0 and f["current_run_rate"] > f["required_run_rate"]:
            drivers.append("Run rate ahead of required — batting side in control")

        if f["chase_difficulty"] > 0.6:
            drivers.append("High chase difficulty index")

        if f["pressure_index"] > 2:
            drivers.append("Extreme pressure situation")
    else:
        if f["score_diff_to_par"] > 15:
            drivers.append(f"Scoring {f['score_diff_to_par']:.0f} runs above venue par")
        elif f["score_diff_to_par"] < -15:
            drivers.append(f"Scoring {abs(f['score_diff_to_par']):.0f} runs below venue par")

    if f["collapse_risk"] > 0.5:
        drivers.append("Collapse risk detected — cluster of wickets")

    if f["momentum_10_ball"] > 0.3:
        drivers.append("Positive batting momentum in recent overs")
    elif f["momentum_10_ball"] < -0.3:
        drivers.append("Bowling-side momentum — scoring slowed")

    if f["batting_depth_index"] > 0.6:
        drivers.append("Deep batting lineup remaining")

    if f["phase"] == "death" and f["current_run_rate"] > 10:
        drivers.append("Death-overs acceleration")
    elif f["phase"] == "powerplay":
        drivers.append("Powerplay phase — field restrictions favoring batting")

    if f["dew_indicator"]:
        drivers.append("Dew factor — helps chasing side")

    return drivers[:6]  # Return top 6
