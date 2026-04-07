import os
import logging
import httpx
from typing import Dict, Optional

logger = logging.getLogger(__name__)

SPORTMONKS_TOKEN = os.environ.get("SPORTMONKS_API_TOKEN", "")
BASE_URL = "https://cricket.sportmonks.com/api/v2.0"


async def _get(endpoint: str, params: dict = None) -> dict:
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
        logger.error(f"SportMonks API error: {e}")
        return {"error": str(e)}


async def fetch_live_fixtures() -> list:
    """Fetch all currently live cricket fixtures."""
    data = await _get("livescores", {
        "include": "localteam,visitorteam,runs,venue"
    })
    return data.get("data", [])


async def fetch_fixture_details(fixture_id: int) -> dict:
    """Fetch full fixture details: scoreboards, batting, bowling, runs, balls, lineup, venue."""
    data = await _get(f"fixtures/{fixture_id}", {
        "include": "localteam,visitorteam,scoreboards,batting,bowling,runs,balls,venue,tosswon,manofmatch,lineup"
    })
    return data.get("data", {})


def parse_fixture(raw: dict) -> dict:
    """Parse raw SportMonks fixture into a clean match state."""
    if not raw or raw.get("error"):
        return None

    local = raw.get("localteam", {})
    visitor = raw.get("visitorteam", {})
    venue_data = raw.get("venue", {})
    
    team1 = local.get("name", "Team A")
    team2 = visitor.get("name", "Team B")
    t1_code = local.get("code", "T1")
    t2_code = visitor.get("code", "T2")
    team1_id = local.get("id") or raw.get("localteam_id")
    team2_id = visitor.get("id") or raw.get("visitorteam_id")

    # Parse runs per innings
    runs_data = raw.get("runs", [])
    if isinstance(runs_data, dict):
        runs_data = runs_data.get("data", [])

    innings_scores = {}
    for r in runs_data:
        inn = str(r.get("inning", 1))
        innings_scores[inn] = {
            "team_id": r.get("team_id"),
            "runs": r.get("score", 0),
            "wickets": r.get("wickets", 0),
            "overs": r.get("overs", 0),
        }

    # Determine current innings
    current_inn = max(int(k) for k in innings_scores.keys()) if innings_scores else 1
    current_score = innings_scores.get(str(current_inn), {})
    
    batting_team_id = current_score.get("team_id")
    batting_team = team1 if batting_team_id == team1_id else team2
    bowling_team = team2 if batting_team == team1 else team1

    target = None
    # Try to extract target from note text
    note_text = raw.get("note", "") or ""
    if "target" in note_text.lower():
        try:
            target = int(''.join(c for c in note_text.split("Target")[1].split("runs")[0].strip() if c.isdigit()))
        except Exception:
            pass
    # Fallback: compute target from 1st innings score when in 2nd innings
    if target is None and current_inn >= 2 and "1" in innings_scores:
        inn1_runs = innings_scores["1"].get("runs", 0)
        if inn1_runs > 0:
            target = inn1_runs + 1

    # Parse batting
    bat_raw = raw.get("batting", [])
    if isinstance(bat_raw, dict):
        bat_raw = bat_raw.get("data", [])

    batsmen_inn1 = []
    batsmen_inn2 = []
    for b in bat_raw:
        sb = b.get("scoreboard", "S1")
        entry = {
            "player_id": b.get("player_id"),
            "runs": b.get("score", 0),
            "balls": b.get("ball", 0),
            "fours": b.get("four_x", 0),
            "sixes": b.get("six_x", 0),
            "strike_rate": round((b.get("score", 0) / max(b.get("ball", 1), 1)) * 100, 1),
            "active": b.get("active", False),
            "fow_score": b.get("fow_score"),
            "fow_balls": b.get("fow_balls"),
            "sort": b.get("sort", 99),
        }
        if sb == "S1":
            batsmen_inn1.append(entry)
        else:
            batsmen_inn2.append(entry)

    # Parse bowling
    bowl_raw = raw.get("bowling", [])
    if isinstance(bowl_raw, dict):
        bowl_raw = bowl_raw.get("data", [])

    bowlers_inn1 = []
    bowlers_inn2 = []
    for bw in bowl_raw:
        sb = bw.get("scoreboard", "S1")
        entry = {
            "player_id": bw.get("player_id"),
            "overs": bw.get("overs", 0),
            "maidens": bw.get("medians", 0),
            "runs": bw.get("runs", 0),
            "wickets": bw.get("wickets", 0),
            "economy": bw.get("rate", 0),
            "wides": bw.get("wide", 0),
            "no_balls": bw.get("noball", 0),
            "active": bw.get("active", False),
            "sort": bw.get("sort", 99),
        }
        if sb == "S1":
            bowlers_inn1.append(entry)
        else:
            bowlers_inn2.append(entry)

    # Parse lineup (playing XI)
    lineup_raw = raw.get("lineup", [])
    if isinstance(lineup_raw, dict):
        lineup_raw = lineup_raw.get("data", [])

    team1_lineup = []
    team2_lineup = []
    for p in lineup_raw:
        player = {
            "id": p.get("id"),
            "name": p.get("fullname", f"{p.get('firstname', '')} {p.get('lastname', '')}".strip()),
            "batting_style": p.get("battingstyle", ""),
            "bowling_style": p.get("bowlingstyle", ""),
            "position": p.get("position", {}).get("name", "") if isinstance(p.get("position"), dict) else "",
            "image": p.get("image_path", ""),
        }
        # We need to figure out which team — check lineup pivot or team_id
        pivot = p.get("lineup", {})
        if isinstance(pivot, dict):
            tid = pivot.get("team_id")
        else:
            tid = None
        if tid == team1_id:
            team1_lineup.append(player)
        elif tid == team2_id:
            team2_lineup.append(player)
        else:
            # Fallback: first 11 to team1, rest to team2
            if len(team1_lineup) < 11:
                team1_lineup.append(player)
            else:
                team2_lineup.append(player)

    # Build player name map from lineup
    player_names = {}
    for p in lineup_raw:
        player_names[p.get("id")] = p.get("fullname", f"{p.get('firstname', '')} {p.get('lastname', '')}".strip())

    # Attach names to batting/bowling
    for b in batsmen_inn1 + batsmen_inn2:
        b["name"] = player_names.get(b["player_id"], f"Player #{b['player_id']}")
    for bw in bowlers_inn1 + bowlers_inn2:
        bw["name"] = player_names.get(bw["player_id"], f"Player #{bw['player_id']}")

    # Active batsmen (currently at crease)
    active_batsmen = [b for b in (batsmen_inn2 if current_inn == 2 else batsmen_inn1) if b.get("active")]

    # Active bowler
    active_bowler = None
    current_bowlers = bowlers_inn2 if current_inn == 2 else bowlers_inn1
    for bw in current_bowlers:
        if bw.get("active"):
            active_bowler = bw
            break

    # Calculate who's yet to bat
    batted_ids = set(b["player_id"] for b in (batsmen_inn2 if current_inn == 2 else batsmen_inn1))
    batting_lineup = team2_lineup if batting_team == team2 else team1_lineup
    yet_to_bat = [p for p in batting_lineup if p["id"] not in batted_ids]

    # Calculate who's yet to bowl
    bowled_ids = set(bw["player_id"] for bw in current_bowlers)
    bowling_lineup = team1_lineup if batting_team == team2 else team2_lineup
    yet_to_bowl = [p for p in bowling_lineup if p["id"] not in bowled_ids]

    # Recent balls
    balls_raw = raw.get("balls", [])
    if isinstance(balls_raw, dict):
        balls_raw = balls_raw.get("data", [])
    recent_balls = []
    for b in balls_raw[-12:]:
        score = b.get("score", {})
        if isinstance(score, dict):
            rb = score.get("name", "0")
        else:
            rb = str(b.get("score_id", 0))
        recent_balls.append(rb)

    # Scoreboards for extras
    sbs_raw = raw.get("scoreboards", [])
    if isinstance(sbs_raw, dict):
        sbs_raw = sbs_raw.get("data", [])

    extras = {}
    for sb in sbs_raw:
        if sb.get("type") == "extra":
            inn_label = sb.get("scoreboard", "S1")
            extras[inn_label] = {
                "wides": sb.get("wide", 0),
                "no_balls": sb.get("noball_runs", 0),
                "byes": sb.get("bye", 0),
                "leg_byes": sb.get("leg_bye", 0),
                "total": sb.get("wide", 0) + sb.get("noball_runs", 0) + sb.get("bye", 0) + sb.get("leg_bye", 0),
            }

    crr = round(current_score.get("runs", 0) / max(current_score.get("overs", 0.1), 0.1), 2)
    rrr = None
    if target and current_inn == 2:
        remaining_runs = target - current_score.get("runs", 0)
        remaining_overs = 20 - current_score.get("overs", 0)
        rrr = round(remaining_runs / max(remaining_overs, 0.1), 2) if remaining_overs > 0 else 999

    return {
        "fixture_id": raw.get("id"),
        "status": raw.get("status", "Unknown"),
        "note": raw.get("note", ""),
        "team1": team1,
        "team2": team2,
        "team1_code": t1_code,
        "team2_code": t2_code,
        "team1_id": team1_id,
        "team2_id": team2_id,
        "venue": venue_data.get("name", ""),
        "city": venue_data.get("city", ""),
        "toss_won_team_id": raw.get("toss_won_team_id"),
        "elected": raw.get("elected", ""),
        "current_innings": current_inn,
        "batting_team": batting_team,
        "bowling_team": bowling_team,
        "target": target,
        "innings": innings_scores,
        "current_score": current_score,
        "crr": crr,
        "rrr": rrr,
        "batsmen_inn1": sorted(batsmen_inn1, key=lambda x: x["sort"]),
        "batsmen_inn2": sorted(batsmen_inn2, key=lambda x: x["sort"]),
        "bowlers_inn1": sorted(bowlers_inn1, key=lambda x: x["sort"]),
        "bowlers_inn2": sorted(bowlers_inn2, key=lambda x: x["sort"]),
        "active_batsmen": active_batsmen,
        "active_bowler": active_bowler,
        "yet_to_bat": yet_to_bat,
        "yet_to_bowl": yet_to_bowl,
        "team1_lineup": team1_lineup,
        "team2_lineup": team2_lineup,
        "recent_balls": recent_balls,
        "extras": extras,
        "source": "sportmonks",
    }


