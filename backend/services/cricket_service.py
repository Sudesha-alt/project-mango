import httpx
import os
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CRICAPI_KEY = os.environ.get("CRICAPI_KEY", "")
CRICAPI_BASE = "https://api.cricapi.com/v1"
CRICBUZZ_BASE = "https://cricbuzz-live.vercel.app/v1"

# Rate limit tracking
_last_api_call = 0
_api_cooldown = 120  # 2 min between calls to avoid CricAPI 15-min blocks
_blocked_until = 0  # Timestamp when block expires
_api_cache = {}
_cache_ttl = 300  # cache for 5 minutes

IPL_TEAMS = [
    "Chennai Super Kings", "Mumbai Indians", "Royal Challengers Bengaluru",
    "Kolkata Knight Riders", "Delhi Capitals", "Rajasthan Royals",
    "Sunrisers Hyderabad", "Punjab Kings", "Gujarat Titans", "Lucknow Super Giants"
]
IPL_SHORT = {
    "Chennai Super Kings": "CSK", "Mumbai Indians": "MI",
    "Royal Challengers Bengaluru": "RCB", "Royal Challengers Bangalore": "RCB",
    "Kolkata Knight Riders": "KKR", "Delhi Capitals": "DC",
    "Rajasthan Royals": "RR", "Sunrisers Hyderabad": "SRH",
    "Punjab Kings": "PBKS", "Gujarat Titans": "GT", "Lucknow Super Giants": "LSG"
}

def get_short_name(team_name):
    if not team_name:
        return "???"
    for full, short in IPL_SHORT.items():
        if full.lower() in team_name.lower() or short.lower() == team_name.lower():
            return short
    return team_name[:3].upper()

async def fetch_cricapi(endpoint, params=None):
    global _last_api_call, _blocked_until
    cache_key = f"{endpoint}:{str(params)}"
    now = time.time()
    if cache_key in _api_cache:
        cached_time, cached_data = _api_cache[cache_key]
        if now - cached_time < _cache_ttl:
            return cached_data
    # If we're in a block period, don't even try
    if now < _blocked_until:
        logger.debug(f"CricAPI blocked, {int(_blocked_until - now)}s remaining")
        if cache_key in _api_cache:
            return _api_cache[cache_key][1]
        return None
    if now - _last_api_call < _api_cooldown:
        logger.info(f"Rate limiting CricAPI call to {endpoint}")
        if cache_key in _api_cache:
            return _api_cache[cache_key][1]
        return None
    if not params:
        params = {}
    params["apikey"] = CRICAPI_KEY
    try:
        _last_api_call = now
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{CRICAPI_BASE}{endpoint}", params=params)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    result = data.get("data", data)
                    _api_cache[cache_key] = (now, result)
                    _blocked_until = 0  # Clear block on success
                    return result
                reason = data.get("reason", "")
                if "blocked" in reason.lower() or "Blocked" in reason:
                    _blocked_until = now + 960  # Back off 16 minutes
                    logger.warning(f"CricAPI blocked, backing off 16 minutes")
                else:
                    logger.warning(f"CricAPI {endpoint} failed: {reason}")
    except Exception as e:
        logger.error(f"CricAPI error {endpoint}: {e}")
    return _api_cache.get(cache_key, (0, None))[1]

async def fetch_cricbuzz_live():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{CRICBUZZ_BASE}/matches/live", params={"type": "league"})
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
    except Exception as e:
        logger.debug(f"Cricbuzz live error: {e}")
    return []

async def fetch_cricbuzz_score(match_id):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{CRICBUZZ_BASE}/score/{match_id}")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.debug(f"Cricbuzz score error: {e}")
    return None

