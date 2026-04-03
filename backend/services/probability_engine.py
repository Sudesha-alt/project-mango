import math
import random
import numpy as np
from typing import Optional

def pressure_index(runs, wickets, overs, target, innings, total_overs=20):
    if innings == 1:
        if overs == 0:
            return 0.5
        run_rate = runs / overs if overs > 0 else 0
        wicket_factor = 1 - (wickets / 10)
        over_progress = overs / total_overs
        if run_rate > 9:
            batting_strength = 0.65
        elif run_rate > 7:
            batting_strength = 0.55
        else:
            batting_strength = 0.45
        pressure = batting_strength * wicket_factor * (0.5 + 0.5 * over_progress)
        return round(min(max(pressure, 0.05), 0.95), 4)
    if target is None or target == 0:
        return 0.5
    remaining_runs = target - runs
    remaining_overs = total_overs - overs
    remaining_wickets = 10 - wickets
    if remaining_runs <= 0:
        return 1.0
    if remaining_wickets <= 0 or remaining_overs <= 0:
        return 0.0
    required_rate = remaining_runs / remaining_overs if remaining_overs > 0 else 999
    wicket_resource = remaining_wickets / 10
    over_resource = remaining_overs / total_overs
    if required_rate < 6:
        rr_factor = 0.8
    elif required_rate < 8:
        rr_factor = 0.65
    elif required_rate < 10:
        rr_factor = 0.5
    elif required_rate < 12:
        rr_factor = 0.35
    elif required_rate < 15:
        rr_factor = 0.2
    else:
        rr_factor = 0.1
    prob = rr_factor * 0.5 + wicket_resource * 0.3 + over_resource * 0.2
    return round(min(max(prob, 0.02), 0.98), 4)

DLS_RESOURCES = {}
def _init_dls():
    for w in range(11):
        for o_tenths in range(201):
            o = o_tenths / 10
            remaining = 20 - o
            wickets_left = 10 - w
            if wickets_left <= 0 or remaining <= 0:
                DLS_RESOURCES[(w, o_tenths)] = 0.0
            else:
                base = remaining / 20
                wicket_mult = wickets_left / 10
                resource = base * (1 - math.exp(-3 * wicket_mult))
                DLS_RESOURCES[(w, o_tenths)] = round(resource * 100, 2)
_init_dls()

def dls_probability(runs, wickets, overs, target, innings, total_overs=20):
    if innings == 1:
        current_key = (wickets, int(overs * 10))
        remaining_resource = DLS_RESOURCES.get(current_key, 50)
        used_resource = 100 - remaining_resource
        projected = (runs / used_resource * 100) if used_resource > 0 else runs * 2
        typical_t20 = 170
        prob = 0.5 + (projected - typical_t20) / (typical_t20 * 2)
        return round(min(max(prob, 0.05), 0.95), 4)
    if target is None or target == 0:
        return 0.5
    current_key = (wickets, int(overs * 10))
    remaining_resource = DLS_RESOURCES.get(current_key, 50)
    par_score = target * (1 - remaining_resource / 100)
    diff = runs - par_score
    prob = 0.5 + diff / (target * 0.5)
    return round(min(max(prob, 0.02), 0.98), 4)

def bayesian_probability(runs, wickets, overs, target, innings, odds_team_a=None, total_overs=20):
    prior = 0.5
    if odds_team_a is not None and odds_team_a > 0:
        prior = 1 / odds_team_a if odds_team_a > 1 else odds_team_a
        prior = min(max(prior, 0.05), 0.95)
    if innings == 1:
        run_rate = runs / overs if overs > 0 else 0
        if run_rate > 9:
            likelihood = 0.65
        elif run_rate > 7:
            likelihood = 0.55
        else:
            likelihood = 0.45
    else:
        if target and target > 0:
            remaining = target - runs
            remaining_overs = total_overs - overs
            remaining_wickets = 10 - wickets
            if remaining <= 0:
                return 1.0
            if remaining_wickets <= 0 or remaining_overs <= 0:
                return 0.0
            rr = remaining / remaining_overs if remaining_overs > 0 else 99
            if rr < 7:
                likelihood = 0.75
            elif rr < 10:
                likelihood = 0.5
            elif rr < 13:
                likelihood = 0.3
            else:
                likelihood = 0.15
            likelihood *= (remaining_wickets / 10)
        else:
            likelihood = 0.5
    posterior = (likelihood * prior) / ((likelihood * prior) + ((1 - likelihood) * (1 - prior)))
    return round(min(max(posterior, 0.02), 0.98), 4)

