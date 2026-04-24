import os
import logging
import asyncio
from datetime import datetime, timezone
import httpx
from typing import Any, Dict, List, Optional

APP_META_PLAYER_PERF_ID = "player_performance"


async def record_player_performance_db_touch(db, *, source: str, **extra: Any) -> None:
    """Bump monotonic metadata so pre-match UI can prompt re-predict after sync/enrich."""
    payload = {
        "last_update_at": datetime.now(timezone.utc).isoformat(),
        "last_update_source": source,
        **extra,
    }
    await db.app_meta.update_one(
        {"_id": APP_META_PLAYER_PERF_ID},
        {"$set": payload},
        upsert=True,
    )


async def get_player_performance_meta(db) -> dict:
    doc = await db.app_meta.find_one({"_id": APP_META_PLAYER_PERF_ID}, {"_id": 0})
    return dict(doc) if doc else {}

from services.cricket_phase_utils import (
    PHASE_DEATH,
    PHASE_MID,
    PHASE_PP,
    accumulate_phases_from_balls,
    empty_phases_root,
    finalize_phase_derived,
    normalize_balls_payload,
)
from services.player_name_canonical import canonical_player_display_name

logger = logging.getLogger(__name__)

SPORTMONKS_TOKEN = os.environ.get("SPORTMONKS_API_TOKEN", "")
# Cricket API v2.0 — see https://docs.sportmonks.com/v2/cricket-api
BASE_URL = "https://cricket.sportmonks.com/api/v2.0"


def _sm_response_failed(payload) -> bool:
    """True if _get returned an error placeholder (see _get exception path)."""
    if not isinstance(payload, dict):
        return True
    return bool(payload.get("error"))


# Transient SportMonks / CDN responses — safe to retry (bulk sync hammers fixtures/{id}).
_SM_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})
_SM_GET_MAX_RETRIES = 4
_SM_GET_TIMEOUT_S = 35.0


