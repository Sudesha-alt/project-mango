"""
Team Form & Momentum Data Fetcher — The Lucky 11
Uses MongoDB schedule (completed matches) for W/L form; player stats are supplied by callers
(e.g. server + services.sportmonks_service.fetch_team_recent_performance). NO web scraping.
"""
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Historical IPL H2H records (2023-2025 seasons only, alphabetical key pair)
# Format: ("team_a_short", "team_b_short"): (a_wins, b_wins)
# Includes league stage + playoffs from 2023, 2024, and 2025 (suspended mid-season)
HISTORICAL_H2H = {
    ("CSK", "DC"): (4, 2),
    ("CSK", "GT"): (5, 2),   # 2023 playoffs: CSK won Q1 + Final vs GT
    ("CSK", "KKR"): (3, 3),
    ("CSK", "LSG"): (3, 2),
    ("CSK", "MI"): (4, 2),   # CSK dominated 2023-2024, MI won 1 in 2025
    ("CSK", "PBKS"): (2, 4),
    ("CSK", "RR"): (2, 4),
    ("CSK", "RCB"): (3, 3),
    ("CSK", "SRH"): (3, 3),
    ("DC", "GT"): (2, 4),
    ("DC", "KKR"): (2, 3),
    ("DC", "LSG"): (4, 2),
    ("DC", "MI"): (2, 4),
    ("DC", "PBKS"): (3, 3),
    ("DC", "RR"): (3, 3),
    ("DC", "RCB"): (3, 3),
    ("DC", "SRH"): (3, 3),
    ("GT", "KKR"): (3, 2),
    ("GT", "LSG"): (3, 3),
    ("GT", "MI"): (4, 2),   # GT won 2023 Q2 vs MI
    ("GT", "PBKS"): (3, 2),
    ("GT", "RR"): (3, 3),
    ("GT", "RCB"): (3, 2),
    ("GT", "SRH"): (4, 1),
    ("KKR", "LSG"): (3, 2),
    ("KKR", "MI"): (3, 2),
    ("KKR", "PBKS"): (2, 3),
    ("KKR", "RR"): (2, 3),
    ("KKR", "RCB"): (5, 1),  # KKR dominated RCB in 2023-2024
    ("KKR", "SRH"): (4, 3),  # KKR won 2024 Q1 + Final vs SRH
    ("LSG", "MI"): (4, 2),
    ("LSG", "PBKS"): (3, 3),
    ("LSG", "RR"): (3, 3),
    ("LSG", "RCB"): (3, 3),
    ("LSG", "SRH"): (4, 2),
    ("MI", "PBKS"): (3, 3),
    ("MI", "RCB"): (3, 3),
    ("MI", "RR"): (3, 3),
    ("MI", "SRH"): (5, 1),  # MI dominated SRH across 2023-2025
    ("PBKS", "RCB"): (2, 4),
    ("PBKS", "RR"): (3, 3),
    ("PBKS", "SRH"): (1, 5), # SRH dominated PBKS
    ("RCB", "RR"): (5, 2),   # RCB dominated RR + 2024 Eliminator
    ("RCB", "SRH"): (3, 4),  # SRH won 2024 Q2 vs RCB
    ("RR", "SRH"): (2, 4),   # SRH won 2024 Q1 vs RR
}

# Team name to short code mapping
TEAM_SHORT_CODES = {
    "chennai super kings": "CSK",
    "delhi capitals": "DC",
    "delhi daredevils": "DC",
    "gujarat titans": "GT",
    "kolkata knight riders": "KKR",
    "lucknow super giants": "LSG",
    "mumbai indians": "MI",
    "punjab kings": "PBKS",
    "kings xi punjab": "PBKS",
    "royal challengers bengaluru": "RCB",
    "royal challengers bangalore": "RCB",
    "rajasthan royals": "RR",
    "sunrisers hyderabad": "SRH",
}


