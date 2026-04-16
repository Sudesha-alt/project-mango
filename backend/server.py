from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks, Body, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
import copy
import hashlib
import math
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

import pytz

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

IST = pytz.timezone("Asia/Kolkata")

# When false (default), no cron jobs — avoids automatic SportMonks/CricAPI polling (user uses buttons).
ENABLE_BACKGROUND_SCHEDULERS = os.environ.get("ENABLE_BACKGROUND_SCHEDULERS", "false").lower() in (
    "1",
    "true",
    "yes",
)
_scheduler_started = False
# Created only when ENABLE_BACKGROUND_SCHEDULERS (APScheduler is optional — not installed in slim prod).
scheduler = None

from services.cricket_service import get_short_name
from services.probability_engine import (
    ensemble_probability, calculate_odds_from_probability,
    calculate_momentum, calculate_betting_edge
)
from services.ai_service import (
    fetch_ipl_schedule, fetch_ipl_squads, fetch_live_match_update,
    get_match_prediction, get_player_predictions,
    fetch_player_stats_for_prediction, gpt_contextual_analysis,
    gpt_consultation,
    resolve_tbd_venues,
    claude_deep_match_analysis, claude_live_analysis,
    claude_sportmonks_prediction, fetch_pre_match_stats, validate_factor_reasons_with_claude,
    claude_infer_playing_xi_roles, normalize_primary_cricket_role,
    claude_generate_player_impact_points,
)
from services.sportmonks_service import (
    fetch_live_match,
    check_fixture_status,
    fetch_livescores_ipl,
    parse_fixture,
    fetch_fixture_details,
    fetch_recent_fixtures,
    fetch_last_played_xi,
    fetch_playing_xi_from_live,
    fetch_team_recent_performance,
    fetch_playing_xi_from_last_match,
    sync_player_performance_to_db,
    fetch_season_fixtures,
    IPL_SEASON_IDS,
    _get_team_sm_id,
    fetch_fixture_start_time,
    fetch_ipl_season_schedule,
    fetch_venue_stats,
    fetch_h2h_record,
    fetch_team_standings,
    fetch_player_season_stats_for_xi,
    fetch_team_impact_sub_history,
    format_livescore_entry_text,
)
from services.beta_prediction_engine import run_beta_prediction
from services.consultant_engine import run_consultation, build_features
from services.cricdata_service import fetch_live_ipl_details, fetch_venue_stats_from_cricapi
from services.pre_match_predictor import (
    compute_prediction,
    resolve_star_player_rating,
    compute_strength_metrics_for_match,
)
from services.live_predictor import (
    compute_live_prediction,
    compute_combined_prediction,
    detect_match_phase,
    stabilize_team1_win_pct,
)
from services.weather_service import fetch_weather_for_venue
from services.schedule_data import get_schedule_documents, TEAM_SHORT_CODES, CITY_STADIUMS
from services.web_scraper import fetch_match_news
from services.form_service import fetch_team_form, fetch_momentum, generate_expected_xi

def _require_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise RuntimeError(f"Missing or empty required environment variable: {name}")
    return val


mongo_url = _require_env("MONGO_URL")
client = AsyncIOMotorClient(mongo_url)
db = client[_require_env("DB_NAME")]


app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ws_connections: Dict[str, List[WebSocket]] = {}
live_match_state: Dict[str, Any] = {}


async def _get_squads_for_match(team1: str, team2: str) -> dict:
    """Fetch both team squads from DB. Returns {team_name: [players]}."""
    squads = {}
    for team_name in [team1, team2]:
        doc = await db.ipl_squads.find_one(
            {"$or": [
                {"team": {"$regex": team_name.split()[0], "$options": "i"}},
                {"teamName": {"$regex": team_name.split()[0], "$options": "i"}},
            ]},
            {"_id": 0}
        )
        if doc:
            squads[team_name] = doc.get("players", [])
    return squads


# Playing XI is mandatory for pre-match and live model+Claude paths
MIN_PLAYING_XI = 11


def _xi_named_count(xi: list) -> int:
    n = 0
    for p in xi or []:
        if not isinstance(p, dict):
            continue
        if (p.get("name") or p.get("fullname") or "").strip():
            n += 1
    return n


def _prematch_xi_complete(xi_data: dict) -> bool:
    if not xi_data:
        return False
    return (
        _xi_named_count(xi_data.get("team1_xi")) >= MIN_PLAYING_XI
        and _xi_named_count(xi_data.get("team2_xi")) >= MIN_PLAYING_XI
    )


def _sm_playing_xi_complete(sm: dict) -> bool:
    if not sm:
        return False
    return (
        _xi_named_count(sm.get("team1_playing_xi")) >= MIN_PLAYING_XI
        and _xi_named_count(sm.get("team2_playing_xi")) >= MIN_PLAYING_XI
    )


def _squad_rows_from_lineup_xi(xi_list: list) -> list:
    rows = []
    for p in (xi_list or [])[:16]:
        if not isinstance(p, dict):
            continue
        nm = (p.get("name") or p.get("fullname") or "").strip()
        if not nm:
            continue
        rows.append({
            "name": nm,
            "role": p.get("role") or p.get("position") or "Batsman",
            "isCaptain": bool(p.get("isCaptain") or p.get("is_captain")),
        })
    return rows


def _normalize_player_name(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _compact_player_name_vowels(name: str) -> str:
    return re.sub(r"[aeiou]+", "a", _normalize_player_name(name))


def _vaibhav_suryavanshi_family_key(name: str) -> Optional[str]:
    """Unify Vaibhav Suryavanshi vs Sooryanvanshi / Sooryanvanshi-style transliterations."""
    n = _normalize_player_name(name)
    if "vaibhav" in n and "vanshi" in n:
        return "vaibhav_suryavanshi"
    return None


def _player_name_matches(a: str, b: str) -> bool:
    """Robust player name match for DB roster vs SportMonks lineup."""
    na = _normalize_player_name(a)
    nb = _normalize_player_name(b)
    if not na or not nb:
        return False
    vk_a = _vaibhav_suryavanshi_family_key(a)
    vk_b = _vaibhav_suryavanshi_family_key(b)
    if vk_a and vk_b:
        return True
    if na == nb or na in nb or nb in na:
        return True

    a_parts = na.split()
    b_parts = nb.split()
    a_last = a_parts[-1] if a_parts else ""
    b_last = b_parts[-1] if b_parts else ""
    a_first_i = a_parts[0][0] if a_parts and a_parts[0] else ""
    b_first_i = b_parts[0][0] if b_parts and b_parts[0] else ""

    if a_last and b_last and a_last == b_last and a_first_i and a_first_i == b_first_i:
        return True
    if _compact_player_name_vowels(na) == _compact_player_name_vowels(nb):
        return True
    if a_first_i and b_first_i and a_first_i == b_first_i:
        if SequenceMatcher(None, na, nb).ratio() >= 0.88:
            return True
    return False


# SportMonks "last match" XI sometimes omits players who are confirmed starters; inject from DB roster.
RR_VAIBHAV_CANONICAL = "Vaibhav Suryavanshi"
RR_VAIBHAV_INJECT_REPLACE_FIRST = (
    "Brijesh Sharma",
    "Vignesh Puthur",
    "Sushant Mishra",
    "Ravi Singh",
    "Yash Raj Punja",
)


def _is_rajasthan_team_label(team_label: str) -> bool:
    return "rajasthan" in (team_label or "").lower()


def _find_rr_vaibhav_roster_row(full_roster: list) -> Optional[dict]:
    for p in full_roster or []:
        if not isinstance(p, dict):
            continue
        if _player_name_matches(p.get("name", ""), RR_VAIBHAV_CANONICAL):
            return dict(p)
    return None


def _xi_rows_include_vaibhav(xi_rows: list) -> bool:
    for p in xi_rows or []:
        if not isinstance(p, dict):
            continue
        nm = p.get("name") or p.get("fullname") or ""
        if _player_name_matches(nm, RR_VAIBHAV_CANONICAL):
            return True
    return False


def ensure_rr_vaibhav_in_playing_xi_rows(
    xi_rows: list,
    team_label: str,
    full_team_roster: list,
) -> list:
    """If Rajasthan XI has no Vaibhav Suryavanshi but he is on the roster, swap out a fringe pick."""
    if not xi_rows or not _is_rajasthan_team_label(team_label):
        return xi_rows
    if len(xi_rows) < 11:
        return xi_rows
    if _xi_rows_include_vaibhav(xi_rows):
        return xi_rows
    roster_v = _find_rr_vaibhav_roster_row(full_team_roster)
    if not roster_v:
        return xi_rows
    out: list = []
    for p in xi_rows:
        if isinstance(p, dict):
            out.append(dict(p))
        else:
            out.append(p)
    row = {
        "name": roster_v.get("name", RR_VAIBHAV_CANONICAL),
        "role": roster_v.get("role", "Batsman"),
        "isCaptain": bool(roster_v.get("isCaptain", False)),
        "isOverseas": bool(roster_v.get("isOverseas", False)),
    }
    for drop in RR_VAIBHAV_INJECT_REPLACE_FIRST:
        for i, p in enumerate(out):
            if not isinstance(p, dict):
                continue
            nm = p.get("name") or p.get("fullname") or ""
            if _player_name_matches(nm, drop):
                logger.info("RR XI: injected %s (replaced %s)", RR_VAIBHAV_CANONICAL, nm)
                out[i] = {**p, **row}
                return out
    last = out[-1]
    last_nm = last.get("name", "") if isinstance(last, dict) else ""
    logger.info("RR XI: injected %s (replaced last: %s)", RR_VAIBHAV_CANONICAL, last_nm)
    out[-1] = {**last, **row} if isinstance(last, dict) else row
    return out


def _playing_xi_squads_from_doc(
    xi_doc: dict,
    match_squads: dict,
    team1: str,
    team2: str,
) -> dict:
    """
    Build squad dict for pre-match algo / Claude strictly from the playing_xi collection
    (Expected11 per side), merged with ipl_squads rows when names match.
    Never includes players not listed in the cached XI.
    """
    if not xi_doc or not _prematch_xi_complete(xi_doc):
        return {}

    def _named_rows(rows: list) -> list:
        out = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            nm = (row.get("name") or row.get("fullname") or "").strip()
            if nm:
                out.append(row)
        return out

    t1_rows = _named_rows(xi_doc.get("team1_xi"))
    t2_rows = _named_rows(xi_doc.get("team2_xi"))
    if len(t1_rows) < MIN_PLAYING_XI or len(t2_rows) < MIN_PLAYING_XI:
        return {}

    def _enrich(rows: list, sched_team: str) -> list:
        squad_list = (match_squads or {}).get(sched_team, [])
        res: list = []
        seen: set = set()
        for row in rows:
            if len(res) >= MIN_PLAYING_XI:
                break
            nm = (row.get("name") or row.get("fullname") or "").strip()
            key = _normalize_player_name(nm)
            if key in seen:
                continue
            seen.add(key)
            match_p = next(
                (p for p in squad_list if _player_name_matches(p.get("name", ""), nm)),
                None,
            )
            if match_p:
                res.append(dict(match_p))
            else:
                res.append({
                    "name": nm,
                    "role": row.get("role", "Batsman"),
                    "isCaptain": bool(row.get("isCaptain") or row.get("is_captain")),
                    "isOverseas": bool(row.get("isOverseas") or row.get("is_overseas")),
                })
        if len(res) < MIN_PLAYING_XI:
            return []
        return res[:MIN_PLAYING_XI]

    t1_final = _enrich(t1_rows, team1)
    t2_final = _enrich(t2_rows, team2)
    if len(t1_final) < MIN_PLAYING_XI or len(t2_final) < MIN_PLAYING_XI:
        return {}
    return {team1: t1_final, team2: t2_final}


def _xi_roles_fingerprint(prediction_squads: dict, team1: str, team2: str) -> str:
    t1 = prediction_squads.get(team1) or []
    t2 = prediction_squads.get(team2) or []
    n1 = tuple(_normalize_player_name(p.get("name", "")) for p in t1[:MIN_PLAYING_XI])
    n2 = tuple(_normalize_player_name(p.get("name", "")) for p in t2[:MIN_PLAYING_XI])
    raw = json.dumps({"t1": n1, "t2": n2}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ingest_name_role_mapping(m: dict, mapping: dict) -> None:
    if not isinstance(mapping, dict):
        return
    for nm, r in mapping.items():
        k = str(nm).strip()
        if k:
            m[_normalize_player_name(k)] = normalize_primary_cricket_role(r)


def _role_map_from_claude_xi_cache(cached: dict) -> dict:
    """normalized_player_name -> canonical role"""
    m: dict = {}
    _ingest_name_role_mapping(m, cached.get("team_a") or {})
    _ingest_name_role_mapping(m, cached.get("team_b") or {})
    _ingest_name_role_mapping(m, cached.get("teamA") or {})
    _ingest_name_role_mapping(m, cached.get("teamB") or {})
    for side in ("team1", "team2"):
        block = cached.get(side)
        if isinstance(block, dict):
            _ingest_name_role_mapping(m, block)
            continue
        for row in block or []:
            if not isinstance(row, dict):
                continue
            nm = (row.get("name") or "").strip()
            if not nm:
                continue
            m[_normalize_player_name(nm)] = normalize_primary_cricket_role(row.get("role"))
    return m


def _role_map_from_claude_infer_payload(payload: dict) -> dict:
    m: dict = {}
    _ingest_name_role_mapping(m, payload.get("team_a") or {})
    _ingest_name_role_mapping(m, payload.get("team_b") or {})
    _ingest_name_role_mapping(m, payload.get("teamA") or {})
    _ingest_name_role_mapping(m, payload.get("teamB") or {})
    for side in ("team1", "team2"):
        block = payload.get(side)
        if isinstance(block, dict):
            _ingest_name_role_mapping(m, block)
        elif isinstance(block, list):
            for row in block:
                if not isinstance(row, dict):
                    continue
                nm = (row.get("name") or "").strip()
                if nm:
                    m[_normalize_player_name(nm)] = normalize_primary_cricket_role(row.get("role"))
    return m


def _apply_role_map_to_prediction_squads(prediction_squads: dict, team1: str, team2: str, role_map: dict) -> None:
    for tkey in (team1, team2):
        for p in prediction_squads.get(tkey) or []:
            if not isinstance(p, dict):
                continue
            nm = _normalize_player_name(p.get("name", ""))
            if nm in role_map:
                p["role"] = role_map[nm]
                p["role_source"] = "claude"


def _role_map_from_claude_infer_payload_fuzzy(
    payload: dict,
    prediction_squads: dict,
    team1: str,
    team2: str,
) -> dict:
    """Normalize Claude name→role maps, then fuzzy-match any XI names Claude keyed slightly differently."""
    m = _role_map_from_claude_infer_payload(payload)
    pairs: list = []
    for block in (
        payload.get("team_a"),
        payload.get("team_b"),
        payload.get("teamA"),
        payload.get("teamB"),
    ):
        if not isinstance(block, dict):
            continue
        for k, v in block.items():
            nk = str(k).strip()
            if nk:
                pairs.append((nk, normalize_primary_cricket_role(v)))
    for tk in (team1, team2):
        for p in prediction_squads.get(tk) or []:
            nm = (p.get("name") or "").strip()
            if not nm:
                continue
            nn = _normalize_player_name(nm)
            if nn in m:
                continue
            best_role = None
            best_sc = 0.0
            for ck, cr in pairs:
                sc = SequenceMatcher(None, nn, _normalize_player_name(ck)).ratio()
                if sc > best_sc:
                    best_sc = sc
                    best_role = cr
            if best_sc >= 0.80 and best_role is not None:
                m[nn] = best_role
                logger.info("Claude XI roles: fuzzy matched %r (score %.2f)", nm, best_sc)
    return m


def _playing_xi_needs_claude_roles(cached_doc: dict) -> bool:
    """True if cached playing_xi is missing roles or was not assigned by Claude (re-run full predict)."""
    if not cached_doc or not isinstance(cached_doc, dict):
        return False
    px = cached_doc.get("playing_xi") or {}
    for key in ("team1_xi", "team2_xi"):
        rows = px.get(key) or []
        if len(rows) < MIN_PLAYING_XI:
            return True
        for p in rows:
            if not isinstance(p, dict):
                return True
            if not (p.get("role") or "").strip():
                return True
            if p.get("role_source") != "claude":
                return True
    return False


def _sanitize_playing_xi_payload(xi_data: Optional[dict]) -> None:
    """Ensure every XI row has a non-empty canonical role for API/frontend (mutates)."""
    if not xi_data:
        return
    for key in ("team1_xi", "team2_xi"):
        rows = xi_data.get(key) or []
        out = []
        for p in rows:
            if not isinstance(p, dict):
                continue
            d = dict(p)
            d["role"] = normalize_primary_cricket_role(d.get("role"))
            out.append(d)
        xi_data[key] = out


def _merge_playing_xi_roles_from_storage(pred_doc: dict, xi_doc: dict) -> None:
    """Copy role / role_source from playing_xi DB doc onto prediction.playing_xi rows (same names)."""
    px = pred_doc.get("playing_xi")
    if not isinstance(px, dict) or not xi_doc:
        return
    for pk in ("team1_xi", "team2_xi"):
        prow = px.get(pk) or []
        xrow = xi_doc.get(pk) or []
        if not xrow:
            continue
        x_by = {
            _normalize_player_name(
                (r.get("name") or r.get("fullname") or "")
            ): r
            for r in xrow
            if isinstance(r, dict)
        }
        for r in prow:
            if not isinstance(r, dict):
                continue
            nn = _normalize_player_name(r.get("name", ""))
            src = x_by.get(nn)
            if not src:
                continue
            role = (src.get("role") or "").strip()
            if role:
                r["role"] = normalize_primary_cricket_role(role)
                r["role_source"] = src.get("role_source") or "claude"


def _merge_roles_into_stored_xi_rows(rows: list, role_map: dict) -> list:
    out: list = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        d = dict(r)
        nm = _normalize_player_name((d.get("name") or d.get("fullname") or ""))
        if nm in role_map:
            d["role"] = role_map[nm]
            d["role_source"] = "claude"
        out.append(d)
    return out


def _claude_xi_roles_cache_blob(
    fingerprint: str,
    prediction_squads: dict,
    team1: str,
    team2: str,
) -> dict:
    t1 = (prediction_squads.get(team1) or [])[:MIN_PLAYING_XI]
    t2 = (prediction_squads.get(team2) or [])[:MIN_PLAYING_XI]
    team_a = {
        (p.get("name") or "").strip(): normalize_primary_cricket_role(p.get("role"))
        for p in t1
        if (p.get("name") or "").strip()
    }
    team_b = {
        (p.get("name") or "").strip(): normalize_primary_cricket_role(p.get("role"))
        for p in t2
        if (p.get("name") or "").strip()
    }
    return {
        "fingerprint": fingerprint,
        "team_a": team_a,
        "team_b": team_b,
        "inferred_at": datetime.now(timezone.utc).isoformat(),
    }


async def _ensure_claude_playing_xi_roles(
    match_id: str,
    team1: str,
    team2: str,
    prediction_squads: dict,
    xi_doc: dict,
    *,
    mandatory: bool = False,
) -> None:
    """
    Merge Claude-inferred primary roles into prediction_squads (mutates) and persist to playing_xi.

    If mandatory=True (pre-match predict): always calls Claude, validates full coverage, raises on failure.
    If mandatory=False (background): may use fingerprint cache; failures are logged only.
    """
    if not prediction_squads or not xi_doc:
        if mandatory:
            raise HTTPException(
                status_code=500,
                detail={"error": "xi_roles_internal", "message": "Missing squads or XI document for role inference."},
            )
        return

    fp = _xi_roles_fingerprint(prediction_squads, team1, team2)
    cached = (xi_doc or {}).get("claude_xi_roles") or {}

    def _cache_has_both_sides(c: dict) -> bool:
        ta = c.get("team_a") or c.get("teamA") or {}
        tb = c.get("team_b") or c.get("teamB") or {}
        if isinstance(ta, dict) and isinstance(tb, dict):
            return len(ta) >= MIN_PLAYING_XI and len(tb) >= MIN_PLAYING_XI
        return (
            len(c.get("team1") or []) >= MIN_PLAYING_XI
            and len(c.get("team2") or []) >= MIN_PLAYING_XI
        )

    if not mandatory and cached.get("fingerprint") == fp and _cache_has_both_sides(cached):
        role_map = _role_map_from_claude_xi_cache(cached)
        _apply_role_map_to_prediction_squads(prediction_squads, team1, team2, role_map)
        return

    try:
        payload = await claude_infer_playing_xi_roles(team1, team2, prediction_squads)
    except Exception as e:
        msg = str(e)
        logger.warning("Claude XI role inference failed for %s: %s", match_id, msg)
        if mandatory:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "claude_xi_roles_failed",
                    "message": (
                        "Could not infer Playing XI roles from Claude. "
                        "Set ANTHROPIC_API_KEY and try again. "
                        f"Detail: {msg}"
                    ),
                },
            ) from e
        return

    role_map = _role_map_from_claude_infer_payload_fuzzy(payload, prediction_squads, team1, team2)
    missing: list = []
    for tk in (team1, team2):
        for p in prediction_squads.get(tk) or []:
            if not isinstance(p, dict):
                continue
            nn = _normalize_player_name(p.get("name", ""))
            if nn and nn not in role_map:
                missing.append(p.get("name", ""))

    if missing:
        logger.warning("Claude XI roles incomplete for %s: %s", match_id, missing[:6])
        if mandatory:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "claude_xi_roles_incomplete",
                    "message": "Claude did not return a role for every Expected XI player.",
                    "missing_names": [m for m in missing if m],
                },
            )

    _apply_role_map_to_prediction_squads(prediction_squads, team1, team2, role_map)

    t1_rows = _merge_roles_into_stored_xi_rows(xi_doc.get("team1_xi"), role_map)
    t2_rows = _merge_roles_into_stored_xi_rows(xi_doc.get("team2_xi"), role_map)
    blob = _claude_xi_roles_cache_blob(fp, prediction_squads, team1, team2)
    try:
        await db.playing_xi.update_one(
            {"matchId": match_id},
            {"$set": {
                "claude_xi_roles": blob,
                "team1_xi": t1_rows,
                "team2_xi": t2_rows,
            }},
        )
    except Exception as e:
        logger.warning(f"Could not persist Claude XI roles for {match_id}: {e}")
        if mandatory:
            raise HTTPException(
                status_code=500,
                detail={"error": "xi_roles_persist_failed", "message": str(e)},
            ) from e


async def _bg_infer_claude_xi_roles(match_id: str, team1: str, team2: str) -> None:
    """After Playing XI is cached, infer roles in background (non-blocking for poll UX)."""
    await asyncio.sleep(0.5)
    try:
        xi_doc = await db.playing_xi.find_one({"matchId": match_id}, {"_id": 0})
        if not xi_doc or not _prematch_xi_complete(xi_doc):
            return
        match_squads = await _get_squads_for_match(team1, team2)
        prediction_squads = _playing_xi_squads_from_doc(xi_doc, match_squads, team1, team2)
        if not prediction_squads:
            return
        await _ensure_claude_playing_xi_roles(
            match_id, team1, team2, prediction_squads, xi_doc, mandatory=False,
        )
    except Exception as e:
        logger.warning(f"Background Claude XI roles failed for {match_id}: {e}")


def _filter_player_performance_to_playing_xi(
    player_performance: Optional[dict],
    playing_xi_squads: dict,
) -> dict:
    """Restrict SportMonks player_performance blobs to Expected XI names only."""
    if not player_performance or not playing_xi_squads:
        return player_performance or {}
    roster_names: list = []
    for players in playing_xi_squads.values():
        for p in players or []:
            n = (p.get("name") or "").strip()
            if n:
                roster_names.append(n)
    if not roster_names:
        return {}

    def _keep(name: str) -> bool:
        return any(_player_name_matches(name or "", rn) for rn in roster_names)

    out: dict = {}
    for side in ("team1", "team2"):
        raw = player_performance.get(side)
        if not raw:
            continue
        if isinstance(raw, dict):
            filtered = {
                k: v
                for k, v in raw.items()
                if isinstance(v, dict) and _keep(v.get("name", ""))
            }
            if filtered:
                out[side] = filtered
        elif isinstance(raw, list):
            filtered = [
                x for x in raw
                if isinstance(x, dict) and _keep(x.get("name", ""))
            ]
            if filtered:
                out[side] = filtered
    return out


