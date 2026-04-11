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

    # Parse lineup (playing XI + substitutes)
    lineup_raw = raw.get("lineup", [])
    if isinstance(lineup_raw, dict):
        lineup_raw = lineup_raw.get("data", [])

    team1_lineup = []
    team2_lineup = []
    team1_playing_xi = []
    team2_playing_xi = []
    unassigned_players = []

    for p in lineup_raw:
        # Robust pivot extraction — handle dict, None, or unexpected types
        pivot = p.get("lineup") or {}
        if not isinstance(pivot, dict):
            pivot = {}

        tid = pivot.get("team_id")
        is_sub = pivot.get("substitution", False)

        # Normalize substitution flag (API may return int 0/1 instead of bool)
        if isinstance(is_sub, int):
            is_sub = bool(is_sub)

        player = {
            "id": p.get("id"),
            "name": p.get("fullname", f"{p.get('firstname', '')} {p.get('lastname', '')}".strip()),
            "batting_style": p.get("battingstyle", ""),
            "bowling_style": p.get("bowlingstyle", ""),
            "position": p.get("position", {}).get("name", "") if isinstance(p.get("position"), dict) else "",
            "image": p.get("image_path", ""),
            "is_sub": is_sub,
        }

        if tid == team1_id:
            team1_lineup.append(player)
            if not is_sub:
                team1_playing_xi.append(player)
        elif tid == team2_id:
            team2_lineup.append(player)
            if not is_sub:
                team2_playing_xi.append(player)
        else:
            # No team_id from pivot — track for scorecard-based resolution
            unassigned_players.append(player)

    # ── Layer 2: Build confirmed player→team map from batting/bowling scorecard ──
    inn1_bat_tid = innings_scores.get("1", {}).get("team_id")
    inn2_bat_tid = innings_scores.get("2", {}).get("team_id")
    bowl_inn1_tid = (team2_id if inn1_bat_tid == team1_id else
                     team1_id if inn1_bat_tid == team2_id else None)
    bowl_inn2_tid = (team2_id if inn2_bat_tid == team1_id else
                     team1_id if inn2_bat_tid == team2_id else None)

    scorecard_team_map = {}  # player_id → confirmed team_id
    for b in batsmen_inn1:
        if inn1_bat_tid:
            scorecard_team_map[b.get("player_id")] = inn1_bat_tid
    for b in batsmen_inn2:
        if inn2_bat_tid:
            scorecard_team_map[b.get("player_id")] = inn2_bat_tid
    for bw in bowlers_inn1:
        if bowl_inn1_tid:
            scorecard_team_map[bw.get("player_id")] = bowl_inn1_tid
    for bw in bowlers_inn2:
        if bowl_inn2_tid:
            scorecard_team_map[bw.get("player_id")] = bowl_inn2_tid

    # ── Layer 2b: Resolve unassigned players using scorecard evidence ──
    if unassigned_players:
        logger.warning(f"Lineup pivot missing team_id for {len(unassigned_players)}/{len(lineup_raw)} players")
        for player in unassigned_players:
            pid = player["id"]
            confirmed_tid = scorecard_team_map.get(pid)
            if confirmed_tid == team1_id:
                team1_lineup.append(player)
                team1_playing_xi.append(player)
            elif confirmed_tid == team2_id:
                team2_lineup.append(player)
                team2_playing_xi.append(player)
            else:
                logger.debug(f"Skipping unresolvable player {player['name']} (id={pid})")

    # ── Layer 3: Validate & cap Playing XI (max 12 = 11 + 1 impact sub) ──
    MAX_XI = 12
    t1_confirmed_ids = {pid for pid, tid in scorecard_team_map.items() if tid == team1_id}
    t2_confirmed_ids = {pid for pid, tid in scorecard_team_map.items() if tid == team2_id}

    def _prune_xi(xi_list, confirmed_ids, team_label):
        """Prune oversized playing XI using scorecard-confirmed players."""
        if len(xi_list) <= MAX_XI:
            return xi_list
        logger.warning(f"{team_label} playing XI too large ({len(xi_list)}), pruning to {MAX_XI}")
        if confirmed_ids:
            confirmed = [p for p in xi_list if p["id"] in confirmed_ids]
            unconfirmed = [p for p in xi_list if p["id"] not in confirmed_ids]
            pruned = confirmed + unconfirmed[:max(0, MAX_XI - len(confirmed))]
        else:
            pruned = xi_list[:MAX_XI]
        return pruned

    team1_playing_xi = _prune_xi(team1_playing_xi, t1_confirmed_ids, "T1")
    team2_playing_xi = _prune_xi(team2_playing_xi, t2_confirmed_ids, "T2")

    logger.info(f"Lineup parsed: T1 XI={len(team1_playing_xi)}/{len(team1_lineup)}, "
                f"T2 XI={len(team2_playing_xi)}/{len(team2_lineup)}, "
                f"scorecard confirmed={len(scorecard_team_map)}, "
                f"unassigned={len(unassigned_players)}")

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
        "team1_playing_xi": team1_playing_xi,
        "team2_playing_xi": team2_playing_xi,
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



