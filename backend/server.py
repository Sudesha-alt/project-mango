from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks, Body
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import pytz

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

IST = pytz.timezone("Asia/Kolkata")

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
    claude_sportmonks_prediction
)
from services.sportmonks_service import fetch_live_match, check_fixture_status, fetch_livescores_ipl, parse_fixture, fetch_fixture_details, fetch_recent_fixtures, fetch_last_played_xi, fetch_playing_xi_from_live
from services.beta_prediction_engine import run_beta_prediction
from services.consultant_engine import run_consultation, build_features
from services.cricdata_service import fetch_live_ipl_details, fetch_venue_stats_from_cricapi
from services.pre_match_predictor import compute_prediction
from services.live_predictor import compute_live_prediction, compute_combined_prediction, detect_match_phase
from services.weather_service import fetch_weather_for_venue
from services.schedule_data import get_schedule_documents, TEAM_SHORT_CODES, CITY_STADIUMS
from services.web_scraper import fetch_match_news
from services.form_service import fetch_team_form, fetch_momentum, generate_expected_xi

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]


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
        "scheduler": {"active": scheduler.running, "next_runs": ["4:00 PM IST", "7:00 PM IST"]},
        "serverTime": now_ist,
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
    snapshots = await db.live_snapshots.find({}, {"_id": 0, "matchId": 1, "liveData": 1, "team1Short": 1}).to_list(100)
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
        await db.ipl_schedule.update_one(
            {"matchId": mid},
            {"$set": {
                "score": score_text,
                "liveScore": {"runs": runs, "wickets": wickets, "overs": overs, "target": target, "innings": innings},
            }}
        )


# ─── IPL SCHEDULE (AI-powered + cached in MongoDB) ──────────

@api_router.get("/schedule/load")
async def load_ipl_schedule(force: bool = False):
    """Load IPL 2026 schedule using GPT and store in MongoDB."""
    existing = await db.ipl_schedule.count_documents({})
    if existing > 0 and not force:
        return {"status": "already_loaded", "count": existing}
    logger.info("Fetching IPL 2026 schedule via GPT...")
    matches = await fetch_ipl_schedule()
    if matches:
        # Resolve TBD venues
        tbd_count = sum(1 for m in matches if not m.get("venue") or m.get("venue") == "TBD")
        if tbd_count > 0:
            logger.info(f"Resolving {tbd_count} TBD venues...")
            matches = await resolve_tbd_venues(matches)
        await db.ipl_schedule.delete_many({})
        for m in matches:
            m["loadedAt"] = datetime.now(timezone.utc).isoformat()
        await db.ipl_schedule.insert_many(matches)
        return {"status": "loaded", "count": len(matches)}
    return {"status": "error", "count": 0}


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
    """Fetch actual match results from SportMonks and update DB schedule with winners."""
    results = await fetch_recent_fixtures()
    if not results:
        return {"status": "no_results", "message": "No completed fixtures found from SportMonks"}

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

            # Check if both teams match (order-independent)
            t1_words = [w for w in sm_t1.split() if len(w) > 3]
            t2_words = [w for w in sm_t2.split() if len(w) > 3]
            db_t1_match = any(w in db_t1 for w in t1_words) or any(w in sm_t1 for w in db_t1.split() if len(w) > 3)
            db_t2_match = any(w in db_t2 for w in t2_words) or any(w in sm_t2 for w in db_t2.split() if len(w) > 3)

            fwd = db_t1_match and db_t2_match
            rev_t1_match = any(w in db_t1 for w in t2_words) or any(w in sm_t2 for w in db_t1.split() if len(w) > 3)
            rev_t2_match = any(w in db_t2 for w in t1_words) or any(w in sm_t1 for w in db_t2.split() if len(w) > 3)
            rev = rev_t1_match and rev_t2_match

            if (fwd or rev) and match.get("status", "").lower() != "upcoming":
                # Match found - update with result
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
                break

    return {"status": "synced", "updated": updated, "total_fixtures": len(results)}



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
        try:
            match_date = dt_gmt[:10]  # Extract YYYY-MM-DD
        except Exception:
            pass

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