def _impact_role_code(role_label: str) -> str:
    role = normalize_primary_cricket_role(role_label or "")
    if role == "All-rounder":
        return "AR"
    if role == "Bowler":
        return "BOWL"
    return "BAT"


def _impact_points_from_perf_row(perf_row: dict, role_code: str, base_rating: float) -> tuple:
    """
    Convert SportMonks aggregate stats to BatIP/BowlIP in [0,100].
    Falls back to role-aware split around base rating when data is sparse.
    """
    bat = (perf_row or {}).get("batting", {}) if isinstance(perf_row, dict) else {}
    bowl = (perf_row or {}).get("bowling", {}) if isinstance(perf_row, dict) else {}
    has_bat = bool(bat.get("innings", 0))
    has_bowl = bool(bowl.get("innings", 0))

    if has_bat:
        bavg = float(bat.get("avg", 0) or 0)
        bsr = float(bat.get("sr", 0) or 0)
        runs = float(bat.get("runs", 0) or 0)
        bat_ip = 0.55 * min(100.0, (bavg / 55.0) * 100.0) + 0.30 * min(100.0, (bsr / 180.0) * 100.0) + 0.15 * min(
            100.0, (runs / 300.0) * 100.0
        )
    else:
        bat_ip = max(15.0, min(95.0, base_rating - (22.0 if role_code == "BOWL" else 8.0)))

    if has_bowl:
        eco = float(bowl.get("economy", 12.0) or 12.0)
        inns = max(1.0, float(bowl.get("innings", 0) or 0))
        wickets = float(bowl.get("wickets", 0) or 0)
        wpi = wickets / inns
        eco_score = min(100.0, max(0.0, (12.0 - eco) / 6.0 * 100.0))
        wpi_score = min(100.0, (wpi / 2.0) * 100.0)
        bowl_ip = 0.60 * wpi_score + 0.40 * eco_score
    else:
        bowl_ip = max(10.0, min(95.0, base_rating - (24.0 if role_code == "BAT" else 10.0)))

    if role_code == "BAT":
        bowl_ip *= 0.55
    elif role_code == "BOWL":
        bat_ip *= 0.60

    return max(0.0, min(100.0, bat_ip)), max(0.0, min(100.0, bowl_ip))


async def _build_team_strength_inputs(
    team1: str,
    team2: str,
    prediction_squads: dict,
    player_performance: dict,
) -> dict:
    """
    Build per-player required values with source priority:
    DB cache -> SportMonks-derived -> Claude-generated fallback.
    """
    team_rows: Dict[str, list] = {"team1": [], "team2": []}
    missing_for_claude: list = []

    cached_docs = {}
    try:
        d1 = await db.player_impact_points.find_one({"team": team1}, {"_id": 0})
        d2 = await db.player_impact_points.find_one({"team": team2}, {"_id": 0})
        cached_docs = {"team1": d1 or {}, "team2": d2 or {}}
    except Exception:
        cached_docs = {"team1": {}, "team2": {}}

    for side, team_label in (("team1", team1), ("team2", team2)):
        xi = prediction_squads.get(team_label, []) or []
        perf_side = player_performance.get(side, {}) if isinstance(player_performance, dict) else {}
        cached_players = cached_docs.get(side, {}).get("players", {}) if isinstance(cached_docs.get(side), dict) else {}
        for idx, p in enumerate(xi[:11], start=1):
            name = (p.get("name") or "").strip()
            if not name:
                continue
            role_code = _impact_role_code(p.get("role"))
            base_rating = float(resolve_star_player_rating(name))

            cached_match = next(
                (
                    v
                    for _, v in (cached_players.items() if isinstance(cached_players, dict) else [])
                    if isinstance(v, dict) and _player_name_matches(v.get("name", ""), name)
                ),
                None,
            )
            bat_ip = bowl_ip = None
            source = "db"
            if isinstance(cached_match, dict):
                for k in ("BatIP", "bat_ip", "batting_impact", "battingImpact"):
                    if cached_match.get(k) is not None:
                        bat_ip = float(cached_match.get(k))
                        break
                for k in ("BowlIP", "bowl_ip", "bowling_impact", "bowlingImpact"):
                    if cached_match.get(k) is not None:
                        bowl_ip = float(cached_match.get(k))
                        break

            perf_match = next(
                (
                    v
                    for _, v in (perf_side.items() if isinstance(perf_side, dict) else [])
                    if isinstance(v, dict) and _player_name_matches(v.get("name", ""), name)
                ),
                None,
            )
            if bat_ip is None or bowl_ip is None:
                source = "sportmonks" if perf_match is not None else "default_fallback"
                b_est, bo_est = _impact_points_from_perf_row(perf_match or {}, role_code, base_rating)
                bat_ip = b_est if bat_ip is None else bat_ip
                bowl_ip = bo_est if bowl_ip is None else bowl_ip

            if perf_match is None and not isinstance(cached_match, dict):
                missing_for_claude.append(
                    {
                        "name": name,
                        "player_role": role_code,
                        "batting_style": p.get("batting_style") or "",
                        "bowling_style": p.get("bowling_style") or "",
                    }
                )

            team_rows[side].append(
                {
                    "player_id": p.get("id") or p.get("player_id") or name,
                    "name": name,
                    "player_role": role_code,
                    "BatIP": round(float(max(0.0, min(100.0, bat_ip if bat_ip is not None else base_rating))), 4),
                    "BowlIP": round(float(max(0.0, min(100.0, bowl_ip if bowl_ip is not None else base_rating))), 4),
                    "batting_position": idx,
                    "bowling_order": 0,
                    "_source": source,
                }
            )

        # assign bowling_order by descending BowlIP among active bowl roles
        bowl_candidates = [
            r for r in team_rows[side] if r["player_role"] in {"BOWL", "AR"} or r.get("BowlIP", 0.0) >= 40.0
        ]
        bowl_candidates.sort(key=lambda r: r.get("BowlIP", 0.0), reverse=True)
        for ord_idx, row in enumerate(bowl_candidates[:5], start=1):
            row["bowling_order"] = ord_idx

    if missing_for_claude:
        claude_rows = await claude_generate_player_impact_points(team1, team2, missing_for_claude)
        if claude_rows:
            for side in ("team1", "team2"):
                for row in team_rows[side]:
                    if row.get("_source") == "sportmonks":
                        continue
                    nm = row.get("name", "")
                    est = next(
                        (v for k, v in claude_rows.items() if _player_name_matches(k, nm)),
                        None,
                    )
                    if isinstance(est, dict):
                        row["BatIP"] = round(float(est.get("BatIP", row["BatIP"])), 4)
                        row["BowlIP"] = round(float(est.get("BowlIP", row["BowlIP"])), 4)
                        row["_source"] = "claude"

    metrics = compute_strength_metrics_for_match(team_rows, n_bat=5, m_bowl=4, alpha=0.5)
    metrics["team_inputs"] = team_rows
    return metrics


def _xi_flat_names(playing_xi_squads: dict) -> list:
    names: list = []
    for players in (playing_xi_squads or {}).values():
        for p in players or []:
            n = (p.get("name") or "").strip()
            if n:
                names.append(n)
    return names


def _top_performer_in_xi(entry: dict, allow_names: list) -> bool:
    if not isinstance(entry, dict) or not allow_names:
        return False
    nm = entry.get("name") or entry.get("player") or ""
    return any(_player_name_matches(nm, an) for an in allow_names if an)


def _filter_form_data_to_playing_xi(
    form_data: Optional[dict],
    playing_xi_squads: dict,
    team1: str,
    team2: str,
) -> Optional[dict]:
    """Keep form top_performers aligned with Expected XI only (defensive vs stale perf)."""
    if not form_data or not playing_xi_squads:
        return form_data
    for key, tname in (("team1", team1), ("team2", team2)):
        block = form_data.get(key)
        if not isinstance(block, dict):
            continue
        allow = [
            (p.get("name") or "").strip()
            for p in (playing_xi_squads.get(tname) or [])
            if (p.get("name") or "").strip()
        ]
        tp = block.get("top_performers")
        if isinstance(tp, list):
            block["top_performers"] = [x for x in tp if _top_performer_in_xi(x, allow)]
    return form_data


def _scrub_algo_prediction_for_claude(
    algo_doc: Optional[dict],
    playing_xi_squads: dict,
    team1: str,
    team2: str,
) -> Optional[dict]:
    """Deep-copy cached pre-match doc and strip current_form top_performers not on Expected XI."""
    if not algo_doc or not playing_xi_squads:
        return algo_doc
    scrubbed = copy.deepcopy(algo_doc)
    pred = scrubbed.get("prediction") or scrubbed
    factors = pred.get("factors")
    if not isinstance(factors, dict):
        return scrubbed
    cf = factors.get("current_form")
    if not isinstance(cf, dict):
        return scrubbed

    def _filt(tp, tname: str):
        allow = [
            (p.get("name") or "").strip()
            for p in (playing_xi_squads.get(tname) or [])
            if (p.get("name") or "").strip()
        ]
        if not isinstance(tp, list):
            return tp
        return [x for x in tp if _top_performer_in_xi(x, allow)]

    cf["team1_top_performers"] = _filt(cf.get("team1_top_performers"), team1)
    cf["team2_top_performers"] = _filt(cf.get("team2_top_performers"), team2)
    factors["current_form"] = cf
    pred["factors"] = factors
    if scrubbed.get("prediction") is not None:
        scrubbed["prediction"] = pred
    return scrubbed


def _filter_news_items_for_xi(
    news: Optional[list],
    team1: str,
    team2: str,
    playing_xi_squads: dict,
) -> list:
    """
    Drop obvious cross-franchise noise (e.g. CSK/Samson roundups) and shorten bodies for Claude.
    """
    if not news:
        return []
    allow = _xi_flat_names(playing_xi_squads)

    def _allow_substr(sub: str) -> bool:
        sub_l = sub.lower().strip()
        if not sub_l:
            return False
        return any(sub_l in _normalize_player_name(n) for n in allow)

    t1_words = set(team1.lower().split())
    t2_words = set(team2.lower().split())
    out: list = []
    for article in news[:12]:
        if not isinstance(article, dict):
            continue
        title = article.get("title", "") or ""
        body = (article.get("body", "") or "")[:350]
        text_lower = (title + " " + body).lower()
        t1_match = any(w in text_lower for w in t1_words if len(w) > 3)
        t2_match = any(w in text_lower for w in t2_words if len(w) > 3)
        ipl_match = "ipl" in text_lower or "cricket" in text_lower
        if not ((t1_match or t2_match) and ipl_match):
            continue
        if re.search(r"\bsamson\b", text_lower) and not _allow_substr("samson"):
            if any(x in text_lower for x in ("chennai", "csk", "super king")):
                continue
        item = {**article, "body": body[:120]}
        out.append(item)
        if len(out) >= 5:
            break
    return out


def _recent_form_impact_score(season_stats: Optional[dict]) -> Optional[float]:
    """0-100 score from SportMonks last-N aggregates (batting and/or bowling), same spirit as form_service."""
    if not season_stats:
        return None
    bi = int(season_stats.get("bat_innings") or 0)
    bii = int(season_stats.get("bowl_innings") or 0)
    if bi == 0 and bii == 0:
        return None
    parts = []
    if bi > 0:
        avg = float(season_stats.get("bat_avg") or 0)
        sr = float(season_stats.get("bat_sr") or 0)
        parts.append(min(100.0, max(0.0, avg * 2.0 + sr * 0.2)))
    if bii > 0:
        econ = float(season_stats.get("bowl_economy") or 12)
        w = float(season_stats.get("bowl_wickets") or 0)
        wpi = w / max(bii, 1)
        econ_score = max(0.0, min(100.0, (14.0 - econ) * 10.0))
        wicket_score = min(100.0, wpi * 40.0)
        parts.append(econ_score * 0.5 + wicket_score * 0.5)
    if not parts:
        return None
    return round(sum(parts) / len(parts), 1)


async def _enrich_playing_xi_with_impact(
    xi_data: dict,
    team1: str,
    team2: str,
    player_performance: dict,
) -> dict:
    """Attach SportMonks last-5 stats per XI player + Lucky 11 impact_points (model card rating)."""
    if not xi_data:
        return xi_data
    t1 = xi_data.get("team1_xi") or []
    t2 = xi_data.get("team2_xi") or []
    if not t1 and not t2:
        return xi_data
    try:
        t1_e = await fetch_player_season_stats_for_xi(
            [dict(p) for p in t1],
            team1,
            5,
            team_stats_override=player_performance.get("team1"),
        )
        t2_e = await fetch_player_season_stats_for_xi(
            [dict(p) for p in t2],
            team2,
            5,
            team_stats_override=player_performance.get("team2"),
        )
    except Exception as e:
        logger.warning(f"Playing XI SportMonks enrichment failed: {e}")
        t1_e, t2_e = t1, t2

    def stamp(players: list) -> list:
        out = []
        for p in players:
            d = dict(p)
            nm = (d.get("name") or "").strip()
            d["impact_points"] = int(resolve_star_player_rating(nm))
            ss = d.get("season_stats")
            rf = _recent_form_impact_score(ss)
            if rf is not None:
                d["recent_form_impact"] = rf
            d["is_captain"] = bool(d.get("isCaptain") or d.get("is_captain"))
            d["is_overseas"] = bool(d.get("isOverseas") or d.get("is_overseas"))
            d["role"] = normalize_primary_cricket_role(d.get("role"))
            out.append(d)
        return out

    merged = dict(xi_data)
    merged["team1_xi"] = stamp(t1_e)
    merged["team2_xi"] = stamp(t2_e)
    merged["stats_lookback_matches"] = 5
    merged["xi_lineup_note"] = (
        "XI from SportMonks (live fixture if in progress, otherwise each side's last completed IPL match). "
        "Player roles: roster merge + Claude (pre-match) as Batsman, Bowler, All-rounder, or Wicketkeeper. "
        "impact_points = Lucky 11 card rating (same scale as the 8-factor model). "
        "season_stats / recent_form_impact = last-5-match aggregates from SportMonks."
    )
    return merged


def _filter_squads_to_playing_xi(match_squads: dict, sm_data: dict, team1: str, team2: str) -> dict:
    """Filter full DB squads down to the 11 active Playing XI using SportMonks lineup data.
    Falls back to full squad if lineup data is unavailable or name matching is too low.
    Hard-caps at 12 players per team (11 + 1 impact sub) to prevent full-squad leakage."""
    if not sm_data or not match_squads:
        return match_squads

    # Strictly prefer playing_xi (non-subs); only fall back to lineup if playing_xi is empty
    t1_lineup = sm_data.get("team1_playing_xi", [])
    t2_lineup = sm_data.get("team2_playing_xi", [])

    # Only fall back to full lineup if playing_xi is genuinely absent
    if not t1_lineup:
        t1_lineup = sm_data.get("team1_lineup", [])
        if t1_lineup:
            logger.warning(f"team1_playing_xi empty, falling back to team1_lineup ({len(t1_lineup)} players)")
    if not t2_lineup:
        t2_lineup = sm_data.get("team2_lineup", [])
        if t2_lineup:
            logger.warning(f"team2_playing_xi empty, falling back to team2_lineup ({len(t2_lineup)} players)")

    if not t1_lineup and not t2_lineup:
        logger.info("No lineup data in SportMonks response, using full squads")
        return match_squads

    squad_names = list(match_squads.keys())
    if len(squad_names) < 2:
        return match_squads

    # Build name sets from SportMonks lineup (lowercased for fuzzy matching)
    t1_lineup_names = {p.get("name", "").lower() for p in t1_lineup if p.get("name")}
    t2_lineup_names = {p.get("name", "").lower() for p in t2_lineup if p.get("name")}

    logger.info(f"Playing XI filter: T1 names={len(t1_lineup_names)}, T2 names={len(t2_lineup_names)}")

    def _normalize_name(name: str) -> str:
        s = (name or "").lower()
        # Keep ASCII letters/spaces only to reduce punctuation/noise variance.
        s = re.sub(r"[^a-z\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _compact_vowels(name: str) -> str:
        # Reduce repeated vowels to handle variants like sooryavanshi vs suryavanshi.
        return re.sub(r"[aeiou]+", "a", _normalize_name(name))

    def _match_player(player_name: str, lineup_names: set) -> bool:
        """Check if a DB player name matches any lineup name (exact/initials/fuzzy)."""
        pn = _normalize_name(player_name)
        if not pn:
            return False
        if pn in lineup_names:
            return True

        pn_compact = _compact_vowels(pn)
        pn_parts = pn.split()
        pn_last = pn_parts[-1] if pn_parts else ""
        pn_first_initial = pn_parts[0][0] if pn_parts and pn_parts[0] else ""

        for ln in lineup_names:
            ln_norm = _normalize_name(ln)
            if not ln_norm:
                continue
            if pn in ln_norm or ln_norm in pn:
                return True

            ln_parts = ln_norm.split()
            ln_last = ln_parts[-1] if ln_parts else ""
            ln_first_initial = ln_parts[0][0] if ln_parts and ln_parts[0] else ""

            # Strong deterministic match: surname + first initial.
            if pn_last and ln_last and pn_last == ln_last and pn_first_initial == ln_first_initial:
                return True

            # Handle transliteration/spelling variants by compacting vowels.
            if _compact_vowels(ln_norm) == pn_compact:
                return True

            # Final fallback: high fuzzy ratio with same first initial.
            if pn_first_initial and ln_first_initial and pn_first_initial == ln_first_initial:
                ratio = SequenceMatcher(None, pn, ln_norm).ratio()
                if ratio >= 0.88:
                    return True
        return False

    # Filter team1 squad
    t1_filtered = [p for p in match_squads.get(squad_names[0], [])
                   if _match_player(p.get("name", ""), t1_lineup_names)]
    # Filter team2 squad
    t2_filtered = [p for p in match_squads.get(squad_names[1], [])
                   if _match_player(p.get("name", ""), t2_lineup_names)]

    # Only use filtered if we matched at least 8 players per team
    MAX_XI_CAP = 12  # 11 + 1 impact sub
    filtered_squads = {}

    if len(t1_filtered) >= 8 and t1_lineup_names:
        filtered_squads[squad_names[0]] = t1_filtered[:MAX_XI_CAP]
        logger.info(f"Filtered {squad_names[0]} to {len(filtered_squads[squad_names[0]])} Playing XI players")
    else:
        filtered_squads[squad_names[0]] = match_squads.get(squad_names[0], [])
        if t1_lineup_names:
            logger.warning(f"Low XI match for {squad_names[0]} ({len(t1_filtered)}/{len(t1_lineup_names)}), using full squad")

    if len(t2_filtered) >= 8 and t2_lineup_names:
        filtered_squads[squad_names[1]] = t2_filtered[:MAX_XI_CAP]
        logger.info(f"Filtered {squad_names[1]} to {len(filtered_squads[squad_names[1]])} Playing XI players")
    else:
        filtered_squads[squad_names[1]] = match_squads.get(squad_names[1], [])
        if t2_lineup_names:
            logger.warning(f"Low XI match for {squad_names[1]} ({len(t2_filtered)}/{len(t2_lineup_names)}), using full squad")

    for sname in squad_names:
        rows = filtered_squads.get(sname)
        if isinstance(rows, list) and rows:
            filtered_squads[sname] = ensure_rr_vaibhav_in_playing_xi_rows(
                rows, sname, match_squads.get(sname, [])
            )

    return filtered_squads


async def _invalidate_team_predictions(team1: str, team2: str) -> int:
    """Invalidate (delete) cached pre-match predictions for all upcoming matches
    involving either of the given teams. This ensures fresh form/XI data is used
    the next time a prediction is requested."""
    t1_lower = team1.lower()
    t2_lower = team2.lower()
    invalidated = 0

    # Find all upcoming matches for these teams
    async for match in db.ipl_schedule.find(
        {"status": {"$regex": "upcoming|ns|not started", "$options": "i"}},
        {"_id": 0, "matchId": 1, "team1": 1, "team2": 1}
    ):
        mt1 = (match.get("team1", "") or "").lower()
        mt2 = (match.get("team2", "") or "").lower()
        # Check if either team from the completed match is in this upcoming match
        if (t1_lower in mt1 or mt1 in t1_lower or
            t1_lower in mt2 or mt2 in t1_lower or
            t2_lower in mt1 or mt1 in t2_lower or
            t2_lower in mt2 or mt2 in t2_lower):
            mid = match.get("matchId")
            result = await db.pre_match_predictions.delete_one({"matchId": mid})
            if result.deleted_count > 0:
                invalidated += 1
                logger.info(f"Invalidated stale prediction for {mid} ({match.get('team1')} vs {match.get('team2')})")

    return invalidated



# ─── HEALTH & STATUS ─────────────────────────────────────────

@api_router.get("/")
async def root():
    schedule_count = await db.ipl_schedule.count_documents({})
    squad_count = await db.ipl_squads.count_documents({})
    now_ist = datetime.now(IST).strftime("%I:%M %p IST")
    return {
        "message": "Predictability API",
        "version": "4.1.0",
        "dataSource": "Claude Opus + Web Scraping",
        "scheduleLoaded": schedule_count > 0,
        "squadsLoaded": squad_count > 0,
        "matchesInDB": schedule_count,
        "squadsInDB": squad_count,
        "scheduler": {
            "active": _scheduler_started,
            "backgroundJobs": ENABLE_BACKGROUND_SCHEDULERS,
            "next_runs": ["4:00 PM IST", "7:00 PM IST"] if _scheduler_started else [],
        },
        "serverTime": now_ist,
    }


@api_router.get("/health")
async def health_alive():
    """Liveness: does not touch MongoDB (use after fixing startup crashes)."""
    return {"ok": True, "service": "predictability-api"}


@api_router.get("/health/db")
async def health_db():
    """MongoDB connectivity — if this fails, upcoming/completed/live schedule routes will fail too."""
    try:
        n = await db.ipl_schedule.count_documents({})
        return {"ok": True, "mongodb": "connected", "ipl_schedule_documents": n}
    except Exception as e:
        return {"ok": False, "mongodb": "error", "error": str(e)[:500]}


def _eval_winner_label(schedule_doc: dict) -> str:
    w = (schedule_doc.get("winner") or "").lower().strip()
    t1 = (schedule_doc.get("team1") or "").lower().strip()
    t2 = (schedule_doc.get("team2") or "").lower().strip()
    if not w:
        return ""
    if t1 and (t1 in w or w in t1):
        return "team1"
    if t2 and (t2 in w or w in t2):
        return "team2"
    return ""


def _eval_clamp_prob(p: float) -> float:
    return min(1.0 - 1e-8, max(1e-8, float(p)))


def _eval_logloss(p: float, y: int) -> float:
    p = _eval_clamp_prob(p)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def _eval_ece(rows: List[tuple], bins: int = 10) -> tuple[float, List[dict]]:
    bucket = defaultdict(list)
    for p, y in rows:
        idx = min(bins - 1, int(p * bins))
        bucket[idx].append((p, y))
    total = len(rows) or 1
    ece = 0.0
    details = []
    for i in range(bins):
        pts = bucket.get(i, [])
        if not pts:
            continue
        conf = sum(p for p, _ in pts) / len(pts)
        acc = sum(y for _, y in pts) / len(pts)
        w = len(pts) / total
        gap = abs(acc - conf)
        ece += w * gap
        details.append(
            {
                "bin": i,
                "count": len(pts),
                "avg_confidence": round(conf, 4),
                "empirical_accuracy": round(acc, 4),
                "gap": round(gap, 4),
            }
        )
    return ece, details


def _eval_metrics(rows: List[tuple]) -> Optional[dict]:
    if not rows:
        return None
    n = len(rows)
    brier = sum((p - y) ** 2 for p, y in rows) / n
    logloss = sum(_eval_logloss(p, y) for p, y in rows) / n
    ece, bins = _eval_ece(rows, bins=10)
    return {
        "sample_size": n,
        "brier": round(brier, 6),
        "logloss": round(logloss, 6),
        "ece_10bin": round(ece, 6),
        "calibration_bins": bins,
    }


def _eval_track_prob(track: str, pre_doc: Optional[dict], live_doc: Optional[dict]) -> Optional[float]:
    if track == "algo_only":
        p = ((pre_doc or {}).get("prediction") or {}).get("team1_win_prob")
    elif track == "claude_only":
        cp = (live_doc or {}).get("claudePrediction") or (live_doc or {}).get("claude_prediction") or {}
        p = cp.get("team1_win_pct")
    elif track == "hybrid":
        hp = (live_doc or {}).get("combinedPrediction") or (live_doc or {}).get("combined_prediction") or {}
        p = hp.get("team1_pct")
    else:
        return None
    if p is None:
        return None
    try:
        return _eval_clamp_prob(float(p) / 100.0)
    except (TypeError, ValueError):
        return None


def _eval_gate(metrics: dict, min_samples: int = 10, ece_threshold: float = 0.08) -> dict:
    reasons = []
    passed = True
    algo = metrics.get("algo_only")
    claude = metrics.get("claude_only")
    hybrid = metrics.get("hybrid")

    if not hybrid or hybrid["sample_size"] < min_samples:
        passed = False
        reasons.append(
            f"hybrid sample size too low ({0 if not hybrid else hybrid['sample_size']}, min {min_samples})"
        )
    if algo and hybrid:
        if hybrid["brier"] > algo["brier"]:
            passed = False
            reasons.append(f"hybrid brier {hybrid['brier']} > algo {algo['brier']}")
        if hybrid["logloss"] > algo["logloss"]:
            passed = False
            reasons.append(f"hybrid logloss {hybrid['logloss']} > algo {algo['logloss']}")
    if claude and hybrid:
        if hybrid["brier"] > claude["brier"]:
            passed = False
            reasons.append(f"hybrid brier {hybrid['brier']} > claude {claude['brier']}")
        if hybrid["logloss"] > claude["logloss"]:
            passed = False
            reasons.append(f"hybrid logloss {hybrid['logloss']} > claude {claude['logloss']}")
    if hybrid and hybrid["ece_10bin"] > ece_threshold:
        passed = False
        reasons.append(f"hybrid ece {hybrid['ece_10bin']} exceeds threshold {ece_threshold}")
    return {
        "passed": passed,
        "reasons": reasons,
        "min_samples": min_samples,
        "ece_threshold": ece_threshold,
    }


@api_router.get("/model-evaluation")
async def get_model_evaluation(min_samples: int = 10, ece_threshold: float = 0.08):
    schedule_docs = await db.ipl_schedule.find(
        {"status": {"$in": ["completed", "Completed"]}},
        {"_id": 0, "matchId": 1, "winner": 1, "team1": 1, "team2": 1},
    ).to_list(2000)
    schedule = {d["matchId"]: d for d in schedule_docs if d.get("matchId")}
    pre_docs = await db.pre_match_predictions.find({}, {"_id": 0}).to_list(4000)
    live_docs = await db.live_snapshots.find({}, {"_id": 0}).to_list(4000)
    pre_by_mid = {d["matchId"]: d for d in pre_docs if d.get("matchId")}
    live_by_mid = {d["matchId"]: d for d in live_docs if d.get("matchId")}

    rows_by_track = {"algo_only": [], "claude_only": [], "hybrid": []}
    for mid, sched_doc in schedule.items():
        wlab = _eval_winner_label(sched_doc)
        if not wlab:
            continue
        y = 1 if wlab == "team1" else 0
        pre_doc = pre_by_mid.get(mid)
        live_doc = live_by_mid.get(mid)
        for track in rows_by_track:
            p = _eval_track_prob(track, pre_doc, live_doc)
            if p is not None:
                rows_by_track[track].append((p, y))

    metrics = {k: _eval_metrics(v) for k, v in rows_by_track.items()}
    gate = _eval_gate(metrics, min_samples=min_samples, ece_threshold=ece_threshold)
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "tracks": metrics,
        "gate": gate,
    }


