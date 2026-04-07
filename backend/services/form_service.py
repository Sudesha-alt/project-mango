"""
Team Form & Momentum Data Fetcher — The Lucky 11
Uses SportMonks API and DB schedule data. NO web scraping.
"""
import os
import logging
import httpx
from typing import Dict, List

logger = logging.getLogger(__name__)

SPORTMONKS_TOKEN = os.environ.get("SPORTMONKS_API_TOKEN", "")
BASE_URL = "https://cricket.sportmonks.com/api/v2.0"


async def _sm_get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to SportMonks Cricket API."""
    if not SPORTMONKS_TOKEN:
        return {"error": "SPORTMONKS_API_TOKEN not configured"}
    url = f"{BASE_URL}/{endpoint}"
    query = {"api_token": SPORTMONKS_TOKEN}
    if params:
        query.update(params)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=query)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"SportMonks form API error: {e}")
        return {"error": str(e)}


async def fetch_team_form(db, team1: str, team2: str) -> Dict:
    """
    Fetch current season form data for both teams.
    Uses completed matches from DB schedule + SportMonks standings as fallback.
    Returns form scores (0-100) based on recent results.
    """
    form = {"team1": {}, "team2": {}, "h2h": {}}

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

        # Form score: weighted by recency (recent matches count more)
        form_score = 50.0
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
            form_score = weighted / weight_sum if weight_sum > 0 else 50

        form[key] = {
            "form_score": round(form_score, 1),
            "matches_played": total,
            "wins": wins,
            "losses": losses,
            "win_pct": round(win_pct, 1),
            "recent_results": results_list[:5],
            "nrr": 0,  # NRR requires detailed match data
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
