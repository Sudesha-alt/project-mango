from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from services.cricket_service import (
    get_live_matches, get_match_info, get_match_scorecard,
    get_match_squad, get_ipl_fixtures, get_player_info, IPL_SHORT, get_short_name
)
import services.cricket_service as cricket_svc
from services.probability_engine import (
    ensemble_probability, calculate_odds_from_probability,
    calculate_momentum
)
from services.ai_service import get_match_prediction, get_player_prediction

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# In-memory state for WebSocket connections and match data
ws_connections: Dict[str, List[WebSocket]] = {}
match_cache: Dict[str, Any] = {}
ball_history_cache: Dict[str, List[Dict]] = {}
odds_history_cache: Dict[str, List[Dict]] = {}
probability_history_cache: Dict[str, List[Dict]] = {}


# ─── REST ENDPOINTS ───────────────────────────────────────────

@api_router.get("/")
async def root():
    import time as _time
    blocked = _time.time() < cricket_svc._blocked_until
    return {
        "message": "PPL Board API",
        "version": "1.0.0",
        "apiStatus": "blocked" if blocked else "available",
        "blockRemaining": max(0, int(cricket_svc._blocked_until - _time.time())) if blocked else 0,
        "cachedEndpoints": len(cricket_svc._api_cache)
    }

@api_router.get("/matches/live")
async def api_live_matches():
    matches = await get_live_matches()
    # If API returned matches, cache them in MongoDB
    if matches:
        for m in matches:
            mid = m.get("matchId")
            if mid:
                await db.matches_cache.update_one(
                    {"matchId": mid},
                    {"$set": {**m, "cachedAt": datetime.now(timezone.utc).isoformat()}},
                    upsert=True
                )
            if mid and mid in match_cache:
                cached = match_cache[mid]
                m["probabilities"] = cached.get("probabilities", {})
                m["odds"] = cached.get("odds", {})
    else:
        # Fallback to MongoDB cached matches
        cached_matches = await db.matches_cache.find({}, {"_id": 0}).to_list(50)
        if cached_matches:
            matches = cached_matches
            logger.info(f"Serving {len(matches)} cached matches from MongoDB")
    return {"matches": matches}

@api_router.get("/matches/fixtures")
async def api_fixtures():
    fixtures = await get_ipl_fixtures()
    return {"fixtures": fixtures if fixtures else []}

@api_router.get("/matches/{match_id}")
async def api_match_detail(match_id: str):
    info = await get_match_info(match_id)
    if not info:
        return {"error": "Match not found", "matchId": match_id}
    squad = await get_match_squad(match_id)
    result = {
        "matchId": match_id,
        "info": info,
        "squad": squad,
        "probabilities": match_cache.get(match_id, {}).get("probabilities", {}),
        "odds": match_cache.get(match_id, {}).get("odds", {}),
        "ballHistory": ball_history_cache.get(match_id, []),
        "oddsHistory": odds_history_cache.get(match_id, []),
        "probabilityHistory": probability_history_cache.get(match_id, []),
    }
    return result

@api_router.get("/matches/{match_id}/scorecard")
async def api_scorecard(match_id: str):
    sc = await get_match_scorecard(match_id)
    return {"matchId": match_id, "scorecard": sc}

@api_router.get("/matches/{match_id}/squad")
async def api_squad(match_id: str):
    sq = await get_match_squad(match_id)
    return {"matchId": match_id, "squad": sq}

@api_router.get("/matches/{match_id}/predictions")
async def api_predictions(match_id: str):
    match_data = match_cache.get(match_id, {})
    if not match_data:
        matches = await get_live_matches()
        for m in matches:
            if m["matchId"] == match_id:
                match_data = m
                break
    if not match_data:
        info = await get_match_info(match_id)
        if info:
            match_data = {
                "matchId": match_id,
                "team1": info.get("teams", ["Team A"])[0] if info.get("teams") else "Team A",
                "team2": info.get("teams", ["", "Team B"])[1] if info.get("teams") and len(info["teams"]) > 1 else "Team B",
                "venue": info.get("venue", ""),
                "status": info.get("status", ""),
                "score": str(info.get("score", "")),
            }
    ai_pred = await get_match_prediction(match_data)
    return {"matchId": match_id, "predictions": ai_pred}

@api_router.get("/matches/{match_id}/odds")
async def api_odds(match_id: str):
    cached = match_cache.get(match_id, {})
    odds = cached.get("odds", {})
    history = odds_history_cache.get(match_id, [])
    return {"matchId": match_id, "odds": odds, "history": history[-50:]}

@api_router.post("/matches/{match_id}/calculate")
async def api_calculate(match_id: str):
    result = await compute_match_probabilities(match_id)
    return {"matchId": match_id, "result": result}

@api_router.get("/matches/{match_id}/player-predictions")
async def api_player_predictions(match_id: str):
    sq = await get_match_squad(match_id)
    if not sq:
        return {"matchId": match_id, "players": []}
    cached = match_cache.get(match_id, {})
    venue = cached.get("venue", "")
    team1 = cached.get("team1", "Team A")
    team2 = cached.get("team2", "Team B")
    players = []
    if isinstance(sq, list):
        for team_data in sq[:2]:
            team_name = team_data.get("teamName", "Unknown")
            opponent = team2 if team_name == team1 else team1
            player_list = team_data.get("players", [])[:11]
            for p in player_list:
                pred = await get_player_prediction(p.get("name", ""), team_name, opponent, venue)
                players.append({
                    "name": p.get("name", ""),
                    "team": team_name,
                    "role": p.get("role", ""),
                    "prediction": pred
                })
    return {"matchId": match_id, "players": players}