def _get_short_code(team_name: str) -> str:
    """Get team short code from full name."""
    lower = team_name.lower().strip()
    for key, code in TEAM_SHORT_CODES.items():
        if key in lower or lower in key:
            return code
    return ""


def _get_historical_h2h(team1: str, team2: str):
    """Look up historical H2H record between two teams."""
    code1 = _get_short_code(team1)
    code2 = _get_short_code(team2)
    if not code1 or not code2 or code1 == code2:
        return None
    # Key is always alphabetically ordered
    key = (min(code1, code2), max(code1, code2))
    record = HISTORICAL_H2H.get(key)
    if not record:
        return None
    a_wins, b_wins = record
    # Map back to team1/team2
    if code1 == key[0]:
        return {"team1_wins": a_wins, "team2_wins": b_wins, "source": "historical_ipl"}
    else:
        return {"team1_wins": b_wins, "team2_wins": a_wins, "source": "historical_ipl"}


async def fetch_team_form(db, team1: str, team2: str, player_performance: Dict = None) -> Dict:
    """
    Fetch current season form data for both teams.
    Uses completed matches from DB schedule + player performance stats from SportMonks.
    Returns form scores (0-100) based on recent results AND player-level performance.
    """
    form = {"team1": {}, "team2": {}, "h2h": {}}
    player_performance = player_performance or {}

    # Get completed matches from DB for form calculation
    completed = []
    async for m in db.ipl_schedule.find(
        {"status": {"$regex": "completed", "$options": "i"}},
        {"_id": 0}
    ).sort("match_number", -1):
        completed.append(m)

    for idx, (team, key) in enumerate([(team1, "team1"), (team2, "team2")]):
        team_lower = team.lower()
        # Find this team's recent results (only matches WITH a winner field)
        team_matches = []
        for m in completed:
            if not m.get("winner"):
                continue  # Skip matches without actual results
            t1 = (m.get("team1", "") or "").lower()
            t2 = (m.get("team2", "") or "").lower()
            if team_lower in t1 or team_lower in t2 or t1 in team_lower or t2 in team_lower:
                team_matches.append(m)
            if len(team_matches) >= 15:
                break

        wins = 0
        losses = 0
        results_list = []
        for m in team_matches:
            winner = (m.get("winner", "") or "").lower()
            if winner and (team_lower in winner or winner in team_lower):
                wins += 1
                results_list.append("W")
            elif winner:
                losses += 1
                results_list.append("L")
            else:
                results_list.append("NR")

        total = wins + losses
        win_pct = (wins / total * 100) if total > 0 else 50

        # Base form score from W/L weighted by recency
        wl_form = 50.0
        if results_list:
            weighted = 0
            weight_sum = 0
            for i, r in enumerate(results_list):
                w = max(1, 10 - i)  # Most recent = weight 10, oldest = weight 1
                if r == "W":
                    weighted += w * 100
                elif r == "L":
                    weighted += w * 0
                else:
                    weighted += w * 50
                weight_sum += w
            wl_form = weighted / weight_sum if weight_sum > 0 else 50

        # ── Player Performance Form Enhancement ──
        # Use actual batting/bowling stats from recent matches to compute player-level form
        team_perf = player_performance.get(key, {})
        player_form_score = 0
        player_form_count = 0
        player_details = []

        if team_perf:
            for pid, ps in team_perf.items():
                p_score = 0
                matches_played = ps.get("matches", 0)
                if matches_played == 0:
                    continue

                bat = ps.get("batting", {})
                bowl = ps.get("bowling", {})

                # Batting form: weighted by avg, SR, and consistency
                if bat.get("innings", 0) > 0:
                    bat_avg = bat.get("avg", 0)
                    bat_sr = bat.get("sr", 0)
                    # Scale: avg 40+ = excellent (90+), avg 20-40 = good (60-90), avg 0-20 = poor (30-60)
                    bat_form = min(100, max(0, bat_avg * 2 + bat_sr * 0.2))
                    p_score += bat_form * 0.5

                # Bowling form: weighted by economy and wickets per innings
                if bowl.get("innings", 0) > 0:
                    economy = bowl.get("economy", 12)
                    wpi = bowl.get("wickets", 0) / bowl["innings"]
                    # Scale: economy < 7 = excellent, 7-9 = good, > 9 = poor
                    econ_score = max(0, min(100, (14 - economy) * 10))
                    wicket_score = min(100, wpi * 40)
                    bowl_form = (econ_score * 0.5 + wicket_score * 0.5)
                    p_score += bowl_form * 0.5

                if p_score > 0:
                    player_form_score += p_score
                    player_form_count += 1
                    player_details.append({
                        "name": ps.get("name", ""),
                        "form_score": round(p_score, 1),
                        "matches": matches_played,
                        "batting": {
                            "runs": bat.get("runs", 0),
                            "avg": bat.get("avg", 0),
                            "sr": bat.get("sr", 0),
                        },
                        "bowling": {
                            "wickets": bowl.get("wickets", 0),
                            "economy": bowl.get("economy", 0),
                        },
                    })

        # Combine W/L form (60%) + player performance form (40%)
        if player_form_count > 0:
            avg_player_form = player_form_score / player_form_count
            form_score = wl_form * 0.6 + avg_player_form * 0.4
        else:
            form_score = wl_form

        form[key] = {
            "form_score": round(form_score, 1),
            "wl_form_score": round(wl_form, 1),
            "player_form_score": round(player_form_score / max(player_form_count, 1), 1) if player_form_count > 0 else 0,
            "matches_played": total,
            "wins": wins,
            "losses": losses,
            "win_pct": round(win_pct, 1),
            "recent_results": results_list[:5],
            "player_count": player_form_count,
            "top_performers": sorted(player_details, key=lambda x: x["form_score"], reverse=True)[:5],
            "nrr": 0,
        }

    # Head-to-Head from completed matches (only matches with a winner)
    h2h_t1_wins = 0
    h2h_t2_wins = 0
    t1_lower = team1.lower()
    t2_lower = team2.lower()
    for m in completed:
        if not m.get("winner"):
            continue
        mt1 = (m.get("team1", "") or "").lower()
        mt2 = (m.get("team2", "") or "").lower()
        has_t1 = t1_lower in mt1 or t1_lower in mt2 or mt1 in t1_lower or mt2 in t1_lower
        has_t2 = t2_lower in mt1 or t2_lower in mt2 or mt1 in t2_lower or mt2 in t2_lower
        if has_t1 and has_t2:
            winner = (m.get("winner", "") or "").lower()
            if t1_lower in winner or winner in t1_lower:
                h2h_t1_wins += 1
            elif t2_lower in winner or winner in t2_lower:
                h2h_t2_wins += 1

    form["h2h"] = {
        "team1_wins": h2h_t1_wins,
        "team2_wins": h2h_t2_wins,
        "total": h2h_t1_wins + h2h_t2_wins,
        "source": "season_2026",
    }

    # Fallback to historical IPL H2H if no season data
    if h2h_t1_wins + h2h_t2_wins == 0:
        hist = _get_historical_h2h(team1, team2)
        if hist:
            form["h2h"] = {
                "team1_wins": hist["team1_wins"],
                "team2_wins": hist["team2_wins"],
                "total": hist["team1_wins"] + hist["team2_wins"],
                "source": hist["source"],
            }

    return form