@api_router.post("/scheduler/promote-now")
async def manual_promote():
    """Manually trigger match promotion to LIVE (same as scheduled 4PM/7PM)."""
    await promote_matches_to_live()
    await sync_live_scores_to_schedule()
    live_count = await db.ipl_schedule.count_documents({"status": "live"})
    return {"status": "done", "live_matches": live_count}


async def sync_live_scores_to_schedule():
    """Sync any existing live snapshot scores to the schedule collection for match cards."""
    try:
        snapshots = await db.live_snapshots.find({}, {"_id": 0, "matchId": 1, "liveData": 1, "team1Short": 1}).to_list(100)
    except Exception as e:
        # Do not fail application startup if MongoDB is unreachable (SSL/network/Atlas allowlist).
        logger.warning(
            "sync_live_scores_to_schedule: could not read live_snapshots (%s). "
            "Fix MONGO_URL / network / Atlas IP access if schedule endpoints stay empty.",
            e,
        )
        return
    for snap in snapshots:
        mid = snap.get("matchId")
        ld = snap.get("liveData", {})
        score = ld.get("score", {})
        if not mid or not isinstance(score, dict) or score.get("runs") is None:
            continue
        t1_short = snap.get("team1Short", "")
        runs = score.get("runs", 0)
        wickets = score.get("wickets", 0)
        overs = score.get("overs", 0)
        target = score.get("target")
        innings = ld.get("innings", 1)
        score_text = f"{t1_short} {runs}/{wickets} ({overs} ov)"
        if target:
            score_text += f" | Target: {target}"
        try:
            await db.ipl_schedule.update_one(
                {"matchId": mid},
                {"$set": {
                    "score": score_text,
                    "liveScore": {"runs": runs, "wickets": wickets, "overs": overs, "target": target, "innings": innings},
                }}
            )
        except Exception as e:
            logger.warning("sync_live_scores_to_schedule: update failed for %s: %s", mid, e)


# ─── IPL SCHEDULE (AI-powered + cached in MongoDB) ──────────

@api_router.get("/schedule/load")
async def load_ipl_schedule(force: bool = False):
    """Load IPL 2026 schedule from SportMonks API and store in MongoDB.
    Merges with existing DB matches to preserve predictions and cached analysis."""
    existing = await db.ipl_schedule.count_documents({})
    if existing > 0 and not force:
        return {
            "status": "already_loaded",
            "count": existing,
            "message": "Schedule is cached in the database. Pass ?force=true to re-fetch fixtures from SportMonks.",
        }

    logger.info("Fetching IPL 2026 schedule from SportMonks API...")
    matches = await fetch_ipl_season_schedule()

    if not matches:
        # Fallback to seed data if SportMonks API fails
        logger.warning("SportMonks returned 0 fixtures, falling back to seed data")
        docs = get_schedule_documents()
        if not docs:
            return {"status": "error", "message": "No schedule data available from SportMonks or seed"}
        # Merge seed data
        existing_map = {}
        async for m in db.ipl_schedule.find({}, {"_id": 0}):
            existing_map[m.get("matchId")] = m
        inserted = 0
        for doc in docs:
            if doc["matchId"] not in existing_map:
                doc["loadedAt"] = datetime.now(timezone.utc).isoformat()
                await db.ipl_schedule.insert_one(doc)
                inserted += 1
        total = await db.ipl_schedule.count_documents({})
        return {"status": "loaded", "count": total, "source": "seed_fallback", "inserted": inserted}

    # Build map of existing DB matches to preserve predictions/cached data
    existing_map = {}
    async for m in db.ipl_schedule.find({}, {"_id": 0}):
        existing_map[m.get("matchId")] = m

    inserted = 0
    updated = 0
    preserved = 0

    for match in matches:
        mid = match["matchId"]
        match["loadedAt"] = datetime.now(timezone.utc).isoformat()

        if mid in existing_map:
            old = existing_map[mid]
            # Update with fresh SportMonks data but preserve predictions and analysis keys
            update_fields = {
                "team1": match["team1"],
                "team2": match["team2"],
                "team1Short": match["team1Short"],
                "team2Short": match["team2Short"],
                "team1_id": match.get("team1_id"),
                "team2_id": match.get("team2_id"),
                "venue": match["venue"],
                "city": match["city"],
                "dateTimeGMT": match["dateTimeGMT"],
                "fixture_id": match.get("fixture_id"),
                "source": "sportmonks",
                "loadedAt": match["loadedAt"],
            }
            # Update status/winner/scores only if SportMonks says completed (don't overwrite live state)
            if match.get("winner") and match["status"] == "Completed":
                update_fields["winner"] = match["winner"]
                update_fields["status"] = "Completed"
                update_fields["note"] = match.get("note", "")
                update_fields["score"] = match.get("score", "")
                update_fields["team1_score"] = match.get("team1_score", "")
                update_fields["team2_score"] = match.get("team2_score", "")
                update_fields["toss_won_by"] = match.get("toss_won_by", "")
            elif old.get("status", "").lower() not in ("completed", "live"):
                update_fields["status"] = match["status"]

            await db.ipl_schedule.update_one({"matchId": mid}, {"$set": update_fields})
            updated += 1
        else:
            await db.ipl_schedule.insert_one(match)
            inserted += 1

    total = await db.ipl_schedule.count_documents({})
    logger.info(f"SportMonks schedule: {inserted} inserted, {updated} updated, {total} total")
    return {
        "status": "loaded",
        "count": total,
        "source": "sportmonks",
        "inserted": inserted,
        "updated": updated,
    }


@api_router.post("/schedule/resolve-venues")
async def api_resolve_venues():
    """Resolve TBD venues in the schedule using GPT web search."""
    matches = await db.ipl_schedule.find({}, {"_id": 0}).sort("match_number", 1).to_list(100)
    tbd = [m for m in matches if not m.get("venue") or m.get("venue") == "TBD"]
    if not tbd:
        return {"status": "no_tbd", "message": "All matches already have venues"}
    
    resolved_matches = await resolve_tbd_venues(matches)
    
    updated = 0
    for m in resolved_matches:
        if m.get("venue") and m["venue"] != "TBD":
            result = await db.ipl_schedule.update_one(
                {"matchId": m["matchId"]},
                {"$set": {"venue": m["venue"]}}
            )
            if result.modified_count > 0:
                updated += 1
    
    return {"status": "resolved", "total_tbd": len(tbd), "updated": updated}


@api_router.post("/schedule/seed-official")
async def seed_official_schedule(force: bool = False):
    """Seed the official TATA IPL 2026 schedule from the PDF data.
    This replaces AI-generated schedule with accurate official data."""
    existing = await db.ipl_schedule.count_documents({})
    if existing > 0 and not force:
        return {"status": "already_loaded", "count": existing, "message": "Use ?force=true to replace existing schedule"}

    docs = get_schedule_documents()
    if not docs:
        return {"status": "error", "message": "No schedule data available"}

    await db.ipl_schedule.delete_many({})
    for doc in docs:
        doc["loadedAt"] = datetime.now(timezone.utc).isoformat()
    await db.ipl_schedule.insert_many(docs)
    # Remove _id from response docs
    for doc in docs:
        doc.pop("_id", None)

    return {"status": "loaded", "count": len(docs), "source": "official_pdf"}


@api_router.post("/schedule/sync-results")
async def sync_results_from_sportmonks():
    """Fetch actual match results from SportMonks and update DB schedule with winners.
    Only updates matches whose date has already passed (prevents future match contamination)."""
    results = await fetch_recent_fixtures()
    if not results:
        return {"status": "no_results", "message": "No completed fixtures found from SportMonks"}

    now = datetime.now(timezone.utc)
    updated = 0
    for result in results:
        sm_t1 = (result.get("team1", "") or "").lower()
        sm_t2 = (result.get("team2", "") or "").lower()
        winner = result.get("winner", "")

        if not winner:
            continue

        # Find matching schedule entry by fuzzy team name matching
        async for match in db.ipl_schedule.find({}, {"_id": 0}):
            db_t1 = (match.get("team1", "") or "").lower()
            db_t2 = (match.get("team2", "") or "").lower()

            # GUARD: Only update matches whose date has passed
            dt_str = match.get("dateTimeGMT", "")
            if dt_str:
                try:
                    match_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    if match_dt.tzinfo is None:
                        match_dt = match_dt.replace(tzinfo=timezone.utc)
                    if match_dt > now:
                        continue  # Skip future matches — they haven't been played yet
                except (ValueError, TypeError):
                    pass

            # Check if both teams match (order-independent)
            t1_words = [w for w in sm_t1.split() if len(w) > 3]
            t2_words = [w for w in sm_t2.split() if len(w) > 3]
            db_t1_match = any(w in db_t1 for w in t1_words) or any(w in sm_t1 for w in db_t1.split() if len(w) > 3)
            db_t2_match = any(w in db_t2 for w in t2_words) or any(w in sm_t2 for w in db_t2.split() if len(w) > 3)

            fwd = db_t1_match and db_t2_match
            rev_t1_match = any(w in db_t1 for w in t2_words) or any(w in sm_t2 for w in db_t1.split() if len(w) > 3)
            rev_t2_match = any(w in db_t2 for w in t1_words) or any(w in sm_t1 for w in db_t2.split() if len(w) > 3)
            rev = rev_t1_match and rev_t2_match

            if fwd or rev:
                # Map SportMonks winner name to our DB team name
                db_winner = None
                winner_lower = winner.lower()
                for team_field in ["team1", "team2"]:
                    db_team = (match.get(team_field, "") or "").lower()
                    if any(w in db_team for w in winner_lower.split() if len(w) > 3) or \
                       any(w in winner_lower for w in db_team.split() if len(w) > 3):
                        db_winner = match.get(team_field)
                        break

                if db_winner and not match.get("winner"):
                    await db.ipl_schedule.update_one(
                        {"matchId": match.get("matchId")},
                        {"$set": {
                            "winner": db_winner,
                            "status": "completed",
                            "result": result.get("note", ""),
                            "team1_score": result.get("team1_score", ""),
                            "team2_score": result.get("team2_score", ""),
                            "toss_won_by": result.get("toss_won_by", ""),
                        }}
                    )
                    updated += 1
                    logger.info(f"Synced result: {match.get('matchId')} -> winner: {db_winner}")

                    # ── Invalidate stale pre-match predictions ──
                    invalidated = await _invalidate_team_predictions(
                        match.get("team1", ""), match.get("team2", "")
                    )
                    if invalidated > 0:
                        logger.info(f"Invalidated {invalidated} stale predictions after result update")
                break

    # Clear season fixtures cache so next prediction fetches fresh data
    from services.sportmonks_service import _season_fixtures_cache
    _season_fixtures_cache.clear()
    logger.info("Cleared SportMonks season fixtures cache after sync")

    return {"status": "synced", "updated": updated, "total_fixtures": len(results)}


@api_router.post("/sync-player-stats")
async def api_sync_player_stats(background_tasks: BackgroundTasks):
    """Sync player performance stats from last 3 IPL seasons (2024-2026) into MongoDB.
    Runs in background to avoid blocking."""
    async def _sync():
        try:
            result = await sync_player_performance_to_db(db)
            logger.info(f"Player stats sync complete: {result}")
        except Exception as e:
            logger.error(f"Player stats sync failed: {e}")
    background_tasks.add_task(_sync)
    return {"status": "sync_started", "message": "Player performance sync started in background"}




# ─── WEATHER API ─────────────────────────────────────────────

@api_router.get("/weather/{city}")
async def get_weather(city: str, match_date: str = None):
    """Fetch current weather and forecast for a city using Open-Meteo (free, no API key)."""
    weather = await fetch_weather_for_venue(city, match_date)
    return weather


@api_router.get("/matches/{match_id}/weather")
async def get_match_weather(match_id: str):
    """Fetch weather for a specific match venue on the match date."""
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    city = match_info.get("city", "")
    venue = match_info.get("venue", "")
    # Extract city from venue string if city field is empty
    if not city and venue:
        city = venue.split(",")[-1].strip() if "," in venue else venue

    match_date = None
    dt_gmt = match_info.get("dateTimeGMT", "")
    if dt_gmt:
        match_date = str(dt_gmt)[:10]  # YYYY-MM-DD

    weather = await fetch_weather_for_venue(city, match_date)
    weather["matchId"] = match_id
    weather["venue"] = venue
    weather["team1"] = match_info.get("team1", "")
    weather["team2"] = match_info.get("team2", "")
    return weather


# ─── NEWS API (DuckDuckGo News Search, Free) ─────────────────

@api_router.get("/matches/{match_id}/news")
async def get_match_news(match_id: str):
    """Fetch latest news articles for a match using DuckDuckGo news search (free, no API key)."""
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found", "articles": []}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    articles = await fetch_match_news(team1, team2)

    return {
        "matchId": match_id,
        "team1": team1,
        "team2": team2,
        "articles": articles,
        "count": len(articles),
    }

def _parse_schedule_match_datetime(m: dict) -> Optional[datetime]:
    """Parse scheduled start time for classification (UTC)."""
    raw = m.get("dateTimeGMT") or m.get("date") or m.get("starting_at")
    if not raw:
        return None
    try:
        if isinstance(raw, datetime):
            dt = raw
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        s = str(raw).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        if "T" not in s and len(s) >= 10:
            s = s[:10] + "T00:00:00+00:00"
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _schedule_status_completed(sl: str) -> bool:
    s = (sl or "").lower()
    if s in ("completed", "finished", "abandoned", "cancelled", "tie", "no result"):
        return True
    if "abandon" in s or "no result" in s:
        return True
    return False


def _schedule_status_live(sl: str) -> bool:
    s = (sl or "").lower()
    return s in (
        "live",
        "in progress",
        "1st innings",
        "2nd innings",
        "innings break",
        "int.",
    )


@api_router.get("/schedule")
async def get_schedule():
    """Get the full IPL 2026 schedule from MongoDB."""
    matches = await db.ipl_schedule.find({}, {"_id": 0}).sort("match_number", 1).to_list(100)
    if not matches:
        return {"matches": [], "loaded": False}

    now = datetime.now(timezone.utc)
    live = []
    upcoming = []
    completed = []
    for m in matches:
        status_lower = m.get("status", "").lower()
        has_winner = bool(m.get("winner"))
        dt = _parse_schedule_match_datetime(m)

        if has_winner or _schedule_status_completed(status_lower):
            completed.append(m)
        elif _schedule_status_live(status_lower):
            live.append(m)
        elif dt is not None:
            if dt > now:
                upcoming.append(m)
            else:
                completed.append(m)
        else:
            upcoming.append(m)

    def _seq_key(x: dict):
        d = _parse_schedule_match_datetime(x)
        dkey = d.timestamp() if d else float("inf")
        mn = x.get("match_number")
        try:
            mnum = int(mn) if mn is not None else 10**9
        except (TypeError, ValueError):
            mnum = 10**9
        return (dkey, mnum, x.get("matchId", ""))

    upcoming.sort(key=_seq_key)
    live.sort(key=_seq_key)
    completed.sort(key=lambda x: (_parse_schedule_match_datetime(x) or datetime.min.replace(tzinfo=timezone.utc)).timestamp(), reverse=True)

    return {
        "matches": matches,
        "loaded": True,
        "live": live,
        "upcoming": upcoming,
        "completed": completed,
        "total": len(matches)
    }


# ─── SQUADS (AI-powered + cached) ───────────────────────────

@api_router.get("/squads/load")
async def load_squads(force: bool = False):
    """Load all IPL 2026 squads using GPT."""
    existing = await db.ipl_squads.count_documents({})
    if existing > 0 and not force:
        return {"status": "already_loaded", "count": existing}
    logger.info("Fetching IPL 2026 squads via GPT...")
    squads = await fetch_ipl_squads()
    if squads:
        await db.ipl_squads.delete_many({})
        for s in squads:
            s["loadedAt"] = datetime.now(timezone.utc).isoformat()
        await db.ipl_squads.insert_many(squads)
        return {"status": "loaded", "count": len(squads)}
    return {"status": "error", "count": 0}

@api_router.get("/squads")
async def get_all_squads():
    squads = await db.ipl_squads.find({}, {"_id": 0}).to_list(20)
    return {"squads": squads}

@api_router.get("/squads/{team_short}")
async def get_team_squad(team_short: str):
    squad = await db.ipl_squads.find_one(
        {"teamShort": team_short.upper()}, {"_id": 0}
    )
    if not squad:
        squad = await db.ipl_squads.find_one(
            {"teamShort": {"$regex": team_short, "$options": "i"}}, {"_id": 0}
        )
    return {"squad": squad}


class FetchLiveRequest(BaseModel):
    betting_team1_pct: Optional[float] = None   # 0-100 probability %
    betting_team2_pct: Optional[float] = None   # 0-100 probability %
    betting_confidence: Optional[float] = None  # 0-100
    gut_feeling: Optional[str] = None           # User's gut feeling text
    current_betting_odds: Optional[float] = None  # 0-100, team1 implied probability from market
    dls_info: Optional[str] = None               # DLS/overs reduced context from user

class BetaPredictRequest(BaseModel):
    market_team1_pct: Optional[float] = None    # 0-100 probability %
    market_team2_pct: Optional[float] = None    # 0-100 probability %

class ConsultRequest(BaseModel):
    market_pct_team1: Optional[float] = None   # 0-100 probability %
    market_pct_team2: Optional[float] = None   # 0-100 probability %
    risk_tolerance: Optional[str] = "balanced"  # "safe", "balanced", "aggressive"
    odds_trend_increasing: Optional[str] = None  # team name whose odds are rising
    odds_trend_decreasing: Optional[str] = None  # team name whose odds are falling

class ChatRequest(BaseModel):
    question: str
    risk_tolerance: Optional[str] = "balanced"
    market_pct_team1: Optional[float] = None   # 0-100 probability %
    market_pct_team2: Optional[float] = None   # 0-100 probability %

# ─── LIVE MATCH (on-demand via button) ───────────────────────
# Live prediction now handled by services/live_predictor.py (6-factor model)