# ── IPL Team Name to SportMonks v2 Team ID mapping ──
TEAM_SM_IDS = {
    "chennai super kings": 2,
    "delhi capitals": 3,
    "punjab kings": 4,
    "kolkata knight riders": 5,
    "mumbai indians": 6,
    "rajasthan royals": 7,
    "royal challengers bengaluru": 8,
    "royal challengers bangalore": 8,
    "sunrisers hyderabad": 9,
    "gujarat titans": 1976,
    "lucknow super giants": 1979,
}

# IPL Season IDs (last 3 years for player form)
IPL_SEASON_IDS = {2024: 1484, 2025: 1689, 2026: 1795}

# In-memory cache for season fixtures and player stats
_season_fixtures_cache: Dict[int, list] = {}
_player_stats_cache: Dict[int, dict] = {}  # player_id -> aggregated stats


def _get_team_sm_id(team_name: str) -> Optional[int]:
    """Resolve team name to SportMonks team ID."""
    lower = team_name.lower().strip()
    for name, tid in TEAM_SM_IDS.items():
        if name in lower or lower in name:
            return tid
    # Partial match on first word
    first_word = lower.split()[0] if lower else ""
    for name, tid in TEAM_SM_IDS.items():
        if first_word and first_word in name:
            return tid
    return None


async def fetch_season_fixtures(season_id: int) -> list:
    """Fetch all fixtures for an IPL season. Cached in memory."""
    if season_id in _season_fixtures_cache:
        return _season_fixtures_cache[season_id]

    data = await _get(f"seasons/{season_id}", {"include": "fixtures"})
    raw_fixtures = data.get("data", {}).get("fixtures", {})
    if isinstance(raw_fixtures, dict):
        raw_fixtures = raw_fixtures.get("data", [])

    _season_fixtures_cache[season_id] = raw_fixtures
    logger.info(f"Cached {len(raw_fixtures)} fixtures for season {season_id}")
    return raw_fixtures


async def fetch_team_last_completed_fixture(team_name: str) -> Optional[dict]:
    """Find the most recent completed fixture for a team in IPL 2026.

    Returns the raw fixture dict with id, localteam_id, visitorteam_id, note, starting_at.
    """
    team_id = _get_team_sm_id(team_name)
    if not team_id:
        logger.warning(f"Could not resolve team ID for: {team_name}")
        return None

    season_id = IPL_SEASON_IDS.get(2026, 1795)
    fixtures = await fetch_season_fixtures(season_id)
    finished = [f for f in fixtures if (f.get("status") or "").lower() == "finished"]
    # Sort by starting_at descending
    finished.sort(key=lambda x: x.get("starting_at", ""), reverse=True)

    for f in finished:
        if f.get("localteam_id") == team_id or f.get("visitorteam_id") == team_id:
            logger.info(f"Last completed match for {team_name} (id={team_id}): fixture {f.get('id')}")
            return f
    logger.warning(f"No completed fixture found for {team_name} (id={team_id})")
    return None


