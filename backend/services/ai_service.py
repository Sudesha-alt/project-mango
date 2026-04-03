import os
import logging
import json
import uuid
import re
from openai import AsyncOpenAI
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        key = OPENAI_KEY
        if not key:
            raise ValueError("OPENAI_API_KEY not configured in .env")
        _openai_client = AsyncOpenAI(api_key=key)
    return _openai_client


def _get_gpt_chat(session_id, system_msg):
    """For analytical tasks (predictions) that don't need web search."""
    key = OPENAI_KEY if OPENAI_KEY else EMERGENT_KEY
    chat = LlmChat(api_key=key, session_id=session_id, system_message=system_msg)
    chat.with_model("openai", "gpt-5.4")
    return chat


def _extract_json(text):
    """Robustly extract JSON from GPT response text."""
    cleaned = text.strip()
    cleaned = re.sub(r'\[\d+\]', '', cleaned)
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts[1::2]:
            part = part.strip()
            if part.startswith('{') or part.startswith('['):
                cleaned = part
                break
    if not (cleaned.startswith('{') or cleaned.startswith('[')):
        for i, ch in enumerate(cleaned):
            if ch in ('{', '['):
                cleaned = cleaned[i:]
                break
    if cleaned.startswith('{'):
        depth = 0
        end = len(cleaned)
        for i, ch in enumerate(cleaned):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            if depth == 0:
                end = i + 1
                break
        cleaned = cleaned[:end]
    return json.loads(cleaned)


async def _web_search(prompt):
    """Step 1: GPT-5.1 web search to get raw text data."""
    client = _get_openai_client()
    response = await client.responses.create(
        model="gpt-5.4",
        tools=[{"type": "web_search_preview"}],
        input=prompt,
    )
    return response.output_text


async def _parse_to_json(raw_text, parse_instruction):
    """Step 2: Parse raw web search text into structured JSON (no web search needed)."""
    client = _get_openai_client()
    response = await client.responses.create(
        model="gpt-5.4",
        instructions="You are a precise data parser. Output ONLY valid JSON with no markdown formatting, no code blocks, no explanation. Just raw JSON.",
        input=f"{parse_instruction}\n\nSource data:\n{raw_text}",
    )
    return _extract_json(response.output_text)


async def fetch_ipl_schedule():
    """Fetch real IPL 2026 schedule using GPT-5.1 web search (two-step)."""
    # Step 1: Web search for raw schedule data
    raw_text = await _web_search(
        "Search for the complete IPL 2026 Indian Premier League 2026 schedule. "
        "I need ALL completed match results with scores, winners, and dates, "
        "ALL upcoming fixtures with dates and venues, "
        "and any currently LIVE matches. "
        "Include as many matches as possible from the full season."
    )
    logger.info(f"Web search schedule raw response: {len(raw_text)} chars")

    # Step 2: Parse into structured JSON
    parse_instruction = """Parse the IPL 2026 schedule data below into this exact JSON format.
Return a JSON object: {"matches": [...]}

Each match object must have:
- "matchId": unique string like "ipl2026_001" (number based on match_number)
- "match_number": sequential integer
- "team1": full team name
- "team2": full team name
- "team1Short": abbreviation (CSK, MI, RCB, KKR, DC, RR, SRH, PBKS, GT, LSG)
- "team2Short": abbreviation
- "venue": stadium/city from source data (or "TBD" if not mentioned)
- "dateTimeGMT": ISO date string (e.g. "2026-03-28T14:00:00Z")
- "status": exactly one of "Completed", "Live", or "Upcoming"
- "matchType": "T20"
- "series": "IPL 2026"

For Completed matches, also include:
- "winner": full name of winning team
- "score": score summary string like "RCB 203/4 (15.4) | SRH 201/9 (20)"
- "manOfMatch": player name if available (or omit)

For Live matches, also include:
- "score": current score string

For Upcoming matches, no score/winner fields.

IMPORTANT: Only include matches that appear in the source data. Do not invent additional matches.
Use these team name mappings:
- CSK = Chennai Super Kings
- MI = Mumbai Indians
- RCB = Royal Challengers Bengaluru
- KKR = Kolkata Knight Riders
- DC = Delhi Capitals
- RR = Rajasthan Royals
- SRH = Sunrisers Hyderabad
- PBKS = Punjab Kings
- GT = Gujarat Titans
- LSG = Lucknow Super Giants"""

    try:
        data = await _parse_to_json(raw_text, parse_instruction)
        matches = data.get("matches", [])
        logger.info(f"Parsed {len(matches)} real matches from web search")
        return matches
    except Exception as e:
        logger.error(f"Schedule parse error: {e}")
        return []