@api_router.post("/matches/{match_id}/fetch-live")
async def fetch_live_data(match_id: str, body: FetchLiveRequest = None):
    """Fetch live scores from SportMonks (or CricAPI fallback), ensemble probabilities, and decay (α×H+L) model.
    Does not call Claude Opus — use Check Status or Refresh Predictions after scores are loaded."""
    if body is None:
        body = FetchLiveRequest()

    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found in schedule"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")
    t1_short = get_short_name(team1)
    t2_short = get_short_name(team2)

    logger.info(f"Fetching live data for {team1} vs {team2}")

    # ── Step 1: Try SportMonks API (rich data: batting, bowling, lineup) ──
    sm_data = await fetch_live_match(team1, team2)
    source = "sportmonks"

    if sm_data:
        logger.info(f"SportMonks: {sm_data['batting_team']} batting, {sm_data['status']}")
        current_score = sm_data.get("current_score", {})
        runs = current_score.get("runs", 0)
        wickets = current_score.get("wickets", 0)
        overs = current_score.get("overs", 0)
        target = sm_data.get("target")
        innings = sm_data.get("current_innings", 1)

        # Build the live_data in our standard format from SportMonks
        live_data = {
            "matchId": match_id,
            "team1": team1, "team2": team2,
            "venue": sm_data.get("venue", venue),
            "isLive": True,
            "noLiveMatch": False,
            "innings": innings,
            "battingTeam": sm_data.get("batting_team", team1),
            "bowlingTeam": sm_data.get("bowling_team", team2),
            "score": {"runs": runs, "wickets": wickets, "overs": overs, "target": target},
            "currentRunRate": sm_data.get("crr", 0),
            "requiredRunRate": sm_data.get("rrr"),
            "status": sm_data.get("status", "Live"),
            "note": sm_data.get("note", ""),
            "source": "sportmonks",
        }
    else:
        # ── Step 2: Fallback to CricketData.org ──
        logger.info("SportMonks has no data, trying CricAPI fallback")
        source = "cricketdata.org"
        cricapi_result = await fetch_live_ipl_details()
        live_data = None

        if cricapi_result.get("matches"):
            for m in cricapi_result["matches"]:
                m_t1 = (m.get("team1", "") or "").lower()
                m_t2 = (m.get("team2", "") or "").lower()
                t1_lower = team1.lower()
                t2_lower = team2.lower()
                if (t1_lower in m_t1 or m_t1 in t1_lower) or (t2_lower in m_t2 or m_t2 in t2_lower):
                    cs = m.get("current_score", {})
                    live_data = {
                        "matchId": match_id, "team1": team1, "team2": team2,
                        "venue": venue, "isLive": True, "noLiveMatch": False,
                        "innings": m.get("current_innings", 1),
                        "battingTeam": team1, "bowlingTeam": team2,
                        "score": {"runs": cs.get("runs", 0), "wickets": cs.get("wickets", 0),
                                  "overs": cs.get("overs", 0), "target": m.get("target")},
                        "status": m.get("status", "Live"),
                        "source": "cricketdata.org",
                    }
                    break

        if not live_data:
            return {
                "matchId": match_id, "team1": team1, "team1Short": t1_short,
                "team2": team2, "team2Short": t2_short, "venue": venue,
                "noLiveMatch": True, "isLive": False,
                "status": "No live data available. Match may not be in progress.",
                "liveData": {}, "source": "none",
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
            }

        runs = live_data["score"]["runs"]
        wickets = live_data["score"]["wickets"]
        overs = live_data["score"]["overs"]
        target = live_data["score"].get("target")
        innings = live_data.get("innings", 1)

    # Parse score for algorithms
    recent_balls = sm_data.get("recent_balls", []) if sm_data else []
    ball_objects = []
    for b in recent_balls:
        ball_obj = {"runs": 0, "isWicket": False, "isWide": False, "isNoBall": False}
        if b == "W":
            ball_obj["isWicket"] = True
        elif b == "WD":
            ball_obj["isWide"] = True; ball_obj["runs"] = 1
        elif b == "NB":
            ball_obj["isNoBall"] = True; ball_obj["runs"] = 1
        elif b in ["0", "\u2022"]:
            ball_obj["runs"] = 0
        else:
            try:
                ball_obj["runs"] = int(b)
            except (ValueError, TypeError):
                ball_obj["runs"] = 0
        ball_objects.append(ball_obj)

    # Betting odds input
    odds_team_a = None
    if body.betting_team1_pct and body.betting_team2_pct:
        t1_prob = max(0.01, body.betting_team1_pct / 100)
        t2_prob = max(0.01, body.betting_team2_pct / 100)
        total_implied = t1_prob + t2_prob
        odds_team_a = t1_prob / total_implied
    betting_t1_decimal = round(1 / max(0.01, body.betting_team1_pct / 100), 2) if body.betting_team1_pct else None
    betting_t2_decimal = round(1 / max(0.01, body.betting_team2_pct / 100), 2) if body.betting_team2_pct else None

    # Run all 4 algorithms + ensemble
    probs = ensemble_probability(runs, wickets, overs, target, innings,
                                  odds_team_a, ball_objects, venue_avg=165)
    team1_odds = calculate_odds_from_probability(probs["ensemble"])
    team2_odds = calculate_odds_from_probability(1 - probs["ensemble"])

    edge_team1 = calculate_betting_edge(probs["ensemble"], betting_t1_decimal) if betting_t1_decimal else None
    edge_team2 = calculate_betting_edge(1 - probs["ensemble"], betting_t2_decimal) if betting_t2_decimal else None

    # ── Fetch squads for Claude context ──
    match_squads = await _get_squads_for_match(team1, team2)

    # ── Filter squads to Playing XI using SportMonks lineup data ──
    live_squads = match_squads  # Default: full squad
    if sm_data:
        live_squads = _filter_squads_to_playing_xi(match_squads, sm_data, team1, team2)

    # ── Fetch weather for venue ──
    match_city = match_info.get("city", "")
    if not match_city and venue:
        match_city = venue.split(",")[-1].strip() if "," in venue else venue
    match_weather = await fetch_weather_for_venue(match_city) if match_city else None

    # ── Fetch news for match context ──
    match_news = await fetch_match_news(team1, team2)

    # ── DATA ENRICHMENT: Gather real stats for Claude's layered analysis ──
    import asyncio as _aio
    enrichment_data = {}
    try:
        # Parallel fetch: venue stats, H2H, standings, player stats for both teams
        venue_stats_task = fetch_venue_stats(venue)
        h2h_task = fetch_h2h_record(team1, team2)
        standings_task = fetch_team_standings(2026)

        # Fetch player season stats for Playing XI of each team
        t1_xi_for_stats = sm_data.get("team1_playing_xi", []) if sm_data else []
        t2_xi_for_stats = sm_data.get("team2_playing_xi", []) if sm_data else []

        async def _noop_list(lst):
            return lst

        t1_stats_task = fetch_player_season_stats_for_xi(t1_xi_for_stats, team1, 5) if t1_xi_for_stats else _noop_list(t1_xi_for_stats)
        t2_stats_task = fetch_player_season_stats_for_xi(t2_xi_for_stats, team2, 5) if t2_xi_for_stats else _noop_list(t2_xi_for_stats)

        venue_stats, h2h_record, standings, t1_enriched_xi, t2_enriched_xi = await _aio.gather(
            venue_stats_task, h2h_task, standings_task, t1_stats_task, t2_stats_task,
            return_exceptions=True
        )

        # Handle exceptions gracefully
        if isinstance(venue_stats, Exception):
            logger.warning(f"Venue stats fetch failed: {venue_stats}")
            venue_stats = {}
        if isinstance(h2h_record, Exception):
            logger.warning(f"H2H fetch failed: {h2h_record}")
            h2h_record = {}
        if isinstance(standings, Exception):
            logger.warning(f"Standings fetch failed: {standings}")
            standings = []
        if isinstance(t1_enriched_xi, Exception):
            logger.warning(f"T1 stats fetch failed: {t1_enriched_xi}")
            t1_enriched_xi = t1_xi_for_stats
        if isinstance(t2_enriched_xi, Exception):
            logger.warning(f"T2 stats fetch failed: {t2_enriched_xi}")
            t2_enriched_xi = t2_xi_for_stats

        enrichment_data = {
            "venue_stats": venue_stats,
            "h2h": h2h_record,
            "standings": standings,
            "team1_enriched_xi": t1_enriched_xi,
            "team2_enriched_xi": t2_enriched_xi,
        }
        logger.info(f"Enrichment data gathered: venue={bool(venue_stats)}, h2h={bool(h2h_record)}, "
                     f"standings={len(standings) if isinstance(standings, list) else 0}, "
                     f"t1_stats={len(t1_enriched_xi) if isinstance(t1_enriched_xi, list) else 0}, "
                     f"t2_stats={len(t2_enriched_xi) if isinstance(t2_enriched_xi, list) else 0}")
    except Exception as e:
        logger.error(f"Enrichment data fetch failed: {e}")
        enrichment_data = {}

    # ── Decay combined model (α × H + L) without Claude — Opus runs via Check Status / Refresh Predictions ──
    claude_prediction = None
    probs["source"] = "ensemble"

    pre_match_cached = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
    historical_pred = pre_match_cached.get("prediction", {}) if pre_match_cached else {}
    pre_match_prob = historical_pred.get("team1_win_prob") if historical_pred else None
    cached_xi = pre_match_cached.get("playing_xi") if pre_match_cached else None
    weighted_pred = compute_live_prediction(
        sm_data, None, match_info,
        pre_match_prob=pre_match_prob, xi_data=cached_xi, enrichment=enrichment_data,
    ) if sm_data else None
    combined_pred = None

    result = {
        "matchId": match_id,
        "team1": team1, "team1Short": t1_short,
        "team2": team2, "team2Short": t2_short,
        "venue": venue,
        "liveData": live_data,
        "sportmonks": sm_data,  # Full rich data from SportMonks
        "probabilities": probs,
        "odds": {"team1": team1_odds, "team2": team2_odds},
        "bettingEdge": {"team1": edge_team1, "team2": edge_team2},
        "bettingInput": {
            "team1Pct": body.betting_team1_pct,
            "team2Pct": body.betting_team2_pct,
            "confidence": body.betting_confidence,
        },
        "userInputs": {
            "gut_feeling": body.gut_feeling,
            "current_betting_odds": body.current_betting_odds,
        },
        "claudePrediction": claude_prediction,
        "weightedPrediction": weighted_pred,
        "combinedPrediction": combined_pred,
        "historicalPrediction": historical_pred,
        "preMatchComputedAt": pre_match_cached.get("computed_at") if pre_match_cached else None,
        "momentum": calculate_momentum(ball_objects),
        "ballHistory": ball_objects,
        "batsmen": [
            {**b, "strikeRate": b.get("strike_rate", 0)} for b in sm_data.get("active_batsmen", [])
        ] if sm_data else live_data.get("batsmen", []),
        "bowler": sm_data.get("active_bowler", {}) if sm_data else live_data.get("bowler", {}),
        "yetToBat": sm_data.get("yet_to_bat", []) if sm_data else [],
        "yetToBowl": sm_data.get("yet_to_bowl", []) if sm_data else [],
        "fullBattingCard": sm_data.get(f"batsmen_inn{sm_data.get('current_innings', 1)}", []) if sm_data else [],
        "fullBowlingCard": sm_data.get(f"bowlers_inn{sm_data.get('current_innings', 1)}", []) if sm_data else [],
        "fallOfWickets": live_data.get("fallOfWickets", []),
        "lastBallCommentary": live_data.get("note", "") or live_data.get("status", ""),
        "weather": match_weather,
        "source": source,
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
    }

    # Compute live prediction considering current players on field
    live_pred = _compute_live_prediction(result, match_info)
    result["live_prediction"] = live_pred

    live_match_state[match_id] = result
    # Store sportmonks data in DB-safe format (convert any integer keys to strings)
    def make_db_safe(obj):
        if isinstance(obj, dict):
            return {str(k): make_db_safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [make_db_safe(i) for i in obj]
        return obj
    db_result = make_db_safe(result)
    await db.live_snapshots.update_one(
        {"matchId": match_id},
        {"$set": {**db_result, "updatedAt": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )

    # Update match card score on schedule so it shows on the matches list
    score_text = f"{get_short_name(team1)} {runs}/{wickets} ({overs} ov)"
    if target:
        score_text += f" | Target: {target}"
    schedule_update = {
        "score": score_text,
        "status": "live",
        "liveScore": {"runs": runs, "wickets": wickets, "overs": overs, "target": target, "innings": innings},
        "lastFetchedAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.ipl_schedule.update_one({"matchId": match_id}, {"$set": schedule_update})

    if match_id in ws_connections and ws_connections[match_id]:
        await broadcast_update(match_id, result)

    return result


class RefreshClaudeRequest(BaseModel):
    dls_info: Optional[str] = None
    gut_feeling: Optional[str] = None
    current_betting_odds: Optional[float] = None

@api_router.post("/matches/{match_id}/refresh-claude-prediction")
async def refresh_claude_prediction(match_id: str, body: RefreshClaudeRequest = RefreshClaudeRequest()):
    """Re-run Claude prediction using cached SportMonks data (no API refetch)."""
    cached = live_match_state.get(match_id)
    if not cached:
        db_snap = await db.live_snapshots.find_one({"matchId": match_id}, {"_id": 0})
        if db_snap:
            cached = db_snap
    if not cached or not cached.get("sportmonks"):
        return {"error": "No cached live data. Click 'Fetch Live Scores' first."}

    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    sm_data = cached["sportmonks"]
    if not _sm_playing_xi_complete(sm_data):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "playing_xi_required",
                "message": (
                    "Playing XI for both teams is missing in the live snapshot. "
                    "Re-run “Fetch Live Scores” when SportMonks exposes full lineups."
                ),
            },
        )
    t1_short = cached.get("team1Short", "T1")
    t2_short = cached.get("team2Short", "T2")
    old_probs = cached.get("probabilities", {})

    match_squads = await _get_squads_for_match(
        match_info.get("team1", ""), match_info.get("team2", "")
    )

    # ── Filter squads to Playing XI using SportMonks lineup data ──
    live_squads = _filter_squads_to_playing_xi(match_squads, sm_data, match_info.get("team1", ""), match_info.get("team2", ""))

    # Fetch weather for Claude context
    refresh_city = match_info.get("city", "")
    if not refresh_city:
        v = match_info.get("venue", "")
        refresh_city = v.split(",")[-1].strip() if "," in v else v
    refresh_weather = await fetch_weather_for_venue(refresh_city) if refresh_city else None
    # Fetch news for Claude context
    refresh_news = await fetch_match_news(match_info.get("team1", ""), match_info.get("team2", ""))

    # ── DATA ENRICHMENT for refresh ──
    import asyncio as _aio
    enrichment_data = {}
    try:
        team1 = match_info.get("team1", "")
        team2 = match_info.get("team2", "")
        venue = match_info.get("venue", "")

        t1_xi = sm_data.get("team1_playing_xi", [])
        t2_xi = sm_data.get("team2_playing_xi", [])

        async def _noop_list(lst):
            return lst

        venue_stats_task = fetch_venue_stats(venue)
        h2h_task = fetch_h2h_record(team1, team2)
        standings_task = fetch_team_standings(2026)
        t1_stats_task = fetch_player_season_stats_for_xi(t1_xi, team1, 5) if t1_xi else _noop_list(t1_xi)
        t2_stats_task = fetch_player_season_stats_for_xi(t2_xi, team2, 5) if t2_xi else _noop_list(t2_xi)
        impact_t1_task = fetch_team_impact_sub_history(team1, 4)
        impact_t2_task = fetch_team_impact_sub_history(team2, 4)

        venue_stats, h2h_record, standings, t1_enriched, t2_enriched, imp1, imp2 = await _aio.gather(
            venue_stats_task, h2h_task, standings_task, t1_stats_task, t2_stats_task,
            impact_t1_task, impact_t2_task,
            return_exceptions=True
        )
        for name, val in [("venue_stats", venue_stats), ("h2h", h2h_record), ("standings", standings)]:
            if isinstance(val, Exception):
                logger.warning(f"Refresh enrichment {name} failed: {val}")
        if isinstance(imp1, Exception):
            logger.warning(f"Refresh enrichment impact_sub team1 failed: {imp1}")
        if isinstance(imp2, Exception):
            logger.warning(f"Refresh enrichment impact_sub team2 failed: {imp2}")
        enrichment_data = {
            "venue_stats": venue_stats if not isinstance(venue_stats, Exception) else {},
            "h2h": h2h_record if not isinstance(h2h_record, Exception) else {},
            "standings": standings if not isinstance(standings, Exception) else [],
            "team1_enriched_xi": t1_enriched if not isinstance(t1_enriched, Exception) else t1_xi,
            "team2_enriched_xi": t2_enriched if not isinstance(t2_enriched, Exception) else t2_xi,
            "impact_sub_history": {
                "team1": imp1 if not isinstance(imp1, Exception) else {},
                "team2": imp2 if not isinstance(imp2, Exception) else {},
            },
        }
    except Exception as e:
        logger.error(f"Refresh enrichment failed: {e}")

    user_inputs = cached.get("userInputs", {}) if isinstance(cached, dict) else {}
    claude_prediction = await claude_sportmonks_prediction(
        sm_data, old_probs, match_info, squads=live_squads, weather=refresh_weather, news=refresh_news,
        dls_info=body.dls_info,
        gut_feeling=body.gut_feeling if body.gut_feeling is not None else user_inputs.get("gut_feeling"),
        betting_odds_pct=body.current_betting_odds if body.current_betting_odds is not None else user_inputs.get("current_betting_odds"),
        enrichment=enrichment_data
    )

    if claude_prediction and not claude_prediction.get("error"):
        # Extract Claude's direct committed probability from Section 10
        s10 = claude_prediction.get("section_10_final_prediction", {})
        claude_direct_t1 = None
        if s10 and s10.get("team1_win_pct") is not None:
            try:
                claude_direct_t1 = float(s10["team1_win_pct"])
            except (TypeError, ValueError):
                claude_direct_t1 = None

        # Also extract contextual_adjustment_pct
        adjustment = claude_prediction.get("contextual_adjustment_pct", 0)
        try:
            adjustment = float(adjustment)
        except (TypeError, ValueError):
            adjustment = 0.0
        adjustment = max(-30, min(30, adjustment))

        algo_t1_pct = old_probs.get("ensemble", 0.5) * 100

        if claude_direct_t1 is not None:
            # Use Claude's committed Section 10 probability directly
            claude_t1 = max(1, min(99, claude_direct_t1))
            claude_t2 = 100 - claude_t1
            claude_prediction["source"] = "section_10_direct"
        else:
            # Fallback chain: team_short_win_pct → predicted_winner → algo+adjustment
            claude_t1 = claude_prediction.get(f"{t1_short}_win_pct")
            claude_t2 = claude_prediction.get(f"{t2_short}_win_pct")
            if claude_t1 is None:
                winner = claude_prediction.get("predicted_winner", "")
                win_pct = claude_prediction.get("win_pct", 50)
                if winner == t1_short:
                    claude_t1, claude_t2 = win_pct, 100 - win_pct
                elif winner == t2_short:
                    claude_t2, claude_t1 = win_pct, 100 - win_pct
                else:
                    claude_t1 = algo_t1_pct + adjustment
            claude_t1 = float(claude_t1 or 50)
            claude_t2 = float(claude_t2 or (100 - claude_t1))
            claude_t1 = max(1, min(99, claude_t1))
            claude_t2 = 100 - claude_t1
            claude_prediction["source"] = "legacy_fallback"

        prev_claude_t1 = None
        _prev_cp = cached.get("claudePrediction") if isinstance(cached, dict) else None
        if _prev_cp and not _prev_cp.get("error") and _prev_cp.get("team1_win_pct") is not None:
            try:
                prev_claude_t1 = float(_prev_cp["team1_win_pct"])
            except (TypeError, ValueError):
                prev_claude_t1 = None

        claude_t1, claude_stab = stabilize_team1_win_pct(
            claude_t1, prev_claude_t1, ema_alpha=0.42, min_lead_past_50_to_flip=3.25
        )
        claude_t2 = 100.0 - claude_t1
        claude_prediction["team1_win_pct"] = round(claude_t1, 1)
        claude_prediction["team2_win_pct"] = round(claude_t2, 1)
        claude_prediction["stabilization"] = claude_stab
        s10_sync = claude_prediction.get("section_10_final_prediction")
        if isinstance(s10_sync, dict):
            s10_sync["team1_win_pct"] = round(claude_t1, 1)
            s10_sync["team2_win_pct"] = round(claude_t2, 1)

        claude_prediction["algo_baseline_t1_pct"] = round(algo_t1_pct, 1)
        claude_prediction["adjustment_applied"] = round(adjustment, 1)

        # Update cached state
        new_probs = {**old_probs, "ensemble": round(claude_t1 / 100, 4), "source": "algo+claude"}
        cached["claudePrediction"] = claude_prediction
        cached["probabilities"] = new_probs
        live_match_state[match_id] = cached

        # Persist
        await db.live_snapshots.update_one(
            {"matchId": match_id},
            {"$set": {"claudePrediction": claude_prediction, "probabilities": new_probs,
                      "updatedAt": datetime.now(timezone.utc).isoformat()}}
        )

    # Recompute weighted prediction with new Claude factors (6-factor model)
    pre_match_cached = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
    pre_match_prob = pre_match_cached.get("prediction", {}).get("team1_win_prob") if pre_match_cached else None
    cached_xi = pre_match_cached.get("playing_xi") if pre_match_cached else None
    weighted_pred = compute_live_prediction(
        sm_data,
        claude_prediction,
        match_info,
        pre_match_prob=pre_match_prob,
        xi_data=cached_xi,
        enrichment=enrichment_data,
    ) if sm_data else None
    historical_pred = pre_match_cached.get("prediction", {}) if pre_match_cached else {}
    if historical_pred:
        cached["historicalPrediction"] = historical_pred
    if pre_match_cached and pre_match_cached.get("computed_at"):
        cached["preMatchComputedAt"] = pre_match_cached["computed_at"]
    if weighted_pred:
        cached["weightedPrediction"] = weighted_pred
        live_match_state[match_id] = cached

    # Recompute combined prediction (phase-based blend)
    user_inputs = cached.get("userInputs", {})
    combined_pred = compute_combined_prediction(
        algo_pred=weighted_pred,
        claude_pred=claude_prediction,
        sm_data=sm_data,
        gut_feeling=user_inputs.get("gut_feeling"),
        betting_odds_pct=user_inputs.get("current_betting_odds"),
    ) if (weighted_pred or claude_prediction) else None
    if combined_pred:
        cached["combinedPrediction"] = combined_pred
        live_match_state[match_id] = cached

    await db.live_snapshots.update_one(
        {"matchId": match_id},
        {"$set": {
            "weightedPrediction": weighted_pred,
            "combinedPrediction": combined_pred,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=False,
    )

    return {
        "matchId": match_id,
        "claudePrediction": claude_prediction,
        "weightedPrediction": weighted_pred,
        "combinedPrediction": combined_pred,
        "historicalPrediction": historical_pred,
        "preMatchComputedAt": pre_match_cached.get("computed_at") if pre_match_cached else None,
        "probabilities": cached.get("probabilities", {}),
        "refreshedAt": datetime.now(timezone.utc).isoformat(),
    }



@api_router.post("/matches/{match_id}/check-status")
async def check_match_status(match_id: str):
    """Check fixture on SportMonks. If finished, update schedule. If live, refresh scores then re-run Claude Opus + decay + phase blend."""
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found in schedule"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")

    result = await check_fixture_status(team1, team2)
    sm_score = result.get("score") or ""
    now_iso = datetime.now(timezone.utc).isoformat()
    predictions_refreshed = None

    # If match is finished, update schedule to "completed"
    if result.get("is_finished"):
        update = {
            "status": "completed",
            "completedAt": now_iso,
        }
        if result.get("winner"):
            update["winner"] = result["winner"]
        if result.get("note"):
            update["result"] = result["note"]
        if sm_score:
            update["score"] = sm_score
        await db.ipl_schedule.update_one({"matchId": match_id}, {"$set": update})
        logger.info(f"Match {match_id} marked completed: {result.get('note')}")
    elif result.get("is_live"):
        await db.ipl_schedule.update_one({"matchId": match_id}, {"$set": {
            "status": "live",
            "score": sm_score or match_info.get("score", ""),
            "sportmonks_fixture_id": result.get("fixture_id"),
            "updatedFromSportMonksAt": now_iso,
        }})
        # Re-sync live snapshot from SportMonks, then Claude Opus + weighted + combined (same as Refresh Predictions)
        cached_pre = live_match_state.get(match_id) or await db.live_snapshots.find_one({"matchId": match_id}, {"_id": 0})
        body = FetchLiveRequest()
        if cached_pre:
            ui = cached_pre.get("userInputs") or {}
            body.gut_feeling = ui.get("gut_feeling")
            body.current_betting_odds = ui.get("current_betting_odds")
            bi = cached_pre.get("bettingInput") or {}
            body.betting_team1_pct = bi.get("team1Pct")
            body.betting_team2_pct = bi.get("team2Pct")
            body.betting_confidence = bi.get("confidence")
        fetch_payload = await fetch_live_data(match_id, body)
        if isinstance(fetch_payload, dict) and not fetch_payload.get("error") and not fetch_payload.get("noLiveMatch"):
            try:
                predictions_refreshed = await refresh_claude_prediction(
                    match_id,
                    RefreshClaudeRequest(
                        gut_feeling=body.gut_feeling,
                        current_betting_odds=body.current_betting_odds,
                    ),
                )
            except HTTPException as he:
                predictions_refreshed = {"error": he.detail}
        else:
            err = fetch_payload.get("error") if isinstance(fetch_payload, dict) else None
            predictions_refreshed = {"error": err or "live_fetch_failed"}

    return {
        "matchId": match_id,
        "sportmonks_status": result.get("status"),
        "is_live": result.get("is_live", False),
        "is_finished": result.get("is_finished", False),
        "winner": result.get("winner"),
        "note": result.get("note", ""),
        "score": sm_score,
        "schedule_status": "completed" if result.get("is_finished") else (
            "live" if result.get("is_live") else match_info.get("status")
        ),
        "predictions_refreshed": predictions_refreshed,
    }


@api_router.get("/live/current")
async def get_current_live_match():
    """Find currently live IPL matches from our schedule."""
    live_schedule = await db.ipl_schedule.find(
        {"status": {"$in": ["live", "Live"]}}, {"_id": 0}
    ).to_list(10)

    found = []
    for sched in live_schedule:
        found.append({
            "matchId": sched["matchId"],
            "team1": sched.get("team1"),
            "team2": sched.get("team2"),
            "score": sched.get("score", ""),
            "venue": sched.get("venue", ""),
        })

    return {
        "live_matches": found,
        "count": len(found),
    }



@api_router.post("/matches/refresh-live-status")
async def refresh_live_status():
    """Discover live IPL matches from SportMonks + CricAPI, promote them to 'live',
    and mark finished ones as 'completed'. Full discovery + cleanup."""

    # Load entire schedule for matching
    all_schedule = await db.ipl_schedule.find({}, {"_id": 0}).to_list(100)
    current_live = [m for m in all_schedule if m.get("status") in ("live", "Live", "in progress")]

    newly_promoted = []
    still_live = []
    newly_completed = []

    # ─── Step 1: Discover from SportMonks livescores ───
    sm_live = await fetch_livescores_ipl()
    sm_matched_mids = set()

    for sm in sm_live:
        sm_t1 = sm.get("team1", "").lower()
        sm_t2 = sm.get("team2", "").lower()

        # Match to our schedule — require strong team name overlap
        candidates = []
        for sched in all_schedule:
            s_t1 = sched.get("team1", "").lower()
            s_t2 = sched.get("team2", "").lower()
            s_t1_short = sched.get("team1Short", "").lower()
            s_t2_short = sched.get("team2Short", "").lower()

            def team_match(sm_name, sched_name, sched_short):
                """Require at least 2 significant words to match, or full short code match."""
                sm_words = [w for w in sm_name.split() if len(w) > 3]
                sched_words = [w for w in sched_name.split() if len(w) > 3]
                # Short code check (e.g. "kkr" in "kolkata knight riders")
                if sched_short and sched_short in sm_name:
                    return True
                # Require at least 2 matching words (avoids "Kings" false positives)
                matched_words = sum(1 for w in sm_words if w in sched_name)
                if matched_words >= 2:
                    return True
                # Single unique word match (city names like "kolkata", "chennai", "mumbai")
                city_words = {"mumbai", "chennai", "kolkata", "bangalore", "bengaluru", "hyderabad",
                              "delhi", "rajasthan", "punjab", "lucknow", "gujarat", "ahmedabad"}
                for w in sm_words:
                    if w in city_words and w in sched_name:
                        return True
                return False

            # Check both orderings
            if (team_match(sm_t1, s_t1, s_t1_short) and team_match(sm_t2, s_t2, s_t2_short)):
                candidates.append(sched)
            elif (team_match(sm_t1, s_t2, s_t2_short) and team_match(sm_t2, s_t1, s_t1_short)):
                candidates.append(sched)

        # Pick best candidate: prefer "upcoming" or "live", then earliest by matchId
        matched = None
        if candidates:
            # Prefer already-live or upcoming (not completed)
            for c in candidates:
                if c.get("status") in ("live", "Live", "in progress"):
                    matched = c
                    break
            if not matched:
                for c in candidates:
                    if c.get("status") in ("upcoming", "Upcoming", "not_started"):
                        matched = c
                        break
            if not matched:
                # All candidates are completed — this is likely a rematch (teams play twice in IPL).
                # Auto-create a new schedule entry for this live match.
                existing_ids = [int(s["matchId"].replace("ipl2026_", "")) for s in all_schedule if s.get("matchId", "").startswith("ipl2026_")]
                new_num = max(existing_ids) + 1 if existing_ids else 100
                new_mid = f"ipl2026_{new_num:03d}"
                # Use the SportMonks team names, map to our schedule format
                ref = candidates[0]  # Use first completed match as reference for team metadata
                # Determine short codes — check if team order matches reference
                sm_team1 = sm.get("team1", "")
                sm_team2 = sm.get("team2", "")
                ref_t1 = ref.get("team1", "").lower()
                ref_t2 = ref.get("team2", "").lower()
                # Match SM team1 to ref teams
                if any(w in sm_team1.lower() for w in ref_t1.split() if len(w) > 3 and w not in ("kings", "super")):
                    t1_short = ref.get("team1Short", "")
                    t2_short = ref.get("team2Short", "")
                else:
                    t1_short = ref.get("team2Short", "")
                    t2_short = ref.get("team1Short", "")
                new_entry = {
                    "matchId": new_mid,
                    "team1": sm_team1,
                    "team2": sm_team2,
                    "team1Short": t1_short,
                    "team2Short": t2_short,
                    "status": "live",
                    "venue": ref.get("venue", ""),
                    "dateTimeGMT": datetime.now(timezone.utc).isoformat(),
                    "matchType": "T20",
                    "series": ref.get("series", "IPL 2026"),
                    "match_number": new_num,
                    "sportmonks_fixture_id": sm.get("fixture_id"),
                    "auto_created": True,
                }
                await db.ipl_schedule.insert_one(new_entry)
                del new_entry["_id"]  # Remove MongoDB _id before using in response
                matched = new_entry
                all_schedule.append(new_entry)
                logger.info(f"Auto-created schedule entry {new_mid} for live rematch: {sm.get('team1')} vs {sm.get('team2')}")

        if not matched:
            continue

        mid = matched["matchId"]
        sm_matched_mids.add(mid)

        if sm.get("is_live"):
            score_text = format_livescore_entry_text(sm) or sm.get("note", "")
            # Promote to live if not already
            if matched.get("status") != "live":
                await db.ipl_schedule.update_one({"matchId": mid}, {"$set": {
                    "status": "live",
                    "score": score_text,
                    "sportmonks_fixture_id": sm.get("fixture_id"),
                    "updatedFromSportMonksAt": datetime.now(timezone.utc).isoformat(),
                }})
                newly_promoted.append({"matchId": mid, "team1": matched["team1"], "team2": matched["team2"], "status": sm.get("status"), "score": score_text})
                logger.info(f"Match {mid} promoted to live via SportMonks: {matched['team1']} vs {matched['team2']}")
            else:
                await db.ipl_schedule.update_one({"matchId": mid}, {"$set": {
                    "score": score_text,
                    "sportmonks_fixture_id": sm.get("fixture_id"),
                    "updatedFromSportMonksAt": datetime.now(timezone.utc).isoformat(),
                }})
                still_live.append({"matchId": mid, "team1": matched["team1"], "team2": matched["team2"], "status": sm.get("status"), "score": score_text, "note": sm.get("note")})

        elif sm.get("is_finished"):
            await db.ipl_schedule.update_one({"matchId": mid}, {"$set": {
                "status": "completed",
                "result": sm.get("note", ""),
                "completedAt": datetime.now(timezone.utc).isoformat(),
            }})
            newly_completed.append({"matchId": mid, "team1": matched["team1"], "team2": matched["team2"], "result": sm.get("note", "")})
            logger.info(f"Match {mid} marked completed via SportMonks: {sm.get('note')}")

    # ─── Step 2: Discover from CricAPI ───
    cric_matched_mids = set()
    try:
        cricapi_result = await fetch_live_ipl_details()
        cricapi_matches = cricapi_result.get("matches", [])

        for cm in cricapi_matches:
            cm_t1 = cm.get("team1", "").lower()
            cm_t2 = cm.get("team2", "").lower()

            candidates = []
            for sched in all_schedule:
                s_t1 = sched.get("team1", "").lower()
                s_t2 = sched.get("team2", "").lower()
                match_a = (any(w in cm_t1 for w in s_t1.split() if len(w) > 3) or any(w in s_t1 for w in cm_t1.split() if len(w) > 3))
                match_b = (any(w in cm_t2 for w in s_t2.split() if len(w) > 3) or any(w in s_t2 for w in cm_t2.split() if len(w) > 3))
                match_a2 = (any(w in cm_t1 for w in s_t2.split() if len(w) > 3) or any(w in s_t2 for w in cm_t1.split() if len(w) > 3))
                match_b2 = (any(w in cm_t2 for w in s_t1.split() if len(w) > 3) or any(w in s_t1 for w in cm_t2.split() if len(w) > 3))
                if (match_a and match_b) or (match_a2 and match_b2):
                    candidates.append(sched)

            matched = None
            if candidates:
                for c in candidates:
                    if c.get("status") in ("live", "Live", "in progress"):
                        matched = c
                        break
                if not matched:
                    for c in candidates:
                        if c.get("status") in ("upcoming", "Upcoming", "not_started"):
                            matched = c
                            break
                if not matched:
                    matched = candidates[0]

            if not matched or matched["matchId"] in sm_matched_mids:
                continue

            mid = matched["matchId"]
            cric_matched_mids.add(mid)
            cm_status = cm.get("status", "").lower()
            is_ended = cm.get("matchEnded", False) or any(w in cm_status for w in ["won", "result", "tie", "no result", "abandoned"])

            if is_ended:
                await db.ipl_schedule.update_one({"matchId": mid}, {"$set": {
                    "status": "completed",
                    "result": cm.get("status", ""),
                    "completedAt": datetime.now(timezone.utc).isoformat(),
                }})
                newly_completed.append({"matchId": mid, "team1": matched["team1"], "team2": matched["team2"], "result": cm.get("status", "")})
            elif cm.get("matchStarted", False):
                if matched.get("status") != "live":
                    score_parts = []
                    for inn in cm.get("innings", []):
                        score_parts.append(f"{inn.get('inning_label','')}: {inn.get('runs',0)}/{inn.get('wickets',0)} ({inn.get('overs',0)} ov)")
                    score_text = " | ".join(score_parts)
                    await db.ipl_schedule.update_one({"matchId": mid}, {"$set": {
                        "status": "live",
                        "score": score_text,
                        "cricapi_id": cm.get("cricapi_id"),
                    }})
                    newly_promoted.append({"matchId": mid, "team1": matched["team1"], "team2": matched["team2"], "status": "live (cricapi)", "score": score_text})
                    logger.info(f"Match {mid} promoted to live via CricAPI")
                else:
                    if mid not in [s["matchId"] for s in still_live]:
                        still_live.append({"matchId": mid, "team1": matched["team1"], "team2": matched["team2"], "status": "live (cricapi)"})
    except Exception as e:
        logger.error(f"CricAPI discovery failed: {e}")

    # ─── Step 3: Clean up stale 'live' matches not found in any source ───
    all_discovered_mids = sm_matched_mids | cric_matched_mids
    for match in current_live:
        mid = match.get("matchId")
        if mid in all_discovered_mids:
            continue
        if mid in [s["matchId"] for s in still_live] or mid in [s["matchId"] for s in newly_completed]:
            continue
        # Not found in any live source — check score text for completion
        score = match.get("score", "")
        if any(w in score.lower() for w in ["won", "tie", "no result", "abandoned"]):
            await db.ipl_schedule.update_one({"matchId": mid}, {"$set": {"status": "completed", "result": score}})
            newly_completed.append({"matchId": mid, "team1": match.get("team1"), "team2": match.get("team2"), "result": score})
        else:
            # Only mark completed if match date is actually in the past
            dt_str = match.get("dateTimeGMT", "")
            is_past = False
            if dt_str:
                try:
                    mdt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    is_past = (datetime.now(timezone.utc) - mdt).total_seconds() > 6 * 3600
                except Exception:
                    pass
            if is_past:
                await db.ipl_schedule.update_one({"matchId": mid}, {"$set": {
                    "status": "completed", "completedAt": datetime.now(timezone.utc).isoformat(),
                }})
                newly_completed.append({"matchId": mid, "team1": match.get("team1"), "team2": match.get("team2"), "result": "Match ended (no longer live)"})
                logger.info(f"Match {mid} marked completed: not found on any live source")
            else:
                # Future match — reset to upcoming, not completed
                await db.ipl_schedule.update_one({"matchId": mid}, {"$set": {"status": "Upcoming"}})
                logger.info(f"Match {mid} reset to Upcoming: future date, not live")

    return {
        "checked": len(current_live),
        "sportmonks_live": len(sm_live),
        "cricapi_live": len(cricapi_matches) if cricapi_matches else 0,
        "newly_promoted": newly_promoted,
        "still_live": still_live,
        "completed": newly_completed,
        "still_live_count": len(still_live),
        "promoted_count": len(newly_promoted),
        "completed_count": len(newly_completed),
    }





def _compute_live_prediction(result: Dict, match_info: Dict) -> Dict:
    """
    Compute real-time win prediction based on current match state:
    - Current batsmen on field + their career data
    - Current bowler performance
    - Required rate vs current rate
    - Wickets in hand
    - Historical chase patterns at this venue
    - Phase of the game (PP/middle/death)
    """
    live_data = result.get("liveData", {})
    probs = result.get("probabilities", {})
    score = live_data.get("score", {})
    if isinstance(score, dict):
        runs = score.get("runs", 0)
        wickets = score.get("wickets", 0)
        overs = score.get("overs", 0)
        target = score.get("target")
    else:
        runs = 0
        wickets = 0
        overs = 0
        target = None
    
    innings = live_data.get("innings", 1)
    batsmen = result.get("batsmen", [])
    bowler = result.get("bowler", {})
    
    # Determine phase
    phase = "powerplay" if overs <= 6 else "middle" if overs <= 15 else "death"
    
    # Current run rate
    crr = round(runs / max(overs, 0.1), 2)
    
    # Required run rate (2nd innings only)
    rrr = None
    runs_remaining = None
    balls_remaining = None
    if target and innings == 2:
        runs_remaining = target - runs
        balls_remaining = max(1, (20 - overs) * 6)
        overs_remaining = max(0.1, 20 - overs)
        rrr = round(runs_remaining / overs_remaining, 2)
    
    # Wickets in hand factor (more wickets = better)
    wickets_in_hand = 10 - wickets
    
    # Batting team's advantage factors
    batting_team = live_data.get("battingTeam", match_info.get("team1", ""))
    bowling_team = live_data.get("bowlingTeam", match_info.get("team2", ""))
    
    # Current batsmen analysis
    batsmen_info = []
    for b in batsmen:
        name = b.get("name", "Unknown")
        bat_runs = b.get("runs", 0)
        bat_balls = b.get("balls", 0)
        bat_sr = round(bat_runs / max(bat_balls, 1) * 100, 1) if bat_balls > 0 else 0
        batsmen_info.append({
            "name": name,
            "runs": bat_runs,
            "balls": bat_balls,
            "sr": bat_sr,
            "is_set": bat_balls >= 15,
            "impact": "high" if bat_sr > 150 and bat_balls >= 10 else "medium" if bat_sr > 120 else "low",
        })
    
    # Bowler analysis
    bowler_info = None
    if bowler:
        bowler_name = bowler.get("name", "Unknown")
        bowler_overs = bowler.get("overs", 0)
        bowler_runs = bowler.get("runs", 0)
        bowler_wickets = bowler.get("wickets", 0)
        bowler_econ = round(bowler_runs / max(bowler_overs, 0.1), 2) if bowler_overs > 0 else 0
        bowler_info = {
            "name": bowler_name,
            "overs": bowler_overs,
            "runs": bowler_runs,
            "wickets": bowler_wickets,
            "economy": bowler_econ,
            "impact": "high" if bowler_wickets >= 2 or bowler_econ < 6 else "medium" if bowler_econ < 8 else "low",
        }
    
    # Win probability adjustment based on match state
    ensemble_prob = probs.get("ensemble", 0.5)
    
    # Compute projected score (1st innings)
    projected_score = None
    if innings == 1 and overs > 2:
        projected_score = round(crr * 20)
        # Adjust for wickets lost and phase acceleration
        if phase == "death":
            projected_score = round(runs + (crr * 1.15) * (20 - overs))
        elif phase == "middle":
            projected_score = round(runs + (crr * 1.05) * (20 - overs))
    
    # Chase analysis (2nd innings)
    chase_analysis = None
    if innings == 2 and target:
        chase_difficulty = "easy" if rrr and rrr < crr * 0.85 else "moderate" if rrr and rrr < crr * 1.15 else "difficult" if rrr and rrr < crr * 1.5 else "very_difficult"
        chase_analysis = {
            "target": target,
            "runs_remaining": runs_remaining,
            "balls_remaining": balls_remaining,
            "required_rate": rrr,
            "current_rate": crr,
            "difficulty": chase_difficulty,
            "wickets_in_hand": wickets_in_hand,
        }
    
    # Summary text
    if innings == 1:
        if overs > 2:
            summary = f"{batting_team} at {runs}/{wickets} in {overs} overs (CRR: {crr}). Projected: ~{projected_score}. Phase: {phase.upper()}."
        else:
            summary = f"Early stages — {batting_team} {runs}/{wickets} in {overs} overs."
    else:
        if rrr:
            rate_diff = "ahead" if crr > rrr else "behind"
            summary = f"{batting_team} need {runs_remaining} off {balls_remaining} balls (RRR: {rrr}). Currently {rate_diff} the rate. {wickets_in_hand} wickets in hand."
        else:
            summary = f"{batting_team} chasing — {runs}/{wickets} in {overs} overs."
    
    return {
        "batting_team": batting_team,
        "bowling_team": bowling_team,
        "phase": phase,
        "crr": crr,
        "rrr": rrr,
        "projected_score": projected_score,
        "wickets_in_hand": wickets_in_hand,
        "batsmen_on_field": batsmen_info,
        "current_bowler": bowler_info,
        "chase_analysis": chase_analysis,
        "win_probability": round(ensemble_prob * 100, 1),
        "summary": summary,
    }



async def _attach_pre_match_historical(match_id: str, payload: dict) -> None:
    """Overlay historicalPrediction from pre_match_predictions (DB source of truth for pre-game model)."""
    if not isinstance(payload, dict):
        return
    try:
        pre = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
    except Exception:
        return
    if not pre:
        return
    pred = pre.get("prediction")
    if isinstance(pred, dict) and pred:
        payload["historicalPrediction"] = pred
    ca = pre.get("computed_at")
    if ca:
        payload["preMatchComputedAt"] = ca


@api_router.get("/matches/{match_id}/state")
async def get_match_state(match_id: str):
    """Get last known state of a live match, always including schedule info."""
    schedule_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})

    if match_id in live_match_state:
        result = live_match_state[match_id]
        # Merge schedule info into live state
        if schedule_info:
            for key in ("city", "timeIST", "match_number", "series"):
                if key in schedule_info and key not in result:
                    result[key] = schedule_info[key]
        await _attach_pre_match_historical(match_id, result)
        return result

    cached = await db.live_snapshots.find_one({"matchId": match_id}, {"_id": 0})
    if cached:
        # Merge schedule info into cached state
        if schedule_info:
            for key in ("city", "timeIST", "match_number", "series"):
                if key in schedule_info and key not in cached:
                    cached[key] = schedule_info[key]
        await _attach_pre_match_historical(match_id, cached)
        return cached

    return {"matchId": match_id, "info": schedule_info, "noLiveData": True}


# ─── PLAYER PREDICTIONS (on-demand) ─────────────────────────

@api_router.post("/matches/{match_id}/player-predictions")
async def api_player_predictions(match_id: str):
    """Fetch AI player predictions for a match."""
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")
    t1_short = match_info.get("team1Short", get_short_name(team1))
    t2_short = match_info.get("team2Short", get_short_name(team2))

    sq1 = await db.ipl_squads.find_one({"teamShort": t1_short}, {"_id": 0})
    sq2 = await db.ipl_squads.find_one({"teamShort": t2_short}, {"_id": 0})

    players = await get_player_predictions(
        team1, team2, venue,
        sq1.get("players") if sq1 else None,
        sq2.get("players") if sq2 else None
    )

    return {"matchId": match_id, "players": players}


# ─── MATCH PREDICTION (on-demand) ───────────────────────────

@api_router.post("/matches/{match_id}/predict")
async def api_predict(match_id: str):
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}
    live_state = live_match_state.get(match_id)
    if not live_state:
        live_state = await db.live_snapshots.find_one({"matchId": match_id}, {"_id": 0})
    sm = {}
    if live_state:
        sm = live_state.get("sportmonks") or live_state.get("sportmonksData") or {}
    if not _sm_playing_xi_complete(sm if isinstance(sm, dict) else {}):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "playing_xi_required",
                "message": (
                    "Live Playing XI (11 per side from SportMonks) is required. "
                    "Use “Fetch Live Scores” first so lineups are stored, then run prediction."
                ),
            },
        )
    if live_state:
        match_info["score"] = live_state.get("liveData", {}).get("score", {})
    pred = await get_match_prediction(match_info)
    return {"matchId": match_id, "prediction": pred}