async def fetch_playing_xi_from_last_match(team_name: str) -> list:
    """Fetch the Playing XI for a team from their most recent completed IPL match.

    Pipeline (per user doc):
    1. Resolve team name → SportMonks team ID
    2. Find last completed fixture from season fixtures
    3. Fetch fixture with lineup include
    4. Extract non-substitute players = Playing XI
    5. Enrich with batting/bowling style from player endpoint
    """
    fixture = await fetch_team_last_completed_fixture(team_name)
    if not fixture:
        return []

    fixture_id = fixture.get("id")
    team_id = _get_team_sm_id(team_name)

    # Fetch fixture with lineup
    data = await _get(f"fixtures/{fixture_id}", {"include": "lineup"})
    fixture_detail = data.get("data", {})

    lineup_raw = fixture_detail.get("lineup", {})
    if isinstance(lineup_raw, dict):
        lineup_raw = lineup_raw.get("data", [])

    if not lineup_raw:
        logger.warning(f"No lineup data for fixture {fixture_id}")
        return []

    # Extract Playing XI (non-subs) for this team
    xi = _parse_lineup(lineup_raw, team_id)
    logger.info(f"Playing XI for {team_name} from fixture {fixture_id}: {len(xi)} players")

    # Enrich players with batting/bowling style (parallel fetch)
    enriched = await _enrich_players(xi)
    return enriched