async def _get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to SportMonks Cricket API v2.0 (token query param).

    Retries on rate-limit and server errors (429/502/503/504) and common transient
    network failures so player sync is less brittle during SportMonks outages.
    """
    if not SPORTMONKS_TOKEN:
        return {"error": "SPORTMONKS_API_TOKEN not configured"}

    url = f"{BASE_URL}/{endpoint}"
    query = {"api_token": SPORTMONKS_TOKEN}
    if params:
        query.update(params)

    last_exc: Optional[Exception] = None
    for attempt in range(_SM_GET_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_SM_GET_TIMEOUT_S) as client:
                resp = await client.get(url, params=query)
                if resp.status_code in _SM_RETRYABLE_STATUS and attempt < _SM_GET_MAX_RETRIES - 1:
                    delay = min(45.0, 1.5 * (2**attempt))
                    logger.warning(
                        "SportMonks %s: HTTP %s (attempt %s/%s), retrying in %.1fs",
                        endpoint,
                        resp.status_code,
                        attempt + 1,
                        _SM_GET_MAX_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                resp.raise_for_status()
                body = resp.json()
                if (
                    isinstance(body, dict)
                    and body.get("message")
                    and body.get("data") is None
                ):
                    logger.warning(f"SportMonks {endpoint}: {body.get('message')}")
                return body
        except httpx.HTTPStatusError as e:
            last_exc = e
            st = e.response.status_code if e.response is not None else 0
            if st in _SM_RETRYABLE_STATUS and attempt < _SM_GET_MAX_RETRIES - 1:
                delay = min(45.0, 1.5 * (2**attempt))
                logger.warning(
                    "SportMonks %s: HTTP %s (attempt %s/%s), retrying in %.1fs",
                    endpoint,
                    st,
                    attempt + 1,
                    _SM_GET_MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            logger.error(f"SportMonks API error: {e}")
            return {"error": str(e)}
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
            last_exc = e
            if attempt < _SM_GET_MAX_RETRIES - 1:
                delay = min(45.0, 1.5 * (2**attempt))
                logger.warning(
                    "SportMonks %s: %s (attempt %s/%s), retrying in %.1fs",
                    endpoint,
                    type(e).__name__,
                    attempt + 1,
                    _SM_GET_MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            logger.error(f"SportMonks API error: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"SportMonks API error: {e}")
            return {"error": str(e)}

    if last_exc:
        logger.error(f"SportMonks API error after retries: {last_exc}")
        return {"error": str(last_exc)}
    return {"error": "SportMonks request failed"}


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
    if _sm_response_failed(data):
        logger.warning(f"fetch_fixture_details({fixture_id}): {data.get('error') or data.get('message')}")
        return {}
    return data.get("data") or {}


# SportMonks fixture status strings that mean the match is in play ("ns" = not started — not live).
SM_LIVE_STATUSES = frozenset({"1st innings", "2nd innings", "innings break", "int.", "live"})


def score_entry_from_fixture_raw(raw: dict) -> dict:
    """Build a livescore-shaped dict (team1/team2 + innN_*) from a fixture payload."""
    local = (raw or {}).get("localteam", {}) or {}
    visitor = (raw or {}).get("visitorteam", {}) or {}
    lt = local.get("name", "")
    vt = visitor.get("name", "")
    runs_data = (raw or {}).get("runs", [])
    if isinstance(runs_data, dict):
        runs_data = runs_data.get("data", [])
    entry = {"team1": lt, "team2": vt, "note": (raw or {}).get("note", "")}
    for r in runs_data:
        inn = r.get("inning", 1)
        entry[f"inn{inn}_runs"] = r.get("score", 0)
        entry[f"inn{inn}_wickets"] = r.get("wickets", 0)
        entry[f"inn{inn}_overs"] = r.get("overs", 0)
    return entry


def format_livescore_entry_text(entry: dict) -> str:
    """Format score line like fetch_livescores_ipl / refresh-live-status (two innings)."""
    if not entry:
        return ""
    parts = []
    if entry.get("inn1_runs") is not None:
        parts.append(
            f"{entry['team1']} {entry.get('inn1_runs', 0)}/{entry.get('inn1_wickets', 0)} "
            f"({entry.get('inn1_overs', 0)} ov)"
        )
    if entry.get("inn2_runs") is not None:
        parts.append(
            f"{entry['team2']} {entry.get('inn2_runs', 0)}/{entry.get('inn2_wickets', 0)} "
            f"({entry.get('inn2_overs', 0)} ov)"
        )
    return " | ".join(parts) if parts else (entry.get("note") or "")


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

        _raw_nm = p.get("fullname", f"{p.get('firstname', '')} {p.get('lastname', '')}".strip())
        player = {
            "id": p.get("id"),
            "name": canonical_player_display_name(_raw_nm),
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
        _rid = p.get("id")
        if _rid is None:
            continue
        _rnm = p.get("fullname", f"{p.get('firstname', '')} {p.get('lastname', '')}".strip())
        player_names[_rid] = canonical_player_display_name(_rnm)

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
    payload = await _get("livescores", {
        "include": "localteam,visitorteam,runs,batting,bowling,lineup,venue",
    })
    if _sm_response_failed(payload):
        return []
    data = payload.get("data", [])
    if not isinstance(data, list):
        return []
    results = []
    for m in data:
        lt = m.get("localteam", {}).get("name", "")
        vt = m.get("visitorteam", {}).get("name", "")
        status = m.get("status", "")
        note = m.get("note", "")
        fixture_id = m.get("id")
        st = (status or "").lower()
        entry = {
            "fixture_id": fixture_id,
            "team1": lt,
            "team2": vt,
            "status": status,
            "note": note,
            "league_id": m.get("league_id"),
            "is_live": st in SM_LIVE_STATUSES,
            "is_finished": st in ["finished", "aban.", "cancelled", "no result"],
        }
        runs_data = m.get("runs", [])
        if isinstance(runs_data, dict):
            runs_data = runs_data.get("data", [])
        for r in runs_data:
            inn = r.get("inning", 1)
            entry[f"inn{inn}_runs"] = r.get("score", 0)
            entry[f"inn{inn}_wickets"] = r.get("wickets", 0)
            entry[f"inn{inn}_overs"] = r.get("overs", 0)
        results.append(entry)
    return results


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
    st = (status or "").lower()

    # Determine winner name
    local = raw.get("localteam", {})
    visitor = raw.get("visitorteam", {})
    winner = None
    if winner_team_id:
        if winner_team_id == local.get("id"):
            winner = local.get("name")
        elif winner_team_id == visitor.get("id"):
            winner = visitor.get("name")

    score_entry = score_entry_from_fixture_raw(raw)
    score_text = format_livescore_entry_text(score_entry)

    return {
        "status": status,
        "fixture_id": fid,
        "note": note,
        "winner": winner,
        "team1": local.get("name", ""),
        "team2": visitor.get("name", ""),
        "score": score_text,
        "is_finished": st in ["finished", "aban.", "cancelled", "no result"],
        "is_live": st in SM_LIVE_STATUSES,
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
_venue_id_cache: Dict[str, int] = {}  # venue_name_lower → venue_id
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
    if _sm_response_failed(data):
        logger.error(f"SportMonks seasons/{season_id} failed: {data.get('error') or data.get('message')}")
        return []

    raw_fixtures = data.get("data", {}).get("fixtures", {})
    if isinstance(raw_fixtures, dict):
        raw_fixtures = raw_fixtures.get("data", [])

    _season_fixtures_cache[season_id] = raw_fixtures
    logger.info(f"Cached {len(raw_fixtures)} fixtures for season {season_id}")
    return raw_fixtures


async def fetch_team_last_completed_fixture(team_name: str) -> Optional[dict]:
    """Find the most recent completed IPL fixture for a team (2026, then 2025, 2024).

    Returns the raw fixture dict with id, localteam_id, visitorteam_id, note, starting_at.
    """
    team_id = _get_team_sm_id(team_name)
    if not team_id:
        logger.warning(f"Could not resolve team ID for: {team_name}")
        return None

    tid = int(team_id)
    candidates = []
    for year in [2026, 2025, 2024]:
        season_id = IPL_SEASON_IDS.get(year)
        if not season_id:
            continue
        fixtures = await fetch_season_fixtures(season_id)
        finished = [f for f in fixtures if (f.get("status") or "").lower() == "finished"]
        for f in finished:
            lt = f.get("localteam_id")
            vt = f.get("visitorteam_id")
            try:
                lt_i = int(lt) if lt is not None else 0
                vt_i = int(vt) if vt is not None else 0
            except (TypeError, ValueError):
                continue
            if lt_i == tid or vt_i == tid:
                candidates.append(f)
    if not candidates:
        logger.warning(f"No completed fixture found for {team_name} (id={team_id})")
        return None
    candidates.sort(key=lambda x: x.get("starting_at", "") or "", reverse=True)
    best = candidates[0]
    logger.info(f"Last completed match for {team_name} (id={team_id}): fixture {best.get('id')}")
    return best


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
            p["name"] = canonical_player_display_name(p.get("name", ""))
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
        p["name"] = canonical_player_display_name(p.get("name", ""))
        return p

    # Fetch in batches of 5 to respect rate limits
    batch_size = 5
    for i in range(0, len(players), batch_size):
        batch = players[i:i + batch_size]
        results = await asyncio.gather(*[_fetch_player(p) for p in batch], return_exceptions=True)
        for j, r in enumerate(results):
            if isinstance(r, Exception):
                logger.warning(f"Player enrichment error: {r}")
                enriched.append(batch[j])
            elif isinstance(r, dict):
                enriched.append(r)

    return enriched


def _lineup_team_player_ids(lineup_raw: list, team_id: int) -> set:
    """Player IDs listed in lineup for a team (handles nested lineup pivot like parse_fixture)."""
    ids = set()
    for p in lineup_raw:
        pivot = p.get("lineup") or {}
        if not isinstance(pivot, dict):
            pivot = {}
        if pivot.get("team_id") == team_id and p.get("id"):
            ids.add(p.get("id"))
    return ids


async def fetch_fixture_batting_bowling(fixture_id: int, include_balls: bool = True) -> dict:
    """Fetch batting, bowling, lineup, and optional ball-by-ball data for phase tagging."""
    inc = "batting,bowling,lineup"
    if include_balls:
        inc += ",balls"
    data = await _get(f"fixtures/{fixture_id}", {"include": inc})
    if _sm_response_failed(data):
        logger.warning(f"fetch_fixture_batting_bowling({fixture_id}): {data.get('error') or data.get('message')}")
        return {"fixture_id": fixture_id, "batting": [], "bowling": [], "player_names": {}}

    fixture = data.get("data") or {}
    if not fixture:
        return {"fixture_id": fixture_id, "batting": [], "bowling": [], "player_names": {}}

    batting_raw = fixture.get("batting", {})
    if isinstance(batting_raw, dict):
        batting_raw = batting_raw.get("data", [])

    bowling_raw = fixture.get("bowling", {})
    if isinstance(bowling_raw, dict):
        bowling_raw = bowling_raw.get("data", [])

    lineup_raw = fixture.get("lineup", {})
    if isinstance(lineup_raw, dict):
        lineup_raw = lineup_raw.get("data", [])

    local_id = fixture.get("localteam_id")
    visitor_id = fixture.get("visitorteam_id")
    team_a_ids = _lineup_team_player_ids(lineup_raw, local_id) if local_id else set()
    team_b_ids = _lineup_team_player_ids(lineup_raw, visitor_id) if visitor_id else set()

    # Build player name map from lineup
    player_names = {}
    for p in lineup_raw:
        _pid = p.get("id")
        if _pid is None:
            continue
        player_names[_pid] = canonical_player_display_name(p.get("fullname", ""))

    batting = []
    for b in batting_raw:
        pid = b.get("player_id")
        tid = b.get("team_id")
        if tid is None and pid:
            if pid in team_a_ids and pid not in team_b_ids:
                tid = local_id
            elif pid in team_b_ids and pid not in team_a_ids:
                tid = visitor_id
        batting.append({
            "player_id": pid,
            "player_name": player_names.get(pid, ""),
            "runs": b.get("score", 0),
            "balls": b.get("ball", 0),
            "fours": b.get("four_x", 0),
            "sixes": b.get("six_x", 0),
            "strike_rate": round((b.get("score", 0) / max(b.get("ball", 1), 1)) * 100, 1),
            "scoreboard": b.get("scoreboard", "S1"),
            "team_id": tid,
        })

    bowling = []
    for bw in bowling_raw:
        pid = bw.get("player_id")
        tid = bw.get("team_id")
        if tid is None and pid:
            if pid in team_a_ids and pid not in team_b_ids:
                tid = local_id
            elif pid in team_b_ids and pid not in team_a_ids:
                tid = visitor_id
        bowling.append({
            "player_id": pid,
            "player_name": player_names.get(pid, ""),
            "overs": bw.get("overs", 0),
            "wickets": bw.get("wickets", 0),
            "runs_conceded": bw.get("runs", 0),
            "economy": bw.get("rate", 0),
            "maidens": bw.get("medians", 0),
            "scoreboard": bw.get("scoreboard", "S1"),
            "team_id": tid,
        })

    balls_raw = fixture.get("balls", [])
    balls = normalize_balls_payload(balls_raw)

    return {
        "fixture_id": fixture_id,
        "batting": batting,
        "bowling": bowling,
        "player_names": player_names,
        "balls": balls,
        "winner_team_id": fixture.get("winner_team_id"),
        "localteam_id": fixture.get("localteam_id"),
        "visitorteam_id": fixture.get("visitorteam_id"),
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
            tid = b.get("team_id")
            if tid is None:
                continue
            if tid != team_id:
                continue
            pid = b["player_id"]
            if pid not in player_stats:
                player_stats[pid] = {
                    "name": canonical_player_display_name(b["player_name"] or ""),
                    "matches": 0,
                    "batting": {"runs": 0, "balls": 0, "innings": 0, "fours": 0, "sixes": 0},
                    "bowling": {"overs": 0, "wickets": 0, "runs_conceded": 0, "innings": 0, "maidens": 0},
                }
            player_stats[pid]["name"] = canonical_player_display_name(
                b["player_name"] or player_stats[pid]["name"]
            )
            player_stats[pid]["batting"]["runs"] += b["runs"]
            player_stats[pid]["batting"]["balls"] += b["balls"]
            player_stats[pid]["batting"]["innings"] += 1
            player_stats[pid]["batting"]["fours"] += b["fours"]
            player_stats[pid]["batting"]["sixes"] += b["sixes"]

        # Aggregate bowling — ONLY for this team's players
        for bw in data.get("bowling", []):
            tid = bw.get("team_id")
            if tid is None:
                continue
            if tid != team_id:
                continue
            pid = bw["player_id"]
            if pid not in player_stats:
                player_stats[pid] = {
                    "name": canonical_player_display_name(bw["player_name"] or ""),
                    "matches": 0,
                    "batting": {"runs": 0, "balls": 0, "innings": 0, "fours": 0, "sixes": 0},
                    "bowling": {"overs": 0, "wickets": 0, "runs_conceded": 0, "innings": 0, "maidens": 0},
                }
            player_stats[pid]["name"] = canonical_player_display_name(
                bw["player_name"] or player_stats[pid]["name"]
            )
            player_stats[pid]["bowling"]["overs"] += bw["overs"]
            player_stats[pid]["bowling"]["wickets"] += bw["wickets"]
            player_stats[pid]["bowling"]["runs_conceded"] += bw["runs_conceded"]
            player_stats[pid]["bowling"]["innings"] += 1
            player_stats[pid]["bowling"]["maidens"] += bw["maidens"]

        # Count match appearances (only this team's players)
        seen_players = set()
        for b in data.get("batting", []):
            tid = b.get("team_id")
            if tid is None or tid != team_id:
                continue
            seen_players.add(b["player_id"])
        for bw in data.get("bowling", []):
            tid = bw.get("team_id")
            if tid is None or tid != team_id:
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


def _empty_by_season_block() -> dict:
    return {
        "batting": {
            "runs": 0, "balls": 0, "innings": 0, "fours": 0, "sixes": 0,
            "fifties": 0, "hundreds": 0, "innings_ge15": 0,
        },
        "bowling": {
            "overs": 0, "wickets": 0, "runs_conceded": 0, "innings": 0,
            "maidens": 0, "three_fers": 0,
        },
    }


def _new_player_stat_doc(pid, name: str) -> dict:
    return {
        "player_id": pid,
        "name": canonical_player_display_name(name or ""),
        "batting": {
            "runs": 0, "balls": 0, "innings": 0, "fours": 0, "sixes": 0,
            "fifties": 0, "hundreds": 0, "innings_ge15": 0,
        },
        "bowling": {
            "overs": 0, "wickets": 0, "runs_conceded": 0, "innings": 0,
            "maidens": 0, "three_fers": 0,
            "dot_balls": 0,
            "legal_balls_bowled": 0,
            "dot_ball_pct": 0.0,
        },
        "matches": 0,
        "seasons": [],
        "by_season": {},
        "phases": empty_phases_root(),
        "_bat_entries": [],
        "_bowl_entries": [],
    }


async def fetch_cricket_player_profile_fields(player_id: int) -> Optional[dict]:
    """SportMonks player-by-id includes for career / batting / bowling splits (plan-dependent)."""
    for include in ("career,batting,bowling", "career,battings,bowlings", "career", "batting,bowling"):
        data = await _get(f"players/{int(player_id)}", {"include": include})
        if _sm_response_failed(data):
            continue
        pd = data.get("data")
        if not isinstance(pd, dict) or not pd:
            continue
        bat = pd.get("batting") or pd.get("battings")
        bow = pd.get("bowling") or pd.get("bowlings")
        if isinstance(bat, dict) and "data" in bat:
            bat = bat.get("data")
        if isinstance(bow, dict) and "data" in bow:
            bow = bow.get("data")
        return {
            "api_profile": {
                "player_id": int(player_id),
                "include": include,
                "career": pd.get("career"),
                "batting": bat,
                "bowling": bow,
                "stats": pd.get("stats"),
            },
            "api_profile_fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    return None


async def sync_player_career_enrichment_to_db(db, limit: int = 500) -> dict:
    """On-demand: enrich Mongo player_performance with /players/{id} career-style payloads."""
    from pymongo import UpdateOne

    ids: List[int] = []
    async for doc in db.player_performance.find({"player_id": {"$exists": True}}, {"player_id": 1}).limit(
        max(1, int(limit))
    ):
        try:
            ids.append(int(doc["player_id"]))
        except (TypeError, ValueError, KeyError):
            continue

    ops: list = []
    errors = 0
    for i, pid in enumerate(ids):
        try:
            fields = await fetch_cricket_player_profile_fields(pid)
            if fields:
                ops.append(UpdateOne({"player_id": pid}, {"$set": fields}))
        except Exception as e:
            errors += 1
            logger.warning(f"Career enrich failed for player {pid}: {e}")
        if i and i % 12 == 0:
            await asyncio.sleep(0.25)

    if ops:
        await db.player_performance.bulk_write(ops)
        try:
            await record_player_performance_db_touch(
                db,
                source="career_api_profile_enrich",
                players_touched=len(ids),
                mongodb_writes=len(ops),
                errors=errors,
            )
        except Exception as e:
            logger.warning(f"Could not record player_performance meta after career enrich: {e}")
    return {"players_touched": len(ids), "mongodb_writes": len(ops), "errors": errors}


def _team_result_from_fixture(team_id: Any, winner_team_id: Any) -> Optional[str]:
    """W / L for the player's team in a finished fixture; None if unknown or no result."""
    if team_id is None or winner_team_id is None:
        return None
    try:
        return "W" if int(team_id) == int(winner_team_id) else "L"
    except (TypeError, ValueError):
        return None