async def find_ipl_fixture(team1_name: str, team2_name: str) -> Optional[int]:
    """Find a live IPL fixture ID by team names."""
    live = await fetch_live_fixtures()
    t1 = team1_name.lower()
    t2 = team2_name.lower()
    
    for m in live:
        lt = (m.get("localteam", {}).get("name", "") or "").lower()
        vt = (m.get("visitorteam", {}).get("name", "") or "").lower()
        lt_code = (m.get("localteam", {}).get("code", "") or "").lower()
        vt_code = (m.get("visitorteam", {}).get("code", "") or "").lower()
        
        t1_match = any(x in lt or x in vt for x in [t1, t1.split()[0].lower()] if x)
        t2_match = any(x in lt or x in vt for x in [t2, t2.split()[0].lower()] if x)
        
        if t1_match or t2_match:
            logger.info(f"Found live fixture: {m.get('id')} ({lt} vs {vt})")
            return m.get("id")
    
    return None


async def fetch_live_match(team1: str, team2: str, fixture_id: int = None) -> Optional[dict]:
    """Fetch and parse a live match. Finds fixture by team names if no ID provided."""
    fid = fixture_id
    if not fid:
        fid = await find_ipl_fixture(team1, team2)
    
    if not fid:
        logger.info(f"No live fixture found for {team1} vs {team2}")
        return None
    
    raw = await fetch_fixture_details(fid)
    if not raw or raw.get("error"):
        return None
    
    return parse_fixture(raw)