async def _enrich_players(players: list) -> list:
    """Enrich player list with batting_style, bowling_style, position from player endpoint."""
    import asyncio
    enriched = []

    async def _fetch_player(p):
        pid = p.get("sm_player_id")
        if not pid:
            return p
        data = await _get(f"players/{pid}")
        pd = data.get("data", {})
        if pd:
            p["batting_style"] = pd.get("battingstyle", p.get("batting_style", ""))
            p["bowling_style"] = pd.get("bowlingstyle", p.get("bowling_style", ""))
            pos = pd.get("position", {})
            if isinstance(pos, dict):
                p["position"] = pos.get("name", "")
            p["country_id"] = pd.get("country_id")
        return p

    # Fetch in batches of 5 to respect rate limits
    batch_size = 5
    for i in range(0, len(players), batch_size):
        batch = players[i:i + batch_size]
        results = await asyncio.gather(*[_fetch_player(p) for p in batch], return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Player enrichment error: {r}")
            elif isinstance(r, dict):
                enriched.append(r)

    return enriched


async def fetch_fixture_batting_bowling(fixture_id: int) -> dict:
    """Fetch batting and bowling scorecard data for a fixture."""
    data = await _get(f"fixtures/{fixture_id}", {"include": "batting,bowling,lineup"})
    fixture = data.get("data", {})

    batting_raw = fixture.get("batting", {})
    if isinstance(batting_raw, dict):
        batting_raw = batting_raw.get("data", [])

    bowling_raw = fixture.get("bowling", {})
    if isinstance(bowling_raw, dict):
        bowling_raw = bowling_raw.get("data", [])

    lineup_raw = fixture.get("lineup", {})
    if isinstance(lineup_raw, dict):
        lineup_raw = lineup_raw.get("data", [])

    # Build player name map from lineup
    player_names = {}
    for p in lineup_raw:
        player_names[p.get("id")] = p.get("fullname", "")

    batting = []
    for b in batting_raw:
        batting.append({
            "player_id": b.get("player_id"),
            "player_name": player_names.get(b.get("player_id"), ""),
            "runs": b.get("score", 0),
            "balls": b.get("ball", 0),
            "fours": b.get("four_x", 0),
            "sixes": b.get("six_x", 0),
            "strike_rate": round((b.get("score", 0) / max(b.get("ball", 1), 1)) * 100, 1),
            "scoreboard": b.get("scoreboard", "S1"),
            "team_id": b.get("team_id"),
        })

    bowling = []
    for bw in bowling_raw:
        bowling.append({
            "player_id": bw.get("player_id"),
            "player_name": player_names.get(bw.get("player_id"), ""),
            "overs": bw.get("overs", 0),
            "wickets": bw.get("wickets", 0),
            "runs_conceded": bw.get("runs", 0),
            "economy": bw.get("rate", 0),
            "maidens": bw.get("medians", 0),
            "scoreboard": bw.get("scoreboard", "S1"),
            "team_id": bw.get("team_id"),
        })

    return {
        "fixture_id": fixture_id,
        "batting": batting,
        "bowling": bowling,
        "player_names": player_names,
    }


async def fetch_team_recent_performance(team_name: str, num_matches: int = 5) -> dict:
    """Fetch batting/bowling stats for a team's last N completed matches.

    Returns per-player aggregated stats:
    {
        player_id: {
            "name": str,
            "matches": int,
            "batting": {"runs": int, "balls": int, "innings": int, "avg": float, "sr": float},
            "bowling": {"overs": float, "wickets": int, "runs_conceded": int, "innings": int, "economy": float},
        }
    }
    """
    team_id = _get_team_sm_id(team_name)
    if not team_id:
        return {}

    # Collect finished fixtures across seasons (most recent first)
    all_finished = []
    for year in [2026, 2025, 2024]:
        season_id = IPL_SEASON_IDS.get(year)
        if not season_id:
            continue
        fixtures = await fetch_season_fixtures(season_id)
        finished = [f for f in fixtures if (f.get("status") or "").lower() == "finished"]
        # Filter to team's matches
        team_fixtures = [f for f in finished
                         if f.get("localteam_id") == team_id or f.get("visitorteam_id") == team_id]
        team_fixtures.sort(key=lambda x: x.get("starting_at", ""), reverse=True)
        all_finished.extend(team_fixtures)
        if len(all_finished) >= num_matches:
            break

    all_finished = all_finished[:num_matches]
    if not all_finished:
        return {}

    logger.info(f"Fetching stats from {len(all_finished)} matches for {team_name}")

    # Fetch batting/bowling for each fixture
    player_stats = {}
    for fix in all_finished:
        fid = fix.get("id")
        try:
            data = await fetch_fixture_batting_bowling(fid)
        except Exception as e:
            logger.warning(f"Error fetching fixture {fid} stats: {e}")
            continue

        # Aggregate batting — ONLY for this team's players
        for b in data.get("batting", []):
            if b.get("team_id") and b["team_id"] != team_id:
                continue  # Skip opponent's players
            pid = b["player_id"]
            if pid not in player_stats:
                player_stats[pid] = {
                    "name": b["player_name"],
                    "matches": 0,
                    "batting": {"runs": 0, "balls": 0, "innings": 0, "fours": 0, "sixes": 0},
                    "bowling": {"overs": 0, "wickets": 0, "runs_conceded": 0, "innings": 0, "maidens": 0},
                }
            player_stats[pid]["name"] = b["player_name"] or player_stats[pid]["name"]
            player_stats[pid]["batting"]["runs"] += b["runs"]
            player_stats[pid]["batting"]["balls"] += b["balls"]
            player_stats[pid]["batting"]["innings"] += 1
            player_stats[pid]["batting"]["fours"] += b["fours"]
            player_stats[pid]["batting"]["sixes"] += b["sixes"]

        # Aggregate bowling — ONLY for this team's players
        for bw in data.get("bowling", []):
            if bw.get("team_id") and bw["team_id"] != team_id:
                continue  # Skip opponent's bowlers
            pid = bw["player_id"]
            if pid not in player_stats:
                player_stats[pid] = {
                    "name": bw["player_name"],
                    "matches": 0,
                    "batting": {"runs": 0, "balls": 0, "innings": 0, "fours": 0, "sixes": 0},
                    "bowling": {"overs": 0, "wickets": 0, "runs_conceded": 0, "innings": 0, "maidens": 0},
                }
            player_stats[pid]["name"] = bw["player_name"] or player_stats[pid]["name"]
            player_stats[pid]["bowling"]["overs"] += bw["overs"]
            player_stats[pid]["bowling"]["wickets"] += bw["wickets"]
            player_stats[pid]["bowling"]["runs_conceded"] += bw["runs_conceded"]
            player_stats[pid]["bowling"]["innings"] += 1
            player_stats[pid]["bowling"]["maidens"] += bw["maidens"]

        # Count match appearances (only this team's players)
        seen_players = set()
        for b in data.get("batting", []):
            if b.get("team_id") and b["team_id"] != team_id:
                continue
            seen_players.add(b["player_id"])
        for bw in data.get("bowling", []):
            if bw.get("team_id") and bw["team_id"] != team_id:
                continue
            seen_players.add(bw["player_id"])
        for pid in seen_players:
            if pid in player_stats:
                player_stats[pid]["matches"] += 1

    # Compute derived stats
    for pid, ps in player_stats.items():
        bat = ps["batting"]
        if bat["innings"] > 0:
            bat["avg"] = round(bat["runs"] / bat["innings"], 1)
            bat["sr"] = round((bat["runs"] / max(bat["balls"], 1)) * 100, 1)
        else:
            bat["avg"] = 0
            bat["sr"] = 0

        bowl = ps["bowling"]
        if bowl["innings"] > 0 and bowl["overs"] > 0:
            bowl["economy"] = round(bowl["runs_conceded"] / bowl["overs"], 2)
            bowl["avg"] = round(bowl["runs_conceded"] / max(bowl["wickets"], 1), 1)
        else:
            bowl["economy"] = 0
            bowl["avg"] = 0

    return player_stats


async def sync_player_performance_to_db(db) -> dict:
    """Sync player performance stats from last 3 IPL seasons (2024-2026) into MongoDB.

    Stores aggregated per-player stats for use in form calculations.
    Returns summary of sync operation.
    """
    all_player_stats = {}
    total_fixtures = 0

    for year, season_id in sorted(IPL_SEASON_IDS.items()):
        fixtures = await fetch_season_fixtures(season_id)
        finished = [f for f in fixtures if (f.get("status") or "").lower() == "finished"]
        logger.info(f"Syncing {len(finished)} finished matches from IPL {year}")

        for fix in finished:
            fid = fix.get("id")
            try:
                data = await fetch_fixture_batting_bowling(fid)
                total_fixtures += 1
            except Exception as e:
                logger.warning(f"Error fetching fixture {fid}: {e}")
                continue

            for b in data.get("batting", []):
                pid = b["player_id"]
                if pid not in all_player_stats:
                    all_player_stats[pid] = {
                        "player_id": pid,
                        "name": b["player_name"],
                        "batting": {"runs": 0, "balls": 0, "innings": 0, "fours": 0, "sixes": 0, "fifties": 0, "hundreds": 0},
                        "bowling": {"overs": 0, "wickets": 0, "runs_conceded": 0, "innings": 0, "maidens": 0, "three_fers": 0},
                        "matches": 0,
                        "seasons": [],
                    }
                ps = all_player_stats[pid]
                ps["name"] = b["player_name"] or ps["name"]
                ps["batting"]["runs"] += b["runs"]
                ps["batting"]["balls"] += b["balls"]
                ps["batting"]["innings"] += 1
                ps["batting"]["fours"] += b["fours"]
                ps["batting"]["sixes"] += b["sixes"]
                if b["runs"] >= 50:
                    ps["batting"]["fifties"] += 1
                if b["runs"] >= 100:
                    ps["batting"]["hundreds"] += 1
                if year not in ps["seasons"]:
                    ps["seasons"].append(year)

            for bw in data.get("bowling", []):
                pid = bw["player_id"]
                if pid not in all_player_stats:
                    all_player_stats[pid] = {
                        "player_id": pid,
                        "name": bw["player_name"],
                        "batting": {"runs": 0, "balls": 0, "innings": 0, "fours": 0, "sixes": 0, "fifties": 0, "hundreds": 0},
                        "bowling": {"overs": 0, "wickets": 0, "runs_conceded": 0, "innings": 0, "maidens": 0, "three_fers": 0},
                        "matches": 0,
                        "seasons": [],
                    }
                ps = all_player_stats[pid]
                ps["name"] = bw["player_name"] or ps["name"]
                ps["bowling"]["overs"] += bw["overs"]
                ps["bowling"]["wickets"] += bw["wickets"]
                ps["bowling"]["runs_conceded"] += bw["runs_conceded"]
                ps["bowling"]["innings"] += 1
                ps["bowling"]["maidens"] += bw["maidens"]
                if bw["wickets"] >= 3:
                    ps["bowling"]["three_fers"] += 1
                if year not in ps["seasons"]:
                    ps["seasons"].append(year)

    # Compute derived stats and store in DB
    for pid, ps in all_player_stats.items():
        bat = ps["batting"]
        if bat["innings"] > 0:
            bat["avg"] = round(bat["runs"] / bat["innings"], 1)
            bat["sr"] = round((bat["runs"] / max(bat["balls"], 1)) * 100, 1)
        else:
            bat["avg"] = 0
            bat["sr"] = 0

        bowl = ps["bowling"]
        if bowl["innings"] > 0 and bowl["overs"] > 0:
            bowl["economy"] = round(bowl["runs_conceded"] / bowl["overs"], 2)
            bowl["avg"] = round(bowl["runs_conceded"] / max(bowl["wickets"], 1), 1)
        else:
            bowl["economy"] = 0
            bowl["avg"] = 0

    # Bulk upsert to MongoDB
    from pymongo import UpdateOne
    ops = []
    for pid, ps in all_player_stats.items():
        ops.append(UpdateOne(
            {"player_id": pid},
            {"$set": ps},
            upsert=True,
        ))

    if ops:
        result = await db.player_performance.bulk_write(ops)
        logger.info(f"Synced {len(ops)} player stats from {total_fixtures} fixtures")

    return {
        "players_synced": len(all_player_stats),
        "fixtures_processed": total_fixtures,
        "seasons": list(IPL_SEASON_IDS.keys()),
    }


def _parse_lineup(lineup_data: list, team_id: int) -> list:
    """Extract Playing XI (non-subs) for a specific team from SportMonks lineup data.
    Caps at 12 players (11 + 1 impact sub) to prevent full-squad leakage."""
    xi = []
    for p in lineup_data:
        lineup_info = p.get("lineup") or {}
        if not isinstance(lineup_info, dict):
            lineup_info = {}
        if lineup_info.get("team_id") != team_id:
            continue
        is_sub = lineup_info.get("substitution", False)
        if isinstance(is_sub, int):
            is_sub = bool(is_sub)
        if is_sub:
            continue  # Skip impact player subs
        xi.append({
            "name": p.get("fullname", ""),
            "sm_player_id": p.get("id"),
            "batting_style": p.get("battingstyle", ""),
            "bowling_style": p.get("bowlingstyle", ""),
            "is_captain": lineup_info.get("captain", False),
            "is_wicketkeeper": lineup_info.get("wicketkeeper", False),
        })
    # Hard cap at 12 (11 + impact sub)
    if len(xi) > 12:
        logger.warning(f"_parse_lineup: team {team_id} has {len(xi)} non-sub players, capping to 12")
        xi = xi[:12]
    return xi


async def fetch_playing_xi_from_live(team1: str, team2: str) -> dict:
    """Fetch Playing XI for both teams from the current live match."""
    data = await _get("livescores", {
        "include": "lineup,localteam,visitorteam"
    })
    fixtures = data.get("data", [])
    t1_lower = team1.lower()
    t2_lower = team2.lower()

    for f in fixtures:
        lt = f.get("localteam", {})
        vt = f.get("visitorteam", {})
        lt_name = (lt.get("name", "") or "").lower()
        vt_name = (vt.get("name", "") or "").lower()

        match = False
        if (t1_lower in lt_name or lt_name in t1_lower) and (t2_lower in vt_name or vt_name in t2_lower):
            match = True
        elif (t2_lower in lt_name or lt_name in t2_lower) and (t1_lower in vt_name or vt_name in t1_lower):
            match = True

        if not match:
            continue

        lineup = f.get("lineup", {})
        if isinstance(lineup, dict):
            lineup_data = lineup.get("data", [])
        elif isinstance(lineup, list):
            lineup_data = lineup
        else:
            lineup_data = []

        if not lineup_data:
            continue

        lt_id = lt.get("id")
        vt_id = vt.get("id")
        lt_xi = _parse_lineup(lineup_data, lt_id)
        vt_xi = _parse_lineup(lineup_data, vt_id)

        # Map to team1/team2
        if t1_lower in lt_name or lt_name in t1_lower:
            return {
                "team1_xi": lt_xi,
                "team2_xi": vt_xi,
                "fixture_id": f.get("id"),
                "source": "live",
            }
        else:
            return {
                "team1_xi": vt_xi,
                "team2_xi": lt_xi,
                "fixture_id": f.get("id"),
                "source": "live",
            }

    return {"team1_xi": [], "team2_xi": [], "source": "not_found"}


async def fetch_last_played_xi(team_name: str) -> list:
    """Fetch the Playing XI for a team from their most recent completed match.

    Pipeline (per user doc):
    1. Try live fixtures first (current match lineup is most relevant)
    2. Fallback: Find last completed match from IPL 2026 season fixtures
    3. Fetch fixture with lineup include
    4. Extract non-substitute players = Playing XI

    Returns a list of player dicts (name, batting_style, bowling_style, captain, wk).
    """
    # Step 1: Try live fixtures first (today's lineup is most relevant)
    data = await _get("livescores", {
        "include": "lineup,localteam,visitorteam"
    })
    fixtures = data.get("data", [])
    team_lower = team_name.lower()

    for f in fixtures:
        lt = f.get("localteam", {})
        vt = f.get("visitorteam", {})
        lt_name = (lt.get("name", "") or "").lower()
        vt_name = (vt.get("name", "") or "").lower()

        team_id = None
        if team_lower in lt_name or lt_name in team_lower:
            team_id = lt.get("id")
        elif team_lower in vt_name or vt_name in team_lower:
            team_id = vt.get("id")

        if team_id is None:
            continue

        lineup = f.get("lineup", {})
        if isinstance(lineup, dict):
            lineup_data = lineup.get("data", [])
        elif isinstance(lineup, list):
            lineup_data = lineup
        else:
            lineup_data = []

        xi = _parse_lineup(lineup_data, team_id)
        if len(xi) >= 11:
            logger.info(f"Found Playing XI for {team_name} from live match: {len(xi)} players")
            return xi

    # Step 2: Find last completed match from IPL season fixtures
    team_id = _get_team_sm_id(team_name)
    if not team_id:
        logger.warning(f"Could not resolve team ID for: {team_name}")
        return []

    season_id = IPL_SEASON_IDS.get(2026, 1795)
    season_fixtures = await fetch_season_fixtures(season_id)
    finished = [f for f in season_fixtures if (f.get("status") or "").lower() == "finished"]
    finished.sort(key=lambda x: x.get("starting_at", ""), reverse=True)

    # Find team's most recent completed match
    target_fixture_id = None
    for f in finished:
        if f.get("localteam_id") == team_id or f.get("visitorteam_id") == team_id:
            target_fixture_id = f.get("id")
            break

    if not target_fixture_id:
        logger.warning(f"No completed fixture found for {team_name}")
        return []

    # Step 3: Fetch fixture with lineup
    data = await _get(f"fixtures/{target_fixture_id}", {"include": "lineup"})
    fixture_detail = data.get("data", {})
    lineup = fixture_detail.get("lineup", {})
    if isinstance(lineup, dict):
        lineup_data = lineup.get("data", [])
    elif isinstance(lineup, list):
        lineup_data = lineup
    else:
        lineup_data = []

    # Step 4: Extract non-sub Playing XI
    xi = _parse_lineup(lineup_data, team_id)
    if xi:
        logger.info(f"Found Playing XI for {team_name} from fixture {target_fixture_id}: {len(xi)} players")
    else:
        logger.warning(f"No lineup data for {team_name} in fixture {target_fixture_id}")

    return xi


async def fetch_fixture_start_time(team1: str, team2: str) -> Optional[str]:
    """Fetch the actual match start time from SportMonks season fixtures.
    
    Returns the `starting_at` field (UTC datetime string) from SportMonks,
    which is the authoritative source for match timing.
    This helps distinguish afternoon (3:30 PM IST) vs evening (7:30 PM IST) matches
    for accurate toss/dew impact calculations.
    """
    t1_id = _get_team_sm_id(team1)
    t2_id = _get_team_sm_id(team2)
    if not t1_id or not t2_id:
        return None
    
    season_id = IPL_SEASON_IDS.get(2026, 1795)
    fixtures = await fetch_season_fixtures(season_id)
    
    for f in fixtures:
        lt_id = f.get("localteam_id")
        vt_id = f.get("visitorteam_id")
        if (lt_id == t1_id and vt_id == t2_id) or (lt_id == t2_id and vt_id == t1_id):
            starting_at = f.get("starting_at", "")
            if starting_at:
                logger.info(f"SportMonks start time for {team1} vs {team2}: {starting_at}")
                return starting_at
    
    return None


async def fetch_ipl_season_schedule(season_id: int = None) -> list:
    """Fetch the full IPL season schedule from SportMonks API.

    Returns a list of match dicts in our DB schema format, ready for upsert.
    Each match includes: teams, venue, date, status, scores, winner, toss.
    """
    if season_id is None:
        season_id = IPL_SEASON_IDS.get(2026, 1795)

    # Step 1: Get fixture IDs from season endpoint (lightweight)
    season_data = await _get(f"seasons/{season_id}", {"include": "fixtures"})
    raw_fixtures = season_data.get("data", {}).get("fixtures", {})
    if isinstance(raw_fixtures, dict):
        raw_fixtures = raw_fixtures.get("data", [])

    if not raw_fixtures:
        logger.warning(f"No fixtures returned from SportMonks for season {season_id}")
        return []

    fixture_ids = [f.get("id") for f in raw_fixtures if f.get("id")]
    logger.info(f"SportMonks season {season_id}: found {len(fixture_ids)} fixture IDs")

    # Step 2: Fetch each fixture with full includes (batch in groups of 5)
    import asyncio
    matches = []

    async def _fetch_one(fid):
        data = await _get(f"fixtures/{fid}", {
            "include": "localteam,visitorteam,venue,runs,tosswon"
        })
        return data.get("data", {})

    batch_size = 5
    for i in range(0, len(fixture_ids), batch_size):
        batch = fixture_ids[i:i + batch_size]
        results = await asyncio.gather(*[_fetch_one(fid) for fid in batch], return_exceptions=True)
        for fix in results:
            if isinstance(fix, Exception) or not fix:
                continue
            parsed = _parse_fixture_to_schedule(fix)
            if parsed:
                matches.append(parsed)

    # Sort by starting_at and assign match numbers
    matches.sort(key=lambda x: x.get("dateTimeGMT", ""))
    for idx, m in enumerate(matches):
        m["match_number"] = idx + 1
        m["matchId"] = f"ipl2026_{idx + 1:03d}"

    logger.info(f"Fetched {len(matches)} full fixtures from SportMonks season {season_id}")
    return matches


def _parse_fixture_to_schedule(fix: dict) -> dict:
    """Parse a single SportMonks fixture into our schedule DB format."""
    if not fix:
        return None

    local = fix.get("localteam", {}) or {}
    visitor = fix.get("visitorteam", {}) or {}
    venue_data = fix.get("venue", {}) or {}
    toss_won = fix.get("tosswon", {}) or {}

    # Handle nested data wrappers
    if isinstance(local, dict) and "data" in local:
        local = local["data"]
    if isinstance(visitor, dict) and "data" in visitor:
        visitor = visitor["data"]
    if isinstance(venue_data, dict) and "data" in venue_data:
        venue_data = venue_data["data"]
    if isinstance(toss_won, dict) and "data" in toss_won:
        toss_won = toss_won["data"]

    team1 = local.get("name", "")
    team2 = visitor.get("name", "")
    if not team1 or not team2:
        return None

    t1_code = local.get("code", "")
    t2_code = visitor.get("code", "")

    # Status mapping
    raw_status = (fix.get("status") or "").lower()
    if raw_status in ("finished", "aban.", "no result"):
        status = "Completed"
    elif raw_status in ("1st innings", "2nd innings", "innings break", "int.", "live"):
        status = "live"
    else:
        status = "Upcoming"

    # Winner
    winner = None
    winner_team_id = fix.get("winner_team_id")
    if winner_team_id:
        if winner_team_id == local.get("id"):
            winner = team1
        elif winner_team_id == visitor.get("id"):
            winner = team2

    # Scores
    runs_data = fix.get("runs", []) or []
    if isinstance(runs_data, dict):
        runs_data = runs_data.get("data", [])
    team1_score = ""
    team2_score = ""
    for r in runs_data:
        if isinstance(r, dict):
            tid = r.get("team_id")
            s = f"{r.get('score', 0)}/{r.get('wickets', 0)} ({r.get('overs', 0)})"
            if tid == local.get("id"):
                team1_score = s
            elif tid == visitor.get("id"):
                team2_score = s

    score_text = ""
    if team1_score or team2_score:
        score_text = f"{t1_code} {team1_score} - {t2_code} {team2_score}".strip()

    venue_name = venue_data.get("name", "") if isinstance(venue_data, dict) else ""
    city = venue_data.get("city", "") if isinstance(venue_data, dict) else ""

    return {
        "fixture_id": fix.get("id"),
        "team1": team1,
        "team2": team2,
        "team1Short": t1_code,
        "team2Short": t2_code,
        "team1_id": local.get("id"),
        "team2_id": visitor.get("id"),
        "venue": venue_name,
        "city": city,
        "dateTimeGMT": fix.get("starting_at", ""),
        "matchType": "T20",
        "series": "IPL 2026",
        "status": status,
        "winner": winner,
        "note": fix.get("note", ""),
        "score": score_text if status == "Completed" else "",
        "team1_score": team1_score,
        "team2_score": team2_score,
        "toss_won_by": toss_won.get("name", "") if isinstance(toss_won, dict) else "",
        "source": "sportmonks",
    }