@api_router.get("/schedule")
async def get_schedule():
    """Get the full IPL 2026 schedule from MongoDB."""
    matches = await db.ipl_schedule.find({}, {"_id": 0}).sort("match_number", 1).to_list(100)
    if not matches:
        return {"matches": [], "loaded": False}

    # Auto-classify based on both status field AND date
    # CRITICAL: Date always overrides DB status for future matches
    now = datetime.now(timezone.utc)
    live = []
    upcoming = []
    completed = []
    for m in matches:
        status_lower = m.get("status", "").lower()
        dt_str = m.get("dateTimeGMT", "")
        match_dt = None
        if dt_str:
            try:
                match_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except Exception:
                pass

        # Future-dated match = always upcoming (regardless of DB status)
        if match_dt and match_dt > now:
            upcoming.append(m)
        elif status_lower in ["live", "in progress"]:
            live.append(m)
        elif match_dt and (now - match_dt).total_seconds() > 6 * 3600:
            # Match date passed > 6 hours ago → completed
            completed.append(m)
        elif status_lower in ["completed", "result"]:
            completed.append(m)
        else:
            upcoming.append(m)

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
    """Button-triggered: Fetch live data via SportMonks API + Claude win prediction."""
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
            try: ball_obj["runs"] = int(b)
            except: pass
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

    # ── Fetch weather for venue ──
    match_city = match_info.get("city", "")
    if not match_city and venue:
        match_city = venue.split(",")[-1].strip() if "," in venue else venue
    match_weather = await fetch_weather_for_venue(match_city) if match_city else None

    # ── Fetch news for match context ──
    match_news = await fetch_match_news(team1, team2)

    # ── Claude Win Prediction (pass full SportMonks data + squads + weather + news + user context) ──
    claude_prediction = None
    if sm_data:
        claude_prediction = await claude_sportmonks_prediction(
            sm_data, probs, match_info, squads=match_squads, weather=match_weather, news=match_news,
            gut_feeling=body.gut_feeling, betting_odds_pct=body.current_betting_odds
        )

    # ── Apply Claude's CONTEXTUAL ADJUSTMENT to the algo baseline ──
    # Claude no longer produces direct win %. Instead it produces a +/- adjustment
    # that gets applied on top of the algorithm's structural baseline.
    if claude_prediction and not claude_prediction.get("error"):
        adjustment = claude_prediction.get("contextual_adjustment_pct", 0)
        try:
            adjustment = float(adjustment)
        except (TypeError, ValueError):
            adjustment = 0.0
        adjustment = max(-30, min(30, adjustment))  # Cap at +/- 30%

        algo_t1_pct = probs.get("ensemble", 0.5) * 100
        # Apply adjustment: positive favours team1, negative favours team2
        adjusted_t1_pct = algo_t1_pct + adjustment
        adjusted_t1_pct = max(1, min(99, adjusted_t1_pct))
        adjusted_t2_pct = 100 - adjusted_t1_pct

        claude_prediction["team1_win_pct"] = round(adjusted_t1_pct, 1)
        claude_prediction["team2_win_pct"] = round(adjusted_t2_pct, 1)
        claude_prediction["algo_baseline_t1_pct"] = round(algo_t1_pct, 1)
        claude_prediction["adjustment_applied"] = round(adjustment, 1)

        # Update ensemble with the adjusted probability
        probs["ensemble"] = round(adjusted_t1_pct / 100, 4)
        probs["source"] = "algo+claude_adjustment"
        # Recalculate odds from adjusted probability
        team1_odds = calculate_odds_from_probability(probs["ensemble"])
        team2_odds = calculate_odds_from_probability(1 - probs["ensemble"])

    # ── Weighted Probability Prediction (6-Factor Live Model) ──
    # Fetch pre-match base probability and playing XI as anchors
    pre_match_cached = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
    pre_match_prob = pre_match_cached.get("prediction", {}).get("team1_win_prob") if pre_match_cached else None
    cached_xi = pre_match_cached.get("playing_xi") if pre_match_cached else None
    weighted_pred = compute_live_prediction(sm_data, claude_prediction, match_info, pre_match_prob=pre_match_prob, xi_data=cached_xi) if sm_data else None

    # ── Phase-Based Combined Prediction (Algo vs Claude dynamic blend) ──
    combined_pred = compute_combined_prediction(
        algo_pred=weighted_pred,
        claude_pred=claude_prediction,
        sm_data=sm_data,
        gut_feeling=body.gut_feeling,
        betting_odds_pct=body.current_betting_odds,
    ) if (weighted_pred or claude_prediction) else None

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