# ─── PRE-MATCH PREDICTION ───────────────────────────────────


@api_router.get("/predictions/{match_id}/pre-match")
async def get_pre_match_prediction(match_id: str):
    """Get cached pre-match prediction (does not trigger new prediction)."""
    cached = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
    if cached:
        d = dict(cached)
        if _playing_xi_needs_claude_roles(d):
            xi = await db.playing_xi.find_one({"matchId": match_id}, {"_id": 0})
            if xi:
                _merge_playing_xi_roles_from_storage(d, xi)
        if d.get("playing_xi"):
            _sanitize_playing_xi_payload(d["playing_xi"])
        return d
    return {"matchId": match_id, "prediction": None}


@api_router.post("/matches/{match_id}/pre-match-predict")
async def api_pre_match_predict(match_id: str, force: bool = False):
    """
    Predict upcoming match winner using 8-category algorithm.

    Strict gate: Expected Playing XI must already exist in the playing_xi collection
    (11 named players per side from “Fetch Playing XI”). Inline SportMonks lineup
    fetch is not used here — only the generated cache drives the XI.

    Playing XI primary roles (Batsman/Bowler/All-rounder/Wicketkeeper) are always
    inferred via Claude on this path (ANTHROPIC_API_KEY required); prediction fails if that step fails.

    Auto-refreshes stale predictions (>6 hours old) to keep data fresh, or sooner if
    cached playing_xi rows lack Claude-assigned roles.
    """
    cached = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
    if cached and not force:
        # Check staleness — auto-refresh if older than 6 hours
        computed_at = cached.get("computed_at", "")
        is_stale = False
        if computed_at:
            try:
                computed_dt = datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - computed_dt).total_seconds() / 3600
                if age_hours > 6:
                    is_stale = True
                    logger.info(f"Prediction for {match_id} is {age_hours:.1f}h old — auto-refreshing")
            except (ValueError, TypeError):
                pass
        if not is_stale and not _playing_xi_needs_claude_roles(cached):
            return cached
        if not is_stale and _playing_xi_needs_claude_roles(cached):
            logger.info(
                "Prediction cache for %s is fresh but Playing XI lacks Claude roles — recomputing",
                match_id,
            )

    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")
    t1_short = match_info.get("team1Short", get_short_name(team1))
    t2_short = match_info.get("team2Short", get_short_name(team2))

    logger.info(f"Pre-match predict: {team1} vs {team2} at {venue}")

    # ── Cross-reference match start time from SportMonks API ──
    # This ensures accurate afternoon vs evening classification for toss/dew impact
    try:
        api_start_time = await fetch_fixture_start_time(team1, team2)
        if api_start_time:
            db_time = match_info.get("dateTimeGMT", "")
            # Normalize for comparison (SportMonks includes microseconds)
            api_time_normalized = api_start_time.split(".")[0].replace("Z", "") + "Z"
            db_time_normalized = db_time.split(".")[0].replace("Z", "") + "Z"
            if api_time_normalized != db_time_normalized:
                logger.info(f"Match time updated from SportMonks: {db_time} → {api_start_time}")
                match_info["dateTimeGMT"] = api_start_time
                # Also update DB for future calls
                await db.ipl_schedule.update_one(
                    {"matchId": match_id},
                    {"$set": {"dateTimeGMT": api_start_time, "dateTimeGMT_source": "sportmonks"}}
                )
            match_info["dateTimeGMT_source"] = "sportmonks"
    except Exception as e:
        logger.warning(f"Failed to fetch match time from SportMonks: {e}")

    # Fetch squads from DB (user-provided IPL 2026 rosters)
    match_squads = await _get_squads_for_match(team1, team2)

    # ── Strict: Expected XI must come from generated playing_xi cache (Fetch Playing XI) ──
    xi_doc = await db.playing_xi.find_one({"matchId": match_id}, {"_id": 0})
    if not xi_doc or not _prematch_xi_complete(xi_doc):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "playing_xi_required",
                "message": (
                    "Expected Playing XI (11 named players per side) must be generated before pre-match prediction. "
                    "Run “Fetch Playing XI” for this match, wait until it completes, then try again."
                ),
            },
        )

    prediction_squads = _playing_xi_squads_from_doc(xi_doc, match_squads, team1, team2)
    if not prediction_squads:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "playing_xi_invalid",
                "message": (
                    "Could not build Playing XI from cache. Re-run “Fetch Playing XI” for this match "
                    "and ensure both teams have 11 named players."
                ),
            },
        )

    await _ensure_claude_playing_xi_roles(
        match_id, team1, team2, prediction_squads, xi_doc, mandatory=True,
    )

    xi_data = {
        "team1_xi": [
            {
                "name": p.get("name"),
                "role": normalize_primary_cricket_role(p.get("role")),
                "isCaptain": p.get("isCaptain", False),
                "isOverseas": p.get("isOverseas", False),
                "role_source": p.get("role_source") or "claude",
            }
            for p in prediction_squads.get(team1, [])
        ],
        "team2_xi": [
            {
                "name": p.get("name"),
                "role": normalize_primary_cricket_role(p.get("role")),
                "isCaptain": p.get("isCaptain", False),
                "isOverseas": p.get("isOverseas", False),
                "role_source": p.get("role_source") or "claude",
            }
            for p in prediction_squads.get(team2, [])
        ],
        "source": xi_doc.get("source", "last_match"),
        "confidence": xi_doc.get("confidence", "api-verified"),
    }
    logger.info(
        f"Pre-match using cached Expected XI only: {len(prediction_squads.get(team1, []))}+"
        f"{len(prediction_squads.get(team2, []))} players (matchId={match_id})"
    )

    # Fetch weather for venue (Open-Meteo, free)
    prematch_city = match_info.get("city", "")
    if not prematch_city and venue:
        prematch_city = venue.split(",")[-1].strip() if "," in venue else venue
    match_date_str = match_info.get("dateTimeGMT", "")[:10] if match_info.get("dateTimeGMT") else None
    prematch_weather = await fetch_weather_for_venue(prematch_city, match_date_str) if prematch_city else {}

    # ── Fetch player performance stats from SportMonks (last 5 matches per team) ──
    player_performance = {}
    try:
        t1_perf = await fetch_team_recent_performance(team1, num_matches=5)
        t2_perf = await fetch_team_recent_performance(team2, num_matches=5)
        if t1_perf:
            player_performance["team1"] = t1_perf
        if t2_perf:
            player_performance["team2"] = t2_perf
        logger.info(f"Player performance fetched: {len(t1_perf)} + {len(t2_perf)} players")
    except Exception as e:
        logger.warning(f"Failed to fetch player performance: {e}")

    player_performance = _filter_player_performance_to_playing_xi(player_performance, prediction_squads)
    strength_metrics = await _build_team_strength_inputs(team1, team2, prediction_squads, player_performance)

    # Fetch form data from DB completed matches + player performance
    form_data = await fetch_team_form(db, team1, team2, player_performance=player_performance)
    form_data = _filter_form_data_to_playing_xi(form_data, prediction_squads, team1, team2)

    # Fetch momentum (last 2 results)
    momentum_data = await fetch_momentum(db, team1, team2)

    # Enrich Playing XI with last-N stats + impact before the 8-factor model consumes context
    if xi_data:
        try:
            xi_data = await _enrich_playing_xi_with_impact(
                xi_data, team1, team2, player_performance
            )
        except Exception as e:
            logger.warning(f"Playing XI impact enrichment skipped: {e}")

    _sanitize_playing_xi_payload(xi_data)

    # Web-search enrichment is consumed ONLY for PP/death/key-availability factors.
    web_context = {}
    try:
        web_context = await fetch_pre_match_stats(team1, team2, venue)
    except Exception as e:
        logger.warning(f"Web context fetch skipped for {match_id}: {e}")

    # Run pre-match algorithm — squads are strictly the Playing XI rows above
    prediction = compute_prediction(
        squad_data=prediction_squads,
        match_info=match_info,
        weather=prematch_weather,
        form_data=form_data,
        momentum_data=momentum_data,
        player_performance=player_performance,
        web_context=web_context,
        team_strength_metrics=strength_metrics,
    )
    try:
        prediction["factor_claude_validation"] = await validate_factor_reasons_with_claude(
            t1_short, t2_short, prediction
        )
    except Exception as e:
        logger.warning(f"Factor reason validation failed for {match_id}: {e}")
        prediction["factor_claude_validation"] = {}

    # Compute odds direction vs previous prediction
    odds_direction = {"team1": "new", "team2": "new"}
    if cached:
        old_t1 = cached.get("prediction", {}).get("team1_win_prob", 50)
        new_t1 = prediction["team1_win_prob"]
        diff = round(new_t1 - old_t1, 1)
        if diff > 0.5:
            odds_direction["team1"] = "up"
            odds_direction["team2"] = "down"
        elif diff < -0.5:
            odds_direction["team1"] = "down"
            odds_direction["team2"] = "up"
        else:
            odds_direction["team1"] = "stable"
            odds_direction["team2"] = "stable"
        odds_direction["team1_change"] = diff
        odds_direction["team2_change"] = round(-diff, 1)
        odds_direction["previous_team1_prob"] = old_t1
        odds_direction["previous_team2_prob"] = cached.get("prediction", {}).get("team2_win_prob", 50)

    # Store previous prediction in history
    if cached:
        await db.prediction_history.insert_one({
            "matchId": match_id,
            "prediction": cached.get("prediction"),
            "computed_at": cached.get("computed_at"),
            "superseded_at": datetime.now(timezone.utc).isoformat(),
        })

    result = {
        "matchId": match_id,
        "team1": team1,
        "team2": team2,
        "team1Short": t1_short,
        "team2Short": t2_short,
        "venue": venue,
        "city": match_info.get("city", ""),
        "dateTimeGMT": match_info.get("dateTimeGMT", ""),
        "timeIST": match_info.get("timeIST", ""),
        "match_number": match_info.get("match_number"),
        "prediction": prediction,
        "playing_xi": xi_data,
        "weather": prematch_weather,
        "odds_direction": odds_direction,
        "form_data": form_data,
        "momentum": momentum_data,
        "player_performance_summary": {
            "team1_players": len(player_performance.get("team1", {})),
            "team2_players": len(player_performance.get("team2", {})),
            "source": "sportmonks_recent_matches",
            "has_data": bool(player_performance.get("team1") or player_performance.get("team2")),
        },
        "team_strength_metrics": {
            "config": strength_metrics.get("config", {}),
            "team1": strength_metrics.get("team1", {}),
            "team2": strength_metrics.get("team2", {}),
            "source_priority": ["db", "sportmonks", "claude"],
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Store in DB
    await db.pre_match_predictions.update_one(
        {"matchId": match_id},
        {"$set": result},
        upsert=True,
    )
    logger.info(f"Stored prediction for {match_id}: {t1_short} {prediction['team1_win_prob']}% vs {t2_short} {prediction['team2_win_prob']}%")

    return result


@api_router.post("/matches/{match_id}/fetch-playing-xi-roles-and-predict")
async def api_fetch_playing_xi_roles_and_predict(match_id: str):
    """
    One click: infer Expected XI roles via Claude (mandatory), then run a full pre-match
    prediction refresh (same as pre-match-predict?force=true).
    """
    return await api_pre_match_predict(match_id, force=True)


@api_router.post("/matches/{match_id}/injury-override")
async def api_injury_override(match_id: str, body: dict = Body(...)):
    """
    Add or update a manual injury/absence override for a match.
    Manual overrides take priority over auto-scraped injury data.
    Body: { player: str, team: "team1"|"team2", impact_score: 1-10, reason: str }
    """
    player = body.get("player", "")
    team = body.get("team", "")
    impact_score = body.get("impact_score", 0)
    reason = body.get("reason", "")

    if not player or not team:
        return {"error": "player and team are required"}

    override = {
        "matchId": match_id,
        "player": player,
        "team": team,
        "impact_score": impact_score,
        "reason": reason,
        "source": "manual",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.injury_overrides.update_one(
        {"matchId": match_id, "player": player},
        {"$set": override},
        upsert=True
    )

    return {"status": "ok", "override": override}


@api_router.get("/matches/{match_id}/injury-overrides")
async def api_get_injury_overrides(match_id: str):
    """Get all injury overrides for a match."""
    overrides = []
    async for doc in db.injury_overrides.find({"matchId": match_id}, {"_id": 0}):
        overrides.append(doc)
    return {"matchId": match_id, "overrides": overrides}


@api_router.delete("/matches/{match_id}/injury-override/{player_name}")
async def api_delete_injury_override(match_id: str, player_name: str):
    """Delete a specific injury override."""
    result = await db.injury_overrides.delete_one({"matchId": match_id, "player": player_name})
    return {"deleted": result.deleted_count > 0}



@api_router.post("/schedule/predict-upcoming")
async def api_predict_upcoming(force: bool = False):
    """
    Batch predict all upcoming matches using 8-category model.
    NO web scraping. Uses DB squads + weather + form data.
    """
    upcoming = []
    async for doc in db.ipl_schedule.find({"status": "Upcoming"}, {"_id": 0}).sort("match_number", 1):
        upcoming.append(doc)

    predictions = []
    new_count = 0
    already_count = 0

    for match in upcoming:
        mid = match.get("matchId", "")
        if not force:
            cached = await db.pre_match_predictions.find_one({"matchId": mid}, {"_id": 0})
            if cached:
                predictions.append(cached)
                already_count += 1
                continue

        try:
            result = await api_pre_match_predict(mid, force=force)
            if result and "error" not in result:
                predictions.append(result)
                new_count += 1
        except Exception as e:
            logger.error(f"Failed to predict {mid}: {e}")

    return {
        "total_upcoming": len(upcoming),
        "already_predicted": already_count,
        "newly_predicted": new_count,
        "predictions": predictions,
    }


@api_router.get("/predictions/upcoming")
async def api_get_upcoming_predictions():
    """Get all stored pre-match predictions for upcoming matches."""
    predictions = []
    async for doc in db.pre_match_predictions.find({}, {"_id": 0}).sort("match_number", 1):
        d = dict(doc)
        mid = d.get("matchId")
        if mid and _playing_xi_needs_claude_roles(d):
            xi = await db.playing_xi.find_one({"matchId": mid}, {"_id": 0})
            if xi:
                _merge_playing_xi_roles_from_storage(d, xi)
        if d.get("playing_xi"):
            _sanitize_playing_xi_payload(d["playing_xi"])
        predictions.append(d)
    return {"predictions": predictions, "count": len(predictions)}


# ─── BACKGROUND RE-PREDICTION ────────────────────────────────

repredict_status = {"running": False, "total": 0, "completed": 0, "failed": 0, "current_match": "", "started_at": None, "phase": "", "cancelled": False}

async def _background_repredict_all():
    """Background task: re-predict ALL upcoming matches from scratch.

    For each match:
    1. Delete old pre-match prediction from DB
    2. Delete old Claude analysis from DB
    3. Clear SportMonks fixtures cache (fresh Playing XI)
    4. Re-run 8-category algo prediction (fresh Playing XI + player performance)
    5. Re-run Claude deep analysis with filtered Playing XI
    6. Store fresh results in DB
    """
    global repredict_status
    repredict_status = {
        "running": True, "total": 0, "completed": 0, "failed": 0,
        "current_match": "", "started_at": datetime.now(timezone.utc).isoformat(),
        "phase": "init", "cancelled": False,
    }

    # Clear SportMonks season fixtures cache so fresh data is fetched
    from services.sportmonks_service import _season_fixtures_cache
    _season_fixtures_cache.clear()
    logger.info("[RePredict] Cleared SportMonks cache")

    # Get all upcoming matches
    upcoming = []
    async for doc in db.ipl_schedule.find({"status": "Upcoming"}, {"_id": 0}).sort("match_number", 1):
        upcoming.append(doc)
    repredict_status["total"] = len(upcoming)
    logger.info(f"[RePredict] Starting for {len(upcoming)} upcoming matches")

    for i, match in enumerate(upcoming):
        # ── Check cancellation ──
        if repredict_status.get("cancelled"):
            logger.info(f"[RePredict] Cancelled at {i}/{len(upcoming)}")
            break
        # Yield to event loop between matches
        await asyncio.sleep(0.5)
        mid = match.get("matchId", "")
        team1 = match.get("team1", "")
        team2 = match.get("team2", "")
        t1_short = match.get("team1Short", get_short_name(team1))
        t2_short = match.get("team2Short", get_short_name(team2))
        repredict_status["current_match"] = f"{t1_short} vs {t2_short}"

        try:
            # ── Step 1: Delete old predictions from DB ──
            repredict_status["phase"] = f"cleaning {t1_short} vs {t2_short}"
            await db.pre_match_predictions.delete_one({"matchId": mid})
            await db.claude_analysis.delete_one({"matchId": mid})
            logger.info(f"[RePredict {i+1}/{len(upcoming)}] Cleared old data for {mid}")

            # ── Step 2: Re-run algo prediction (fresh Playing XI + player perf) ──
            repredict_status["phase"] = f"algo {t1_short} vs {t2_short}"
            algo_result = await api_pre_match_predict(mid, force=True)
            algo_ok = algo_result and "error" not in algo_result
            if algo_ok:
                logger.info(f"[RePredict {i+1}/{len(upcoming)}] Algo done: {t1_short} vs {t2_short}")
            else:
                logger.warning(f"[RePredict {i+1}/{len(upcoming)}] Algo failed: {mid} - {algo_result.get('error', 'unknown')}")

            # ── Step 3: Re-run Claude deep analysis (Expected XI from playing_xi only) ──
            repredict_status["phase"] = f"claude {t1_short} vs {t2_short}"
            venue = match.get("venue", "")
            if not algo_ok:
                logger.warning(f"[RePredict] Skipping Claude for {mid} (pre-match did not complete)")
            else:
                xi_doc_r = await db.playing_xi.find_one({"matchId": mid}, {"_id": 0})
                match_squads = await _get_squads_for_match(team1, team2)
                playing_xi_squads = (
                    _playing_xi_squads_from_doc(xi_doc_r, match_squads, team1, team2)
                    if xi_doc_r
                    else {}
                )
                if not playing_xi_squads:
                    logger.warning(f"[RePredict] Skipping Claude for {mid} (invalid Expected XI cache)")
                else:
                    match_news = await fetch_match_news(team1, team2)
                    algo_pred = None
                    try:
                        algo_pred = await db.pre_match_predictions.find_one({"matchId": mid}, {"_id": 0})
                    except Exception:
                        pass
                    player_perf = {}
                    try:
                        t1p = await db.player_performance.find_one({"team": team1}, {"_id": 0})
                        t2p = await db.player_performance.find_one({"team": team2}, {"_id": 0})
                        if t1p:
                            player_perf["team1"] = t1p.get("players", t1p)
                        if t2p:
                            player_perf["team2"] = t2p.get("players", t2p)
                    except Exception:
                        pass
                    player_perf = _filter_player_performance_to_playing_xi(player_perf, playing_xi_squads)
                    weather_data = None
                    try:
                        city_name = match.get("city", "") or venue.split(",")[-1].strip() if venue else ""
                        if city_name:
                            weather_data = await get_weather(city_name, match.get("dateTimeGMT"))
                    except Exception:
                        pass
                    form_data = None
                    try:
                        form_data = await fetch_team_form(db, team1, team2, player_performance=player_perf)
                    except Exception:
                        pass
                    if form_data:
                        form_data = _filter_form_data_to_playing_xi(
                            form_data, playing_xi_squads, team1, team2
                        )
                    news_for_claude = _filter_news_items_for_xi(
                        match_news, team1, team2, playing_xi_squads
                    )
                    algo_for_claude = _scrub_algo_prediction_for_claude(
                        algo_pred, playing_xi_squads, team1, team2
                    )

                    try:
                        analysis = await claude_deep_match_analysis(
                            team1, team2, venue, match, squads=playing_xi_squads, news=news_for_claude,
                            algo_prediction=algo_for_claude, player_performance=player_perf,
                            weather=weather_data, form_data=form_data,
                        )
                        if analysis and "error" not in analysis:
                            await db.claude_analysis.update_one(
                                {"matchId": mid},
                                {"$set": {
                                    "matchId": mid,
                                    "analysis": analysis,
                                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                                    "playing_xi_used": True,
                                }},
                                upsert=True,
                            )
                            logger.info(f"[RePredict {i+1}/{len(upcoming)}] Claude done: {t1_short} vs {t2_short}")
                        else:
                            logger.warning(f"[RePredict] Claude returned error for {mid}: {analysis.get('error', '')}")
                    except Exception as e:
                        logger.error(f"[RePredict] Claude failed for {mid}: {e}")

            repredict_status["completed"] += 1

        except Exception as e:
            repredict_status["failed"] += 1
            logger.error(f"[RePredict] Failed {mid}: {e}")

    was_cancelled = repredict_status.get("cancelled", False)
    repredict_status["running"] = False
    repredict_status["phase"] = "cancelled" if was_cancelled else "done"
    repredict_status["current_match"] = "Cancelled" if was_cancelled else "Done"
    logger.info(f"[RePredict] {'Cancelled' if was_cancelled else 'Complete'}: {repredict_status['completed']}/{repredict_status['total']} predicted, {repredict_status['failed']} failed")


@api_router.post("/predictions/repredict-all")
async def api_repredict_all(background_tasks: Any = None):
    """
    Trigger background re-prediction of ALL upcoming matches with fresh data.
    Includes Playing XI, expanded H2H/venue stats, and odds direction tracking.
    Returns immediately — poll /api/predictions/repredict-status for progress.
    """
    if repredict_status["running"]:
        return {"status": "already_running", "progress": repredict_status}

    asyncio.create_task(_background_repredict_all())
    return {"status": "started", "message": "Background re-prediction started. Poll /api/predictions/repredict-status for progress."}


@api_router.get("/predictions/repredict-status")
async def api_repredict_status():
    """Get the current status of the background re-prediction task."""
    return repredict_status


# ─── BACKGROUND CLAUDE-ONLY RE-RUN ──────────────────────────

claude_rerun_status = {"running": False, "total": 0, "completed": 0, "failed": 0, "current_match": "", "started_at": None, "phase": "", "cancelled": False}

async def _background_claude_rerun_all():
    """Background task: re-run Claude 7-layer analysis for ALL upcoming matches.
    Includes cancellation support and proper event-loop yielding."""
    global claude_rerun_status
    claude_rerun_status = {
        "running": True, "total": 0, "completed": 0, "failed": 0,
        "current_match": "", "started_at": datetime.now(timezone.utc).isoformat(),
        "phase": "starting", "cancelled": False
    }

    upcoming = []
    async for m in db.ipl_schedule.find(
        {"status": {"$regex": "upcoming|ns|not started", "$options": "i"}},
        {"_id": 0}
    ).sort("match_number", 1):
        upcoming.append(m)

    claude_rerun_status["total"] = len(upcoming)
    logger.info(f"[Claude Rerun] Starting for {len(upcoming)} upcoming matches")

    for i, match in enumerate(upcoming):
        # ── Check cancellation ──
        if claude_rerun_status.get("cancelled"):
            logger.info(f"[Claude Rerun] Cancelled at {i}/{len(upcoming)}")
            break

        # Yield generously between matches
        await asyncio.sleep(0.5)

        mid = match.get("matchId")
        team1 = match.get("team1", "")
        team2 = match.get("team2", "")
        venue = match.get("venue", "")
        t1_short = match.get("team1Short", get_short_name(team1))
        t2_short = match.get("team2Short", get_short_name(team2))

        claude_rerun_status["current_match"] = f"{t1_short} vs {t2_short}"
        claude_rerun_status["phase"] = f"claude {i+1}/{len(upcoming)}: {t1_short} vs {t2_short}"

        try:
            await db.claude_analysis.delete_one({"matchId": mid})

            xi_doc_r = await db.playing_xi.find_one({"matchId": mid}, {"_id": 0})
            match_squads = await _get_squads_for_match(team1, team2)
            playing_xi_squads = (
                _playing_xi_squads_from_doc(xi_doc_r, match_squads, team1, team2)
                if xi_doc_r
                else {}
            )
            algo_pred = await db.pre_match_predictions.find_one({"matchId": mid}, {"_id": 0})
            if (
                not playing_xi_squads
                or not algo_pred
                or not algo_pred.get("prediction")
            ):
                logger.warning(
                    f"[Claude Rerun] Skip {mid}: need playing_xi (11+11) + pre-match prediction first"
                )
                claude_rerun_status["failed"] += 1
                continue

            player_perf = {}
            try:
                t1p = await db.player_performance.find_one({"team": team1}, {"_id": 0})
                t2p = await db.player_performance.find_one({"team": team2}, {"_id": 0})
                if t1p:
                    player_perf["team1"] = t1p.get("players", t1p)
                if t2p:
                    player_perf["team2"] = t2p.get("players", t2p)
            except Exception:
                pass
            player_perf = _filter_player_performance_to_playing_xi(player_perf, playing_xi_squads)
            weather_data = None
            try:
                city_name = match.get("city", "") or (venue.split(",")[-1].strip() if venue else "")
                if city_name:
                    weather_data = await get_weather(city_name, match.get("dateTimeGMT"))
            except Exception:
                pass
            form_data = None
            try:
                form_data = await fetch_team_form(db, team1, team2, player_performance=player_perf)
            except Exception:
                pass
            if form_data:
                form_data = _filter_form_data_to_playing_xi(
                    form_data, playing_xi_squads, team1, team2
                )

            match_news = await fetch_match_news(team1, team2)
            news_for_claude = _filter_news_items_for_xi(
                match_news, team1, team2, playing_xi_squads
            )
            algo_for_claude = _scrub_algo_prediction_for_claude(
                algo_pred, playing_xi_squads, team1, team2
            )

            analysis = await claude_deep_match_analysis(
                team1, team2, venue, match, squads=playing_xi_squads, news=news_for_claude,
                algo_prediction=algo_for_claude, player_performance=player_perf,
                weather=weather_data, form_data=form_data,
            )

            # Yield after the heavy Claude call
            await asyncio.sleep(0.5)

            if analysis and "error" not in analysis:
                await db.claude_analysis.update_one(
                    {"matchId": mid},
                    {"$set": {
                        "matchId": mid, "team1": team1, "team2": team2,
                        "team1Short": t1_short, "team2Short": t2_short,
                        "venue": venue, "analysis": analysis,
                        "generatedAt": datetime.now(timezone.utc).isoformat(),
                        "model": "claude-opus-4.5",
                    }},
                    upsert=True,
                )
                logger.info(f"[Claude Rerun {i+1}/{len(upcoming)}] Done: {t1_short} vs {t2_short}")
            else:
                logger.warning(f"[Claude Rerun] Error for {mid}: {analysis.get('error', '')}")

            claude_rerun_status["completed"] += 1
        except Exception as e:
            logger.error(f"[Claude Rerun] Failed for {mid}: {e}")
            claude_rerun_status["failed"] += 1

    was_cancelled = claude_rerun_status.get("cancelled", False)
    claude_rerun_status["running"] = False
    claude_rerun_status["phase"] = "cancelled" if was_cancelled else "done"
    claude_rerun_status["current_match"] = "Cancelled" if was_cancelled else "Done"
    logger.info(f"[Claude Rerun] {'Cancelled' if was_cancelled else 'Complete'}: {claude_rerun_status['completed']}/{claude_rerun_status['total']}, {claude_rerun_status['failed']} failed")


@api_router.post("/predictions/claude-rerun-all")
async def api_claude_rerun_all():
    """Trigger background Claude 7-layer re-analysis for ALL upcoming matches."""
    if claude_rerun_status["running"]:
        return {"status": "already_running", "progress": claude_rerun_status}
    if repredict_status["running"]:
        return {"status": "repredict_running", "message": "Wait for Re-Predict All to finish first."}
    asyncio.create_task(_background_claude_rerun_all())
    return {"status": "started", "message": "Claude re-analysis started for all upcoming matches."}


@api_router.get("/predictions/claude-rerun-status")
async def api_claude_rerun_status():
    """Get the current status of the Claude re-run task."""
    return claude_rerun_status


@api_router.post("/predictions/claude-rerun-cancel")
async def api_claude_rerun_cancel():
    """Cancel the running Claude re-run task."""
    if not claude_rerun_status["running"]:
        return {"status": "not_running"}
    claude_rerun_status["cancelled"] = True
    return {"status": "cancelling", "message": "Claude re-run will stop after current match completes."}


@api_router.post("/predictions/repredict-cancel")
async def api_repredict_cancel():
    """Cancel the running Re-Predict All task."""
    if not repredict_status["running"]:
        return {"status": "not_running"}
    repredict_status["cancelled"] = True
    return {"status": "cancelling", "message": "Re-prediction will stop after current match completes."}

@api_router.get("/data-source")
async def api_data_source():
    return {"source": "Claude Opus + Web Scraping", "model": "claude-opus-4.5", "tool": "web_search + duckduckgo"}


# ─── CRICKETDATA.ORG LIVE API ────────────────────────────────

@api_router.post("/cricket-api/fetch-live")
async def api_cricdata_fetch_live():
    """
    Fetch live IPL 2026 match details from CricketData.org API.
    Manual trigger only — costs 1 API hit (100/day limit).
    """
    # Track usage in MongoDB
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = await db.api_usage.find_one({"date": today, "service": "cricketdata"}, {"_id": 0})

    if usage and usage.get("hits", 0) >= 100:
        return {
            "error": "Daily API limit reached (100/day). Try again tomorrow.",
            "api_usage": usage,
        }

    # Make the API call
    result = await fetch_live_ipl_details()

    if result.get("error"):
        return result

    # Update usage counter in MongoDB
    api_info = result.get("api_info", {})
    await db.api_usage.update_one(
        {"date": today, "service": "cricketdata"},
        {"$set": {
            "hits": api_info.get("hits_today", 0),
            "limit": api_info.get("hits_limit", 100),
            "remaining": api_info.get("hits_remaining", 100),
            "last_fetched": api_info.get("fetched_at"),
        }},
        upsert=True,
    )

    # Store live match data for quick access
    for match in result.get("matches", []):
        await db.cricdata_live.update_one(
            {"cricapi_id": match["cricapi_id"]},
            {"$set": {**match, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

    return result


@api_router.get("/cricket-api/usage")
async def api_cricdata_usage():
    """Get current API usage stats for CricketData.org."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = await db.api_usage.find_one({"date": today, "service": "cricketdata"}, {"_id": 0})
    if not usage:
        return {"date": today, "hits": 0, "limit": 100, "remaining": 100, "last_fetched": None}
    return usage


@api_router.get("/cricket-api/cached")
async def api_cricdata_cached():
    """Get cached live match data from last CricAPI fetch (no API hit)."""
    matches = []
    async for doc in db.cricdata_live.find({}, {"_id": 0}):
        matches.append(doc)
    return {"matches": matches, "count": len(matches), "source": "cache"}



@api_router.get("/cricket-api/venue/{venue_name}")
async def api_cricdata_venue(venue_name: str):
    """On-demand venue data from CricketData.org. Costs 1 API hit."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    usage = await db.api_usage.find_one({"date": today, "service": "cricketdata"}, {"_id": 0})
    if usage and usage.get("hits", 0) >= 100:
        return {"error": "Daily API limit reached (100/day)."}
    result = await fetch_venue_stats_from_cricapi(venue_name)
    if not result.get("error"):
        api_info = result.get("api_info", {})
        await db.api_usage.update_one(
            {"date": today, "service": "cricketdata"},
            {"$set": {"hits": api_info.get("hits_today", 0), "limit": 100,
                       "remaining": 100 - api_info.get("hits_today", 0),
                       "last_fetched": api_info.get("fetched_at")}},
            upsert=True,
        )
    return result


# ─── PLAYING XI (GPT Web Search) ────────────────────────────

# In-memory store for playing XI background tasks
playing_xi_tasks: Dict[str, Dict] = {}

async def _bg_fetch_playing_xi(match_id: str, team1: str, team2: str, venue: str):
    """Background task to fetch Expected Playing XI from SportMonks API (last match lineup).
    Falls back to squad-based estimate only if API returns no data."""
    playing_xi_tasks[match_id] = {"status": "running", "progress": "Fetching Playing XI from SportMonks API..."}
    try:
        # ── Step 1: Try API-verified Playing XI from last completed match ──
        from services.sportmonks_service import _season_fixtures_cache
        _season_fixtures_cache.clear()  # Fresh data on refresh

        t1_xi_raw = await fetch_last_played_xi(team1)
        t2_xi_raw = await fetch_last_played_xi(team2)

        xi_data = {}
        source = "api-verified"

        # Need both sides from last completed match; allow 5+ if SportMonks returns partial lineups
        min_xi = 5
        if t1_xi_raw and len(t1_xi_raw) >= min_xi and t2_xi_raw and len(t2_xi_raw) >= min_xi:
            # Prefer DB squads for role/buzz fields when names match; never drop SportMonks XI if squads missing or matching fails
            match_squads = await _get_squads_for_match(team1, team2)
            xi_sm_data = {"team1_playing_xi": t1_xi_raw, "team2_playing_xi": t2_xi_raw}
            filtered = (
                _filter_squads_to_playing_xi(match_squads, xi_sm_data, team1, team2)
                if match_squads and len(match_squads) >= 2
                else {}
            )
            t1_db = list(filtered.get(team1, []) or [])
            t2_db = list(filtered.get(team2, []) or [])
            roster1 = match_squads.get(team1, []) if match_squads else []
            roster2 = match_squads.get(team2, []) if match_squads else []
            t1_use = t1_db if len(t1_db) >= 8 else list(t1_xi_raw)
            t2_use = t2_db if len(t2_db) >= 8 else list(t2_xi_raw)
            t1_use = ensure_rr_vaibhav_in_playing_xi_rows(t1_use, team1, roster1)
            t2_use = ensure_rr_vaibhav_in_playing_xi_rows(t2_use, team2, roster2)
            xi_data = {
                "team1_xi": t1_use,
                "team2_xi": t2_use,
                "confidence": "api-verified",
                "source": "last_match",
            }
            logger.info(
                f"Playing XI refresh: last-match API {len(t1_xi_raw)}+{len(t2_xi_raw)} → display "
                f"{len(xi_data['team1_xi'])}+{len(xi_data['team2_xi'])} (DB merge={'yes' if filtered else 'no'})"
            )
        else:
            # Fallback: generate from full squad roster
            playing_xi_tasks[match_id]["progress"] = "API data insufficient, generating from squad roster..."
            match_squads = await _get_squads_for_match(team1, team2)
            squad_names = list(match_squads.keys()) if match_squads else []

            if len(squad_names) >= 2:
                t1_xi = generate_expected_xi(match_squads.get(team1, []))
                t2_xi = generate_expected_xi(match_squads.get(team2, []))
                t1_xi = ensure_rr_vaibhav_in_playing_xi_rows(t1_xi, team1, match_squads.get(team1, []))
                t2_xi = ensure_rr_vaibhav_in_playing_xi_rows(t2_xi, team2, match_squads.get(team2, []))
                xi_data = {
                    "team1_xi": t1_xi,
                    "team2_xi": t2_xi,
                    "confidence": "squad-based",
                    "source": "squad_estimate",
                }
                source = "squad-based"
                logger.info(f"Playing XI refresh: squad-based fallback {len(t1_xi)}+{len(t2_xi)} players")
            else:
                playing_xi_tasks[match_id] = {"status": "error", "error": "Squad data not available for both teams."}
                return

        xi_data["matchId"] = match_id
        xi_data["venue"] = venue
        xi_data["fetched_at"] = datetime.now(timezone.utc).isoformat()

        # Cache in DB
        await db.playing_xi.update_one(
            {"matchId": match_id},
            {"$set": {k: v for k, v in xi_data.items()}},
            upsert=True,
        )

        # Also update in cached prediction
        await db.pre_match_predictions.update_one(
            {"matchId": match_id},
            {"$set": {
                "playing_xi.team1_xi": xi_data.get("team1_xi", []),
                "playing_xi.team2_xi": xi_data.get("team2_xi", []),
                "playing_xi.confidence": xi_data.get("confidence", source),
                "playing_xi.source": xi_data.get("source", "last_match"),
            }}
        )

        playing_xi_tasks[match_id] = {"status": "done", "data": xi_data}
        logger.info(f"Playing XI refreshed for {match_id}: {len(xi_data.get('team1_xi', []))}+{len(xi_data.get('team2_xi', []))} players ({source})")
        asyncio.create_task(_bg_infer_claude_xi_roles(match_id, team1, team2))
    except Exception as e:
        logger.error(f"Playing XI fetch error for {match_id}: {e}")
        playing_xi_tasks[match_id] = {"status": "error", "error": str(e)}

@api_router.post("/matches/{match_id}/playing-xi")
async def api_fetch_playing_xi(match_id: str, background_tasks: BackgroundTasks = None):
    """Start Playing XI fetch in background. Returns immediately. Poll /playing-xi/status for results."""
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")

    # Check if already running
    task = playing_xi_tasks.get(match_id, {})
    if task.get("status") == "running":
        return {"status": "running", "message": "Playing XI fetch already in progress. Poll /playing-xi/status."}

    # Start background task
    asyncio.create_task(_bg_fetch_playing_xi(match_id, team1, team2, venue))
    playing_xi_tasks[match_id] = {"status": "running", "progress": "Starting web search..."}
    
    return {"status": "started", "message": "Playing XI fetch started. Poll /playing-xi/status for results."}

@api_router.get("/matches/{match_id}/playing-xi/status")
async def api_playing_xi_status(match_id: str):
    """Poll status of Playing XI background fetch."""
    task = playing_xi_tasks.get(match_id, {})
    status = task.get("status", "idle")
    
    if status == "done":
        data = task.get("data", {})
        playing_xi_tasks.pop(match_id, None)
        return data
    elif status == "error":
        error = task.get("error", "Unknown error")
        playing_xi_tasks.pop(match_id, None)
        return {"error": error, "team1_xi": [], "team2_xi": []}
    elif status == "running":
        return {"status": "running", "progress": task.get("progress", "Fetching...")}
    else:
        # Check DB for previously cached Playing XI
        cached = await db.playing_xi.find_one({"matchId": match_id}, {"_id": 0})
        if cached:
            return cached
        return {"status": "idle"}



# ─── CONSULTANT ENGINE ──────────────────────────────────────

@api_router.post("/matches/{match_id}/consult")
async def api_consult(match_id: str, body: ConsultRequest = None):
    """Run the full layered decision engine for a match."""
    if body is None:
        body = ConsultRequest()

    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")
    t1_short = match_info.get("team1Short", get_short_name(team1))
    t2_short = match_info.get("team2Short", get_short_name(team2))

    # Build snapshot from live state or defaults
    live_state = live_match_state.get(match_id)
    snapshot = {
        "match_id": match_id,
        "batting_team": team1,
        "bowling_team": team2,
        "team1": team1,
        "team2": team2,
        "team1Short": t1_short,
        "team2Short": t2_short,
        "venue": venue,
        "innings": 1,
        "over": 0,
        "ball": 0,
        "score": 0,
        "wickets_lost": 0,
        "balls_remaining": 120,
        "target": None,
        "venue_par_score": 165,
        "ball_history": [],
    }

    if live_state and live_state.get("liveData"):
        ld = live_state["liveData"]
        score = ld.get("score", {})
        if isinstance(score, dict):
            snapshot["score"] = score.get("runs", 0)
            snapshot["wickets_lost"] = score.get("wickets", 0)
            overs = score.get("overs", 0)
            snapshot["over"] = int(overs)
            snapshot["ball"] = int((overs % 1) * 10)
            snapshot["target"] = score.get("target")
        snapshot["innings"] = ld.get("innings", 1)
        if ld.get("battingTeam"):
            snapshot["batting_team"] = ld["battingTeam"]
        if ld.get("bowlingTeam"):
            snapshot["bowling_team"] = ld["bowlingTeam"]
        snapshot["balls_remaining"] = max(int((20 - overs) * 6), 0) if overs else 120
        snapshot["ball_history"] = live_state.get("ballHistory", [])
        if ld.get("batsmen"):
            snapshot["striker"] = ld["batsmen"][0] if ld["batsmen"] else {}
        if ld.get("bowler"):
            snapshot["bowler"] = ld["bowler"]

    # Get player predictions from Playing XI (cached prediction) instead of random squad
    player_preds = []
    cached_pred = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
    if cached_pred and cached_pred.get("playing_xi"):
        xi = cached_pred["playing_xi"]
        for team_key, team_name in [("team1_xi", team1), ("team2_xi", team2)]:
            for p in xi.get(team_key, []):
                player_preds.append({
                    "name": p.get("name", "Unknown"),
                    "team": team_name,
                    "role": p.get("role", "All-rounder"),
                    "predicted_runs": p.get("expected_runs", 15),
                    "predicted_wickets": p.get("expected_wickets", 0),
                    "predicted_sr": p.get("season_sr", 130),
                    "predicted_economy": p.get("season_economy", 8.0),
                    "confidence": max(0, min(1, (p.get("buzz_score", 0) + 100) / 200)),
                    "luck_bias": p.get("luck_factor", 1.0),
                    "venue_stats": p.get("venue_stats", {}),
                    "buzz_score": p.get("buzz_score", 0),
                    "buzz_reason": p.get("buzz_reason", ""),
                    "buzz_confidence": p.get("buzz_confidence", 50),
                })
    
    if not player_preds:
        # Fallback: fetch from squads
        sq1 = await db.ipl_squads.find_one({"teamShort": t1_short}, {"_id": 0})
        sq2 = await db.ipl_squads.find_one({"teamShort": t2_short}, {"_id": 0})
        t1_players = sq1.get("players", [])[:11] if sq1 else []
        t2_players = sq2.get("players", [])[:11] if sq2 else []
        player_stats = await fetch_player_stats_for_prediction(team1, team2, t1_players, t2_players, venue)
        if not player_stats:
            player_stats = _generate_default_player_stats(t1_players, t2_players, team1, team2)
        from services.beta_prediction_engine import predict_player_performance
        player_preds = [predict_player_performance(p) for p in player_stats]

    # Run consultation engine (market inputs are 0-100 percentages)
    # Pass the cached 11-factor prediction so the consultation uses it
    cached_11f_prediction = cached_pred.get("prediction") if cached_pred else None
    result = run_consultation(
        snapshot=snapshot,
        player_predictions=player_preds,
        team1_data={"name": team1, "rating": 55, "batting_depth": 7, "bowling_rating": 52},
        team2_data={"name": team2, "rating": 52, "batting_depth": 6, "bowling_rating": 50},
        market_pct_team1=body.market_pct_team1,
        market_pct_team2=body.market_pct_team2,
        risk_tolerance=body.risk_tolerance,
        odds_trend_increasing=body.odds_trend_increasing,
        odds_trend_decreasing=body.odds_trend_decreasing,
        cached_prediction=cached_11f_prediction,
    )

    result["team1Short"] = t1_short
    result["team2Short"] = t2_short
    return result



@api_router.get("/matches/{match_id}/claude-analysis")
async def get_claude_analysis(match_id: str):
    """Get cached Claude analysis (does not trigger new generation)."""
    cached = await db.claude_analysis.find_one({"matchId": match_id}, {"_id": 0})
    if cached and cached.get("analysis"):
        return cached
    return {"matchId": match_id, "analysis": None}


# ─── CLAUDE DEEP ANALYSIS ENDPOINT ───────────────────────────

@api_router.post("/matches/{match_id}/claude-analysis")
async def api_claude_analysis(match_id: str, background_tasks: BackgroundTasks = None):
    """Claude Opus 7-layer pre-match analysis with full SportMonks data + algorithm output."""
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    # Check cache first
    cached = await db.claude_analysis.find_one({"matchId": match_id}, {"_id": 0})
    if cached and cached.get("analysis"):
        return cached

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")

    # ── 1. Strict Expected XI from playing_xi collection (same gate as pre-match predict) ──
    xi_doc = await db.playing_xi.find_one({"matchId": match_id}, {"_id": 0})
    if not xi_doc or not _prematch_xi_complete(xi_doc):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "playing_xi_required",
                "message": (
                    "Claude pre-match analysis requires Expected Playing XI (11 per side). "
                    "Run “Fetch Playing XI”, then pre-match prediction, then try again."
                ),
            },
        )
    match_squads = await _get_squads_for_match(team1, team2)
    playing_xi_squads = _playing_xi_squads_from_doc(xi_doc, match_squads, team1, team2)
    if not playing_xi_squads:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "playing_xi_invalid",
                "message": "Could not build Playing XI from cache. Re-run “Fetch Playing XI” for this match.",
            },
        )

    # ── 2. Algorithm output must exist (computed only after Expected XI is present) ──
    algo_prediction = None
    try:
        algo_cached = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
        if algo_cached and algo_cached.get("prediction"):
            algo_prediction = algo_cached
            logger.info(f"Claude analysis enriched with algorithm prediction for {match_id}")
    except Exception as e:
        logger.warning(f"Failed to fetch algo prediction for Claude: {e}")
    if not algo_prediction or not algo_prediction.get("prediction"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "pre_match_required",
                "message": (
                    "Run pre-match prediction first (8-factor model). "
                    "It is only available after Expected Playing XI is generated."
                ),
            },
        )

    # ── 3. Fetch player performance stats from SportMonks ──
    player_performance = {}
    try:
        t1_perf = await db.player_performance.find_one({"team": team1}, {"_id": 0})
        t2_perf = await db.player_performance.find_one({"team": team2}, {"_id": 0})
        if t1_perf:
            player_performance["team1"] = t1_perf.get("players", t1_perf)
        if t2_perf:
            player_performance["team2"] = t2_perf.get("players", t2_perf)
    except Exception as e:
        logger.warning(f"Failed to fetch player performance for Claude: {e}")

    player_performance = _filter_player_performance_to_playing_xi(player_performance, playing_xi_squads)

    # ── 4. Fetch weather for venue ──
    weather = None
    try:
        city_name = match_info.get("city", "") or venue.split(",")[-1].strip() if venue else ""
        if city_name:
            weather = await get_weather(city_name, match_info.get("dateTimeGMT"))
    except Exception as e:
        logger.warning(f"Failed to fetch weather for Claude: {e}")

    # ── 5. Fetch form data (H2H, momentum) ──
    form_data = None
    try:
        form_data = await fetch_team_form(db, team1, team2, player_performance=player_performance)
    except Exception as e:
        logger.warning(f"Failed to fetch form data for Claude: {e}")
    if form_data:
        form_data = _filter_form_data_to_playing_xi(
            form_data, playing_xi_squads, team1, team2
        )

    # ── 6. Fetch news ──
    match_news = await fetch_match_news(team1, team2)
    news_for_claude = _filter_news_items_for_xi(
        match_news, team1, team2, playing_xi_squads
    )
    algo_for_claude = _scrub_algo_prediction_for_claude(
        algo_prediction, playing_xi_squads, team1, team2
    )

    impact_sub_history = {"team1": {}, "team2": {}}
    try:
        h1, h2 = await asyncio.gather(
            fetch_team_impact_sub_history(team1, 4),
            fetch_team_impact_sub_history(team2, 4),
            return_exceptions=True,
        )
        impact_sub_history = {
            "team1": h1 if not isinstance(h1, Exception) else {"team": team1, "error": str(h1)},
            "team2": h2 if not isinstance(h2, Exception) else {"team": team2, "error": str(h2)},
        }
    except Exception as e:
        logger.warning(f"Impact sub history fetch for Claude pre-match failed: {e}")

    # ── 7. Run Claude 7-layer analysis ──
    analysis = await claude_deep_match_analysis(
        team1, team2, venue, match_info,
        squads=playing_xi_squads,
        news=news_for_claude,
        algo_prediction=algo_for_claude,
        player_performance=player_performance,
        weather=weather,
        form_data=form_data,
        impact_sub_history=impact_sub_history,
    )

    # Cache in DB
    result = {
        "matchId": match_id,
        "team1": team1,
        "team2": team2,
        "team1Short": match_info.get("team1Short", get_short_name(team1)),
        "team2Short": match_info.get("team2Short", get_short_name(team2)),
        "venue": venue,
        "analysis": analysis,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "model": "claude-opus-4.5",
        "data_sources": {
            "has_algo": bool(algo_prediction),
            "has_player_perf": bool(player_performance.get("team1") or player_performance.get("team2")),
            "has_weather": bool(weather and weather.get("available")),
            "has_form": bool(form_data),
            "has_news": bool(match_news),
            "has_impact_sub_history": bool(
                (impact_sub_history.get("team1") or {}).get("fixtures")
                or (impact_sub_history.get("team2") or {}).get("fixtures")
            ),
        }
    }
    await db.claude_analysis.update_one(
        {"matchId": match_id},
        {"$set": result},
        upsert=True
    )
    return result


@api_router.delete("/matches/{match_id}/claude-analysis")
async def api_clear_claude_analysis(match_id: str):
    """Clear cached Claude analysis to force re-generation."""
    await db.claude_analysis.delete_one({"matchId": match_id})
    return {"status": "cleared"}


# ─── CLAUDE LIVE ANALYSIS ENDPOINT ───────────────────────────

@api_router.post("/matches/{match_id}/claude-live")
async def api_claude_live(match_id: str):
    """Claude Opus real-time analysis during a live match."""
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    live_state = live_match_state.get(match_id)
    if not live_state:
        db_snapshot = await db.live_snapshots.find_one({"matchId": match_id}, {"_id": 0})
        if db_snapshot:
            live_state = db_snapshot

    if not live_state:
        return {"error": "No live data available. Fetch live scores first."}

    sm_data = (
        live_state.get("sportmonks")
        or live_state.get("sportmonksData")
        or live_state.get("sm_data")
        or {}
    )
    if not _sm_playing_xi_complete(sm_data if isinstance(sm_data, dict) else {}):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "playing_xi_required",
                "message": "Full Playing XI for both teams is required. Fetch live scores when SportMonks lineups are available.",
            },
        )

    algo_probs = live_state.get("probabilities", {})
    live_data = live_state.get("liveData", {})

    match_squads = await _get_squads_for_match(
        match_info.get("team1", ""), match_info.get("team2", "")
    )
    # ── Filter to Playing XI for Claude live analysis ──
    live_squads = _filter_squads_to_playing_xi(
        match_squads, sm_data, match_info.get("team1", ""), match_info.get("team2", "")
    )
    xi_for_live = None
    try:
        xi_for_live = await db.playing_xi.find_one({"matchId": match_id}, {"_id": 0})
    except Exception:
        xi_for_live = None

    impact_sub_history = {"team1": {}, "team2": {}}
    try:
        t1n = match_info.get("team1", "")
        t2n = match_info.get("team2", "")
        h1, h2 = await asyncio.gather(
            fetch_team_impact_sub_history(t1n, 4),
            fetch_team_impact_sub_history(t2n, 4),
            return_exceptions=True,
        )
        impact_sub_history = {
            "team1": h1 if not isinstance(h1, Exception) else {"team": t1n, "error": str(h1)},
            "team2": h2 if not isinstance(h2, Exception) else {"team": t2n, "error": str(h2)},
        }
    except Exception as e:
        logger.warning(f"Impact sub history for Claude live failed: {e}")

    analysis = await claude_live_analysis(
        match_info,
        live_data,
        algo_probs,
        squads=live_squads,
        sm_data=sm_data if isinstance(sm_data, dict) else None,
        playing_xi_doc=xi_for_live,
        impact_sub_history=impact_sub_history,
    )

    return {
        "matchId": match_id,
        "analysis": analysis,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "model": "claude-opus-4.5",
    }



