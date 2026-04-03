import os
import logging
import json
import uuid
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

def _get_gpt_chat(session_id, system_msg):
    key = OPENAI_KEY if OPENAI_KEY else EMERGENT_KEY
    chat = LlmChat(api_key=key, session_id=session_id, system_message=system_msg)
    chat.with_model("openai", "gpt-4.1")
    return chat


async def fetch_ipl_schedule():
    """Use GPT to generate the complete IPL 2026 schedule with all teams and venues."""
    chat = _get_gpt_chat(
        f"ipl-schedule-{uuid.uuid4().hex[:8]}",
        "You are an expert cricket database. Provide accurate IPL 2026 data. Always respond ONLY with valid JSON, no markdown."
    )
    prompt = """Generate the complete IPL 2026 season schedule. The season opener is RCB vs SRH.

CRITICAL: Match 1 MUST be Royal Challengers Bengaluru (RCB) vs Sunrisers Hyderabad (SRH).

Include ALL 74 league stage matches. Each team plays 14 matches (7 home, 7 away).

For each match provide:
- matchId (unique string like "ipl2026_001")  
- match_number (1-74)
- team1 and team2 (full names from: Chennai Super Kings, Mumbai Indians, Royal Challengers Bengaluru, Kolkata Knight Riders, Delhi Capitals, Rajasthan Royals, Sunrisers Hyderabad, Punjab Kings, Gujarat Titans, Lucknow Super Giants)
- team1Short and team2Short (CSK, MI, RCB, KKR, DC, RR, SRH, PBKS, GT, LSG)
- venue (real IPL venues: M Chinnaswamy Stadium Bengaluru, Wankhede Stadium Mumbai, MA Chidambaram Stadium Chennai, Eden Gardens Kolkata, Arun Jaitley Stadium Delhi, Sawai Mansingh Stadium Jaipur, Rajiv Gandhi Intl Stadium Hyderabad, IS Bindra Stadium Mohali, Narendra Modi Stadium Ahmedabad, Ekana Sports City Lucknow)
- dateTimeGMT (dates from March 22 to May 25, 2026, in ISO format, matches at 14:00 or 18:00 UTC)
- status: "Completed" for first 25 matches, "Upcoming" for rest
- For completed matches: include winner, score (e.g. "RCB 192/4 (20) | SRH 178/7 (20)"), manOfMatch (real player names)
- matchType: "T20"
- series: "IPL 2026"

Respond ONLY with a JSON object: {"matches": [...]}"""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        cleaned = response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        data = json.loads(cleaned)
        return data.get("matches", [])
    except Exception as e:
        logger.error(f"GPT schedule fetch error: {e}")
        return []


async def fetch_ipl_squads():
    """Use GPT to generate IPL 2026 team squads."""
    chat = _get_gpt_chat(
        f"ipl-squads-{uuid.uuid4().hex[:8]}",
        "You are an expert cricket database. Provide accurate IPL 2026 squad data. Always respond ONLY with valid JSON."
    )
    prompt = """Generate the full playing squads for all 10 IPL 2026 teams.

For each team provide:
- teamName (full name)
- teamShort (abbreviation)
- captain
- players: array of {name, role (Batsman/Bowler/All-rounder/Wicketkeeper), isCaptain: bool, isKeeper: bool, isOverseas: bool}
- Include 18-22 players per team with realistic player names from actual IPL rosters

Teams: CSK, MI, RCB, KKR, DC, RR, SRH, PBKS, GT, LSG

Respond ONLY with JSON: {"squads": [...]}"""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        cleaned = response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        data = json.loads(cleaned)
        return data.get("squads", [])
    except Exception as e:
        logger.error(f"GPT squads fetch error: {e}")
        return []


