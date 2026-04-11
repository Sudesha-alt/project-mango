import math
import random
from typing import Optional, List, Dict

VENUE_AVG = 165  # Default T20 venue average, can be overridden

# ─── ALGORITHM 1: SIGMOID / RRR PRESSURE INDEX ──────────────

def pressure_index(runs, wickets, overs, target, innings, venue_avg=VENUE_AVG, total_overs=20):
    def sigmoid(x):
        return 1.0 / (1.0 + math.exp(-x))

    if innings == 1:
        balls = int(overs) * 6 + round((overs % 1) * 10)  # cricket notation: 15.3 = 15 overs, 3 balls
        if balls == 0:
            return 0.5
        projected = (runs / balls) * 120  # extrapolate to 120 balls
        deviation = (projected - venue_avg) / venue_avg if venue_avg > 0 else 0
        wickets_factor = (10 - wickets) / 10
        batting_favor = 50 + deviation * 40
        prob = batting_favor + wickets_factor * 10 - 5
        return round(max(min(prob, 80), 20) / 100, 4)

    # 2nd innings
    if target is None or target == 0:
        return 0.5
    remaining_runs = target - runs
    if remaining_runs <= 0:
        return 1.0
    overs_remaining = total_overs - overs
    wickets_in_hand = 10 - wickets
    if wickets_in_hand <= 0 or overs_remaining <= 0:
        return 0.0

    crr = runs / overs if overs > 0 else 0
    rrr = remaining_runs / overs_remaining if overs_remaining > 0 else 999
    rrr_ratio = crr / rrr if rrr > 0 else 2.0
    wickets_factor = wickets_in_hand / 10
    resource_pct = (overs_remaining / total_overs) * wickets_factor

    raw = sigmoid(3.0 * (rrr_ratio - 1))
    prob = raw * 0.65 + resource_pct * 0.35
    return round(max(min(prob, 0.97), 0.03), 4)


# ─── ALGORITHM 2: DLS-INSPIRED RESOURCE MODEL ───────────────

# Build 21x11 resource table: Z[overs_remaining][wickets_in_hand]
DLS_TABLE = {}

def _build_dls_table():
    for o in range(21):  # 0 to 20 overs remaining
        for w in range(11):  # 0 to 10 wickets in hand
            if o == 0 or w == 0:
                DLS_TABLE[(o, w)] = 0.0
            else:
                L = 0.04 + 0.015 * (w / 10)
                val = 100.0 * (1.0 - math.exp(-L * o))
                DLS_TABLE[(o, w)] = val
    # Normalize so Z[20][10] = 100
    z_20_10 = DLS_TABLE.get((20, 10), 100)
    if z_20_10 > 0:
        factor = 100.0 / z_20_10
        for k in DLS_TABLE:
            DLS_TABLE[k] = round(DLS_TABLE[k] * factor, 2)

_build_dls_table()

def dls_probability(runs, wickets, overs, target, innings, total_overs=20):
    overs_remaining = total_overs - overs
    wickets_in_hand = 10 - wickets
    o_rem = max(0, min(int(round(overs_remaining)), 20))
    w_hand = max(0, min(wickets_in_hand, 10))

    if innings == 1:
        # Calculate resources used so far
        o_started = int(round(overs))
        resources_at_start = DLS_TABLE.get((20, 10), 100)
        resources_remaining = DLS_TABLE.get((o_rem, w_hand), 50)
        resources_used = resources_at_start - resources_remaining
        if resources_used <= 0:
            return 0.5
        projected = (runs / resources_used) * 100
        typical = 170
        prob = 0.5 + (projected - typical) / (typical * 2)
        return round(max(min(prob, 0.95), 0.05), 4)

    # 2nd innings
    if target is None or target == 0:
        return 0.5
    if target - runs <= 0:
        return 1.0
    if w_hand <= 0 or o_rem <= 0:
        return 0.0

    # Resources used by batting team so far
    resources_at_start_of_innings = DLS_TABLE.get((20, 10), 100)
    resources_remaining = DLS_TABLE.get((o_rem, w_hand), 0)
    resources_used = resources_at_start_of_innings - resources_remaining

    par_score = target * (resources_used / 100)
    runs_ahead = runs - par_score
    resource_remaining_pct = resources_remaining

    advantage_index = runs_ahead / (target * 0.01) if target > 0 else 0
    prob = 50 + advantage_index * 1.2 + (resource_remaining_pct - 50) * 0.15
    return round(max(min(prob / 100, 0.97), 0.03), 4)