@api_router.post("/matches/{match_id}/chat")
async def api_chat(match_id: str, body: ChatRequest):
    """GPT-powered consultation chat — answers user questions in layman language."""
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")
    t1_short = match_info.get("team1Short", get_short_name(team1))
    t2_short = match_info.get("team2Short", get_short_name(team2))

    # Build snapshot from live state (in-memory or from DB)
    live_state = live_match_state.get(match_id)
    if not live_state:
        # Fallback: load from DB snapshot (survives server restarts)
        db_snapshot = await db.live_snapshots.find_one({"matchId": match_id}, {"_id": 0})
        if db_snapshot:
            live_state = db_snapshot
            live_match_state[match_id] = db_snapshot  # Cache for subsequent calls
    snapshot = {
        "match_id": match_id, "batting_team": team1, "bowling_team": team2,
        "team1": team1, "team2": team2, "team1Short": t1_short, "team2Short": t2_short,
        "venue": venue,
        "innings": 1, "over": 0, "ball": 0, "score": 0, "wickets_lost": 0,
        "balls_remaining": 120, "target": None, "venue_par_score": 165,
        "ball_history": [],
    }
    if live_state and live_state.get("liveData"):
        ld = live_state["liveData"]
        score = ld.get("score", {})
        if isinstance(score, dict):
            snapshot["score"] = score.get("runs", 0)
            snapshot["wickets_lost"] = score.get("wickets", 0)
            overs = score.get("overs", 0)
            snapshot["over"] = int(overs)
            snapshot["ball"] = int((overs % 1) * 10)
            snapshot["target"] = score.get("target")
        snapshot["innings"] = ld.get("innings", 1)
        snapshot["balls_remaining"] = max(int((20 - overs) * 6), 0) if overs else 120

    # Quick consultation (no player stats fetch for speed)
    cached_pred = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
    cached_11f = cached_pred.get("prediction") if cached_pred else None
    result = run_consultation(
        snapshot=snapshot,
        market_pct_team1=body.market_pct_team1,
        market_pct_team2=body.market_pct_team2,
        risk_tolerance=body.risk_tolerance,
        cached_prediction=cached_11f,
    )

    # Build rich live context for GPT from fetched live data + algo outputs
    live_context = _build_live_chat_context(live_state) if live_state else None

    # GPT answer with enriched context
    answer = await gpt_consultation(body.question, result, body.risk_tolerance, live_context=live_context)

    return {
        "question": body.question,
        "answer": answer,
        "risk_tolerance": body.risk_tolerance,
        "consultation_summary": {
            "win_probability": result["win_probability"],
            "value_signal": result["value_signal"],
            "edge_pct": result.get("edge_pct"),
            "confidence": result["confidence"],
            "fair_odds": result["fair_decimal_odds"],
        },
    }