async def sync_player_performance_to_db(db) -> dict:
    """Sync player performance stats from last 3 IPL seasons (2024-2026) into MongoDB.

    Stores career totals, per-season splits (for BPR: career / last-3 / current),
    last5 + extended recent (50), plus ``csa_season_*`` = every innings/spell in the active IPL year for CSA.
    """
    all_player_stats: dict = {}
    total_fixtures = 0

    for year, season_id in sorted(IPL_SEASON_IDS.items()):
        fixtures = await fetch_season_fixtures(season_id)
        finished = [f for f in fixtures if (f.get("status") or "").lower() == "finished"]
        logger.info(f"Syncing {len(finished)} finished matches from IPL {year}")

        for fix in finished:
            fid = fix.get("id")
            fix_started = fix.get("starting_at") or ""
            try:
                data = await fetch_fixture_batting_bowling(fid)
                total_fixtures += 1
            except Exception as e:
                logger.warning(f"Error fetching fixture {fid}: {e}")
                continue

            winner_team_id = data.get("winner_team_id")

            seen_bat = set()
            for b in data.get("batting", []):
                pid = b["player_id"]
                sb = b.get("scoreboard") or "S1"
                bkey = (fid, pid, sb)
                if bkey in seen_bat:
                    continue
                seen_bat.add(bkey)
                if int(b.get("balls") or 0) <= 0 and int(b.get("runs") or 0) <= 0:
                    continue
                if pid not in all_player_stats:
                    all_player_stats[pid] = _new_player_stat_doc(pid, b["player_name"])
                ps = all_player_stats[pid]
                ps["name"] = canonical_player_display_name(b["player_name"] or ps["name"])
                ps["batting"]["runs"] += b["runs"]
                ps["batting"]["balls"] += b["balls"]
                ps["batting"]["innings"] += 1
                if int(b.get("runs") or 0) >= 15:
                    ps["batting"]["innings_ge15"] = int(ps["batting"].get("innings_ge15") or 0) + 1
                ps["batting"]["fours"] += b["fours"]
                ps["batting"]["sixes"] += b["sixes"]
                if b["runs"] >= 50:
                    ps["batting"]["fifties"] += 1
                if b["runs"] >= 100:
                    ps["batting"]["hundreds"] += 1
                if year not in ps["seasons"]:
                    ps["seasons"].append(year)

                ys = ps.setdefault("by_season", {})
                blk = ys.setdefault(str(year), _empty_by_season_block())
                bb = blk["batting"]
                bb["runs"] += b["runs"]
                bb["balls"] += b["balls"]
                bb["innings"] += 1
                if int(b.get("runs") or 0) >= 15:
                    bb["innings_ge15"] = int(bb.get("innings_ge15") or 0) + 1
                bb["fours"] += b["fours"]
                bb["sixes"] += b["sixes"]
                if b["runs"] >= 50:
                    bb["fifties"] += 1
                if b["runs"] >= 100:
                    bb["hundreds"] += 1

                sr = round((b["runs"] / max(b["balls"], 1)) * 100, 1)
                tid_bat = b.get("team_id")
                ps["_bat_entries"].append({
                    "date": fix_started,
                    "season_year": year,
                    "fixture_id": fid,
                    "team_id": tid_bat,
                    "winner_team_id": winner_team_id,
                    "team_result": _team_result_from_fixture(tid_bat, winner_team_id),
                    "runs": int(b.get("runs") or 0),
                    "balls": int(b.get("balls") or 0),
                    "sr": sr,
                })

            for bw in data.get("bowling", []):
                pid = bw["player_id"]
                if pid not in all_player_stats:
                    all_player_stats[pid] = _new_player_stat_doc(pid, bw["player_name"])
                ps = all_player_stats[pid]
                ps["name"] = canonical_player_display_name(bw["player_name"] or ps["name"])
                ps["bowling"]["overs"] += bw["overs"]
                ps["bowling"]["wickets"] += bw["wickets"]
                ps["bowling"]["runs_conceded"] += bw["runs_conceded"]
                ps["bowling"]["innings"] += 1
                ps["bowling"]["maidens"] += bw["maidens"]
                if bw["wickets"] >= 3:
                    ps["bowling"]["three_fers"] += 1
                if year not in ps["seasons"]:
                    ps["seasons"].append(year)

                ys = ps.setdefault("by_season", {})
                blk = ys.setdefault(str(year), _empty_by_season_block())
                bwblk = blk["bowling"]
                bwblk["overs"] += bw["overs"]
                bwblk["wickets"] += bw["wickets"]
                bwblk["runs_conceded"] += bw["runs_conceded"]
                bwblk["innings"] += 1
                bwblk["maidens"] += bw["maidens"]
                if bw["wickets"] >= 3:
                    bwblk["three_fers"] += 1

                eco = float(bw.get("economy") or 0) or (
                    float(bw.get("runs_conceded") or 0) / max(float(bw.get("overs") or 0), 0.01)
                )
                tid_bowl = bw.get("team_id")
                ps["_bowl_entries"].append({
                    "date": fix_started,
                    "season_year": year,
                    "fixture_id": fid,
                    "team_id": tid_bowl,
                    "winner_team_id": winner_team_id,
                    "team_result": _team_result_from_fixture(tid_bowl, winner_team_id),
                    "overs": float(bw.get("overs") or 0),
                    "wickets": int(bw.get("wickets") or 0),
                    "runs_conceded": int(bw.get("runs_conceded") or 0),
                    "economy": round(eco, 2),
                })

            balls_list = data.get("balls") or []
            if balls_list:
                accumulate_phases_from_balls(all_player_stats, balls_list)

    # Match appearances (approx): unique fixtures per player from logs
    _csa_recent_cap = 50
    _cur_ipl_season_y = max(IPL_SEASON_IDS.keys())
    for pid, ps in all_player_stats.items():
        fids = set()
        for e in ps.get("_bat_entries") or []:
            fids.add(e.get("fixture_id"))
        for e in ps.get("_bowl_entries") or []:
            fids.add(e.get("fixture_id"))
        ps["matches"] = len(fids)

        bat_logs = sorted(
            ps.pop("_bat_entries", []),
            key=lambda x: x.get("date") or "",
            reverse=True,
        )
        # Every IPL batting innings in the active season (e.g. all 2026) for CSA — not capped at 5 or 50.
        csa_season_bat = []
        seen_csa_bat_fid = set()
        for e in bat_logs:
            sy = e.get("season_year")
            try:
                if sy is None or int(sy) != int(_cur_ipl_season_y):
                    continue
            except (TypeError, ValueError):
                continue
            fid = e.get("fixture_id")
            if fid is not None:
                if fid in seen_csa_bat_fid:
                    continue
                seen_csa_bat_fid.add(fid)
            br = int(e.get("runs") or 0)
            bb = int(e.get("balls") or 0)
            sr_val = e.get("sr")
            if sr_val is None:
                sr_val = round((br / max(bb, 1)) * 100, 1)
            csa_season_bat.append(
                {
                    "runs": br,
                    "balls": bb,
                    "sr": sr_val,
                    "season_year": sy,
                    "date": e.get("date"),
                    "fixture_id": e.get("fixture_id"),
                    "team_id": e.get("team_id"),
                    "winner_team_id": e.get("winner_team_id"),
                    "team_result": e.get("team_result")
                    or _team_result_from_fixture(e.get("team_id"), e.get("winner_team_id")),
                }
            )
        ps["csa_season_bat_innings"] = csa_season_bat

        out_bat = []
        recent_bat = []
        seen_bf = set()
        for e in bat_logs:
            bf = e.get("fixture_id")
            if bf is not None:
                if bf in seen_bf:
                    continue
                seen_bf.add(bf)
            row = {
                "runs": e["runs"],
                "balls": e["balls"],
                "sr": e["sr"],
                "season_year": e.get("season_year"),
                "date": e.get("date"),
                "fixture_id": e.get("fixture_id"),
                "team_result": e.get("team_result")
                or _team_result_from_fixture(e.get("team_id"), e.get("winner_team_id")),
            }
            if len(recent_bat) < _csa_recent_cap:
                recent_bat.append(row)
            if len(out_bat) < 5:
                out_bat.append(row)
            if len(recent_bat) >= _csa_recent_cap and len(out_bat) >= 5:
                break
        ps["last5_bat_innings"] = out_bat
        ps["recent_bat_innings"] = recent_bat

        bowl_logs = sorted(
            ps.pop("_bowl_entries", []),
            key=lambda x: x.get("date") or "",
            reverse=True,
        )
        csa_season_bowl = []
        seen_csa_bowl_fid = set()
        for e in bowl_logs:
            sy = e.get("season_year")
            try:
                if sy is None or int(sy) != int(_cur_ipl_season_y):
                    continue
            except (TypeError, ValueError):
                continue
            fid = e.get("fixture_id")
            if fid is not None:
                if fid in seen_csa_bowl_fid:
                    continue
                seen_csa_bowl_fid.add(fid)
            ovs = float(e.get("overs") or 0)
            if ovs <= 0:
                continue
            wk = int(e.get("wickets") or 0)
            rc = int(e.get("runs_conceded") or 0)
            eco = float(e.get("economy") or 0) or (rc / max(ovs, 0.01))
            csa_season_bowl.append(
                {
                    "overs": ovs,
                    "wickets": wk,
                    "runs_conceded": rc,
                    "economy": round(eco, 2),
                    "season_year": sy,
                    "date": e.get("date"),
                    "fixture_id": e.get("fixture_id"),
                    "team_id": e.get("team_id"),
                    "winner_team_id": e.get("winner_team_id"),
                    "team_result": e.get("team_result")
                    or _team_result_from_fixture(e.get("team_id"), e.get("winner_team_id")),
                }
            )
        ps["csa_season_bowl_spells"] = csa_season_bowl

        out_bowl = []
        recent_bowl = []
        seen_bwf = set()
        for e in bowl_logs:
            bf = e.get("fixture_id")
            if bf is not None:
                if bf in seen_bwf:
                    continue
                seen_bwf.add(bf)
            row = {
                "overs": e["overs"],
                "wickets": e["wickets"],
                "runs_conceded": e["runs_conceded"],
                "economy": e["economy"],
                "season_year": e.get("season_year"),
                "date": e.get("date"),
                "fixture_id": e.get("fixture_id"),
                "team_result": e.get("team_result")
                or _team_result_from_fixture(e.get("team_id"), e.get("winner_team_id")),
            }
            if len(recent_bowl) < _csa_recent_cap:
                recent_bowl.append(row)
            if len(out_bowl) < 5:
                out_bowl.append(row)
            if len(recent_bowl) >= _csa_recent_cap and len(out_bowl) >= 5:
                break
        ps["last5_bowl_spells"] = out_bowl
        ps["recent_bowl_spells"] = recent_bowl
        ph = ps.get("phases")
        if isinstance(ph, dict):
            finalize_phase_derived(ph)
            bowl_ph = ph.get("bowl") or {}
            dots = legal = 0
            for pk in (PHASE_PP, PHASE_MID, PHASE_DEATH):
                bbb = bowl_ph.get(pk) or {}
                dots += int(bbb.get("dots") or 0)
                legal += int(bbb.get("legal_balls") or 0)
            ps["bowling"]["dot_balls"] = dots
            ps["bowling"]["legal_balls_bowled"] = legal
            ps["bowling"]["dot_ball_pct"] = round(100.0 * dots / max(legal, 1), 2) if legal else 0.0

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

        for y, blk in (ps.get("by_season") or {}).items():
            bb = blk.get("batting") or {}
            if bb.get("innings", 0) > 0:
                bb["avg"] = round(bb["runs"] / bb["innings"], 1)
                bb["sr"] = round((bb["runs"] / max(bb["balls"], 1)) * 100, 1)
            else:
                bb["avg"] = 0
                bb["sr"] = 0
            bw = blk.get("bowling") or {}
            if bw.get("innings", 0) > 0 and bw.get("overs", 0) > 0:
                bw["economy"] = round(bw["runs_conceded"] / bw["overs"], 2)
                bw["avg"] = round(bw["runs_conceded"] / max(bw["wickets"], 1), 1)
            else:
                bw["economy"] = 0
                bw["avg"] = 0

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
        await db.player_performance.bulk_write(ops)
        logger.info(f"Synced {len(ops)} player stats from {total_fixtures} fixtures")
        try:
            await record_player_performance_db_touch(
                db,
                source="bulk_ipl_sync",
                players_synced=len(all_player_stats),
                fixtures_processed=total_fixtures,
            )
        except Exception as e:
            logger.warning(f"Could not record player_performance meta after bulk sync: {e}")

    return {
        "players_synced": len(all_player_stats),
        "fixtures_processed": total_fixtures,
        "seasons": list(IPL_SEASON_IDS.keys()),
    }