@api_router.get("/players/{player_id}")
async def api_player(player_id: str):
    info = await get_player_info(player_id)
    return {"playerId": player_id, "info": info}


# ─── PROBABILITY COMPUTATION ─────────────────────────────────

async def compute_match_probabilities(match_id):
    matches = await get_live_matches()
    match_data = None
    for m in matches:
        if m["matchId"] == match_id:
            match_data = m
            break
    if not match_data:
        return None
    runs = match_data.get("runs", 0)
    wickets = match_data.get("wickets", 0)
    overs = match_data.get("overs", 0)
    innings = match_data.get("innings", 1)
    target = None
    if innings == 2:
        score_str = match_data.get("score", "")
        if "Target" in str(score_str):
            try:
                target = int(str(score_str).split("Target")[1].strip().split()[0])
            except (ValueError, IndexError):
                pass
    cached_odds = match_cache.get(match_id, {}).get("odds", {})
    odds_a = cached_odds.get("team1", 2.0) if cached_odds else None
    probs = ensemble_probability(runs, wickets, overs, target, innings, odds_a)
    team1_odds = calculate_odds_from_probability(probs["ensemble"])
    team2_odds = calculate_odds_from_probability(1 - probs["ensemble"])
    now_str = datetime.now(timezone.utc).isoformat()
    match_cache[match_id] = {
        **match_data,
        "probabilities": probs,
        "odds": {"team1": team1_odds, "team2": team2_odds},
        "momentum": calculate_momentum(ball_history_cache.get(match_id, [])),
        "lastUpdated": now_str,
    }
    odds_history_cache.setdefault(match_id, []).append({
        "time": now_str,
        "team1": team1_odds,
        "team2": team2_odds,
    })
    probability_history_cache.setdefault(match_id, []).append({
        "time": now_str,
        **probs
    })
    if len(odds_history_cache[match_id]) > 200:
        odds_history_cache[match_id] = odds_history_cache[match_id][-200:]
    if len(probability_history_cache[match_id]) > 200:
        probability_history_cache[match_id] = probability_history_cache[match_id][-200:]
    await db.match_snapshots.update_one(
        {"matchId": match_id},
        {"$set": {
            "matchId": match_id,
            "team1": match_data.get("team1"),
            "team2": match_data.get("team2"),
            "probabilities": probs,
            "odds": {"team1": team1_odds, "team2": team2_odds},
            "lastUpdated": now_str,
        }},
        upsert=True
    )
    return match_cache[match_id]


# ─── WEBSOCKET ────────────────────────────────────────────────

@api_router.websocket("/ws/{match_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str):
    await websocket.accept()
    ws_connections.setdefault(match_id, []).append(websocket)
    logger.info(f"WS connected for match {match_id}. Total: {len(ws_connections[match_id])}")
    try:
        cached = match_cache.get(match_id)
        if cached:
            await websocket.send_json({
                "type": "LIVE_UPDATE",
                "matchId": match_id,
                **{k: cached[k] for k in ["probabilities", "odds", "momentum", "lastUpdated"] if k in cached},
                "ballHistory": ball_history_cache.get(match_id, [])[-30:],
                "oddsHistory": odds_history_cache.get(match_id, [])[-30:],
                "probabilityHistory": probability_history_cache.get(match_id, [])[-30:],
            })
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "PING":
                await websocket.send_json({"type": "PONG"})
            elif msg.get("type") == "REQUEST_UPDATE":
                result = await compute_match_probabilities(match_id)
                if result:
                    await broadcast_update(match_id, result)
    except WebSocketDisconnect:
        ws_connections[match_id].remove(websocket)
        logger.info(f"WS disconnected for match {match_id}")
    except Exception as e:
        logger.error(f"WS error: {e}")
        if websocket in ws_connections.get(match_id, []):
            ws_connections[match_id].remove(websocket)

async def broadcast_update(match_id, data):
    if match_id not in ws_connections:
        return
    payload = {
        "type": "LIVE_UPDATE",
        "matchId": match_id,
        "score": data.get("score", ""),
        "runs": data.get("runs", 0),
        "overs": data.get("overs", 0),
        "wickets": data.get("wickets", 0),
        "innings": data.get("innings", 1),
        "probabilities": data.get("probabilities", {}),
        "odds": data.get("odds", {}),
        "momentum": data.get("momentum", {}),
        "lastUpdated": data.get("lastUpdated", ""),
        "team1": data.get("team1", ""),
        "team2": data.get("team2", ""),
        "team1Short": data.get("team1Short", ""),
        "team2Short": data.get("team2Short", ""),
        "ballHistory": ball_history_cache.get(match_id, [])[-30:],
        "probabilityHistory": probability_history_cache.get(match_id, [])[-30:],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    disconnected = []
    for ws in ws_connections[match_id]:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        ws_connections[match_id].remove(ws)


# ─── BACKGROUND WORKER ───────────────────────────────────────

async def background_updater():
    await asyncio.sleep(10)  # Initial delay
    while True:
        try:
            matches = await get_live_matches()
            live_matches = [m for m in matches if m.get("isLive")]
            for m in live_matches[:3]:  # Only process first 3 live matches
                mid = m["matchId"]
                if mid:
                    await compute_match_probabilities(mid)
                    cached = match_cache.get(mid)
                    if cached and mid in ws_connections and ws_connections[mid]:
                        await broadcast_update(mid, cached)
        except Exception as e:
            logger.error(f"Background updater error: {e}")
        await asyncio.sleep(120)  # 2 minutes to respect CricAPI rate limits


# ─── STARTUP / SHUTDOWN ──────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("PPL Board starting up...")
    asyncio.create_task(background_updater())

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