@api_router.post("/matches/{match_id}/refresh-claude-prediction")
async def refresh_claude_prediction(match_id: str):
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
    t1_short = cached.get("team1Short", "T1")
    t2_short = cached.get("team2Short", "T2")
    old_probs = cached.get("probabilities", {})

    match_squads = await _get_squads_for_match(
        match_info.get("team1", ""), match_info.get("team2", "")
    )
    # Fetch weather for Claude context
    refresh_city = match_info.get("city", "")
    if not refresh_city:
        v = match_info.get("venue", "")
        refresh_city = v.split(",")[-1].strip() if "," in v else v
    refresh_weather = await fetch_weather_for_venue(refresh_city) if refresh_city else None
    # Fetch news for Claude context
    refresh_news = await fetch_match_news(match_info.get("team1", ""), match_info.get("team2", ""))
    claude_prediction = await claude_sportmonks_prediction(
        sm_data, old_probs, match_info, squads=match_squads, weather=refresh_weather, news=refresh_news
    )

    if claude_prediction and not claude_prediction.get("error"):
        claude_t1 = claude_prediction.get(f"{t1_short}_win_pct")
        claude_t2 = claude_prediction.get(f"{t2_short}_win_pct")
        if claude_t1 is None:
            winner = claude_prediction.get("predicted_winner", "")
            win_pct = claude_prediction.get("win_pct", 50)
            if winner == t1_short:
                claude_t1, claude_t2 = win_pct, 100 - win_pct
            else:
                claude_t2, claude_t1 = win_pct, 100 - win_pct
        claude_t1 = float(claude_t1 or 50)
        claude_t2 = float(claude_t2 or 50)
        claude_prediction["team1_win_pct"] = round(claude_t1, 1)
        claude_prediction["team2_win_pct"] = round(claude_t2, 1)

        # Update cached state
        new_probs = {**old_probs, "ensemble": round(claude_t1 / 100, 4), "source": "claude"}
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
    weighted_pred = compute_live_prediction(sm_data, claude_prediction, match_info, pre_match_prob=pre_match_prob) if sm_data else None
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

    return {
        "matchId": match_id,
        "claudePrediction": claude_prediction,
        "weightedPrediction": weighted_pred,
        "combinedPrediction": combined_pred,
        "probabilities": cached.get("probabilities", {}),
        "refreshedAt": datetime.now(timezone.utc).isoformat(),
    }