# ─── ALGORITHM 3: BAYESIAN BELIEF UPDATE ─────────────────────

# Event likelihoods: P(event | batting team winning)
EVENT_LIKELIHOODS_WIN = {
    "boundary": 0.72,  # 4 or 6
    "dot": 0.35,
    "single": 0.52,
    "wicket": 0.18,
    "extra": 0.55,  # wide/no ball
    "double": 0.55,
    "triple": 0.60,
}
EVENT_LIKELIHOODS_LOSE = {
    "boundary": 0.28,
    "dot": 0.65,
    "single": 0.48,
    "wicket": 0.82,
    "extra": 0.45,
    "double": 0.45,
    "triple": 0.40,
}

def classify_ball_event(ball):
    if ball.get("isWicket"):
        return "wicket"
    if ball.get("isWide") or ball.get("isNoBall"):
        return "extra"
    r = ball.get("runs", 0)
    if r >= 4:
        return "boundary"
    if r == 0:
        return "dot"
    if r == 1:
        return "single"
    if r == 2:
        return "double"
    if r == 3:
        return "triple"
    return "single"

def bayesian_probability(runs, wickets, overs, target, innings,
                         odds_team_a=None, ball_history=None,
                         pressure_index_prob=None, total_overs=20):
    # Set prior from betting odds
    if odds_team_a is not None and odds_team_a > 1:
        prior = 1.0 / odds_team_a
    elif odds_team_a is not None and 0 < odds_team_a <= 1:
        prior = odds_team_a
    else:
        prior = 0.5
    prior = max(min(prior, 0.95), 0.05)

    prob = prior

    # Update with ball history
    if ball_history:
        for ball in ball_history:
            event = classify_ball_event(ball)
            p_event_win = EVENT_LIKELIHOODS_WIN.get(event, 0.5)
            p_event_lose = EVENT_LIKELIHOODS_LOSE.get(event, 0.5)
            # Bayes update
            numerator = p_event_win * prob
            denominator = p_event_win * prob + p_event_lose * (1 - prob)
            if denominator > 0:
                prob = numerator / denominator
            prob = max(min(prob, 0.98), 0.02)

    # Blend with pressure index every over (approximate)
    if pressure_index_prob is not None:
        prob = prob * 0.75 + pressure_index_prob * 0.25

    # Clamp
    if innings == 2:
        if target and runs >= target:
            return 1.0
        remaining_wickets = 10 - wickets
        remaining_overs = total_overs - overs
        if remaining_wickets <= 0 or (remaining_overs <= 0 and runs < target):
            return 0.0

    return round(max(min(prob, 0.97), 0.03), 4)


# ─── ALGORITHM 4: MONTE CARLO SIMULATION ─────────────────────

def monte_carlo_simulation(runs, wickets, overs, target, innings,
                           n_simulations=500, venue_avg=VENUE_AVG, total_overs=20):
    if innings == 1:
        return _mc_first_innings(runs, wickets, overs, n_simulations, venue_avg, total_overs)

    if target is None or target == 0:
        return 0.5, None
    remaining_runs = target - runs
    if remaining_runs <= 0:
        return 1.0, None
    remaining_overs = total_overs - overs
    remaining_wickets = 10 - wickets
    if remaining_wickets <= 0 or remaining_overs <= 0:
        return 0.0, None

    scale = venue_avg / 160 if venue_avg > 0 else 1.0
    wins = 0
    balls_remaining = int(remaining_overs * 6)

    for _ in range(n_simulations):
        sim_runs = 0
        sim_wickets = 0
        for _ in range(balls_remaining):
            if remaining_wickets - sim_wickets <= 0:
                break
            r = random.random()
            if r < 0.05 * scale:
                sim_runs += 6
            elif r < 0.20 * scale:
                sim_runs += 4
            elif r < 0.35:
                sim_runs += 3
            elif r < 0.55:
                sim_runs += 2
            elif r < 0.72:
                sim_runs += 1
            elif r < 0.84:
                pass  # dot
            else:
                sim_wickets += 1
            if sim_runs >= remaining_runs:
                break
        # Wicket penalty
        total_wkts = wickets + sim_wickets
        wicket_penalty = (total_wkts - 6) * 8 if total_wkts > 6 else 0
        final_score = sim_runs - wicket_penalty * 0.3
        if final_score >= remaining_runs:
            wins += 1

    prob = wins / n_simulations
    return round(max(min(prob, 0.97), 0.03), 4), None

