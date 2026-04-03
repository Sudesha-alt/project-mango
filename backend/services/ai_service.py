import os
import logging
import json
import uuid
import re
from typing import Dict, List
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


async def gpt_consultation(user_question: str, consultation_data: Dict, risk_tolerance: str = "balanced"):
    """
    GPT-5.4: Answer user's betting question in layman language,
    analyzing all model outputs and risk profile.
    """
    chat = _get_gpt_chat(
        f"consult-{uuid.uuid4().hex[:8]}",
        """You are a sharp, no-nonsense gambling consultant. You analyze cricket match data and betting models to give clear, honest advice.

Rules:
- Speak in plain English. No jargon. As if explaining to a friend at a bar.
- Be direct: YES do it, NO don't, or WAIT.
- Always explain WHY in 2-3 sentences.
- Factor in their risk profile.
- Never guarantee outcomes. Acknowledge uncertainty.
- If the data says NO, say NO firmly. Don't sugarcoat.
- Reference specific numbers from the analysis (probability, edge, odds).
- Keep it under 150 words."""
    )

    # Build context from consultation data
    prob = consultation_data.get("win_probability", 50)
    signal = consultation_data.get("value_signal", "NO_BET")
    edge = consultation_data.get("edge_pct")
    confidence = consultation_data.get("confidence", 0.5)
    team = consultation_data.get("team", "")
    opponent = consultation_data.get("opponent", "")
    fair_odds = consultation_data.get("fair_decimal_odds", 0)
    market_odds = consultation_data.get("market_decimal_odds")
    drivers = consultation_data.get("top_drivers", [])
    uncertainty = consultation_data.get("uncertainty_band", {})
    recommendation = consultation_data.get("bet_recommendation", "")

    drivers_text = "; ".join(drivers[:4]) if drivers else "No clear drivers"

    prompt = f"""User asks: "{user_question}"

Risk profile: {risk_tolerance.upper()}

Current analysis for {team} vs {opponent}:
- Win probability: {prob}% (confidence: {confidence})
- Uncertainty range: {uncertainty.get('low', 0)*100:.0f}% to {uncertainty.get('high', 0)*100:.0f}%
- Model signal: {signal}
- Fair odds: {fair_odds}
- Market odds: {market_odds or 'not provided'}
- Edge: {edge}% {'(positive - model sees value)' if edge and edge > 0 else '(negative - market is better)' if edge and edge < 0 else ''}
- Key drivers: {drivers_text}
- System recommendation: {recommendation}

Answer their question directly. Be honest. Factor in their {risk_tolerance} risk profile."""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        return response.strip()
    except Exception as e:
        logger.error(f"GPT consultation error: {e}")
        return f"I couldn't analyze this right now. Based on the numbers: win probability is {prob}%, signal is {signal}. {recommendation}"


async def fetch_pre_match_stats(team1: str, team2: str, venue: str) -> Dict:
    """
    GPT-5.4 Web Search: Fetch real head-to-head (last 5 years),
    venue stats, recent form, and squad strength for two IPL teams.
    Expanded: requests match-by-match H2H detail, deeper form data.
    """
    raw_text = await _web_search(
        f"Search ESPNcricinfo and Cricbuzz for detailed IPL cricket stats for {team1} vs {team2}. "
        f"I need COMPREHENSIVE data: "
        f"1) COMPLETE head-to-head record between {team1} and {team2} in IPL from 2021 to 2026. "
        f"List every single match with date, venue, winner, and margin of victory. "
        f"How many matches each team won? Any dominant pattern? "
        f"2) Detailed performance at {venue} — average first innings score, average second innings score, "
        f"highest and lowest totals, win percentage batting first vs chasing, toss decision trends, "
        f"and each team's individual record at this ground. "
        f"3) Recent form — LAST 5 IPL 2026 match results for both teams with opponents and scores. "
        f"Include Net Run Rate if available. "
        f"4) Full squad strength — key batsmen averages, strike rates; key bowlers economy, wickets; "
        f"batting depth rating, bowling attack quality, overseas player impact for both teams."
    )
    logger.info(f"Pre-match stats web search for {team1} vs {team2}: {len(raw_text)} chars")

    parse_instruction = f"""Parse the cricket statistics into this exact JSON format:
{{
  "h2h": {{
    "team1_wins": number (wins for {team1} vs {team2} in IPL in last 5 years),
    "team2_wins": number (wins for {team2} vs {team1} in IPL in last 5 years),
    "no_result": number (ties or no results),
    "total_matches": number,
    "last_5_results": ["W", "L", "W", "W", "L"] (from {team1}'s perspective, most recent first),
    "match_details": [
      {{"date": "YYYY-MM-DD", "venue": "Ground", "winner": "Team", "margin": "5 wkts"}}
    ]
  }},
  "venue_stats": {{
    "venue_name": "{venue}",
    "team1_avg_score": number (average score for {team1} at this venue),
    "team2_avg_score": number (average score for {team2} at this venue),
    "avg_first_innings_score": number (overall average 1st innings score at venue),
    "avg_second_innings_score": number (overall average 2nd innings score at venue),
    "highest_total": number,
    "lowest_total": number,
    "bat_first_win_pct": number (win % batting first at this venue, 0-100),
    "team1_win_pct": number (win % for {team1} at this venue, 0-100),
    "team2_win_pct": number (win % for {team2} at this venue, 0-100),
    "team1_matches_at_venue": number,
    "team2_matches_at_venue": number,
    "is_team1_home": boolean (is this {team1}'s home ground?),
    "is_team2_home": boolean (is this {team2}'s home ground?)
  }},
  "form": {{
    "team1_last5_wins": number,
    "team1_last5_losses": number,
    "team1_last5_win_pct": number (0-100),
    "team1_recent_results": ["W vs CSK", "L vs MI", "W vs RR", "W vs DC", "L vs SRH"],
    "team1_nrr": number or null,
    "team2_last5_wins": number,
    "team2_last5_losses": number,
    "team2_last5_win_pct": number (0-100),
    "team2_recent_results": ["W vs KKR", "W vs GT", "L vs RCB", "W vs PBKS", "L vs LSG"],
    "team2_nrr": number or null
  }},
  "squad_strength": {{
    "team1_batting_rating": number (0-100, based on batting lineup quality),
    "team1_bowling_rating": number (0-100, based on bowling attack quality),
    "team1_key_players": ["Player1", "Player2", "Player3"],
    "team2_batting_rating": number (0-100),
    "team2_bowling_rating": number (0-100),
    "team2_key_players": ["Player1", "Player2", "Player3"]
  }}
}}

RULES:
- Use ONLY real data from the source text. 
- For stats not found in source, use reasonable IPL defaults:
  * H2H: if unknown, use 5-5 split
  * Venue avg: if unknown, use 165
  * Form: if unknown, use 50% win rate
  * Squad rating: estimate from known player quality (60-80 range)
- team1 is always {team1}, team2 is always {team2}
- match_details should contain as many matches as found in source (up to 20)"""

    try:
        data = await _parse_to_json(raw_text, parse_instruction)
        return data
    except Exception as e:
        logger.error(f"Pre-match stats parse error: {e}")
        return _default_pre_match_stats()