async def fetch_ipl_squads():
    """Fetch real IPL 2026 squads using GPT-5.1 web search (two-step)."""
    raw_text = await _web_search(
        "Search for IPL 2026 team squads and player lists for all 10 IPL teams: "
        "CSK, MI, RCB, KKR, DC, RR, SRH, PBKS, GT, LSG. "
        "Include captain names and key players for each team."
    )

    parse_instruction = """Parse the IPL 2026 squad data into this JSON format:
{"squads": [
  {
    "teamName": "Full Team Name",
    "teamShort": "ABR",
    "captain": "Captain Name",
    "players": [
      {"name": "Player Name", "role": "Batsman/Bowler/All-rounder/Wicketkeeper", "isCaptain": false, "isKeeper": false, "isOverseas": false}
    ]
  }
]}
Include only players mentioned in the source data. Mark captains and overseas players based on available info."""

    try:
        data = await _parse_to_json(raw_text, parse_instruction)
        return data.get("squads", [])
    except Exception as e:
        logger.error(f"Squads parse error: {e}")
        return []


async def fetch_live_match_update(match_info):
    """Fetch real live match data using GPT-5.1 web search (two-step)."""
    team1 = match_info.get("team1", "Team A")
    team2 = match_info.get("team2", "Team B")
    venue = match_info.get("venue", "")
    match_id = match_info.get("matchId", "")

    # Step 1: Web search for live score
    raw_text = await _web_search(
        f"Search for the LIVE cricket score of {team1} vs {team2} IPL 2026 right now. "
        f"If the match is currently being played, get the latest score, batting details, bowling figures. "
        f"If not live, get the most recent result or upcoming status."
    )
    logger.info(f"Web search live data for {team1} vs {team2}: {len(raw_text)} chars")

    # Step 2: Parse into structured JSON
    parse_instruction = f"""Parse the cricket match data below into this exact JSON format:
{{
  "matchId": "{match_id}",
  "team1": "{team1}",
  "team2": "{team2}",
  "venue": "{venue}",
  "isLive": boolean (true if match is currently in progress),
  "noLiveMatch": boolean (true if the match is NOT currently being played),
  "innings": 1 or 2,
  "battingTeam": "team currently batting",
  "bowlingTeam": "team currently bowling",
  "score": {{
    "runs": number,
    "wickets": number,
    "overs": number (like 15.2),
    "target": null or number (set if 2nd innings)
  }},
  "currentRunRate": number,
  "requiredRunRate": null or number,
  "recentBalls": ["4", "1", "W", "0", "6", "2"],
  "batsmen": [
    {{"name": "Player", "runs": number, "balls": number, "fours": number, "sixes": number, "strikeRate": number}}
  ],
  "bowler": {{"name": "Player", "overs": number, "runs": number, "wickets": number, "economy": number}},
  "fallOfWickets": [],
  "status": "descriptive match status text",
  "lastBallCommentary": "latest event description"
}}

RULES:
- If the match IS live, set isLive=true and noLiveMatch=false, fill score from real data
- If the match is NOT live (completed, not started, or no data), set isLive=false and noLiveMatch=true
- For completed matches, put final result in status
- Only use data from the source text. Fill unavailable fields with reasonable defaults (empty arrays, null, 0)."""

    try:
        data = await _parse_to_json(raw_text, parse_instruction)
        return data
    except Exception as e:
        logger.error(f"Live data parse error: {e}")
        return None


async def get_match_prediction(match_data):
    """AI-powered match prediction with detailed analysis."""
    team1 = match_data.get("team1", "Team A")
    team2 = match_data.get("team2", "Team B")
    venue = match_data.get("venue", "")
    score = match_data.get("score", {})

    chat = _get_gpt_chat(
        f"pred-{match_data.get('matchId', '')}-{uuid.uuid4().hex[:6]}",
        "You are an expert cricket analyst. Provide detailed match predictions. Respond ONLY with valid JSON."
    )
    score_context = ""
    if isinstance(score, dict) and score.get("runs"):
        score_context = f"\nCurrent score: {score.get('runs', 0)}/{score.get('wickets', 0)} in {score.get('overs', 0)} overs."
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
  "analysis": "Detailed 2-3 sentence analysis",
  "keyFactors": ["factor1", "factor2", "factor3", "factor4"],
  "projectedScore": {{
    "team1": {{"low": 155, "expected": 175, "high": 195}},
    "team2": {{"low": 150, "expected": 170, "high": 190}}
  }},
  "manOfTheMatch": "Player Name",
  "tossAdvantage": "bat" or "bowl",
  "venueStats": "Brief venue history"
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
        return {"team1WinProb": 0.5, "team2WinProb": 0.5, "analysis": "Prediction unavailable", "keyFactors": []}


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

