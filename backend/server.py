from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from services.cricket_service import get_short_name
from services.probability_engine import (
    ensemble_probability, calculate_odds_from_probability,
    calculate_momentum, calculate_betting_edge
)
from services.ai_service import (
    fetch_ipl_schedule, fetch_ipl_squads, fetch_live_match_update,
    get_match_prediction, get_player_predictions,
    fetch_player_stats_for_prediction, gpt_contextual_analysis,
    gpt_consultation, fetch_pre_match_stats
)
from services.beta_prediction_engine import run_beta_prediction
from services.consultant_engine import run_consultation, build_features
from services.cricdata_service import fetch_live_ipl_details, fetch_venue_stats_from_cricapi
from services.pre_match_predictor import compute_prediction
from services.ai_service import fetch_playing_xi, resolve_tbd_venues

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]


def apply_buzz_and_luck(xi_data: dict) -> dict:
    """
    Apply buzz sentiment and luck factor to player base stats.
    Formula: expected = base * (1 + buzz_modifier) * luck_factor
    buzz_score: -100 to +100 → buzz_modifier: -0.20 to +0.20
    luck_factor: random ±15%
    """
    import random
    for team_key in ["team1_xi", "team2_xi"]:
        for player in xi_data.get(team_key, []):
            buzz_score = player.get("buzz_score", 0)
            # Clamp buzz to [-100, +100]
            buzz_score = max(-100, min(100, buzz_score))
            # Map buzz to ±20% modifier
            buzz_modifier = buzz_score / 500.0  # -100→-0.20, +100→+0.20
            luck_factor = random.uniform(0.85, 1.15)

            base_runs = player.get("base_expected_runs") or player.get("expected_runs", 15)
            base_wickets = player.get("base_expected_wickets") or player.get("expected_wickets", 0)

            adjusted_runs = base_runs * (1 + buzz_modifier) * luck_factor
            adjusted_wickets = base_wickets * (1 + buzz_modifier) * random.uniform(0.85, 1.15)

            player["expected_runs"] = round(max(0, adjusted_runs), 1)
            player["expected_wickets"] = round(max(0, adjusted_wickets), 1)
            player["luck_factor"] = round(luck_factor, 3)
            player["buzz_modifier"] = round(buzz_modifier, 3)

            # Backward compat: keep buzz_confidence as abs(buzz_score) mapped to 0-100
            player["buzz_confidence"] = abs(buzz_score)
    return xi_data

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ws_connections: Dict[str, List[WebSocket]] = {}
live_match_state: Dict[str, Any] = {}


# ─── HEALTH & STATUS ─────────────────────────────────────────

@api_router.get("/")
async def root():
    schedule_count = await db.ipl_schedule.count_documents({})
    squad_count = await db.ipl_squads.count_documents({})
    return {
        "message": "Gamble Consultant API",
        "version": "4.0.0",
        "dataSource": "GPT-5.4 Web Search",
        "scheduleLoaded": schedule_count > 0,
        "squadsLoaded": squad_count > 0,
        "matchesInDB": schedule_count,
        "squadsInDB": squad_count,
    }


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

@api_router.get("/schedule")
async def get_schedule():
    """Get the full IPL 2026 schedule from MongoDB."""
    matches = await db.ipl_schedule.find({}, {"_id": 0}).sort("match_number", 1).to_list(100)
    if not matches:
        return {"matches": [], "loaded": False}
    live = [m for m in matches if m.get("status", "").lower() in ["live", "in progress"]]
    upcoming = [m for m in matches if m.get("status", "").lower() in ["upcoming", "scheduled"]]
    completed = [m for m in matches if m.get("status", "").lower() in ["completed", "result"]]
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

