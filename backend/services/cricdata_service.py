"""
CricketData.org API Service — Live Match Data
==============================================
Base URL: https://api.cricapi.com/v1/
Rate Limit: 100 hits/day (free tier)
Used ONLY for live match details on manual user trigger.
"""
import os
import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CRICAPI_BASE = "https://api.cricapi.com/v1"
CRICAPI_KEY = os.environ.get("CRICAPI_KEY", "")


async def _get(endpoint: str, params: dict = None) -> dict:
    """Make an authenticated GET request to CricAPI."""
    if not CRICAPI_KEY:
        return {"status": "error", "error": "CRICAPI_KEY not configured"}

    url = f"{CRICAPI_BASE}/{endpoint}"
    query = {"apikey": CRICAPI_KEY, "offset": "0"}
    if params:
        query.update(params)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=query)
        resp.raise_for_status()
        return resp.json()


async def fetch_current_matches_from_api() -> dict:
    """
    Fetch current matches from CricAPI.
    Returns raw API response with info (hits tracking) and data.
    """
    try:
        data = await _get("currentMatches")
        return data
    except Exception as e:
        logger.error(f"CricAPI currentMatches error: {e}")
        return {"status": "error", "error": str(e)}


def filter_ipl_matches(api_data: dict) -> list:
    """Filter API response to only IPL 2026 matches."""
    matches = api_data.get("data", [])
    ipl = []
    for m in matches:
        name = (m.get("name", "") + " " + m.get("series", "")).lower()
        if "ipl" in name or "indian premier league" in name:
            ipl.append(m)
    return ipl


def parse_match_details(match: dict) -> dict:
    """Parse a CricAPI match object into our structured format."""
    scores = match.get("score", [])
    teams = match.get("teams", [])
    team1 = teams[0] if len(teams) > 0 else match.get("teamInfo", [{}])[0].get("name", "Team A") if match.get("teamInfo") else "Team A"
    team2 = teams[1] if len(teams) > 1 else match.get("teamInfo", [{}])[1].get("name", "Team B") if match.get("teamInfo") and len(match.get("teamInfo", [])) > 1 else "Team B"

    # Parse scores per innings
    innings_data = []
    for s in scores:
        innings_data.append({
            "runs": s.get("r", 0),
            "wickets": s.get("w", 0),
            "overs": s.get("o", 0),
            "inning_label": s.get("inning", ""),
        })

    # Current batting state
    current_innings = len(innings_data)
    current_score = innings_data[-1] if innings_data else {"runs": 0, "wickets": 0, "overs": 0}
    target = innings_data[0]["runs"] + 1 if current_innings >= 2 else None

    # Team info with images
    team_info = {}
    for ti in match.get("teamInfo", []):
        team_info[ti.get("name", "")] = {
            "shortname": ti.get("shortname", ""),
            "img": ti.get("img", ""),
        }

    return {
        "cricapi_id": match.get("id", ""),
        "name": match.get("name", ""),
        "status": match.get("status", ""),
        "matchType": match.get("matchType", "t20"),
        "venue": match.get("venue", ""),
        "date": match.get("date", ""),
        "dateTimeGMT": match.get("dateTimeGMT", ""),
        "team1": team1,
        "team2": team2,
        "team_info": team_info,
        "innings": innings_data,
        "current_innings": current_innings,
        "current_score": current_score,
        "target": target,
        "matchStarted": match.get("matchStarted", False),
        "matchEnded": match.get("matchEnded", False),
        "source": "cricketdata.org",
    }


async def fetch_live_ipl_details() -> dict:
    """
    Fetch live IPL 2026 match details from CricAPI.
    Returns parsed matches and API hit info.
    Costs 1 API hit per call.
    """
    raw = await fetch_current_matches_from_api()

    if raw.get("status") == "error":
        return {
            "error": raw.get("error", "API call failed"),
            "api_info": raw.get("info", {}),
        }

    api_info = raw.get("info", {})
    hits_today = api_info.get("hitsToday", 0)
    hits_limit = api_info.get("hitsLimit", 100)

    # Filter IPL matches
    ipl_matches = filter_ipl_matches(raw)

    # Parse each match
    parsed = [parse_match_details(m) for m in ipl_matches]

    return {
        "matches": parsed,
        "count": len(parsed),
        "api_info": {
            "hits_today": hits_today,
            "hits_limit": hits_limit,
            "hits_remaining": hits_limit - hits_today,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
        "all_matches_count": len(raw.get("data", [])),
        "source": "cricketdata.org",
    }



async def fetch_match_info(match_id: str) -> dict:
    """
    Fetch detailed match info including venue from CricAPI.
    Costs 1 API hit.
    """
    try:
        data = await _get("match_info", {"id": match_id})
        return data
    except Exception as e:
        logger.error(f"CricAPI match_info error: {e}")
        return {"status": "error", "error": str(e)}


async def fetch_venue_stats_from_cricapi(venue_name: str) -> dict:
    """
    On-demand venue data fetch using CricAPI search.
    Searches current matches for venue info. Returns parsed venue details.
    Costs 1 API hit (uses currentMatches endpoint).
    """
    try:
        raw = await fetch_current_matches_from_api()
        if raw.get("status") == "error":
            return {"error": raw.get("error"), "venue": venue_name}

        api_info = raw.get("info", {})
        matches = raw.get("data", [])

        # Find matches at this venue
        venue_matches = []
        for m in matches:
            m_venue = (m.get("venue", "") or "").lower()
            if venue_name.lower() in m_venue or m_venue in venue_name.lower():
                venue_matches.append({
                    "match_name": m.get("name", ""),
                    "venue": m.get("venue", ""),
                    "status": m.get("status", ""),
                    "date": m.get("date", ""),
                    "teams": m.get("teams", []),
                    "score": m.get("score", []),
                    "matchStarted": m.get("matchStarted", False),
                    "matchEnded": m.get("matchEnded", False),
                })

        return {
            "venue": venue_name,
            "matches_found": len(venue_matches),
            "matches": venue_matches,
            "api_info": {
                "hits_today": api_info.get("hitsToday", 0),
                "hits_limit": api_info.get("hitsLimit", 100),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
            "source": "cricketdata.org",
        }
    except Exception as e:
        logger.error(f"CricAPI venue fetch error: {e}")
        return {"error": str(e), "venue": venue_name}