async def fetch_live_match_update(match_info):
    """Use GPT to fetch/simulate real-time match updates."""
    team1 = match_info.get("team1", "Team A")
    team2 = match_info.get("team2", "Team B")
    venue = match_info.get("venue", "")
    match_id = match_info.get("matchId", "")

    chat = _get_gpt_chat(
        f"live-{match_id}-{uuid.uuid4().hex[:6]}",
        "You are a live cricket match simulator and analyst. Generate realistic live match data based on current IPL context. Respond ONLY with valid JSON."
    )
    prompt = f"""Generate a realistic live match update for this IPL 2026 match:
{team1} vs {team2} at {venue}

Provide a complete live match state:
{{
  "matchId": "{match_id}",
  "team1": "{team1}",
  "team2": "{team2}",
  "venue": "{venue}",
  "innings": 1 or 2,
  "battingTeam": "team batting now",
  "bowlingTeam": "team bowling now",
  "score": {{
    "runs": number,
    "wickets": number,
    "overs": number (like 14.3),
    "target": null or number (if 2nd innings)
  }},
  "currentRunRate": number,
  "requiredRunRate": number or null,
  "recentBalls": ["4", "1", "W", "0", "6", "2", "1", "0", "4", "1", "0", "W"],
  "batsmen": [
    {{"name": "Player Name", "runs": 45, "balls": 30, "fours": 5, "sixes": 2, "strikeRate": 150.0}},
    {{"name": "Player Name", "runs": 22, "balls": 18, "fours": 2, "sixes": 1, "strikeRate": 122.2}}
  ],
  "bowler": {{"name": "Player Name", "overs": 3.2, "runs": 28, "wickets": 1, "economy": 8.4}},
  "fallOfWickets": [{{"player": "Name", "score": 45, "overs": 5.3}}],
  "status": "Match in progress - {team1} batting",
  "isLive": true,
  "lastBallCommentary": "Short delivery, pulled away for FOUR!"
}}

Make it realistic for a T20 match between these specific teams. Vary the match state randomly."""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        cleaned = response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"GPT live update error: {e}")
        return None


async def get_match_prediction(match_data):
    """AI-powered match prediction with detailed analysis."""
    team1 = match_data.get("team1", "Team A")
    team2 = match_data.get("team2", "Team B")
    venue = match_data.get("venue", "")
    score = match_data.get("score", {})

    chat = _get_gpt_chat(
        f"pred-{match_data.get('matchId','')}-{uuid.uuid4().hex[:6]}",
        "You are an expert cricket analyst. Provide detailed match predictions. Respond ONLY with valid JSON."
    )
    score_context = ""
    if isinstance(score, dict) and score.get("runs"):
        score_context = f"\nCurrent score: {score.get('runs',0)}/{score.get('wickets',0)} in {score.get('overs',0)} overs."
        if score.get("target"):
            score_context += f" Target: {score['target']}"
    elif isinstance(score, str) and score:
        score_context = f"\nScore: {score}"

    prompt = f"""Analyze this IPL 2026 match and predict outcomes:
{team1} vs {team2} at {venue}{score_context}

Respond with:
{{
  "team1WinProb": 0.55,
  "team2WinProb": 0.45,
  "analysis": "Detailed 2-3 sentence analysis based on team strengths, venue, conditions",
  "keyFactors": ["factor1", "factor2", "factor3", "factor4"],
  "projectedScore": {{
    "team1": {{"low": 155, "expected": 175, "high": 195}},
    "team2": {{"low": 150, "expected": 170, "high": 190}}
  }},
  "manOfTheMatch": "Player Name",
  "tossAdvantage": "bat" or "bowl",
  "venueStats": "Brief venue history for T20s"
}}"""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        cleaned = response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"GPT prediction error: {e}")
        return {"team1WinProb": 0.5, "team2WinProb": 0.5, "analysis": f"Prediction error: {str(e)}", "keyFactors": []}


async def get_player_predictions(team1, team2, venue, squad1=None, squad2=None):
    """AI-powered player performance predictions."""
    chat = _get_gpt_chat(
        f"players-{uuid.uuid4().hex[:8]}",
        "You are an expert IPL cricket analyst. Predict individual player performances. Respond ONLY with valid JSON."
    )

    squad1_str = ", ".join([p.get("name", "") for p in (squad1 or [])[:11]]) if squad1 else "Playing XI not available"
    squad2_str = ", ".join([p.get("name", "") for p in (squad2 or [])[:11]]) if squad2 else "Playing XI not available"

    prompt = f"""Predict player performances for this IPL 2026 match:
{team1} vs {team2} at {venue}

{team1} squad: {squad1_str}
{team2} squad: {squad2_str}

For each player in both playing XIs (top 11 per team), predict:
{{
  "players": [
    {{
      "name": "Player Name",
      "team": "Team Name",
      "role": "Batsman/Bowler/All-rounder/Wicketkeeper",
      "batting": {{
        "predictedRuns": 35,
        "strikeRate": 140,
        "boundaryProb": 0.7,
        "fiftyProb": 0.3,
        "duckProb": 0.05,
        "confidence": 0.6
      }},
      "bowling": {{
        "predictedWickets": 1,
        "economy": 8.5,
        "dotBallPerc": 35,
        "maidenProb": 0.05,
        "confidence": 0.5
      }},
      "impactScore": 7.5
    }}
  ]
}}

Include realistic predictions based on actual player abilities and venue conditions. Set bowling confidence to 0 for pure batsmen."""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        cleaned = response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        data = json.loads(cleaned)
        return data.get("players", [])
    except Exception as e:
        logger.error(f"GPT player predictions error: {e}")
        return []