def _norm_id(v) -> int:
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def _sm_team_name_from_id(team_id: int) -> str:
    """Canonical display label for a SportMonks IPL team id."""
    if not team_id:
        return "Unknown"
    tid = _norm_id(team_id)
    for canonical, sm_id in TEAM_SM_IDS.items():
        if _norm_id(sm_id) == tid:
            return canonical.title()
    return f"Team {tid}"


def _opponent_name_from_fixture(fix: dict, team_id: int) -> str:
    """Opponent franchise name for a team in a season fixture row."""
    tid = _norm_id(team_id)
    try:
        lt_i = _norm_id(fix.get("localteam_id"))
        vt_i = _norm_id(fix.get("visitorteam_id"))
    except (TypeError, ValueError):
        return "Unknown"
    if lt_i == tid:
        opp_id = vt_i
    elif vt_i == tid:
        opp_id = lt_i
    else:
        return "Unknown"
    return _sm_team_name_from_id(opp_id)


def _parse_impact_subs_from_lineup(lineup_data: list, team_id: int) -> List[dict]:
    """Players flagged substitution=true in lineup (named impact / bench subs, 11+2 model)."""
    subs: List[dict] = []
    tid = _norm_id(team_id)
    if not lineup_data:
        return subs
    for p in lineup_data:
        lineup_info = p.get("lineup") or {}
        if not isinstance(lineup_info, dict):
            lineup_info = {}
        if _norm_id(lineup_info.get("team_id")) != tid:
            continue
        is_sub = lineup_info.get("substitution", False)
        if isinstance(is_sub, int):
            is_sub = bool(is_sub)
        if not is_sub:
            continue
        _sub_nm = (p.get("fullname") or p.get("lastname") or "").strip() or "?"
        subs.append({
            "name": canonical_player_display_name(_sub_nm),
            "sm_player_id": p.get("id"),
        })
    return subs