def _build_live_chat_context(live_state: Dict) -> str:
    """Build a rich text context from live match state + algorithm outputs for GPT chat."""
    parts = []

    # Score
    ld = live_state.get("liveData", {})
    score = ld.get("score", {})
    if isinstance(score, dict) and score.get("runs") is not None:
        parts.append(f"CURRENT SCORE: {score.get('runs', 0)}/{score.get('wickets', 0)} in {score.get('overs', 0)} overs (Innings {ld.get('innings', 1)})")
        if score.get("target"):
            parts.append(f"TARGET: {score['target']}")

    # Batsmen on field
    batsmen = live_state.get("batsmen", [])
    if batsmen:
        bat_lines = []
        for b in batsmen:
            name = b.get("name", "Unknown")
            runs = b.get("runs", 0)
            balls = b.get("balls", 0)
            sr = b.get("strikeRate") or b.get("strike_rate", 0)
            fours = b.get("fours", 0)
            sixes = b.get("sixes", 0)
            bat_lines.append(f"  {name}: {runs}({balls}) SR:{sr} 4s:{fours} 6s:{sixes}")
        parts.append("BATSMEN AT CREASE:\n" + "\n".join(bat_lines))

    # Yet to bat
    ytb = live_state.get("yetToBat", [])
    if ytb:
        names = [p.get("name", "?") for p in ytb]
        parts.append(f"YET TO BAT: {', '.join(names)}")

    # Bowler
    bowler = live_state.get("bowler", {})
    if bowler and bowler.get("name"):
        parts.append(f"CURRENT BOWLER: {bowler['name']} — {bowler.get('wickets', 0)}/{bowler.get('runs', 0)} ({bowler.get('overs', 0)} ov) Econ: {bowler.get('economy', 0)}")

    # Yet to bowl
    ytbowl = live_state.get("yetToBowl", [])
    if ytbowl:
        names = [p.get("name", "?") for p in ytbowl]
        parts.append(f"YET TO BOWL: {', '.join(names)}")

    # Full bowling card
    fbc = live_state.get("fullBowlingCard", [])
    if fbc:
        bowl_lines = [f"  {bw.get('name','?')}: {bw.get('overs',0)}-{bw.get('maidens',0)}-{bw.get('runs',0)}-{bw.get('wickets',0)} Econ:{bw.get('economy',0)}" for bw in fbc]
        parts.append("ALL BOWLERS:\n" + "\n".join(bowl_lines))

    # Claude prediction
    cp = live_state.get("claudePrediction", {})
    if cp and not cp.get("error"):
        parts.append(f"CLAUDE PREDICTION: {cp.get('headline', '')} Winner: {cp.get('predicted_winner', '')} ({cp.get('win_pct', 50)}%) Confidence: {cp.get('confidence', 'N/A')}")
        if cp.get("reasoning"):
            parts.append(f"CLAUDE REASONING: {cp['reasoning']}")

    # Algorithm probabilities
    probs = live_state.get("probabilities", {})
    if probs:
        parts.append(f"ALGORITHM PROBABILITIES: Ensemble={probs.get('ensemble', 0)*100:.1f}%, "
                     f"Bayesian={probs.get('bayesian', 0)*100:.1f}%, "
                     f"Poisson={probs.get('poisson', 0)*100:.1f}%, "
                     f"DLS={probs.get('dls', 0)*100:.1f}%, "
                     f"Momentum={probs.get('momentum', 0)*100:.1f}%")
        if probs.get("projected_score"):
            parts.append(f"PROJECTED SCORE: ~{round(probs['projected_score'])}")

    # Live prediction (batsmen impact, phase, chase analysis)
    lp = live_state.get("live_prediction", {})
    if lp:
        parts.append(f"LIVE PREDICTION: {lp.get('summary', '')}")
        parts.append(f"PHASE: {lp.get('phase', 'unknown')} | WIN PROB: {lp.get('win_probability', 0)}% ({lp.get('batting_team', '')})")
        parts.append(f"CRR: {lp.get('crr', 0)} | WICKETS IN HAND: {lp.get('wickets_in_hand', 0)}")

        if lp.get("projected_score"):
            parts.append(f"LIVE PROJECTED SCORE: ~{lp['projected_score']}")

        chase = lp.get("chase_analysis")
        if chase:
            parts.append(f"CHASE ANALYSIS: Need {chase.get('runs_remaining', 0)} off {chase.get('balls_remaining', 0)} balls, "
                         f"RRR: {chase.get('required_rate', 0)}, Difficulty: {chase.get('difficulty', 'unknown')}")

        bat_on_field = lp.get("batsmen_on_field", [])
        if bat_on_field:
            for b in bat_on_field:
                set_tag = " (SET)" if b.get("is_set") else ""
                parts.append(f"  BATSMAN IMPACT: {b.get('name', '')}{set_tag} — {b.get('runs', 0)}({b.get('balls', 0)}) SR:{b.get('sr', 0)} Impact:{b.get('impact', 'low')}")

        cb = lp.get("current_bowler")
        if cb:
            parts.append(f"  BOWLER IMPACT: {cb.get('name', '')} — {cb.get('wickets', 0)}/{cb.get('runs', 0)} ({cb.get('overs', 0)}ov) Impact:{cb.get('impact', 'low')}")

    # Betting edge
    edge = live_state.get("bettingEdge", {})
    t1_edge = edge.get("team1")
    t2_edge = edge.get("team2")
    if t1_edge:
        parts.append(f"BETTING EDGE {live_state.get('team1Short', 'T1')}: Market={t1_edge.get('market_implied', 0)}% Model={t1_edge.get('model_prob', 0)}% Edge={t1_edge.get('edge', 0)}%")
    if t2_edge:
        parts.append(f"BETTING EDGE {live_state.get('team2Short', 'T2')}: Market={t2_edge.get('market_implied', 0)}% Model={t2_edge.get('model_prob', 0)}% Edge={t2_edge.get('edge', 0)}%")

    # AI prediction summary
    ai = live_state.get("aiPrediction", {})
    if ai and ai.get("analysis"):
        parts.append(f"AI ANALYSIS: {ai['analysis']}")

    # Last ball commentary
    commentary = live_state.get("lastBallCommentary", "")
    if commentary:
        parts.append(f"LAST BALL: {commentary}")

    return "\n".join(parts)