def normalize_cricapi_match(m):
    team_info = m.get("teamInfo", [])
    teams = m.get("teams", [])
    t1 = team_info[0].get("name", teams[0] if teams else "Team A") if len(team_info) > 0 else (teams[0] if teams else "Team A")
    t2 = team_info[1].get("name", teams[1] if len(teams) > 1 else "Team B") if len(team_info) > 1 else (teams[1] if len(teams) > 1 else "Team B")
    score_parts = m.get("score", [])
    score_str = ""
    runs = 0
    overs = 0
    wickets = 0
    innings = 1
    for i, s in enumerate(score_parts):
        r = s.get("r", 0)
        w = s.get("w", 0)
        o = s.get("o", 0)
        inning_name = s.get("inning", f"Inn {i+1}")
        if i == len(score_parts) - 1:
            runs = r
            wickets = w
            overs = o
            innings = i + 1
        score_str += f"{inning_name}: {r}/{w} ({o}) | "
    score_str = score_str.rstrip(" | ")
    return {
        "matchId": m.get("id", ""),
        "team1": t1,
        "team1Short": get_short_name(t1),
        "team2": t2,
        "team2Short": get_short_name(t2),
        "score": score_str,
        "runs": runs,
        "overs": overs,
        "wickets": wickets,
        "innings": innings,
        "status": m.get("status", ""),
        "venue": m.get("venue", ""),
        "matchType": m.get("matchType", ""),
        "dateTimeGMT": m.get("dateTimeGMT", ""),
        "series": m.get("series", ""),
        "isLive": m.get("matchStarted", False) and not m.get("matchEnded", False),
        "matchEnded": m.get("matchEnded", False),
        "source": "cricapi",
        "t1Img": team_info[0].get("img", "") if len(team_info) > 0 else "",
        "t2Img": team_info[1].get("img", "") if len(team_info) > 1 else "",
    }

async def get_live_matches():
    matches = []
    # Try currentMatches first
    cricapi_data = await fetch_cricapi("/currentMatches")
    if cricapi_data and isinstance(cricapi_data, list):
        for m in cricapi_data:
            matches.append(normalize_cricapi_match(m))
    # If no results, try matches endpoint
    if not matches:
        matches_data = await fetch_cricapi("/matches", {"offset": 0})
        if matches_data and isinstance(matches_data, list):
            for m in matches_data:
                matches.append(normalize_cricapi_match(m))
    # Cricbuzz fallback
    if not matches:
        cricbuzz_data = await fetch_cricbuzz_live()
        for m in cricbuzz_data:
            matches.append({
                "matchId": str(m.get("id", "")),
                "team1": m.get("t1", ""),
                "team1Short": get_short_name(m.get("t1", "")),
                "team2": m.get("t2", ""),
                "team2Short": get_short_name(m.get("t2", "")),
                "score": m.get("overview", ""),
                "runs": 0, "overs": 0, "wickets": 0, "innings": 1,
                "status": m.get("status", ""),
                "venue": m.get("place", ""),
                "matchType": "T20",
                "dateTimeGMT": "",
                "series": m.get("title", ""),
                "isLive": True,
                "matchEnded": False,
                "source": "cricbuzz",
                "t1Img": "", "t2Img": "",
            })
    return matches

async def get_match_info(match_id):
    data = await fetch_cricapi("/match_info", {"id": match_id})
    if data:
        return data
    return await fetch_cricbuzz_score(match_id)

async def get_match_scorecard(match_id):
    return await fetch_cricapi("/match_scorecard", {"id": match_id})

async def get_match_squad(match_id):
    return await fetch_cricapi("/match_squad", {"id": match_id})

async def get_series_list():
    return await fetch_cricapi("/series")

async def get_player_info(player_id):
    return await fetch_cricapi("/players_info", {"id": player_id})

async def get_ipl_fixtures():
    series_data = await fetch_cricapi("/series")
    ipl_series_id = None
    if series_data and isinstance(series_data, list):
        for s in series_data:
            name = str(s.get("name", "")).lower()
            if "ipl" in name or "indian premier league" in name:
                ipl_series_id = s.get("id")
                break
    if ipl_series_id:
        fixtures = await fetch_cricapi("/series_info", {"id": ipl_series_id})
        if fixtures:
            return fixtures
    matches = await fetch_cricapi("/matches", {"offset": 0})
    if matches and isinstance(matches, list):
        return matches
    return []