async def fetch_team_impact_sub_history(team_name: str, num_matches: int = 4) -> dict:
    """Last N completed IPL matches per team: who was listed as substitution (impact) in lineups.

    Uses SportMonks lineup pivot field substitution=true. Does not prove they entered the game.
    """
    team_id = _get_team_sm_id(team_name)
    if not team_id:
        logger.warning(f"fetch_team_impact_sub_history: unknown team {team_name!r}")
        return {
            "team": team_name,
            "error": "unknown_team",
            "matches_considered": 0,
            "fixtures": [],
            "frequency": [],
        }

    tid = int(team_id)
    all_finished: List[dict] = []
    for year in [2026, 2025, 2024]:
        season_id = IPL_SEASON_IDS.get(year)
        if not season_id:
            continue
        fixtures = await fetch_season_fixtures(season_id)
        finished = [f for f in fixtures if (f.get("status") or "").lower() == "finished"]
        team_fixtures = [
            f for f in finished
            if _norm_id(f.get("localteam_id")) == tid or _norm_id(f.get("visitorteam_id")) == tid
        ]
        team_fixtures.sort(key=lambda x: x.get("starting_at", "") or "", reverse=True)
        all_finished.extend(team_fixtures)
        if len(all_finished) >= num_matches:
            break

    all_finished = all_finished[:num_matches]
    if not all_finished:
        return {
            "team": team_name,
            "matches_considered": 0,
            "fixtures": [],
            "frequency": [],
            "source": "sportmonks_lineup_substitution_flag",
        }

    rows: List[dict] = []
    freq: Dict[int, dict] = {}

    for fix in all_finished:
        fid = fix.get("id")
        if not fid:
            continue
        data = await _get(f"fixtures/{fid}", {"include": "lineup"})
        if _sm_response_failed(data):
            logger.warning(f"Impact sub history: lineup fetch failed for fixture {fid}")
            continue
        fd = data.get("data") or {}
        lineup_raw = fd.get("lineup", {})
        if isinstance(lineup_raw, dict):
            lineup_raw = lineup_raw.get("data", [])
        elif not isinstance(lineup_raw, list):
            lineup_raw = []

        subs = _parse_impact_subs_from_lineup(lineup_raw, tid)
        for s in subs:
            pid = s.get("sm_player_id")
            if pid is None:
                continue
            try:
                pid_i = int(pid)
            except (TypeError, ValueError):
                continue
            ent = freq.setdefault(pid_i, {"name": s.get("name") or "?", "appearances": 0})
            ent["appearances"] += 1
            ent["name"] = s.get("name") or ent["name"]

        rows.append({
            "fixture_id": fid,
            "starting_at": fix.get("starting_at", ""),
            "opponent": _opponent_name_from_fixture(fix, tid),
            "impact_subs": subs,
        })

    frequency = sorted(
        (
            {"sm_player_id": pid, "name": v["name"], "appearances": v["appearances"]}
            for pid, v in freq.items()
        ),
        key=lambda x: -x["appearances"],
    )

    return {
        "team": team_name,
        "matches_considered": len(rows),
        "source": "sportmonks_lineup_substitution_flag",
        "fixtures": rows,
        "frequency": frequency,
    }