For each player predict:
{{
  "players": [
    {{
      "name": "Player Name",
      "team": "Team Name",
      "role": "Batsman/Bowler/All-rounder/Wicketkeeper",
      "batting": {{"predictedRuns": 35, "strikeRate": 140, "boundaryProb": 0.7, "fiftyProb": 0.3, "duckProb": 0.05, "confidence": 0.6}},
      "bowling": {{"predictedWickets": 1, "economy": 8.5, "dotBallPerc": 35, "maidenProb": 0.05, "confidence": 0.5}},
      "impactScore": 7.5
    }}
  ]
}}"""

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


def _get_gpt_mini_chat(session_id, system_msg):
    """GPT-5.4 mini for quick real-time decisions."""
    key = OPENAI_KEY if OPENAI_KEY else EMERGENT_KEY
    chat = LlmChat(api_key=key, session_id=session_id, system_message=system_msg)
    chat.with_model("openai", "gpt-5.4-mini")
    return chat


async def fetch_player_stats_for_prediction(team1, team2, team1_players, team2_players, venue):
    """
    GPT-5.4 Web Search: Fetch real player stats (last 5 matches, venue averages)
    for the beta prediction engine.
    """
    players_str = ""
    for p in (team1_players or [])[:11]:
        players_str += f"- {p.get('name', 'Unknown')} ({team1})\n"
    for p in (team2_players or [])[:11]:
        players_str += f"- {p.get('name', 'Unknown')} ({team2})\n"

    raw_text = await _web_search(
        f"Search for recent IPL 2026 cricket stats for these players. "
        f"I need their last 5 match performances (runs scored, wickets taken), "
        f"their average at {venue}, and current form. "
        f"Match: {team1} vs {team2}\n"
        f"Players:\n{players_str}\n"
        f"Search ESPNcricinfo, Cricbuzz for actual stats."
    )
    logger.info(f"Player stats web search: {len(raw_text)} chars")

    parse_instruction = f"""Parse the player statistics into this JSON format:
{{"players": [
  {{
    "name": "Player Name",
    "team": "Full Team Name (must be exactly '{team1}' or '{team2}')",
    "role": "Batsman/Bowler/All-rounder/Wicketkeeper",
    "last5_avg_runs": number (average runs in last 5 IPL matches),
    "last5_avg_wickets": number (average wickets in last 5 IPL matches),
    "venue_avg_runs": number (average runs at this venue),
    "venue_avg_wickets": number (average wickets at this venue),
    "opponent_adj_runs": number (average runs vs this opponent),
    "opponent_adj_wickets": number (average wickets vs this opponent),
    "form_momentum_runs": number (weighted recent form score for batting),
    "form_momentum_wickets": number (weighted recent form score for bowling),
    "predicted_sr": number (expected strike rate),
    "predicted_economy": number (expected economy rate),
    "consistency": number between 0.5 and 1.0 (how consistent the player is)
  }}
]}}

RULES:
- Use real stats from the source data where available
- For missing data, use reasonable IPL T20 defaults based on player role:
  * Top-order batsman: ~30 runs avg, 0.2 wickets, SR 135
  * Middle-order: ~22 runs, 0.3 wickets, SR 130
  * All-rounder: ~18 runs, 1.0 wickets, SR 125, econ 8.0
  * Bowler: ~8 runs, 1.5 wickets, SR 110, econ 7.5
  * Wicketkeeper: ~25 runs, 0 wickets, SR 128
- Include all players from both teams (up to 11 per team)
- team field MUST be exactly '{team1}' or '{team2}'"""

    try:
        data = await _parse_to_json(raw_text, parse_instruction)
        players = data.get("players", [])
        logger.info(f"Parsed {len(players)} player stats")
        return players
    except Exception as e:
        logger.error(f"Player stats parse error: {e}")
        return []


async def gpt_contextual_analysis(match_context, team1, team2, score_summary, alerts):
    """
    GPT-5.4 mini: Quick contextual analysis and alert explanations.
    Used for real-time pattern detection and pressure assessment.
    """
    chat = _get_gpt_mini_chat(
        f"ctx-{uuid.uuid4().hex[:8]}",
        "You are an expert cricket analyst. Provide brief, sharp tactical insights. Respond ONLY with valid JSON."
    )

    alerts_str = "; ".join([a.get("message", "") for a in (alerts or [])[:5]])

    prompt = f"""Quick tactical analysis for {team1} vs {team2}.
Match state: {score_summary}
Phase: {match_context.get('phase', 'unknown')}
Pressure: {match_context.get('pressure', 'medium')}
Wickets pressure: {match_context.get('wickets_pressure', 'normal')}
Active alerts: {alerts_str if alerts_str else 'None'}

Return JSON:
{{
  "tactical_insight": "1-2 sentence sharp tactical observation",
  "pattern_detected": "any pattern (scoring acceleration, collapse, etc.) or null",
  "pressure_assessment": "brief assessment of current pressure dynamics",
  "recommended_strategy": "what the batting/bowling side should do",
  "key_phase": "powerplay/middle/death and why it matters now"
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
        logger.error(f"GPT contextual analysis error: {e}")
        return {
            "tactical_insight": "Analysis unavailable",
            "pattern_detected": None,
            "pressure_assessment": "Unable to assess",
            "recommended_strategy": "",
            "key_phase": match_context.get("phase", "unknown"),
        }