def monte_carlo_simulation(runs, wickets, overs, target, innings, n_simulations=500, total_overs=20):
    if innings == 1:
        return _mc_first_innings(runs, wickets, overs, n_simulations, total_overs)
    if target is None or target == 0:
        return 0.5
    remaining_runs = target - runs
    if remaining_runs <= 0:
        return 1.0
    remaining_overs = total_overs - overs
    remaining_wickets = 10 - wickets
    if remaining_wickets <= 0 or remaining_overs <= 0:
        return 0.0
    wins = 0
    current_rr = runs / overs if overs > 0 else 7.5
    for _ in range(n_simulations):
        sim_runs = 0
        sim_wickets = remaining_wickets
        balls_left = int(remaining_overs * 6)
        for _ in range(balls_left):
            if sim_wickets <= 0:
                break
            wicket_prob = 0.03 + (0.02 * (10 - sim_wickets) / 10)
            if random.random() < wicket_prob:
                sim_wickets -= 1
                continue
            avg_per_ball = current_rr / 6
            ball_runs = random.choices(
                [0, 1, 2, 3, 4, 6],
                weights=[0.35, 0.30, 0.12, 0.03, 0.12, 0.08],
                k=1
            )[0]
            sim_runs += ball_runs
            if sim_runs >= remaining_runs:
                break
        if sim_runs >= remaining_runs:
            wins += 1
    return round(wins / n_simulations, 4)

def _mc_first_innings(runs, wickets, overs, n_simulations, total_overs):
    remaining_overs = total_overs - overs
    remaining_wickets = 10 - wickets
    current_rr = runs / overs if overs > 0 else 7.5
    totals = []
    for _ in range(n_simulations):
        sim_runs = runs
        sim_wickets = remaining_wickets
        balls_left = int(remaining_overs * 6)
        for _ in range(balls_left):
            if sim_wickets <= 0:
                sim_runs += random.choice([0, 1])
                continue
            wicket_prob = 0.03
            if random.random() < wicket_prob:
                sim_wickets -= 1
                continue
            ball_runs = random.choices(
                [0, 1, 2, 3, 4, 6],
                weights=[0.30, 0.30, 0.15, 0.03, 0.13, 0.09],
                k=1
            )[0]
            sim_runs += ball_runs
        totals.append(sim_runs)
    avg_total = np.mean(totals)
    prob = 0.5 + (avg_total - 170) / 200
    return round(min(max(prob, 0.05), 0.95), 4)

def ensemble_probability(runs, wickets, overs, target, innings, odds_team_a=None, total_overs=20):
    pi = pressure_index(runs, wickets, overs, target, innings, total_overs)
    dls = dls_probability(runs, wickets, overs, target, innings, total_overs)
    bayes = bayesian_probability(runs, wickets, overs, target, innings, odds_team_a, total_overs)
    mc = monte_carlo_simulation(runs, wickets, overs, target, innings, 300, total_overs)
    ensemble = pi * 0.25 + dls * 0.30 + bayes * 0.20 + mc * 0.25
    return {
        "pressure_index": pi,
        "dls_resource": dls,
        "bayesian": bayes,
        "monte_carlo": mc,
        "ensemble": round(min(max(ensemble, 0.02), 0.98), 4)
    }

def calculate_odds_from_probability(prob):
    if prob <= 0:
        return 99.0
    if prob >= 1:
        return 1.01
    return round(1 / prob, 2)

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
    return {
        "score": round(score, 2),
        "direction": direction,
        "intensity": round(intensity, 2)
    }