async def fetch_momentum(db, team1: str, team2: str) -> Dict:
    """
    Fetch last 2 match results for momentum calculation.
    Uses DB schedule completed matches.
    """
    completed = []
    async for m in db.ipl_schedule.find(
        {"status": {"$regex": "completed", "$options": "i"}},
        {"_id": 0}
    ).sort("match_number", -1):
        completed.append(m)

    momentum = {"team1_last2": [], "team2_last2": []}

    for team, key in [(team1, "team1_last2"), (team2, "team2_last2")]:
        team_lower = team.lower()
        results = []
        for m in completed:
            if not m.get("winner"):
                continue  # Skip matches without actual results
            mt1 = (m.get("team1", "") or "").lower()
            mt2 = (m.get("team2", "") or "").lower()
            if team_lower in mt1 or team_lower in mt2 or mt1 in team_lower or mt2 in team_lower:
                winner = (m.get("winner", "") or "").lower()
                if winner and (team_lower in winner or winner in team_lower):
                    results.append("W")
                elif winner:
                    results.append("L")
            if len(results) >= 2:
                break
        momentum[key] = results[:2]

    return momentum


def generate_expected_xi(squad: list) -> list:
    """
    Generate expected Playing XI from squad roster. NO scraping.
    Uses player ratings + role balance to pick best 11.
    Rules:
    - Max 4 overseas players
    - 1 wicketkeeper
    - 5-6 batsmen (incl keeper + allrounders)
    - 4-5 bowlers (incl allrounders)
    """
    if not squad or len(squad) < 11:
        return squad  # Return full squad if < 11

    from services.pre_match_predictor import STAR_PLAYERS

    # Score each player
    scored = []
    for p in squad:
        name = p.get("name", "")
        role = p.get("role", "Batsman")
        rating = STAR_PLAYERS.get(name, 65)
        overseas = p.get("isOverseas", False)
        captain = p.get("isCaptain", False)
        scored.append({**p, "_rating": rating, "_overseas": overseas, "_captain": captain, "_role": role})

    # Captain always plays
    captains = [p for p in scored if p["_captain"]]
    non_captains = [p for p in scored if not p["_captain"]]

    # Sort by rating
    non_captains.sort(key=lambda x: x["_rating"], reverse=True)

    xi = list(captains)
    overseas_count = sum(1 for p in xi if p["_overseas"])

    # Ensure 1 WK
    wks = [p for p in non_captains if p["_role"] == "Wicketkeeper"]
    if wks and not any(p["_role"] == "Wicketkeeper" for p in xi):
        best_wk = max(wks, key=lambda x: x["_rating"])
        xi.append(best_wk)
        non_captains.remove(best_wk)
        if best_wk["_overseas"]:
            overseas_count += 1

    # Add best bowlers (need at least 4)
    bowlers = [p for p in non_captains if p["_role"] == "Bowler" and p not in xi]
    bowlers.sort(key=lambda x: x["_rating"], reverse=True)
    bowler_count = sum(1 for p in xi if p["_role"] in ("Bowler", "All-rounder"))
    for b in bowlers:
        if len(xi) >= 11:
            break
        if b["_overseas"] and overseas_count >= 4:
            continue
        xi.append(b)
        if b["_overseas"]:
            overseas_count += 1
        bowler_count += 1
        if bowler_count >= 4:
            break

    # Add best allrounders
    ars = [p for p in non_captains if p["_role"] == "All-rounder" and p not in xi]
    ars.sort(key=lambda x: x["_rating"], reverse=True)
    for ar in ars:
        if len(xi) >= 11:
            break
        if ar["_overseas"] and overseas_count >= 4:
            continue
        xi.append(ar)
        if ar["_overseas"]:
            overseas_count += 1

    # Fill remaining with best available
    remaining = [p for p in non_captains if p not in xi]
    remaining.sort(key=lambda x: x["_rating"], reverse=True)
    for p in remaining:
        if len(xi) >= 11:
            break
        if p["_overseas"] and overseas_count >= 4:
            continue
        xi.append(p)
        if p["_overseas"]:
            overseas_count += 1

    # Clean up internal keys
    result = []
    for p in xi[:11]:
        clean = {k: v for k, v in p.items() if not k.startswith("_")}
        result.append(clean)

    return result