def _parse_lineup(lineup_data: list, team_id: int) -> list:
    """Extract Playing XI (non-subs) for a specific team from SportMonks lineup data.
    Caps at 12 players (11 + 1 impact sub) to prevent full-squad leakage."""
    xi = []
    tid = _norm_id(team_id)
    for p in lineup_data:
        lineup_info = p.get("lineup") or {}
        if not isinstance(lineup_info, dict):
            lineup_info = {}
        if _norm_id(lineup_info.get("team_id")) != tid:
            continue
        is_sub = lineup_info.get("substitution", False)
        if isinstance(is_sub, int):
            is_sub = bool(is_sub)
        if is_sub:
            continue  # Skip impact player subs
        xi.append({
            "name": canonical_player_display_name(p.get("fullname", "")),
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


async def fetch_last_played_xi_bundle(team_name: str) -> Dict[str, Any]:
    """Playing XI plus named impact / substitute rows from the same SportMonks resolution path.

    IPL lineups mark Impact Player(s) with ``lineup.substitution=true``. Those players are
    excluded from `_parse_lineup` (starting XI) but returned here so downstream prompts do not
    treat them as "not playing".
    """
    out: Dict[str, Any] = {"xi": [], "impact_subs": []}

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

        tid = _norm_id(team_id)
        xi = _parse_lineup(lineup_data, tid)
        subs = _parse_impact_subs_from_lineup(lineup_data, tid)
        if len(xi) >= 8:
            logger.info(f"Found Playing XI for {team_name} from live match: {len(xi)} players")
            out["xi"] = await _enrich_players(xi)
            out["impact_subs"] = subs
            return out

    # Step 2: Last completed IPL match (2026 → 2025 → 2024, most recent overall)
    team_id = _get_team_sm_id(team_name)
    if not team_id:
        logger.warning(f"Could not resolve team ID for: {team_name}")
        return out

    fixture = await fetch_team_last_completed_fixture(team_name)
    if not fixture:
        return out

    target_fixture_id = fixture.get("id")
    if not target_fixture_id:
        return out

    data = await _get(f"fixtures/{target_fixture_id}", {"include": "lineup"})
    if _sm_response_failed(data):
        logger.warning(f"Fixture {target_fixture_id} lineup fetch failed for {team_name}")
        return out
    fixture_detail = data.get("data", {})
    lineup = fixture_detail.get("lineup", {})
    if isinstance(lineup, dict):
        lineup_data = lineup.get("data", [])
    elif isinstance(lineup, list):
        lineup_data = lineup
    else:
        lineup_data = []

    tid = _norm_id(team_id)
    xi = _parse_lineup(lineup_data, tid)
    subs = _parse_impact_subs_from_lineup(lineup_data, tid)
    if xi:
        logger.info(f"Found Playing XI for {team_name} from fixture {target_fixture_id}: {len(xi)} players")
        out["xi"] = await _enrich_players(xi)
        out["impact_subs"] = subs
        return out
    logger.warning(f"No lineup data for {team_name} in fixture {target_fixture_id}")
    return out


async def fetch_last_played_xi(team_name: str) -> list:
    """Fetch the Playing XI for a team from their most recent completed match.

    Pipeline (per user doc):
    1. Try live fixtures first (current match lineup is most relevant)
    2. Fallback: Last completed IPL match across 2026 / 2025 / 2024 (most recent)
    3. Fetch fixture with lineup include
    4. Extract non-substitute players = Playing XI

    Returns a list of player dicts (name, batting_style, bowling_style, captain, wk).
    For named Impact Player / substitute rows (substitution=true), use ``fetch_last_played_xi_bundle``.
    """
    bundle = await fetch_last_played_xi_bundle(team_name)
    return bundle.get("xi") or []


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
    if _sm_response_failed(season_data):
        logger.error(
            f"fetch_ipl_season_schedule: seasons/{season_id} failed: "
            f"{season_data.get('error') or season_data.get('message')}"
        )
        return []
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


# ═══════════════════════════════════════════════════════════════════════════
# DATA ENRICHMENT — Venue stats, H2H, Team Standings, Player Season Stats
# Fed directly into Claude's live match prompt for data-driven analysis.
# ═══════════════════════════════════════════════════════════════════════════

async def fetch_venue_stats(venue_name: str, season_years: list = None) -> dict:
    """Compute venue stats from finished fixtures across IPL seasons.

    Uses venue_id matching (not name) for accuracy.
    Returns: avg_1st_innings_score, bat_first_win_pct, sample_size, etc.
    """
    if not venue_name:
        return {}

    if season_years is None:
        season_years = [2026, 2025, 2024]

    # Step 1: Resolve venue_id from cache or from fixtures
    venue_lower = venue_name.lower()
    target_venue_id = _venue_id_cache.get(venue_lower)

    if not target_venue_id:
        # Collect unique venue_ids from season fixtures and resolve names
        for year in season_years:
            sid = IPL_SEASON_IDS.get(year)
            if not sid:
                continue
            fixtures = await fetch_season_fixtures(sid)
            seen_vids = set()
            for f in fixtures:
                vid = f.get("venue_id")
                if vid and vid not in seen_vids:
                    seen_vids.add(vid)
            # Batch resolve venue names
            for vid in seen_vids:
                vdata = await _get(f"venues/{vid}")
                vd = vdata.get("data", {})
                vd_name = (vd.get("name", "") or "").lower()
                if vd_name:
                    _venue_id_cache[vd_name] = vid
                    if venue_lower in vd_name or vd_name in venue_lower:
                        target_venue_id = vid
            if target_venue_id:
                _venue_id_cache[venue_lower] = target_venue_id
                break

    if not target_venue_id:
        return {"sample_size": 0, "note": f"Could not resolve venue_id for '{venue_name}'"}

    # Step 2: Collect all fixtures at this venue
    venue_fixture_ids = []
    for year in season_years:
        sid = IPL_SEASON_IDS.get(year)
        if not sid:
            continue
        fixtures = await fetch_season_fixtures(sid)
        for f in fixtures:
            if (f.get("status") or "").lower() == "finished" and f.get("venue_id") == target_venue_id:
                venue_fixture_ids.append(f)

    if not venue_fixture_ids:
        return {"venue": venue_name, "venue_id": target_venue_id, "sample_size": 0,
                "note": "No finished matches at this venue in recent IPL seasons"}

    # Step 3: Fetch runs for each venue fixture
    first_innings_scores = []
    bat_first_wins = 0
    total_with_winner = 0

    for f in venue_fixture_ids:
        fid = f.get("id")
        try:
            detail = await _get(f"fixtures/{fid}", {"include": "runs"})
            fd = detail.get("data", {})
            runs_data = fd.get("runs", {})
            if isinstance(runs_data, dict):
                runs_data = runs_data.get("data", [])

            inn1_score = None
            inn1_team_id = None
            for r in runs_data:
                if isinstance(r, dict) and r.get("inning") == 1:
                    inn1_score = r.get("score", 0)
                    inn1_team_id = r.get("team_id")
                    break

            if inn1_score is not None:
                first_innings_scores.append(inn1_score)

            winner_id = fd.get("winner_team_id") or f.get("winner_team_id")
            if winner_id and inn1_team_id:
                total_with_winner += 1
                if winner_id == inn1_team_id:
                    bat_first_wins += 1
        except Exception as e:
            logger.debug(f"Error fetching venue fixture {fid}: {e}")

    avg_1st = round(sum(first_innings_scores) / len(first_innings_scores), 1) if first_innings_scores else None
    bat_first_pct = round((bat_first_wins / total_with_winner) * 100, 1) if total_with_winner else None

    return {
        "venue": venue_name,
        "venue_id": target_venue_id,
        "sample_size": len(venue_fixture_ids),
        "seasons": season_years,
        "avg_first_innings_score": avg_1st,
        "bat_first_win_pct": bat_first_pct,
        "highest_1st_innings": max(first_innings_scores) if first_innings_scores else None,
        "lowest_1st_innings": min(first_innings_scores) if first_innings_scores else None,
        "total_matches_with_result": total_with_winner,
    }


async def fetch_h2h_record(team1_name: str, team2_name: str, last_n_seasons: int = 3) -> dict:
    """Head-to-head record between two teams across recent IPL seasons.

    Returns: matches played, wins for each team, last meeting result.
    """
    t1_id = _get_team_sm_id(team1_name)
    t2_id = _get_team_sm_id(team2_name)
    if not t1_id or not t2_id:
        return {"error": "Team IDs not found", "team1": team1_name, "team2": team2_name}

    years = sorted(IPL_SEASON_IDS.keys(), reverse=True)[:last_n_seasons]
    h2h_fixtures = []

    for year in years:
        sid = IPL_SEASON_IDS.get(year)
        if not sid:
            continue
        fixtures = await fetch_season_fixtures(sid)
        for f in fixtures:
            if (f.get("status") or "").lower() != "finished":
                continue
            lt = f.get("localteam_id")
            vt = f.get("visitorteam_id")
            if {lt, vt} == {t1_id, t2_id}:
                h2h_fixtures.append({
                    "fixture_id": f.get("id"),
                    "season": year,
                    "date": f.get("starting_at", ""),
                    "localteam_id": lt,
                    "visitorteam_id": vt,
                    "winner_id": f.get("winner_team_id"),
                    "note": f.get("note", ""),
                })

    t1_wins = sum(1 for f in h2h_fixtures if f["winner_id"] == t1_id)
    t2_wins = sum(1 for f in h2h_fixtures if f["winner_id"] == t2_id)
    no_result = len(h2h_fixtures) - t1_wins - t2_wins

    last_match = h2h_fixtures[0] if h2h_fixtures else None
    last_winner = (team1_name if last_match and last_match["winner_id"] == t1_id
                   else team2_name if last_match and last_match["winner_id"] == t2_id
                   else "N/A")

    return {
        "team1": team1_name,
        "team2": team2_name,
        "matches_played": len(h2h_fixtures),
        "team1_wins": t1_wins,
        "team2_wins": t2_wins,
        "no_result": no_result,
        "seasons_covered": years,
        "last_meeting_winner": last_winner,
        "last_meeting_date": last_match["date"] if last_match else None,
        "last_meeting_note": last_match["note"] if last_match else None,
    }


async def fetch_team_standings(season_year: int = 2026) -> list:
    """Fetch team standings (W/L/Points/NRR) for current season from finished fixtures.

    Returns list of team dicts sorted by points desc.
    """
    sid = IPL_SEASON_IDS.get(season_year)
    if not sid:
        return []

    # Try standings endpoint first
    data = await _get(f"standings/season/{sid}", {"include": "team"})
    standings_raw = data.get("data", [])

    if standings_raw:
        teams = []
        for s in standings_raw:
            if isinstance(s, dict):
                team_data = s.get("team", {}) or {}
                if isinstance(team_data, dict) and "data" in team_data:
                    team_data = team_data["data"]
                team_name = team_data.get("name", "") if isinstance(team_data, dict) else ""
                # Fallback: resolve from TEAM_SM_IDS
                if not team_name:
                    tid = s.get("team_id")
                    team_name = next((tn for tn, sm_id in TEAM_SM_IDS.items() if sm_id == tid), f"Team {tid}")
                recent_form = s.get("recent_form", [])
                form_str = "".join(recent_form) if isinstance(recent_form, list) else str(recent_form)
                teams.append({
                    "team": team_name,
                    "team_id": s.get("team_id"),
                    "played": s.get("played", 0),
                    "won": s.get("won", 0),
                    "lost": s.get("lost", 0),
                    "draw": s.get("draw", 0),
                    "points": s.get("points", 0),
                    "nrr": s.get("netto_run_rate", 0),
                    "position": s.get("position", 0),
                    "recent_form": form_str,
                })
        if teams:
            teams.sort(key=lambda x: (-x["points"], -x.get("nrr", 0) if isinstance(x.get("nrr"), (int, float)) else 0))
            return teams

    # Fallback: compute from fixtures
    fixtures = await fetch_season_fixtures(sid)
    finished = [f for f in fixtures if (f.get("status") or "").lower() == "finished"]

    team_records = {}
    for f in finished:
        lt_id = f.get("localteam_id")
        vt_id = f.get("visitorteam_id")
        winner = f.get("winner_team_id")

        for tid in [lt_id, vt_id]:
            if tid and tid not in team_records:
                team_records[tid] = {"played": 0, "won": 0, "lost": 0, "points": 0}

        if lt_id:
            team_records[lt_id]["played"] += 1
        if vt_id:
            team_records[vt_id]["played"] += 1

        if winner:
            if winner in team_records:
                team_records[winner]["won"] += 1
                team_records[winner]["points"] += 2
            loser = vt_id if winner == lt_id else lt_id
            if loser and loser in team_records:
                team_records[loser]["lost"] += 1

    # Resolve team names
    teams = []
    for tid, rec in team_records.items():
        name = next((tn for tn, sm_id in TEAM_SM_IDS.items() if sm_id == tid), f"Team {tid}")
        teams.append({"team": name, "team_id": tid, **rec})

    teams.sort(key=lambda x: (-x["points"], -x["won"]))
    return teams


async def fetch_player_season_stats_for_xi(
    playing_xi: list,
    team_name: str,
    num_matches: int = 5,
    team_stats_override: Optional[dict] = None,
) -> list:
    """Get per-player IPL stats for a Playing XI from last ``num_matches`` finished games.

    If ``team_stats_override`` is provided (e.g. already fetched for pre-match), it is reused
    so callers avoid duplicate SportMonks fixture calls.
    """
    if not playing_xi:
        return []
    team_stats = team_stats_override
    if team_stats is None:
        team_stats = await fetch_team_recent_performance(team_name, num_matches)
    if not team_stats:
        return [dict(p) for p in playing_xi]

    # Match playing XI players to their stats by name similarity
    enriched = []
    for player in playing_xi:
        pname = (player.get("name") or "").lower()
        matched_stats = None

        for pid, ps in team_stats.items():
            sm_name = (ps.get("name") or "").lower()
            if pname == sm_name:
                matched_stats = ps
                break
            # Partial match: last name or substring
            if pname in sm_name or sm_name in pname:
                matched_stats = ps
                break
            pname_parts = pname.split()
            sm_parts = sm_name.split()
            if len(pname_parts) > 0 and len(sm_parts) > 0 and pname_parts[-1] == sm_parts[-1]:
                matched_stats = ps
                break

        p_copy = dict(player)
        if matched_stats:
            bat = matched_stats.get("batting", {})
            bowl = matched_stats.get("bowling", {})
            p_copy["season_stats"] = {
                "matches": matched_stats.get("matches", 0),
                "bat_runs": bat.get("runs", 0),
                "bat_innings": bat.get("innings", 0),
                "bat_avg": bat.get("avg", 0),
                "bat_sr": bat.get("sr", 0),
                "bat_fours": bat.get("fours", 0),
                "bat_sixes": bat.get("sixes", 0),
                "bowl_wickets": bowl.get("wickets", 0),
                "bowl_innings": bowl.get("innings", 0),
                "bowl_economy": bowl.get("economy", 0),
                "bowl_runs": bowl.get("runs_conceded", 0),
                "bowl_overs": bowl.get("overs", 0),
            }
        else:
            p_copy["season_stats"] = None
        enriched.append(p_copy)

    return enriched