# ─── BETA PREDICTION ENGINE ──────────────────────────────────

@api_router.post("/matches/{match_id}/beta-predict")
async def api_beta_predict(match_id: str, body: BetaPredictRequest = None):
    """Full beta prediction: Poisson, Player Engine, 10K Monte Carlo, Odds, Alerts."""
    if body is None:
        body = BetaPredictRequest()

    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")
    t1_short = match_info.get("team1Short", get_short_name(team1))
    t2_short = match_info.get("team2Short", get_short_name(team2))

    # Get squads
    sq1 = await db.ipl_squads.find_one({"teamShort": t1_short}, {"_id": 0})
    sq2 = await db.ipl_squads.find_one({"teamShort": t2_short}, {"_id": 0})
    t1_players = sq1.get("players", [])[:11] if sq1 else []
    t2_players = sq2.get("players", [])[:11] if sq2 else []

    # Get live state if available
    live_state = live_match_state.get(match_id)
    runs = 0
    wickets = 0
    overs = 0.0
    target = None
    innings = 1
    ball_history = []

    if live_state and live_state.get("liveData"):
        score = live_state["liveData"].get("score", {})
        if isinstance(score, dict):
            runs = score.get("runs", 0)
            wickets = score.get("wickets", 0)
            overs = score.get("overs", 0)
            target = score.get("target")
        innings = live_state["liveData"].get("innings", 1)
        ball_history = live_state.get("ballHistory", [])

    # Fetch player stats via GPT-5.4 web search
    logger.info(f"Beta predict: fetching player stats for {team1} vs {team2}")
    player_stats = await fetch_player_stats_for_prediction(
        team1, team2, t1_players, t2_players, venue
    )

    if not player_stats:
        logger.warning("No player stats returned, using defaults")
        player_stats = _generate_default_player_stats(t1_players, t2_players, team1, team2)

    # Convert 0-100 pct to decimal odds for beta prediction engine
    beta_market_t1_odds = round(1 / max(0.01, body.market_team1_pct / 100), 2) if body.market_team1_pct else None
    beta_market_t2_odds = round(1 / max(0.01, body.market_team2_pct / 100), 2) if body.market_team2_pct else None

    # Run beta prediction engine
    result = run_beta_prediction(
        player_predictions=player_stats,
        team1_name=team1,
        team2_name=team2,
        runs=runs,
        wickets=wickets,
        overs=overs,
        target=target,
        innings=innings,
        venue_avg=165,
        ball_history=ball_history,
        market_team1_odds=beta_market_t1_odds,
        market_team2_odds=beta_market_t2_odds,
    )

    # GPT-5.4 mini contextual analysis
    score_summary = f"{runs}/{wickets} in {overs} overs"
    if target:
        score_summary += f" (target: {target})"

    gpt_context = await gpt_contextual_analysis(
        result["match_context"], team1, team2,
        score_summary, result["alerts"]
    )

    result["gpt_analysis"] = gpt_context
    result["matchId"] = match_id
    result["team1"] = team1
    result["team2"] = team2
    result["team1Short"] = t1_short
    result["team2Short"] = t2_short
    result["venue"] = venue
    result["fetchedAt"] = datetime.now(timezone.utc).isoformat()

    return result


def _generate_default_player_stats(t1_players, t2_players, team1, team2):
    """Generate sensible default player stats when web search fails."""
    defaults = {
        "Batsman": {"runs": 28, "wickets": 0.1, "sr": 135, "econ": 0, "consistency": 0.65},
        "Bowler": {"runs": 8, "wickets": 1.5, "sr": 110, "econ": 7.5, "consistency": 0.6},
        "All-rounder": {"runs": 18, "wickets": 1.0, "sr": 125, "econ": 8.0, "consistency": 0.6},
        "Wicketkeeper": {"runs": 25, "wickets": 0, "sr": 128, "econ": 0, "consistency": 0.65},
    }
    result = []
    for players, team in [(t1_players, team1), (t2_players, team2)]:
        for p in (players or [])[:11]:
            role = p.get("role", "All-rounder")
            d = defaults.get(role, defaults["All-rounder"])
            result.append({
                "name": p.get("name", "Player"),
                "team": team,
                "role": role,
                "last5_avg_runs": d["runs"],
                "venue_avg_runs": d["runs"] * 0.9,
                "opponent_adj_runs": d["runs"] * 0.85,
                "form_momentum_runs": d["runs"] * 1.1,
                "last5_avg_wickets": d["wickets"],
                "venue_avg_wickets": d["wickets"] * 0.9,
                "opponent_adj_wickets": d["wickets"] * 0.85,
                "form_momentum_wickets": d["wickets"],
                "predicted_sr": d["sr"],
                "predicted_economy": d["econ"],
                "consistency": d["consistency"],
            })
    return result


# ─── WEBSOCKET ────────────────────────────────────────────────

@api_router.websocket("/ws/{match_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str):
    await websocket.accept()
    ws_connections.setdefault(match_id, []).append(websocket)
    logger.info(f"WS connected: {match_id}")
    try:
        cached = live_match_state.get(match_id)
        if cached:
            await websocket.send_json({"type": "LIVE_UPDATE", **cached})
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "PING":
                await websocket.send_json({"type": "PONG"})
            elif msg.get("type") == "REQUEST_UPDATE":
                cached = live_match_state.get(match_id)
                if cached:
                    await websocket.send_json({"type": "LIVE_UPDATE", **cached})
    except WebSocketDisconnect:
        ws_connections[match_id].remove(websocket)
    except Exception as e:
        logger.error(f"WS error: {e}")
        if websocket in ws_connections.get(match_id, []):
            ws_connections[match_id].remove(websocket)

async def broadcast_update(match_id, data):
    if match_id not in ws_connections:
        return
    payload = {"type": "LIVE_UPDATE", **data}
    dead = []
    for ws in ws_connections[match_id]:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_connections[match_id].remove(ws)


# ─── MATCH SCHEDULER (4PM & 7PM IST) ─────────────────────────

async def promote_matches_to_live():
    """Move today's upcoming matches to 'live' status at scheduled times (4PM & 7PM IST)."""
    now_ist = datetime.now(IST)
    today_date = now_ist.date()

    logger.info(f"[Scheduler] Checking for matches to promote to LIVE at {now_ist.strftime('%I:%M %p IST')}")

    matches = await db.ipl_schedule.find(
        {"status": {"$in": ["upcoming", "scheduled", "Upcoming", "Scheduled"]}},
        {"_id": 0}
    ).to_list(100)

    promoted = 0
    for m in matches:
        # Check dateTimeGMT field (ISO format: "2026-04-04T14:00:00Z")
        dt_gmt = m.get("dateTimeGMT") or m.get("date") or ""
        if not dt_gmt:
            continue
        try:
            if isinstance(dt_gmt, str):
                match_dt = datetime.fromisoformat(dt_gmt.replace("Z", "+00:00"))
            else:
                match_dt = dt_gmt
            match_date_ist = match_dt.astimezone(IST).date()
        except (ValueError, TypeError):
            continue

        if match_date_ist == today_date:
            await db.ipl_schedule.update_one(
                {"matchId": m["matchId"]},
                {"$set": {"status": "live", "promotedAt": datetime.now(timezone.utc).isoformat()}}
            )
            promoted += 1
            logger.info(f"[Scheduler] Promoted {m.get('team1', '')} vs {m.get('team2', '')} ({m['matchId']}) to LIVE")

    if promoted == 0:
        logger.info(f"[Scheduler] No matches to promote today ({today_date})")
    else:
        logger.info(f"[Scheduler] Promoted {promoted} match(es) to LIVE")


async def auto_scrape_live_matches():
    """Background job: Auto-scrape live match scores from CricketData.org API every 5 minutes."""
    logger.info("[Auto-Scrape] Running background live match scrape...")
    live_matches = await db.ipl_schedule.find(
        {"status": "live"},
        {"_id": 0}
    ).to_list(20)

    if not live_matches:
        logger.info("[Auto-Scrape] No live matches to scrape")
        return

    cricapi_result = await fetch_live_ipl_details()
    if not cricapi_result.get("matches"):
        logger.info("[Auto-Scrape] CricAPI returned no live matches")
        return

    updated = 0
    for match in live_matches:
        mid = match.get("matchId")
        team1 = match.get("team1", "")
        team2 = match.get("team2", "")
        t1_short = match.get("team1Short", get_short_name(team1))

        for api_match in cricapi_result["matches"]:
            m_t1 = (api_match.get("team1", "") or "").lower()
            m_t2 = (api_match.get("team2", "") or "").lower()
            t1_low = team1.lower()
            t2_low = team2.lower()
            # Match both teams: check team1↔m_t1 AND team2↔m_t2 (or swapped)
            def _words_match(a, b):
                a_words = [w for w in a.split() if len(w) > 3 and w not in ("super", "kings")]
                return any(w in b for w in a_words)
            fwd = (_words_match(t1_low, m_t1) or _words_match(m_t1, t1_low)) and \
                  (_words_match(t2_low, m_t2) or _words_match(m_t2, t2_low))
            rev = (_words_match(t1_low, m_t2) or _words_match(m_t2, t1_low)) and \
                  (_words_match(t2_low, m_t1) or _words_match(m_t1, t2_low))
            if fwd or rev:
                cs = api_match.get("current_score", {})
                runs = cs.get("runs", 0)
                wickets = cs.get("wickets", 0)
                overs_val = cs.get("overs", 0)

                score_text = f"{t1_short} {runs}/{wickets} ({overs_val} ov)"
                await db.ipl_schedule.update_one(
                    {"matchId": mid},
                    {"$set": {
                        "score": score_text,
                        "liveScore": {"runs": runs, "wickets": wickets, "overs": overs_val},
                        "lastAutoScrapedAt": datetime.now(timezone.utc).isoformat(),
                    }}
                )
                updated += 1
                logger.info(f"[Auto-Scrape] Updated {team1} vs {team2}: {score_text}")
                break

    logger.info(f"[Auto-Scrape] Updated {updated} of {len(live_matches)} live matches")


async def auto_sync_results_and_invalidate():
    """Background job: Auto-sync results from SportMonks, invalidate stale predictions,
    and clear caches when new match results are detected.
    Only syncs matches whose date has already passed (prevents future contamination)."""
    logger.info("[Auto-Sync] Checking for new match results...")
    try:
        results = await fetch_recent_fixtures()
        if not results:
            return

        now = datetime.now(timezone.utc)
        schedule_matches = await db.ipl_schedule.find({}, {"_id": 0}).to_list(2000)

        synced = 0
        for result in results:
            sm_t1 = (result.get("team1", "") or "").lower()
            sm_t2 = (result.get("team2", "") or "").lower()
            winner = result.get("winner", "")
            if not winner:
                continue

            for match in schedule_matches:
                # GUARD: Skip future matches
                dt_str = match.get("dateTimeGMT", "")
                if dt_str:
                    try:
                        match_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        if match_dt.tzinfo is None:
                            match_dt = match_dt.replace(tzinfo=timezone.utc)
                        if match_dt > now:
                            continue
                    except (ValueError, TypeError):
                        pass

                db_t1 = (match.get("team1", "") or "").lower()
                db_t2 = (match.get("team2", "") or "").lower()
                t1_words = [w for w in sm_t1.split() if len(w) > 3]
                t2_words = [w for w in sm_t2.split() if len(w) > 3]
                db_t1_match = any(w in db_t1 for w in t1_words)
                db_t2_match = any(w in db_t2 for w in t2_words)
                if db_t1_match and db_t2_match and not match.get("winner"):
                    db_winner = None
                    winner_lower = winner.lower()
                    for tf in ["team1", "team2"]:
                        dt = (match.get(tf, "") or "").lower()
                        if any(w in dt for w in winner_lower.split() if len(w) > 3):
                            db_winner = match.get(tf)
                            break
                    if db_winner:
                        await db.ipl_schedule.update_one(
                            {"matchId": match.get("matchId")},
                            {"$set": {"winner": db_winner, "status": "completed",
                                      "result": result.get("note", ""),
                                      "team1_score": result.get("team1_score", ""),
                                      "team2_score": result.get("team2_score", ""),
                                      "toss_won_by": result.get("toss_won_by", "")}}
                        )
                        synced += 1
                        await _invalidate_team_predictions(match.get("team1", ""), match.get("team2", ""))
                        logger.info(f"[Auto-Sync] Synced {match.get('matchId')} winner: {db_winner}")
                    break

        if synced > 0:
            from services.sportmonks_service import _season_fixtures_cache
            _season_fixtures_cache.clear()
            logger.info(f"[Auto-Sync] Synced {synced} results, cleared caches")
    except Exception as e:
        logger.error(f"[Auto-Sync] Error: {e}")


# ─── STARTUP ─────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    global _scheduler_started, scheduler
    logger.info("Predictability starting up...")
    if ENABLE_BACKGROUND_SCHEDULERS:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = AsyncIOScheduler(timezone=IST)
        scheduler.add_job(promote_matches_to_live, CronTrigger(hour=16, minute=0), id="promote_4pm", replace_existing=True)
        scheduler.add_job(promote_matches_to_live, CronTrigger(hour=19, minute=0), id="promote_7pm", replace_existing=True)
        scheduler.add_job(auto_scrape_live_matches, "interval", minutes=5, id="auto_scrape", replace_existing=True)
        scheduler.add_job(auto_sync_results_and_invalidate, "interval", minutes=30, id="auto_sync_results", replace_existing=True)
        scheduler.start()
        _scheduler_started = True
        logger.info("[Scheduler] Started — promote 4PM/7PM IST, auto-scrape 5m, result sync 30m")
    else:
        logger.info(
            "Background schedulers OFF (default). Set ENABLE_BACKGROUND_SCHEDULERS=true for cron jobs. "
            "Live scores / fixture sync use explicit API routes only."
        )

@app.on_event("shutdown")
async def shutdown():
    if _scheduler_started and scheduler is not None:
        scheduler.shutdown(wait=False)
    client.close()

app.include_router(api_router)

_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()] or ["*"]
_cors_allow_credentials = os.environ.get("CORS_ALLOW_CREDENTIALS", "true").lower() in ("1", "true", "yes")
if "*" in _cors_origins:
    _cors_allow_credentials = False  # Browsers forbid credentials with wildcard origin

app.add_middleware(
    CORSMiddleware,
    allow_credentials=_cors_allow_credentials,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