@api_router.post("/matches/{match_id}/check-status")
async def check_match_status(match_id: str):
    """Check if a match is still live, finished, or not found on SportMonks.
    If finished, mark it as 'completed' in the schedule."""
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found in schedule"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")

    result = await check_fixture_status(team1, team2)

    # If match is finished, update schedule to "completed"
    if result.get("is_finished"):
        update = {
            "status": "completed",
            "completedAt": datetime.now(timezone.utc).isoformat(),
        }
        if result.get("winner"):
            update["winner"] = result["winner"]
        if result.get("note"):
            update["result"] = result["note"]
        await db.ipl_schedule.update_one({"matchId": match_id}, {"$set": update})
        logger.info(f"Match {match_id} marked completed: {result.get('note')}")

    return {
        "matchId": match_id,
        "sportmonks_status": result.get("status"),
        "is_live": result.get("is_live", False),
        "is_finished": result.get("is_finished", False),
        "winner": result.get("winner"),
        "note": result.get("note", ""),
        "schedule_status": "completed" if result.get("is_finished") else match_info.get("status"),
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
            # Promote to live if not already
            if matched.get("status") != "live":
                score_text = ""
                if sm.get("inn1_runs") is not None:
                    score_text = f"{sm['team1']} {sm.get('inn1_runs',0)}/{sm.get('inn1_wickets',0)} ({sm.get('inn1_overs',0)} ov)"
                if sm.get("inn2_runs") is not None:
                    score_text += f" | {sm['team2']} {sm.get('inn2_runs',0)}/{sm.get('inn2_wickets',0)} ({sm.get('inn2_overs',0)} ov)"
                await db.ipl_schedule.update_one({"matchId": mid}, {"$set": {
                    "status": "live",
                    "score": score_text or sm.get("note", ""),
                    "sportmonks_fixture_id": sm.get("fixture_id"),
                }})
                newly_promoted.append({"matchId": mid, "team1": matched["team1"], "team2": matched["team2"], "status": sm.get("status"), "score": score_text})
                logger.info(f"Match {mid} promoted to live via SportMonks: {matched['team1']} vs {matched['team2']}")
            else:
                still_live.append({"matchId": mid, "team1": matched["team1"], "team2": matched["team2"], "status": sm.get("status"), "note": sm.get("note")})

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
        return result

    cached = await db.live_snapshots.find_one({"matchId": match_id}, {"_id": 0})
    if cached:
        # Merge schedule info into cached state
        if schedule_info:
            for key in ("city", "timeIST", "match_number", "series"):
                if key in schedule_info and key not in cached:
                    cached[key] = schedule_info[key]
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
        return cached
    return {"matchId": match_id, "prediction": None}


@api_router.post("/matches/{match_id}/pre-match-predict")
async def api_pre_match_predict(match_id: str, force: bool = False):
    """
    Predict upcoming match winner using 8-category algorithm.
    NO web scraping. Uses DB squads, SportMonks form data, Open-Meteo weather.
    Also generates Expected Playing XI from squad roster.
    """
    cached = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
    if cached and not force:
        return cached

    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")
    t1_short = match_info.get("team1Short", get_short_name(team1))
    t2_short = match_info.get("team2Short", get_short_name(team2))

    logger.info(f"Pre-match predict: {team1} vs {team2} at {venue}")

    # Fetch squads from DB (user-provided IPL 2026 rosters)
    match_squads = await _get_squads_for_match(team1, team2)

    # ── Fetch ACTUAL Playing XI from SportMonks API ──
    # Try live match first, then last completed match per team
    api_xi_data = {"team1_xi": [], "team2_xi": [], "source": "none"}
    try:
        live_xi = await fetch_playing_xi_from_live(team1, team2)
        if live_xi.get("team1_xi") and live_xi.get("team2_xi"):
            api_xi_data = live_xi
            logger.info(f"Got Playing XI from LIVE match: {len(live_xi['team1_xi'])} + {len(live_xi['team2_xi'])}")
        else:
            # Fetch last played XI for each team separately
            t1_xi = await fetch_last_played_xi(team1)
            t2_xi = await fetch_last_played_xi(team2)
            if t1_xi or t2_xi:
                api_xi_data = {
                    "team1_xi": t1_xi,
                    "team2_xi": t2_xi,
                    "source": "last_match",
                }
                logger.info(f"Got Playing XI from last matches: {len(t1_xi)} + {len(t2_xi)}")
    except Exception as e:
        logger.warning(f"Failed to fetch Playing XI from API: {e}")

    # ── Filter squad to Playing XI if API data available ──
    # This ensures predictions use actual 11 players, not 25-man squad
    prediction_squads = match_squads  # Default: full squad
    xi_data = {}
    squad_names = list(match_squads.keys()) if match_squads else []

    if api_xi_data.get("team1_xi") and api_xi_data.get("team2_xi") and len(squad_names) >= 2:
        # Cross-reference API XI names with DB squad for role/stats
        t1_api_names = {p["name"].lower() for p in api_xi_data["team1_xi"]}
        t2_api_names = {p["name"].lower() for p in api_xi_data["team2_xi"]}

        t1_filtered = [p for p in match_squads.get(squad_names[0], [])
                       if p.get("name", "").lower() in t1_api_names]
        t2_filtered = [p for p in match_squads.get(squad_names[1], [])
                       if p.get("name", "").lower() in t2_api_names]

        # Only use filtered if we got at least 8 matches (name matching tolerance)
        if len(t1_filtered) >= 8 and len(t2_filtered) >= 8:
            prediction_squads = {
                squad_names[0]: t1_filtered,
                squad_names[1]: t2_filtered,
            }
            logger.info(f"Using API Playing XI: {len(t1_filtered)} + {len(t2_filtered)} players")
        else:
            logger.warning(f"API XI match too low ({len(t1_filtered)}, {len(t2_filtered)}), using full squad")

        xi_data = {
            "team1_xi": [{"name": p.get("name"), "role": p.get("role", ""),
                          "isCaptain": p.get("isCaptain", False)} for p in t1_filtered] if t1_filtered else
                        api_xi_data["team1_xi"],
            "team2_xi": [{"name": p.get("name"), "role": p.get("role", ""),
                          "isCaptain": p.get("isCaptain", False)} for p in t2_filtered] if t2_filtered else
                        api_xi_data["team2_xi"],
            "source": api_xi_data.get("source", "api"),
            "confidence": "api-verified",
        }
    elif len(squad_names) >= 2:
        # Fallback: generate expected XI from squad roster
        t1_xi = generate_expected_xi(match_squads.get(squad_names[0], []))
        t2_xi = generate_expected_xi(match_squads.get(squad_names[1], []))
        xi_data = {
            "team1_xi": t1_xi,
            "team2_xi": t2_xi,
            "source": "squad_estimate",
            "confidence": "squad-based",
        }

    # Fetch weather for venue (Open-Meteo, free)
    prematch_city = match_info.get("city", "")
    if not prematch_city and venue:
        prematch_city = venue.split(",")[-1].strip() if "," in venue else venue
    match_date_str = match_info.get("dateTimeGMT", "")[:10] if match_info.get("dateTimeGMT") else None
    prematch_weather = await fetch_weather_for_venue(prematch_city, match_date_str) if prematch_city else {}

    # Fetch form data from DB completed matches
    form_data = await fetch_team_form(db, team1, team2)

    # Fetch momentum (last 2 results)
    momentum_data = await fetch_momentum(db, team1, team2)

    # Run 8-category algorithm (no scraping)
    prediction = compute_prediction(
        squad_data=match_squads,
        match_info=match_info,
        weather=prematch_weather,
        form_data=form_data,
        momentum_data=momentum_data,
    )

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
        predictions.append(doc)
    return {"predictions": predictions, "count": len(predictions)}


# ─── BACKGROUND RE-PREDICTION ────────────────────────────────

repredict_status = {"running": False, "total": 0, "completed": 0, "failed": 0, "current_match": "", "started_at": None}

async def _background_repredict_all():
    """Background task: re-predict all upcoming matches with 8-category model + Claude + Expected XI."""
    global repredict_status
    repredict_status["running"] = True
    repredict_status["completed"] = 0
    repredict_status["failed"] = 0
    repredict_status["started_at"] = datetime.now(timezone.utc).isoformat()

    upcoming = []
    async for doc in db.ipl_schedule.find({"status": "Upcoming"}, {"_id": 0}).sort("match_number", 1):
        upcoming.append(doc)
    repredict_status["total"] = len(upcoming)

    for match in upcoming:
        mid = match.get("matchId", "")
        team1 = match.get("team1", "")
        team2 = match.get("team2", "")
        t1_short = match.get("team1Short", get_short_name(team1))
        t2_short = match.get("team2Short", get_short_name(team2))
        repredict_status["current_match"] = f"{t1_short} vs {t2_short}"

        try:
            # Run algorithm prediction (reuses api_pre_match_predict with force=True)
            result = await api_pre_match_predict(mid, force=True)
            if result and "error" not in result:
                repredict_status["completed"] += 1
                logger.info(f"[RePredict {repredict_status['completed']}/{repredict_status['total']}] {t1_short} vs {t2_short} done")
            else:
                repredict_status["failed"] += 1
        except Exception as e:
            repredict_status["failed"] += 1
            logger.error(f"[RePredict] Failed {mid}: {e}")

    # Also trigger Claude analysis for next 3 upcoming matches
    try:
        next_3 = upcoming[:3]
        for match in next_3:
            mid = match.get("matchId", "")
            team1 = match.get("team1", "")
            team2 = match.get("team2", "")
            venue = match.get("venue", "")
            match_squads = await _get_squads_for_match(team1, team2)
            match_news = await fetch_match_news(team1, team2)
            try:
                analysis = await claude_deep_match_analysis(team1, team2, venue, match, squads=match_squads, news=match_news)
                if analysis and "error" not in analysis:
                    await db.claude_analysis.update_one(
                        {"matchId": mid},
                        {"$set": {"matchId": mid, "analysis": analysis, "updatedAt": datetime.now(timezone.utc).isoformat()}},
                        upsert=True,
                    )
                    logger.info(f"[RePredict] Claude analysis done for {mid}")
            except Exception as e:
                logger.error(f"[RePredict] Claude failed for {mid}: {e}")
    except Exception as e:
        logger.error(f"[RePredict] Claude batch failed: {e}")

    repredict_status["running"] = False
    repredict_status["current_match"] = "Done"
    logger.info(f"[RePredict] Complete: {repredict_status['completed']} predicted, {repredict_status['failed']} failed")


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


# ─── DATA SOURCE INFO ────────────────────────────────────────

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
    """Background task to generate Expected Playing XI from squad roster (NO scraping)."""
    playing_xi_tasks[match_id] = {"status": "running", "progress": "Generating from official squad roster..."}
    try:
        match_squads = await _get_squads_for_match(team1, team2)
        squad_names = list(match_squads.keys()) if match_squads else []

        xi_data = {}
        if len(squad_names) >= 2:
            t1_xi = generate_expected_xi(match_squads.get(squad_names[0], []))
            t2_xi = generate_expected_xi(match_squads.get(squad_names[1], []))
            xi_data = {
                "team1_xi": t1_xi,
                "team2_xi": t2_xi,
                "confidence": "squad-based",
            }
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
                "playing_xi.confidence": xi_data.get("confidence", "squad-based"),
            }}
        )

        playing_xi_tasks[match_id] = {"status": "done", "data": xi_data}
        logger.info(f"Playing XI generated for {match_id}: {len(xi_data.get('team1_xi', []))}+{len(xi_data.get('team2_xi', []))} players")
    except Exception as e:
        logger.error(f"Playing XI generation error for {match_id}: {e}")
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
        # Clear after retrieval
        playing_xi_tasks.pop(match_id, None)
        return data
    elif status == "error":
        error = task.get("error", "Unknown error")
        playing_xi_tasks.pop(match_id, None)
        return {"error": error, "team1_xi": [], "team2_xi": []}
    elif status == "running":
        return {"status": "running", "progress": task.get("progress", "Fetching...")}
    else:
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
    """Claude Opus deep narrative match analysis with real-time web data."""
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

    # Run Claude deep analysis (this takes time due to web scraping + Claude)
    match_squads = await _get_squads_for_match(team1, team2)
    # Fetch news for Claude context
    match_news = await fetch_match_news(team1, team2)
    analysis = await claude_deep_match_analysis(team1, team2, venue, match_info, squads=match_squads, news=match_news)

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

    algo_probs = live_state.get("probabilities", {})
    live_data = live_state.get("liveData", {})

    match_squads = await _get_squads_for_match(
        match_info.get("team1", ""), match_info.get("team2", "")
    )
    analysis = await claude_live_analysis(match_info, live_data, algo_probs, squads=match_squads)

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

scheduler = AsyncIOScheduler(timezone=IST)

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


# ─── STARTUP ─────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("Predictability starting up...")
    # Schedule match promotion at 4:00 PM and 7:00 PM IST daily
    scheduler.add_job(promote_matches_to_live, CronTrigger(hour=16, minute=0), id="promote_4pm", replace_existing=True)
    scheduler.add_job(promote_matches_to_live, CronTrigger(hour=19, minute=0), id="promote_7pm", replace_existing=True)
    # Auto-scrape live matches every 5 minutes during match hours (2PM-11PM IST)
    scheduler.add_job(auto_scrape_live_matches, "interval", minutes=5, id="auto_scrape", replace_existing=True)
    scheduler.start()
    logger.info("[Scheduler] Started — promote at 4PM/7PM, auto-scrape every 5 min")
    # Sync any existing live scores to schedule on startup
    await sync_live_scores_to_schedule()

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown(wait=False)
    client.close()

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