def _mc_first_innings(runs, wickets, overs, n_simulations, venue_avg, total_overs):
    remaining_overs = total_overs - overs
    remaining_wickets = 10 - wickets
    balls_remaining = int(remaining_overs * 6)
    scale = venue_avg / 160 if venue_avg > 0 else 1.0
    projected_scores = []

    for _ in range(n_simulations):
        sim_runs = runs
        sim_wickets = 0
        for _ in range(balls_remaining):
            if remaining_wickets - sim_wickets <= 0:
                sim_runs += random.choice([0, 1])
                continue
            r = random.random()
            if r < 0.05 * scale:
                sim_runs += 6
            elif r < 0.20 * scale:
                sim_runs += 4
            elif r < 0.35:
                sim_runs += 3
            elif r < 0.55:
                sim_runs += 2
            elif r < 0.72:
                sim_runs += 1
            elif r < 0.84:
                pass
            else:
                sim_wickets += 1
        # Wicket penalty
        total_wkts = wickets + sim_wickets
        penalty = (total_wkts - 6) * 8 if total_wkts > 6 else 0
        projected_scores.append(sim_runs - penalty * 0.3)

    median_score = sorted(projected_scores)[n_simulations // 2]
    va = max(float(venue_avg or 0), float(VENUE_AVG))
    prob = 0.5 + (median_score - va) / (va * 1.5)
    return round(max(min(prob, 0.95), 0.05), 4), round(median_score, 1)


# ─── ENSEMBLE ─────────────────────────────────────────────────

def ensemble_probability(runs, wickets, overs, target, innings,
                         odds_team_a=None, ball_history=None,
                         venue_avg=VENUE_AVG, total_overs=20):
    pi = pressure_index(runs, wickets, overs, target, innings, venue_avg, total_overs)
    dls = dls_probability(runs, wickets, overs, target, innings, total_overs)
    bayes = bayesian_probability(runs, wickets, overs, target, innings,
                                 odds_team_a, ball_history, pi, total_overs)
    mc_result = monte_carlo_simulation(runs, wickets, overs, target, innings,
                                        500, venue_avg, total_overs)
    mc = mc_result[0] if isinstance(mc_result, tuple) else mc_result
    projected_score = mc_result[1] if isinstance(mc_result, tuple) and len(mc_result) > 1 else None

    ensemble = pi * 0.25 + dls * 0.30 + bayes * 0.20 + mc * 0.25

    algos = [pi, dls, bayes, mc]
    confidence_band = (max(algos) - min(algos)) / 2

    return {
        "pressure_index": pi,
        "dls_resource": dls,
        "bayesian": bayes,
        "monte_carlo": mc,
        "ensemble": round(max(min(ensemble, 0.98), 0.02), 4),
        "confidence_band": round(confidence_band, 4),
        "projected_score": projected_score,
    }

def calculate_odds_from_probability(prob):
    if prob <= 0:
        return 99.0
    if prob >= 1:
        return 1.01
    return round(1 / prob, 2)

def calculate_betting_edge(model_prob, market_odds):
    """Calculate edge: model probability vs market implied probability."""
    if market_odds and market_odds > 1:
        implied = 1.0 / market_odds
        edge = model_prob - implied
        return {
            "model_prob": round(model_prob * 100, 1),
            "market_implied": round(implied * 100, 1),
            "edge": round(edge * 100, 1),
            "edge_positive": edge > 0,
        }
    return None

def calculate_momentum(ball_history, window=12):
    if not ball_history or len(ball_history) < 2:
        return {"score": 0, "direction": "neutral", "intensity": 0}
    recent = ball_history[-window:]
    runs = sum(b.get("runs", 0) for b in recent)
    wickets = sum(1 for b in recent if b.get("isWicket", False))
    boundaries = sum(1 for b in recent if b.get("runs", 0) >= 4)
    score = runs - (wickets * 8) + (boundaries * 2)
    if score > 10:
        direction = "batting"
        intensity = min(score / 20, 1.0)
    elif score < -5:
        direction = "bowling"
        intensity = min(abs(score) / 15, 1.0)
    else:
        direction = "neutral"
        intensity = 0.2
    return {"score": round(score, 2), "direction": direction, "intensity": round(intensity, 2)}