def _default_pre_match_stats():
    """Fallback stats when web search fails."""
    return {
        "h2h": {"team1_wins": 5, "team2_wins": 5, "no_result": 0, "total_matches": 10},
        "venue_stats": {
            "team1_avg_score": 165, "team2_avg_score": 165,
            "team1_win_pct": 50, "team2_win_pct": 50,
            "team1_matches_at_venue": 5, "team2_matches_at_venue": 5,
            "is_team1_home": False, "is_team2_home": False,
        },
        "form": {
            "team1_last5_wins": 3, "team1_last5_losses": 2, "team1_last5_win_pct": 60,
            "team2_last5_wins": 3, "team2_last5_losses": 2, "team2_last5_win_pct": 60,
        },
        "squad_strength": {
            "team1_batting_rating": 70, "team1_bowling_rating": 65,
            "team2_batting_rating": 68, "team2_bowling_rating": 67,
            "team1_key_players": [], "team2_key_players": [],
        },
    }



async def fetch_playing_xi(team1: str, team2: str, venue: str) -> Dict:
    """
    GPT-5.4 Web Search: Fetch expected/confirmed 2026 Playing XI for an IPL match.
    Returns player names, roles, and expected performance stats.
    """
    raw_text = await _web_search(
        f"Search for the expected or confirmed Playing XI for {team1} vs {team2} "
        f"IPL 2026 match at {venue}. "
        f"Search Cricbuzz, ESPNcricinfo for predicted or announced lineups. "
        f"For each player, I also need their IPL 2026 season stats so far: "
        f"runs scored, batting average, strike rate, wickets taken, economy rate. "
        f"Include whether each player is capped, uncapped, or overseas."
    )
    logger.info(f"Playing XI web search for {team1} vs {team2}: {len(raw_text)} chars")

    parse_instruction = f"""Parse the Playing XI data into this exact JSON format:
{{
  "team1_name": "{team1}",
  "team2_name": "{team2}",
  "team1_xi": [
    {{
      "name": "Player Name",
      "role": "Batsman/Bowler/All-rounder/Wicketkeeper",
      "is_overseas": boolean,
      "is_captain": boolean,
      "season_runs": number (IPL 2026 runs so far, 0 if not available),
      "season_avg": number (batting average this season),
      "season_sr": number (strike rate this season),
      "season_wickets": number (wickets this season),
      "season_economy": number (economy rate this season),
      "expected_runs": number (predicted runs for this match based on form),
      "expected_wickets": number (predicted wickets for this match)
    }}
  ],
  "team2_xi": [same structure as above],
  "confidence": "confirmed" or "predicted" (whether XI is officially announced or predicted)
}}

RULES:
- Include exactly 11 players per team if available
- Use real stats from source. For missing season stats use reasonable defaults:
  * Top-order bat: 30 runs, avg 28, SR 135, 0 wkts
  * Middle-order: 22 runs, avg 22, SR 128, 0 wkts
  * All-rounder: 18 runs, avg 20, SR 125, 1 wkt, econ 8.0
  * Bowler: 5 runs, avg 8, SR 100, 1.5 wkts, econ 7.8
  * Wicketkeeper: 25 runs, avg 25, SR 130
- team1 is {team1}, team2 is {team2}"""

    try:
        data = await _parse_to_json(raw_text, parse_instruction)
        return data
    except Exception as e:
        logger.error(f"Playing XI parse error: {e}")
        return {"team1_xi": [], "team2_xi": [], "confidence": "unavailable"}