async def fetch_livescores_ipl() -> list:
    """Fetch all currently live IPL matches from SportMonks livescores endpoint.
    Returns list of parsed fixtures with teams, scores, status."""
    url = f"{BASE_URL}/livescores"
    params = {
        "api_token": SPORTMONKS_TOKEN,
        "include": "localteam,visitorteam,runs,batting,bowling,lineup,venue",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(f"SportMonks livescores {resp.status_code}")
                return []
            data = resp.json().get("data", [])
            # Filter for T20 / IPL-like matches (league filtering if available)
            results = []
            for m in data:
                lt = m.get("localteam", {}).get("name", "")
                vt = m.get("visitorteam", {}).get("name", "")
                status = m.get("status", "")
                note = m.get("note", "")
                fixture_id = m.get("id")
                # Include all — we'll match to our schedule later
                entry = {
                    "fixture_id": fixture_id,
                    "team1": lt,
                    "team2": vt,
                    "status": status,
                    "note": note,
                    "league_id": m.get("league_id"),
                    "is_live": status.lower() in ["1st innings", "2nd innings", "innings break", "int.", "live", "ns"],
                    "is_finished": status.lower() in ["finished", "aban.", "cancelled", "no result"],
                }
                # Parse scores
                runs_data = m.get("runs", [])
                for r in runs_data:
                    inn = r.get("inning", 1)
                    entry[f"inn{inn}_runs"] = r.get("score", 0)
                    entry[f"inn{inn}_wickets"] = r.get("wickets", 0)
                    entry[f"inn{inn}_overs"] = r.get("overs", 0)
                results.append(entry)
            return results
    except Exception as e:
        logger.error(f"SportMonks livescores error: {e}")
        return []


async def check_fixture_status(team1: str, team2: str) -> dict:
    """Check the current status of a fixture (live, finished, upcoming)."""
    fid = await find_ipl_fixture(team1, team2)
    if not fid:
        return {"status": "not_found", "fixture_id": None}
    
    raw = await fetch_fixture_details(fid)
    if not raw:
        return {"status": "error", "fixture_id": fid}
    
    status = raw.get("status", "Unknown")
    note = raw.get("note", "")
    winner_team_id = raw.get("winner_team_id")
    
    # Determine winner name
    local = raw.get("localteam", {})
    visitor = raw.get("visitorteam", {})
    winner = None
    if winner_team_id:
        if winner_team_id == local.get("id"):
            winner = local.get("name")
        elif winner_team_id == visitor.get("id"):
            winner = visitor.get("name")
    
    return {
        "status": status,
        "fixture_id": fid,
        "note": note,
        "winner": winner,
        "team1": local.get("name", ""),
        "team2": visitor.get("name", ""),
        "is_finished": status.lower() in ["finished", "aban.", "cancelled", "no result"],
        "is_live": status.lower() in ["1st innings", "2nd innings", "innings break", "int.", "live", "ns"],
    }



async def fetch_recent_fixtures(league_id: int = 1, season_id: int = None) -> list:
    """Fetch recent/completed fixtures from SportMonks for IPL 2026.
    league_id 1 = IPL in SportMonks."""
    params = {
        "include": "localteam,visitorteam,runs,tosswon",
        "sort": "-starting_at",
    }
    if season_id:
        params["filter[season_id]"] = season_id

    # Try fetching by league
    data = await _get(f"leagues/{league_id}/fixtures", params)
    fixtures = data.get("data", [])

    if not fixtures:
        # Fallback: fetch all recent fixtures
        data = await _get("fixtures", {
            "include": "localteam,visitorteam,runs,tosswon",
            "sort": "-starting_at",
            "filter[status]": "Finished",
        })
        fixtures = data.get("data", [])

    results = []
    for raw in fixtures:
        parsed = parse_fixture_result(raw)
        if parsed:
            results.append(parsed)

    return results


def parse_fixture_result(raw: dict) -> dict:
    """Parse a SportMonks fixture into a match result for DB storage."""
    if not raw:
        return None

    local = raw.get("localteam", {}) or {}
    visitor = raw.get("visitorteam", {}) or {}
    status = (raw.get("status") or "").lower()

    # Only process finished matches
    if status not in ("finished", "aban.", "no result"):
        return None

    winner_team_id = raw.get("winner_team_id")
    winner = None
    if winner_team_id:
        if winner_team_id == local.get("id"):
            winner = local.get("name", "")
        elif winner_team_id == visitor.get("id"):
            winner = visitor.get("name", "")

    # Extract scores from runs
    runs_data = raw.get("runs", []) or []
    team1_score = ""
    team2_score = ""
    for r in runs_data:
        if isinstance(r, dict):
            tid = r.get("team_id")
            score_str = f"{r.get('score', 0)}/{r.get('wickets', 0)} ({r.get('overs', 0)})"
            if tid == local.get("id"):
                team1_score = score_str
            elif tid == visitor.get("id"):
                team2_score = score_str

    toss_won = raw.get("tosswon", {}) or {}

    return {
        "fixture_id": raw.get("id"),
        "team1": local.get("name", ""),
        "team2": visitor.get("name", ""),
        "team1_code": (local.get("code") or "")[:5],
        "team2_code": (visitor.get("code") or "")[:5],
        "winner": winner,
        "status": "completed",
        "note": raw.get("note", ""),
        "team1_score": team1_score,
        "team2_score": team2_score,
        "toss_won_by": toss_won.get("name", ""),
        "starting_at": raw.get("starting_at", ""),
    }