@api_router.post("/matches/{match_id}/fetch-live")
async def fetch_live_data(match_id: str, body: FetchLiveRequest = None):
    """Button-triggered: Fetch live data via GPT-5.4 web search."""
    if body is None:
        body = FetchLiveRequest()

    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found in schedule"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")

    logger.info(f"Fetching live data via web search: {team1} vs {team2}")
    gpt_data = await fetch_live_match_update(match_info)

    if not gpt_data:
        return {"error": "Could not fetch live data from web search"}

    # Handle "no live match" scenario
    if gpt_data.get("noLiveMatch"):
        return {
            "matchId": match_id,
            "team1": team1, "team1Short": get_short_name(team1),
            "team2": team2, "team2Short": get_short_name(team2),
            "venue": venue,
            "noLiveMatch": True,
            "isLive": False,
            "status": gpt_data.get("status", "This match is not live right now"),
            "liveData": gpt_data,
            "source": "web_search",
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
        }

    live_data = gpt_data
    live_data["source"] = "web_search"
    source = "web_search"

    # Parse score
    score = live_data.get("score", {})
    runs = score.get("runs", 0) if isinstance(score, dict) else 0
    wickets = score.get("wickets", 0) if isinstance(score, dict) else 0
    overs = score.get("overs", 0) if isinstance(score, dict) else 0
    target = score.get("target") if isinstance(score, dict) else None
    innings = live_data.get("innings", 1)

    # Build ball objects from recentBalls
    recent_balls = live_data.get("recentBalls", [])
    ball_objects = []
    for b in recent_balls:
        ball_obj = {"runs": 0, "isWicket": False, "isWide": False, "isNoBall": False}
        if b == "W":
            ball_obj["isWicket"] = True
        elif b == "WD":
            ball_obj["isWide"] = True
            ball_obj["runs"] = 1
        elif b == "NB":
            ball_obj["isNoBall"] = True
            ball_obj["runs"] = 1
        elif b in ["0", "\u2022"]:
            ball_obj["runs"] = 0
        else:
            try:
                ball_obj["runs"] = int(b)
            except (ValueError, TypeError):
                pass
        ball_objects.append(ball_obj)

    # Convert 0-100 pct inputs to decimal odds for probability engine
    odds_team_a = None
    if body.betting_team1_pct and body.betting_team2_pct:
        t1_prob = max(0.01, body.betting_team1_pct / 100)
        t2_prob = max(0.01, body.betting_team2_pct / 100)
        total_implied = t1_prob + t2_prob
        odds_team_a = t1_prob / total_implied  # normalized
        if body.betting_confidence is not None:
            confidence = body.betting_confidence / 100
            odds_team_a = odds_team_a * confidence + 0.5 * (1 - confidence)

    # Compute decimal odds from pct for edge detection
    betting_t1_decimal = round(1 / max(0.01, body.betting_team1_pct / 100), 2) if body.betting_team1_pct else None
    betting_t2_decimal = round(1 / max(0.01, body.betting_team2_pct / 100), 2) if body.betting_team2_pct else None

    # Run all 4 algorithms + ensemble with ball history and odds
    probs = ensemble_probability(runs, wickets, overs, target, innings,
                                  odds_team_a, ball_objects, venue_avg=165)
    team1_odds = calculate_odds_from_probability(probs["ensemble"])
    team2_odds = calculate_odds_from_probability(1 - probs["ensemble"])

    # Calculate betting edge
    edge_team1 = None
    edge_team2 = None
    if betting_t1_decimal:
        edge_team1 = calculate_betting_edge(probs["ensemble"], betting_t1_decimal)
    if betting_t2_decimal:
        edge_team2 = calculate_betting_edge(1 - probs["ensemble"], betting_t2_decimal)

    # Get AI prediction
    ai_pred = await get_match_prediction({
        "matchId": match_id, "team1": team1, "team2": team2,
        "venue": venue, "score": score
    })

    result = {
        "matchId": match_id,
        "team1": team1, "team1Short": get_short_name(team1),
        "team2": team2, "team2Short": get_short_name(team2),
        "venue": venue,
        "liveData": live_data,
        "probabilities": probs,
        "odds": {"team1": team1_odds, "team2": team2_odds},
        "bettingEdge": {"team1": edge_team1, "team2": edge_team2},
        "bettingInput": {
            "team1Pct": body.betting_team1_pct,
            "team2Pct": body.betting_team2_pct,
            "confidence": body.betting_confidence,
        },
        "aiPrediction": ai_pred,
        "momentum": calculate_momentum(ball_objects),
        "ballHistory": ball_objects,
        "batsmen": live_data.get("batsmen", []),
        "bowler": live_data.get("bowler", {}),
        "fallOfWickets": live_data.get("fallOfWickets", []),
        "lastBallCommentary": live_data.get("lastBallCommentary", ""),
        "source": source,
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
    }

    live_match_state[match_id] = result
    await db.live_snapshots.update_one(
        {"matchId": match_id},
        {"$set": {**{k: v for k, v in result.items()}, "updatedAt": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    if match_id in ws_connections and ws_connections[match_id]:
        await broadcast_update(match_id, result)

    return result


@api_router.get("/matches/{match_id}/state")
async def get_match_state(match_id: str):
    """Get last known state of a live match."""
    if match_id in live_match_state:
        return live_match_state[match_id]
    cached = await db.live_snapshots.find_one({"matchId": match_id}, {"_id": 0})
    if cached:
        return cached
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    return {"matchId": match_id, "info": match_info, "noLiveData": True}


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

@api_router.post("/matches/{match_id}/pre-match-predict")
async def api_pre_match_predict(match_id: str, force: bool = False):
    """
    Predict upcoming match winner using H2H, venue, form, squad algorithms.
    Fetches real stats via GPT-5.4 web search, stores result in DB.
    Also fetches Playing XI with expected performance and luck biasness.
    Tracks odds direction (trend) vs previous prediction.
    """
    # Check if we already have a prediction stored
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

    # Fetch real stats via GPT web search
    logger.info(f"Pre-match predict: {team1} vs {team2} at {venue}")
    stats = await fetch_pre_match_stats(team1, team2, venue)

    # Fetch Playing XI with expected performance + buzz sentiment + luck biasness
    xi_data = await fetch_playing_xi(team1, team2, venue)
    xi_data = apply_buzz_and_luck(xi_data)

    # Run algorithm stack with player-level data
    prediction = compute_prediction(stats, playing_xi=xi_data)

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

    # Store previous prediction in history before overwriting
    if cached:
        await db.prediction_history.insert_one({
            "matchId": match_id,
            "prediction": cached.get("prediction"),
            "computed_at": cached.get("computed_at"),
            "superseded_at": datetime.now(timezone.utc).isoformat(),
        })

    # Build result
    result = {
        "matchId": match_id,
        "team1": team1,
        "team2": team2,
        "team1Short": t1_short,
        "team2Short": t2_short,
        "venue": venue,
        "dateTimeGMT": match_info.get("dateTimeGMT", ""),
        "match_number": match_info.get("match_number"),
        "prediction": prediction,
        "stats": stats,
        "playing_xi": {
            "team1_xi": xi_data.get("team1_xi", []),
            "team2_xi": xi_data.get("team2_xi", []),
            "confidence": xi_data.get("confidence", "unavailable"),
        },
        "odds_direction": odds_direction,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Store in DB
    await db.pre_match_predictions.update_one(
        {"matchId": match_id},
        {"$set": result},
        upsert=True,
    )
    logger.info(f"Stored prediction for {match_id}: {t1_short} {prediction['team1_win_prob']}% vs {t2_short} {prediction['team2_win_prob']}% [dir: {odds_direction['team1']}]")

    return result


@api_router.post("/schedule/predict-upcoming")
async def api_predict_upcoming(force: bool = False):
    """
    Batch predict all upcoming matches.
    If force=true, re-predicts all matches with fresh data (Playing XI + expanded stats).
    Runs sequentially (each takes ~15-30s due to web search).
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

        # Run prediction for this match (with Playing XI + odds direction)
        try:
            team1 = match.get("team1", "")
            team2 = match.get("team2", "")
            venue = match.get("venue", "")
            t1_short = match.get("team1Short", get_short_name(team1))
            t2_short = match.get("team2Short", get_short_name(team2))

            # Get previous prediction for odds direction
            import random
            cached = await db.pre_match_predictions.find_one({"matchId": mid}, {"_id": 0})

            stats = await fetch_pre_match_stats(team1, team2, venue)

            # Fetch Playing XI with buzz sentiment + luck
            xi_data = await fetch_playing_xi(team1, team2, venue)
            xi_data = apply_buzz_and_luck(xi_data)

            prediction = compute_prediction(stats, playing_xi=xi_data)

            # Odds direction
            odds_direction = {"team1": "new", "team2": "new"}
            if cached:
                old_t1 = cached.get("prediction", {}).get("team1_win_prob", 50)
                new_t1 = prediction["team1_win_prob"]
                diff = round(new_t1 - old_t1, 1)
                if diff > 0.5:
                    odds_direction = {"team1": "up", "team2": "down", "team1_change": diff, "team2_change": round(-diff, 1), "previous_team1_prob": old_t1, "previous_team2_prob": cached.get("prediction", {}).get("team2_win_prob", 50)}
                elif diff < -0.5:
                    odds_direction = {"team1": "down", "team2": "up", "team1_change": diff, "team2_change": round(-diff, 1), "previous_team1_prob": old_t1, "previous_team2_prob": cached.get("prediction", {}).get("team2_win_prob", 50)}
                else:
                    odds_direction = {"team1": "stable", "team2": "stable", "team1_change": diff, "team2_change": round(-diff, 1), "previous_team1_prob": old_t1, "previous_team2_prob": cached.get("prediction", {}).get("team2_win_prob", 50)}
                # Archive old prediction
                await db.prediction_history.insert_one({
                    "matchId": mid, "prediction": cached.get("prediction"),
                    "computed_at": cached.get("computed_at"),
                    "superseded_at": datetime.now(timezone.utc).isoformat(),
                })

            result = {
                "matchId": mid,
                "team1": team1, "team2": team2,
                "team1Short": t1_short, "team2Short": t2_short,
                "venue": venue,
                "dateTimeGMT": match.get("dateTimeGMT", ""),
                "match_number": match.get("match_number"),
                "prediction": prediction,
                "stats": stats,
                "playing_xi": {
                    "team1_xi": xi_data.get("team1_xi", []),
                    "team2_xi": xi_data.get("team2_xi", []),
                    "confidence": xi_data.get("confidence", "unavailable"),
                },
                "odds_direction": odds_direction,
                "computed_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.pre_match_predictions.update_one(
                {"matchId": mid}, {"$set": result}, upsert=True
            )
            predictions.append(result)
            new_count += 1
            logger.info(f"Predicted {mid}: {t1_short} {prediction['team1_win_prob']}% vs {t2_short} [dir: {odds_direction['team1']}]")
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
    """Background task: re-predict all upcoming matches with fresh data + Playing XI."""
    import random
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
        venue = match.get("venue", "")
        t1_short = match.get("team1Short", get_short_name(team1))
        t2_short = match.get("team2Short", get_short_name(team2))
        repredict_status["current_match"] = f"{t1_short} vs {t2_short}"

        try:
            # Get old prediction for odds direction
            cached = await db.pre_match_predictions.find_one({"matchId": mid}, {"_id": 0})

            stats = await fetch_pre_match_stats(team1, team2, venue)

            # Fetch Playing XI with buzz sentiment + luck
            xi_data = await fetch_playing_xi(team1, team2, venue)
            xi_data = apply_buzz_and_luck(xi_data)

            prediction = compute_prediction(stats, playing_xi=xi_data)

            # Odds direction
            odds_direction = {"team1": "new", "team2": "new"}
            if cached and cached.get("prediction"):
                old_t1 = cached["prediction"].get("team1_win_prob", 50)
                new_t1 = prediction["team1_win_prob"]
                diff = round(new_t1 - old_t1, 1)
                direction = "stable" if abs(diff) <= 0.5 else ("up" if diff > 0 else "down")
                odds_direction = {
                    "team1": direction,
                    "team2": "down" if direction == "up" else ("up" if direction == "down" else "stable"),
                    "team1_change": diff,
                    "team2_change": round(-diff, 1),
                    "previous_team1_prob": old_t1,
                    "previous_team2_prob": cached["prediction"].get("team2_win_prob", 50),
                }
                await db.prediction_history.insert_one({
                    "matchId": mid, "prediction": cached.get("prediction"),
                    "computed_at": cached.get("computed_at"),
                    "superseded_at": datetime.now(timezone.utc).isoformat(),
                })

            result = {
                "matchId": mid,
                "team1": team1, "team2": team2,
                "team1Short": t1_short, "team2Short": t2_short,
                "venue": venue,
                "dateTimeGMT": match.get("dateTimeGMT", ""),
                "match_number": match.get("match_number"),
                "prediction": prediction,
                "stats": stats,
                "playing_xi": {
                    "team1_xi": xi_data.get("team1_xi", []),
                    "team2_xi": xi_data.get("team2_xi", []),
                    "confidence": xi_data.get("confidence", "unavailable"),
                },
                "odds_direction": odds_direction,
                "computed_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.pre_match_predictions.update_one(
                {"matchId": mid}, {"$set": result}, upsert=True
            )
            repredict_status["completed"] += 1
            logger.info(f"[RePredict {repredict_status['completed']}/{repredict_status['total']}] {t1_short} {prediction['team1_win_prob']}% vs {t2_short} [dir: {odds_direction['team1']}]")
        except Exception as e:
            repredict_status["failed"] += 1
            logger.error(f"[RePredict] Failed {mid}: {e}")

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
    return {"source": "GPT-5.4 Web Search", "model": "gpt-5.4", "tool": "web_search_preview"}


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

@api_router.post("/matches/{match_id}/playing-xi")
async def api_fetch_playing_xi(match_id: str):
    """Fetch expected/confirmed Playing XI via GPT-5.4 web search with luck biasness."""
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")

    xi_data = await fetch_playing_xi(team1, team2, venue)

    # Apply buzz sentiment + luck biasness to expected performance
    xi_data = apply_buzz_and_luck(xi_data)

    xi_data["matchId"] = match_id
    xi_data["venue"] = venue
    xi_data["fetched_at"] = datetime.now(timezone.utc).isoformat()

    # Cache in DB
    await db.playing_xi.update_one(
        {"matchId": match_id},
        {"$set": {k: v for k, v in xi_data.items()}},
        upsert=True,
    )

    return xi_data



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
    )

    result["team1Short"] = t1_short
    result["team2Short"] = t2_short
    return result


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

    # Build snapshot
    live_state = live_match_state.get(match_id)
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
    result = run_consultation(
        snapshot=snapshot,
        market_pct_team1=body.market_pct_team1,
        market_pct_team2=body.market_pct_team2,
        risk_tolerance=body.risk_tolerance,
    )

    # GPT answer
    answer = await gpt_consultation(body.question, result, body.risk_tolerance)

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


# ─── STARTUP ─────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("Gamble Consultant v4 starting up...")

@app.on_event("shutdown")
async def shutdown():
    client.close()

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
