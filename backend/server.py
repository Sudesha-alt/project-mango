from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from services.cricket_service import (
    get_live_matches, get_match_info, get_match_scorecard,
    get_match_squad, get_short_name
)
import services.cricket_service as cricket_svc
from services.probability_engine import (
    ensemble_probability, calculate_odds_from_probability, calculate_momentum
)
from services.ai_service import (
    fetch_ipl_schedule, fetch_ipl_squads, fetch_live_match_update,
    get_match_prediction, get_player_predictions
)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ws_connections: Dict[str, List[WebSocket]] = {}
live_match_state: Dict[str, Any] = {}


# ─── HEALTH & STATUS ─────────────────────────────────────────

@api_router.get("/")
async def root():
    import time
    blocked = time.time() < cricket_svc._blocked_until
    schedule_count = await db.ipl_schedule.count_documents({})
    squad_count = await db.ipl_squads.count_documents({})
    return {
        "message": "PPL Board API",
        "version": "2.0.0",
        "cricapiStatus": "blocked" if blocked else "available",
        "blockRemaining": max(0, int(cricket_svc._blocked_until - time.time())) if blocked else 0,
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
        await db.ipl_schedule.delete_many({})
        for m in matches:
            m["loadedAt"] = datetime.now(timezone.utc).isoformat()
        await db.ipl_schedule.insert_many(matches)
        return {"status": "loaded", "count": len(matches)}
    return {"status": "error", "count": 0}

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


# ─── LIVE MATCH (on-demand via button) ───────────────────────

@api_router.post("/matches/{match_id}/fetch-live")
async def fetch_live_data(match_id: str):
    """Button-triggered: Fetch live data from CricAPI first, fallback to GPT."""
    # Get match info from schedule
    match_info = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not match_info:
        return {"error": "Match not found in schedule"}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue = match_info.get("venue", "")

    # Try CricAPI first
    cricapi_data = None
    cricapi_matches = await get_live_matches()
    if cricapi_matches:
        for m in cricapi_matches:
            if m.get("matchId") == match_id or (
                team1.lower() in m.get("team1", "").lower() and
                team2.lower() in m.get("team2", "").lower()
            ):
                cricapi_data = m
                break

    # If no CricAPI data, use GPT for live simulation
    live_data = None
    source = "cricapi"
    if cricapi_data and cricapi_data.get("score"):
        live_data = {
            "matchId": match_id,
            "team1": team1,
            "team2": team2,
            "venue": venue,
            "score": {
                "runs": cricapi_data.get("runs", 0),
                "wickets": cricapi_data.get("wickets", 0),
                "overs": cricapi_data.get("overs", 0),
                "target": None,
            },
            "innings": cricapi_data.get("innings", 1),
            "status": cricapi_data.get("status", "Live"),
            "isLive": True,
            "source": "cricapi",
        }
    else:
        logger.info(f"Using GPT for live data: {team1} vs {team2}")
        gpt_data = await fetch_live_match_update(match_info)
        if gpt_data:
            live_data = gpt_data
            live_data["source"] = "gpt"
            source = "gpt"

    if not live_data:
        return {"error": "Could not fetch live data"}

    # Run probability algorithms
    score = live_data.get("score", {})
    runs = score.get("runs", 0) if isinstance(score, dict) else 0
    wickets = score.get("wickets", 0) if isinstance(score, dict) else 0
    overs = score.get("overs", 0) if isinstance(score, dict) else 0
    target = score.get("target") if isinstance(score, dict) else None
    innings = live_data.get("innings", 1)

    probs = ensemble_probability(runs, wickets, overs, target, innings)
    team1_odds = calculate_odds_from_probability(probs["ensemble"])
    team2_odds = calculate_odds_from_probability(1 - probs["ensemble"])

    # Get AI prediction
    ai_pred = await get_match_prediction({
        "matchId": match_id, "team1": team1, "team2": team2,
        "venue": venue, "score": score
    })

    # Build balls from recentBalls
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

    result = {
        "matchId": match_id,
        "team1": team1,
        "team1Short": get_short_name(team1),
        "team2": team2,
        "team2Short": get_short_name(team2),
        "venue": venue,
        "liveData": live_data,
        "probabilities": probs,
        "odds": {"team1": team1_odds, "team2": team2_odds},
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

    # Cache in memory and MongoDB
    live_match_state[match_id] = result
    await db.live_snapshots.update_one(
        {"matchId": match_id},
        {"$set": {**{k: v for k, v in result.items()}, "updatedAt": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )

    # Broadcast to WebSocket connections
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


# ─── CRICAPI LIVE (for cross-check) ─────────────────────────

@api_router.get("/matches/cricapi-live")
async def api_cricapi_live():
    matches = await get_live_matches()
    return {"matches": matches, "count": len(matches)}


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
    logger.info("PPL Board v2 starting up...")

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
