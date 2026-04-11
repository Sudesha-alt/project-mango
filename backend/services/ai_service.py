import os
import logging
import json
import uuid
import re
from typing import Dict, List, Optional
from emergentintegrations.llm.chat import LlmChat, UserMessage
from services.web_scraper import web_search, search_cricket_live, search_match_context, search_player_data, fetch_match_news

logger = logging.getLogger(__name__)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# ─── Claude Opus helpers ──────────────────────────────────────

def _get_claude_chat(session_id: str, system_msg: str):
    """Create a Claude Opus chat instance."""
    key = ANTHROPIC_KEY
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not configured in .env")
    chat = LlmChat(api_key=key, session_id=session_id, system_message=system_msg)
    chat.with_model("anthropic", "claude-opus-4-5-20251101")
    return chat


def _extract_json(text):
    """Robustly extract JSON from Claude response text."""
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


async def _claude_json(prompt: str, system_msg: str = "You are a precise data parser. Output ONLY valid JSON with no markdown formatting, no code blocks, no explanation.") -> dict:
    """Send a prompt to Claude and parse the JSON response."""
    chat = _get_claude_chat(f"parse-{uuid.uuid4().hex[:8]}", system_msg)
    response = await chat.send_message(UserMessage(text=prompt))
    return _extract_json(response)


# ─── Schedule & Squads ────────────────────────────────────────

async def fetch_ipl_schedule():
    """Fetch IPL 2026 schedule via web scraping + Claude parsing."""
    raw_text = await web_search(
        "IPL 2026 Indian Premier League complete schedule results fixtures all matches",
        max_results=10
    )
    logger.info(f"Web search schedule: {len(raw_text)} chars")

    prompt = f"""Parse the IPL 2026 schedule data below into this exact JSON format.
Return a JSON object: {{"matches": [...]}}

Each match object must have:
- "matchId": unique string like "ipl2026_001" (number based on match_number)
- "match_number": sequential integer
- "team1": full team name
- "team2": full team name
- "team1Short": abbreviation (CSK, MI, RCB, KKR, DC, RR, SRH, PBKS, GT, LSG)
- "team2Short": abbreviation
- "venue": stadium/city
- "dateTimeGMT": ISO date string (e.g. "2026-03-28T14:00:00Z")
- "status": exactly one of "Completed", "Live", or "Upcoming"
- "matchType": "T20"
- "series": "IPL 2026"

For Completed matches also include: "winner", "score", "manOfMatch"
For Upcoming matches no score/winner.

Source data:
{raw_text}"""

    try:
        data = await _claude_json(prompt)
        matches = data.get("matches", [])
        logger.info(f"Parsed {len(matches)} matches from web search")
        return matches
    except Exception as e:
        logger.error(f"Schedule parse error: {e}")
        return []


async def resolve_tbd_venues(matches: list) -> list:
    """Resolve TBD venues using web search + Claude."""
    tbd_matches = [m for m in matches if not m.get("venue") or m.get("venue") == "TBD"]
    if not tbd_matches:
        return matches

    match_list = "\n".join([
        f"Match #{m.get('match_number', '?')}: {m.get('team1Short', '?')} vs {m.get('team2Short', '?')} on {m.get('dateTimeGMT', '?')}"
        for m in tbd_matches[:40]
    ])

    raw_text = await web_search(f"IPL 2026 match venues stadium schedule {match_list[:200]}", max_results=6)
    logger.info(f"Venue resolution search: {len(raw_text)} chars")

    prompt = f"""Parse the venue data into JSON: {{"venues": [{{"match_number": number, "venue": "Stadium Name, City"}}]}}

Home grounds: CSK=MA Chidambaram Chennai, MI=Wankhede Mumbai, RCB=M Chinnaswamy Bengaluru,
KKR=Eden Gardens Kolkata, DC=Arun Jaitley Delhi, RR=Sawai Mansingh Jaipur,
SRH=Rajiv Gandhi Hyderabad, PBKS=IS Bindra Mohali, GT=Narendra Modi Ahmedabad, LSG=Ekana Lucknow.
If not found, assign home ground of team1.

Matches needing venues:
{match_list}

Source data:
{raw_text}"""

    try:
        data = await _claude_json(prompt)
        venue_map = {v["match_number"]: v["venue"] for v in data.get("venues", [])}
        for m in matches:
            mn = m.get("match_number")
            if mn in venue_map and venue_map[mn]:
                m["venue"] = venue_map[mn]
        return matches
    except Exception as e:
        logger.error(f"Venue resolution error: {e}")
        return matches


async def fetch_ipl_squads():
    """Fetch IPL 2026 squads via web search + Claude."""
    raw_text = await web_search("IPL 2026 all team squads player lists captain", max_results=8)

    prompt = f"""Parse the IPL 2026 squad data into JSON:
{{"squads": [
  {{"teamName": "Full Team Name", "teamShort": "ABR", "captain": "Captain Name",
    "players": [{{"name": "Player Name", "role": "Batsman/Bowler/All-rounder/Wicketkeeper", "isCaptain": false, "isKeeper": false, "isOverseas": false}}]
  }}
]}}

Source data:
{raw_text}"""

    try:
        data = await _claude_json(prompt)
        return data.get("squads", [])
    except Exception as e:
        logger.error(f"Squads parse error: {e}")
        return []


# ─── Live Match ───────────────────────────────────────────────

async def fetch_live_match_update(match_info):
    """Fetch live match data via web scraping + Claude parsing."""
    team1 = match_info.get("team1", "Team A")
    team2 = match_info.get("team2", "Team B")
    venue = match_info.get("venue", "")
    match_id = match_info.get("matchId", "")

    raw_text = await search_cricket_live(team1, team2)
    logger.info(f"Live search for {team1} vs {team2}: {len(raw_text)} chars")

    prompt = f"""Parse the cricket match data below into this exact JSON format:
{{
  "matchId": "{match_id}",
  "team1": "{team1}",
  "team2": "{team2}",
  "venue": "{venue}",
  "isLive": boolean (true if match is currently in progress),
  "noLiveMatch": boolean (true if NOT currently being played),
  "innings": 1 or 2,
  "battingTeam": "team currently batting",
  "bowlingTeam": "team currently bowling",
  "score": {{
    "runs": number, "wickets": number, "overs": number (like 15.2),
    "target": null or number (set if 2nd innings)
  }},
  "currentRunRate": number,
  "requiredRunRate": null or number,
  "recentBalls": ["4", "1", "W", "0", "6", "2"],
  "batsmen": [
    {{"name": "Player", "runs": number, "balls": number, "fours": number, "sixes": number, "strikeRate": number}}
  ],
  "bowler": {{"name": "Player", "overs": number, "runs": number, "wickets": number, "economy": number}},
  "fallOfWickets": [{{"player": "Name", "score": "score at fall", "overs": number}}],
  "recentOvers": [{{"over_num": number, "runs": number, "events": "description"}}],
  "partnerships": [{{"bat1": "Name", "bat2": "Name", "runs": number, "balls": number}}],
  "status": "descriptive match status text",
  "lastBallCommentary": "latest event description"
}}

RULES:
- If match IS live, set isLive=true, noLiveMatch=false, fill all score data
- If NOT live, set isLive=false, noLiveMatch=true
- Fill unavailable fields with reasonable defaults (empty arrays, null, 0)

Source data:
{raw_text}"""

    try:
        data = await _claude_json(prompt)
        return data
    except Exception as e:
        logger.error(f"Live data parse error: {e}")
        return None


# ─── Match Prediction ─────────────────────────────────────────

async def get_match_prediction(match_data):
    """Claude Opus match prediction with detailed analysis."""
    team1 = match_data.get("team1", "Team A")
    team2 = match_data.get("team2", "Team B")
    venue = match_data.get("venue", "")
    score = match_data.get("score", {})

    score_context = ""
    if isinstance(score, dict) and score.get("runs"):
        score_context = f"\nCurrent score: {score.get('runs', 0)}/{score.get('wickets', 0)} in {score.get('overs', 0)} overs."
        if score.get("target"):
            score_context += f" Target: {score['target']}"

    chat = _get_claude_chat(
        f"pred-{match_data.get('matchId', '')}-{uuid.uuid4().hex[:6]}",
        "You are an expert cricket analyst. Provide detailed match predictions. Respond ONLY with valid JSON."
    )

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
        return _extract_json(response)
    except Exception as e:
        logger.error(f"Claude prediction error: {e}")
        return {"team1WinProb": 0.5, "team2WinProb": 0.5, "analysis": "Prediction unavailable", "keyFactors": []}


async def get_player_predictions(team1, team2, venue, squad1=None, squad2=None):
    """Claude Opus player performance predictions."""
    chat = _get_claude_chat(
        f"players-{uuid.uuid4().hex[:8]}",
        "You are an expert IPL cricket analyst. Predict individual player performances. Respond ONLY with valid JSON."
    )

    squad1_str = ", ".join([p.get("name", "") for p in (squad1 or [])[:11]]) if squad1 else "Playing XI not available"
    squad2_str = ", ".join([p.get("name", "") for p in (squad2 or [])[:11]]) if squad2 else "Playing XI not available"

    prompt = f"""Predict player performances for this IPL 2026 match:
{team1} vs {team2} at {venue}

{team1} squad: {squad1_str}
{team2} squad: {squad2_str}

Return JSON:
{{
  "players": [
    {{
      "name": "Player Name", "team": "Team Name",
      "role": "Batsman/Bowler/All-rounder/Wicketkeeper",
      "batting": {{"predictedRuns": 35, "strikeRate": 140, "boundaryProb": 0.7, "fiftyProb": 0.3, "duckProb": 0.05, "confidence": 0.6}},
      "bowling": {{"predictedWickets": 1, "economy": 8.5, "dotBallPerc": 35, "maidenProb": 0.05, "confidence": 0.5}},
      "impactScore": 7.5
    }}
  ]
}}"""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        data = _extract_json(response)
        return data.get("players", [])
    except Exception as e:
        logger.error(f"Claude player predictions error: {e}")
        return []


# ─── Player Stats for Prediction Engine ───────────────────────

async def fetch_player_stats_for_prediction(team1, team2, team1_players, team2_players, venue):
    """Web search + Claude: Fetch real player stats for the prediction engine."""
    players_str = ""
    for p in (team1_players or [])[:11]:
        players_str += f"- {p.get('name', 'Unknown')} ({team1})\n"
    for p in (team2_players or [])[:11]:
        players_str += f"- {p.get('name', 'Unknown')} ({team2})\n"

    raw_text = await web_search(
        f"{team1} vs {team2} IPL 2026 player stats form runs wickets at {venue}",
        max_results=8
    )
    logger.info(f"Player stats search: {len(raw_text)} chars")

    prompt = f"""Parse the player statistics into this JSON format:
{{"players": [
  {{
    "name": "Player Name",
    "team": "Full Team Name (must be exactly '{team1}' or '{team2}')",
    "role": "Batsman/Bowler/All-rounder/Wicketkeeper",
    "last5_avg_runs": number, "last5_avg_wickets": number,
    "venue_avg_runs": number, "venue_avg_wickets": number,
    "opponent_adj_runs": number, "opponent_adj_wickets": number,
    "form_momentum_runs": number, "form_momentum_wickets": number,
    "predicted_sr": number, "predicted_economy": number,
    "consistency": number between 0.5 and 1.0
  }}
]}}

Players:
{players_str}

Use real stats from source. For missing data use IPL T20 defaults based on role.

Source data:
{raw_text}"""

    try:
        data = await _claude_json(prompt)
        players = data.get("players", [])
        logger.info(f"Parsed {len(players)} player stats")
        return players
    except Exception as e:
        logger.error(f"Player stats parse error: {e}")
        return []


# ─── Contextual Analysis (Quick) ─────────────────────────────

async def gpt_contextual_analysis(match_context, team1, team2, score_summary, alerts):
    """Claude Opus: Quick contextual analysis and alert explanations."""
    chat = _get_claude_chat(
        f"ctx-{uuid.uuid4().hex[:8]}",
        "You are an expert cricket analyst. Provide brief, sharp tactical insights. Respond ONLY with valid JSON."
    )

    alerts_str = "; ".join([a.get("message", "") for a in (alerts or [])[:5]])

    prompt = f"""Quick tactical analysis for {team1} vs {team2}.
Match state: {score_summary}
Phase: {match_context.get('phase', 'unknown')}
Pressure: {match_context.get('pressure', 'medium')}
Active alerts: {alerts_str if alerts_str else 'None'}

Return JSON:
{{
  "tactical_insight": "1-2 sentence sharp tactical observation",
  "pattern_detected": "any pattern or null",
  "pressure_assessment": "brief assessment",
  "recommended_strategy": "what sides should do",
  "key_phase": "powerplay/middle/death and why"
}}"""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        return _extract_json(response)
    except Exception as e:
        logger.error(f"Claude contextual analysis error: {e}")
        return {
            "tactical_insight": "Analysis unavailable",
            "pattern_detected": None,
            "pressure_assessment": "Unable to assess",
            "recommended_strategy": "",
            "key_phase": match_context.get("phase", "unknown"),
        }


# ─── Consultation Chat ───────────────────────────────────────

async def gpt_consultation(user_question: str, consultation_data: Dict, risk_tolerance: str = "balanced", live_context: str = None):
    """Claude Opus: Answer user's betting question in layman language."""
    chat = _get_claude_chat(
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
- If live match data is provided, use it: cite current score, batsmen performance, bowler impact, projected scores, phase of play.
- Keep it under 200 words."""
    )

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
- System recommendation: {recommendation}"""

    if live_context:
        prompt += f"""

=== LIVE MATCH DATA & ALGORITHM OUTPUTS ===
{live_context}
=== END LIVE DATA ===

Use the live match data above to enrich your answer. Reference specific player performances, algorithm probabilities, projected scores, and match phase."""

    prompt += f"""

Answer their question directly. Be honest. Factor in their {risk_tolerance} risk profile."""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        return response.strip()
    except Exception as e:
        logger.error(f"Claude consultation error: {e}")
        return f"I couldn't analyze this right now. Based on the numbers: win probability is {prob}%, signal is {signal}. {recommendation}"


# ─── Pre-Match Stats (11-Factor) ─────────────────────────────

async def fetch_pre_match_stats(team1: str, team2: str, venue: str) -> dict:
    """Web search + Claude: Fetch comprehensive 10-category pre-match stats (2023-2026 data only)."""
    raw_text = await search_match_context(team1, team2, venue)
    logger.info(f"Pre-match stats search for {team1} vs {team2}: {len(raw_text)} chars")

    prompt = f"""Parse the cricket statistics into this exact JSON format.
CRITICAL: Only use data from IPL seasons 2023, 2024, 2025, and 2026. Do NOT reference any pre-2023 stats, records, or events. The mega-auction happened before IPL 2025, making older team compositions irrelevant.

{{
  "h2h": {{
    "team1_wins": number (from 2023-2026 IPL only), "team2_wins": number (from 2023-2026 IPL only), "no_result": number, "total_matches": number,
    "last_5_results": ["W", "L", "W", "W", "L"],
    "match_details": [{{"date": "YYYY-MM-DD", "venue": "Ground", "winner": "Team", "margin": "5 wkts"}}]
  }},
  "venue_stats": {{
    "venue_name": "{venue}", "team1_avg_score": number, "team2_avg_score": number,
    "avg_first_innings_score": number, "avg_second_innings_score": number,
    "highest_total": number, "lowest_total": number, "bat_first_win_pct": number,
    "team1_win_pct": number, "team2_win_pct": number,
    "team1_matches_at_venue": number, "team2_matches_at_venue": number,
    "is_team1_home": boolean, "is_team2_home": boolean
  }},
  "form": {{
    "team1_last5_wins": number (IPL 2026 season only), "team1_last5_losses": number, "team1_last5_win_pct": number,
    "team1_recent_results": ["W vs CSK by 20 runs", "L vs MI by 5 wkts"],
    "team1_nrr": number or null (current IPL 2026 NRR),
    "team2_last5_wins": number (IPL 2026 season only), "team2_last5_losses": number, "team2_last5_win_pct": number,
    "team2_recent_results": ["W vs KKR by 8 wkts"],
    "team2_nrr": number or null (current IPL 2026 NRR)
  }},
  "squad_strength": {{
    "team1_batting_rating": number (0-100), "team1_bowling_rating": number (0-100),
    "team1_key_players": ["Player1", "Player2", "Player3"],
    "team2_batting_rating": number (0-100), "team2_bowling_rating": number (0-100),
    "team2_key_players": ["Player1", "Player2", "Player3"]
  }},
  "toss": {{
    "toss_bat_pct": number, "toss_bowl_pct": number,
    "toss_winner_match_win_pct": number, "venue_chase_friendly": boolean
  }},
  "pitch_conditions": {{
    "pitch_type": "batting"/"bowling"/"balanced",
    "pace_assistance": number (1-10), "spin_assistance": number (1-10),
    "dew_factor": number (1-10), "avg_first_innings_score": number,
    "description": "Brief pitch description"
  }},
  "key_matchups": {{
    "team1_batters_vs_team2_bowlers": [{{"batter": "Name", "bowler": "Name", "runs": number, "balls": number, "dismissals": number, "sr": number}}],
    "team2_batters_vs_team1_bowlers": [same format]
  }},
  "death_overs": {{
    "team1_avg_death_score": number, "team1_avg_death_conceded": number,
    "team2_avg_death_score": number, "team2_avg_death_conceded": number
  }},
  "powerplay": {{
    "team1_avg_pp_score": number, "team1_avg_pp_wickets_lost": number,
    "team2_avg_pp_score": number, "team2_avg_pp_wickets_lost": number
  }},
  "momentum": {{
    "team1_current_streak": number (positive = winning streak, negative = losing),
    "team2_current_streak": number,
    "team1_last10_wins": number (out of last 10 IPL matches in 2025-2026),
    "team2_last10_wins": number
  }},
  "injuries": {{
    "team1_injuries": [{{"player": "Name", "impact_score": number (1-10, how key is this player), "reason": "hamstring/rested/dropped"}}],
    "team2_injuries": [same format]
  }}
}}

IMPORTANT: Use ONLY real data from IPL 2023-2026. For missing stats, use reasonable IPL defaults.
For injuries: report any confirmed injuries, fitness concerns, or player absences announced in the last 48 hours.
team1={team1}, team2={team2}

Source data:
{raw_text[:12000]}"""

    try:
        data = await _claude_json(prompt)
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
            "bat_first_win_pct": 48,
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
        "toss": {"toss_bat_pct": 45, "toss_bowl_pct": 55, "toss_winner_match_win_pct": 52, "venue_chase_friendly": True},
        "pitch_conditions": {"pitch_type": "balanced", "pace_assistance": 5, "spin_assistance": 5, "dew_factor": 3, "description": "Balanced surface"},
        "key_matchups": {"team1_batters_vs_team2_bowlers": [], "team2_batters_vs_team1_bowlers": []},
        "death_overs": {"team1_avg_death_score": 45, "team1_avg_death_conceded": 48, "team2_avg_death_score": 45, "team2_avg_death_conceded": 48},
        "powerplay": {"team1_avg_pp_score": 48, "team1_avg_pp_wickets_lost": 1.2, "team2_avg_pp_score": 48, "team2_avg_pp_wickets_lost": 1.2},
        "momentum": {"team1_current_streak": 0, "team2_current_streak": 0, "team1_last10_wins": 5, "team2_last10_wins": 5},
        "injuries": {"team1_injuries": [], "team2_injuries": []},
    }


# ─── Playing XI ───────────────────────────────────────────────

async def fetch_playing_xi(team1: str, team2: str, venue: str, squads: dict = None) -> Dict:
    """Web search + Claude: Fetch expected Playing XI with buzz scores.
    Uses actual squad rosters from DB when provided."""
    raw_text = await search_player_data(team1, team2, venue)
    logger.info(f"Playing XI search for {team1} vs {team2}: {len(raw_text)} chars")

    # Build squad constraint block if DB squads are available
    squad_block = ""
    if squads:
        for team_name, players in squads.items():
            if players:
                player_lines = []
                for p in players:
                    name = p.get("name", "?")
                    role = p.get("role", "Unknown")
                    overseas = " [OVERSEAS]" if p.get("isOverseas") else ""
                    captain = " [CAPTAIN]" if p.get("isCaptain") else ""
                    player_lines.append(f"  - {name} ({role}){overseas}{captain}")
                squad_block += f"\n{team_name} OFFICIAL SQUAD ({len(players)} players):\n" + "\n".join(player_lines) + "\n"

    squad_instruction = ""
    if squad_block:
        squad_instruction = f"""
CRITICAL CONSTRAINT — OFFICIAL IPL 2026 SQUADS:
You MUST ONLY select players from the official squads below. Do NOT invent or include any player not in these lists.
Max 4 overseas players per XI. The captain from the squad should be marked is_captain: true.
{squad_block}"""

    prompt = f"""Pick the expected Playing XI for both teams from their official squads. Return JSON:
{{
  "team1_name": "{team1}",
  "team2_name": "{team2}",
  "team1_xi": [
    {{
      "name": "Player Name",
      "role": "Batsman/Bowler/All-rounder/Wicketkeeper",
      "is_overseas": boolean,
      "is_captain": boolean,
      "base_expected_runs": number,
      "base_expected_wickets": number,
      "buzz_score": number (-100 to +100),
      "buzz_reason": "1-sentence explanation"
    }}
  ],
  "team2_xi": [same structure],
  "confidence": "confirmed" or "predicted"
}}
{squad_instruction}
RULES:
- EXACTLY 11 players per team. Max 4 overseas per XI.
- ONLY pick players from the official squads above. Do NOT invent players.
- buzz_score: -100 to +100. Positive = good form, Negative = injury/poor form.
- buzz_reason: specific facts from 2023-2026 source data or recent IPL knowledge. Do NOT reference pre-2023 stats.
- team1={team1}, team2={team2}

Source data:
{raw_text[:8000]}"""

    try:
        data = await _claude_json(prompt)
        return data
    except Exception as e:
        logger.error(f"Playing XI parse error: {e}")
        return {"team1_xi": [], "team2_xi": [], "confidence": "unavailable"}


# ─── Claude Deep Narrative Analysis (NEW) ─────────────────────

def _format_top_performers(performers: list) -> str:
    """Format top performers list, handling both string and dict items."""
    if not performers:
        return "N/A"
    result = []
    for p in performers[:5]:
        if isinstance(p, str):
            result.append(p)
        elif isinstance(p, dict):
            name = p.get("name", p.get("player", "?"))
            score = p.get("score", p.get("form_score", ""))
            result.append(f"{name}" + (f" ({score})" if score else ""))
        else:
            result.append(str(p))
    return ", ".join(result) or "N/A"


async def claude_deep_match_analysis(team1: str, team2: str, venue: str, match_info: dict,
                                     squads: dict = None, news: list = None,
                                     algo_prediction: dict = None, player_performance: dict = None,
                                     weather: dict = None, form_data: dict = None) -> dict:
    """
    Claude Opus: Elite 7-layer pre-match analysis.
    Combines actual SportMonks API data (Expected XI, player stats, H2H, algorithm output)
    with Claude's contextual cricket intelligence.
    """
    t1_short = match_info.get("team1Short", team1[:3].upper())
    t2_short = match_info.get("team2Short", team2[:3].upper())
    date_str = match_info.get("dateTimeGMT", "")
    time_ist = match_info.get("timeIST", "")
    match_num = match_info.get("match_number", "")
    city = match_info.get("city", "")

    # ── Build Expected Playing XI section ──
    squad_block = ""
    if squads:
        for team_name, players in squads.items():
            if players:
                player_lines = []
                for p in players:
                    name = p.get("name", "?")
                    role = p.get("role", "Unknown")
                    overseas = " [OVERSEAS]" if p.get("isOverseas") else ""
                    captain = " [C]" if p.get("isCaptain") else ""
                    player_lines.append(f"  - {name} ({role}){overseas}{captain}")
                squad_block += f"\n{team_name} EXPECTED PLAYING XI ({len(players)} players):\n" + "\n".join(player_lines) + "\n"

    # ── Build player performance stats section ──
    perf_block = ""
    if player_performance:
        for team_key, label in [("team1", team1), ("team2", team2)]:
            team_perf = player_performance.get(team_key, {})
            if team_perf:
                perf_lines = []
                for pid, ps in team_perf.items():
                    name = ps.get("name", "?")
                    matches = ps.get("matches", 0)
                    bat = ps.get("batting", {})
                    bowl = ps.get("bowling", {})
                    line = f"  {name}: {matches} matches"
                    if bat.get("innings", 0) > 0:
                        line += f" | Bat: {bat.get('runs',0)} runs, Avg {bat.get('avg',0)}, SR {bat.get('sr',0)}"
                    if bowl.get("innings", 0) > 0:
                        line += f" | Bowl: {bowl.get('wickets',0)} wkts, Econ {bowl.get('economy',0)}"
                    perf_lines.append(line)
                if perf_lines:
                    perf_block += f"\n{label} — PLAYER FORM (Last 5 matches from SportMonks) [SPORTMONKS DATA]:\n" + "\n".join(perf_lines) + "\n"

    # ── Build algorithm prediction section ──
    algo_block = ""
    if algo_prediction:
        pred = algo_prediction.get("prediction", algo_prediction)
        factors = pred.get("factors", {})
        algo_block = f"""
=== ALGORITHM OUTPUT [SPORTMONKS DATA] ===
Match Winner Probability: {t1_short} {pred.get('team1_win_prob', 50)}% / {t2_short} {pred.get('team2_win_prob', 50)}%
Model Confidence: {pred.get('confidence', 'unknown')}
Combined Logit: {pred.get('combined_logit', 0)}

Category Breakdown:
- Squad Strength (25%): {t1_short} bat {factors.get('squad_strength',{}).get('team1_batting','?')}/bowl {factors.get('squad_strength',{}).get('team1_bowling','?')} | {t2_short} bat {factors.get('squad_strength',{}).get('team2_batting','?')}/bowl {factors.get('squad_strength',{}).get('team2_bowling','?')} | Logit: {factors.get('squad_strength',{}).get('logit_contribution',0)}
- Current Form (21%): {t1_short} score {factors.get('current_form',{}).get('team1_form_score','?')} ({factors.get('current_form',{}).get('team1_wins',0)}W) | {t2_short} score {factors.get('current_form',{}).get('team2_form_score','?')} ({factors.get('current_form',{}).get('team2_wins',0)}W) | Logit: {factors.get('current_form',{}).get('logit_contribution',0)}
- Venue+Pitch+Home (18%): Pitch: {factors.get('venue_pitch_home',{}).get('pitch_type','?')}, Pace: {factors.get('venue_pitch_home',{}).get('pace_assist','?')}, Spin: {factors.get('venue_pitch_home',{}).get('spin_assist','?')}, Home: {factors.get('venue_pitch_home',{}).get('home_team','neutral')} | Logit: {factors.get('venue_pitch_home',{}).get('logit_contribution',0)}
- H2H (11%): {t1_short} {factors.get('h2h',{}).get('team1_wins',0)} wins / {t2_short} {factors.get('h2h',{}).get('team2_wins',0)} wins (total {factors.get('h2h',{}).get('total',0)}) | Logit: {factors.get('h2h',{}).get('logit_contribution',0)}
- Toss Impact (9%): Time: {factors.get('toss_impact',{}).get('match_time_class','?')}, Dew: {factors.get('toss_impact',{}).get('dew_factor','none')}, Pref: {factors.get('toss_impact',{}).get('preferred_decision','?')} | Logit: {factors.get('toss_impact',{}).get('logit_contribution',0)}
- Bowling Depth (8%): {t1_short} VQ:{factors.get('bowling_depth',{}).get('team1_venue_quality','?')} ({factors.get('bowling_depth',{}).get('team1_variety','?')}) | {t2_short} VQ:{factors.get('bowling_depth',{}).get('team2_venue_quality','?')} ({factors.get('bowling_depth',{}).get('team2_variety','?')}) | Logit: {factors.get('bowling_depth',{}).get('logit_contribution',0)}
- Conditions (5%): {factors.get('conditions',{}).get('conditions_edge_text','Neutral')} | Logit: {factors.get('conditions',{}).get('logit_contribution',0)}
- Momentum (3%): {t1_short} last 2: {factors.get('momentum',{}).get('team1_last2',[])} | {t2_short} last 2: {factors.get('momentum',{}).get('team2_last2',[])} | Logit: {factors.get('momentum',{}).get('logit_contribution',0)}

Top Performers (from form data):
{t1_short}: {_format_top_performers(factors.get('current_form',{}).get('team1_top_performers',[]))}
{t2_short}: {_format_top_performers(factors.get('current_form',{}).get('team2_top_performers',[]))}
"""

    # ── Build H2H section ──
    h2h_block = ""
    if form_data and form_data.get("h2h"):
        h2h = form_data["h2h"]
        h2h_block = f"""
=== HEAD-TO-HEAD RECORD [SPORTMONKS DATA] ===
{t1_short} wins: {h2h.get('team1_wins', 0)} | {t2_short} wins: {h2h.get('team2_wins', 0)} | Total: {h2h.get('team1_wins',0) + h2h.get('team2_wins',0)}
Source: {h2h.get('source', 'season_2026')}
"""

    # ── Build weather section ──
    weather_block = ""
    if weather and weather.get("available"):
        cur = weather.get("current", {})
        impact = weather.get("cricket_impact", {})
        weather_block = f"""
=== WEATHER & PITCH CONDITIONS ===
Temperature: {cur.get('temperature', 'N/A')}C | Humidity: {cur.get('humidity', 'N/A')}% | Wind: {cur.get('wind_speed_kmh', 'N/A')} km/h
Condition: {cur.get('condition', 'N/A')}
Dew Factor: {impact.get('dew_factor', 'unknown')} | Cricket Impact: {impact.get('summary', 'N/A')}
"""

    # ── Build news section ──
    news_section = ""
    if news:
        t1_words = set(team1.lower().split())
        t2_words = set(team2.lower().split())
        relevant = []
        for article in news[:8]:
            title_lower = (article.get("title", "") or "").lower()
            body_lower = (article.get("body", "") or "").lower()
            text = title_lower + " " + body_lower
            t1_match = any(w in text for w in t1_words if len(w) > 3)
            t2_match = any(w in text for w in t2_words if len(w) > 3)
            ipl_match = "ipl" in text or "cricket" in text
            if (t1_match or t2_match) and ipl_match:
                relevant.append(article)
        news_lines = []
        for article in relevant[:5]:
            title = article.get("title", "")
            body = article.get("body", "")[:200]
            if title:
                news_lines.append(f"  - {title}" + (f": {body}" if body else ""))
        if news_lines:
            news_section = "\n=== LATEST NEWS ===\n" + "\n".join(news_lines) + "\n"

    chat = _get_claude_chat(
        f"deep-{uuid.uuid4().hex[:8]}",
        """You are an elite IPL cricket analyst and prediction engine. You produce structured, data-driven, layered match previews that combine live API data with deep contextual cricket intelligence. Your analysis is opinionated, precise, and built for serious cricket followers who want more than surface-level previews.

ANALYTICAL PHILOSOPHY — NON-NEGOTIABLE RULES:
1. Every layer gets an ADVANTAGE verdict. No draws, no "both teams are evenly matched." Pick a side and justify it.
2. Absent players change everything. If a key player is not in the API-returned XI, rebuild team assessments without them.
3. Stats anchor every claim. Averages, strike rates, economy rates — name the numbers. No vague "good form" without figures.
4. Recency beats history. Last 4 games outweigh 5-year H2H record. Say so explicitly.
5. Venue and timing are tactical, not decorative. Every venue point must connect to specific bowler types or batting strategies.
6. Win probability must reflect genuine asymmetry. Never default to false 50/50.
7. Algorithm vs analyst tension is a feature. When your prediction diverges from the algorithm, explain why.
8. Label all SportMonks data clearly with [SPORTMONKS DATA] tags.

STYLE: Sharp, confident, direct. Short sentences. Zero hedging. Write for someone who watches every IPL game. Always name names — never "their opening bowler." Disagreeing with the algorithm is encouraged when contextual case is strong.

CRITICAL DATA CONSTRAINT: Only use IPL 2023-2026 data. Only reference players from the Expected Playing XI — the actual 11, NOT the full squad."""
    )

    prompt = f"""Analyze this IPL 2026 match using the data below. Produce a full 7-layer contextual analysis.

Match: {team1} ({t1_short}) vs {team2} ({t2_short})
Match #{match_num} | Venue: {venue} | City: {city}
Date: {date_str} | Time (IST): {time_ist}

=== EXPECTED PLAYING XIs [SPORTMONKS DATA] ===
{squad_block}
{perf_block}
{algo_block}
{h2h_block}
{weather_block}
{news_section}
=== END DATA ===

Return a JSON object with this EXACT structure:
{{
  "match_header": {{
    "match_number": {match_num or 0},
    "venue": "{venue}",
    "city": "{city}",
    "date": "{date_str}",
    "time_ist": "{time_ist}",
    "time_slot": "AFTERNOON" or "EVENING",
    "home_team": "{t1_short}" or "{t2_short}" or "NEUTRAL"
  }},
  "team1_xi_display": [list of {t1_short} player names in batting order],
  "team2_xi_display": [list of {t2_short} player names in batting order],
  "xi_availability_notes": ["Any notable absences or uncertain availability"],
  "layers": [
    {{
      "layer_num": 1,
      "title": "SQUAD STRENGTH AND CURRENT FORM",
      "analysis": "Assess both teams' overall squad balance with the actual XI. Use form scores to identify who is in form and who is not. Assess bowling depth, batting depth, all-rounder presence, structural weaknesses from absences. 4-6 sentences.",
      "advantage": "{t1_short}" or "{t2_short}",
      "advantage_reason": "One-line reason"
    }},
    {{
      "layer_num": 2,
      "title": "KEY MATCHUPS",
      "analysis": "Identify 2-3 decisive batter vs bowler matchups. For each, state runs, balls, dismissals, SR where available. Identify THE single most decisive matchup. 4-6 sentences.",
      "advantage": "{t1_short}" or "{t2_short}",
      "advantage_reason": "One-line reason"
    }},
    {{
      "layer_num": 3,
      "title": "VENUE AND PITCH ANALYSIS",
      "analysis": "Use venue stats: avg first innings score, batting first win %, pace vs spin economy. Connect pitch to specific bowlers in each XI. Factor in match timing (afternoon=no dew, evening=dew). 4-6 sentences.",
      "advantage": "{t1_short}" or "{t2_short}",
      "advantage_reason": "One-line reason"
    }},
    {{
      "layer_num": 4,
      "title": "BOWLING DEPTH AND ATTACK QUALITY",
      "analysis": "Break down bowling attacks by phase: powerplay, middle, death. Name specific bowlers per phase. Assess quality, economy, form. Identify which attack more likely to restrict. 4-6 sentences.",
      "advantage": "{t1_short}" or "{t2_short}",
      "advantage_reason": "One-line reason"
    }},
    {{
      "layer_num": 5,
      "title": "DEATH BOWLING (OVERS 16-20)",
      "analysis": "Most decisive T20 phase. Assess death bowling options by name. State death economy rates. Identify weakest link in each death attack. 3-5 sentences.",
      "advantage": "{t1_short}" or "{t2_short}",
      "advantage_reason": "One-line reason"
    }},
    {{
      "layer_num": 6,
      "title": "HEAD-TO-HEAD (RECENCY-WEIGHTED)",
      "analysis": "Overall H2H record, last 5, venue-specific. Apply recency weighting — last 3 count more. Discount results where key players were absent. 3-5 sentences.",
      "advantage": "{t1_short}" or "{t2_short}",
      "advantage_reason": "One-line reason"
    }},
    {{
      "layer_num": 7,
      "title": "IMPACT PLAYER OPTIONS",
      "analysis": "Assess likely impact sub choices given pitch and match demands. Evaluate fit for this specific game. 2-4 sentences.",
      "advantage": "{t1_short}" or "{t2_short}",
      "advantage_reason": "One-line reason"
    }}
  ],
  "algorithm_predictions": {{
    "algo_team1_win_pct": number (from algorithm data above),
    "algo_team2_win_pct": number,
    "algo_potm": "Player name from top performers data",
    "algo_top_batters": ["name1", "name2"],
    "algo_top_bowlers": ["name1", "name2"]
  }},
  "team1_win_pct": number (YOUR analyst prediction, 0-100),
  "team2_win_pct": number (YOUR analyst prediction, 0-100),
  "headline": "One bold line — the single biggest factor deciding this match",
  "key_injuries": [
    {{
      "player": "Player Name",
      "team": "{t1_short}" or "{t2_short}",
      "status": "Out" or "Doubtful" or "Fit",
      "impact": "1 sentence impact"
    }}
  ],
  "batting_first_scenario": {{
    "if_team1_bats": {{"team1_win_pct": number}},
    "if_team2_bats": {{"team2_win_pct": number}}
  }},
  "analyst_potm": {{
    "player": "Name",
    "reasons": ["Stat-backed reason 1", "Reason 2", "Reason 3"]
  }},
  "deciding_factor": "One paragraph. What is THE single variable that determines this match? State it plainly and explain what happens if it goes each way.",
  "first_6_overs_signal": "Name exactly what to watch in the powerplay — a specific player/matchup that tells you how the match unfolds.",
  "deciding_logic": "3-5 sentences — your complete reasoning chain for the final probability.",
  "prediction_summary": "1-2 sentence bold prediction with percentage",
  "algo_divergence_note": "If your prediction differs from the algorithm by >10%, explain why in 2-3 sentences. Otherwise null.",
  "confidence": "Low" or "Low-medium" or "Medium" or "Medium-high" or "High",
  "confidence_reason": "Why this confidence level"
}}

RULES:
- All 7 layers MUST have an ADVANTAGE verdict. No ties.
- Only reference players in the Expected Playing XI.
- Win probabilities must add to 100.
- Be opinionated and bold. If one team is structurally superior, reflect it (e.g. 65/35).
- Every claim needs a stat or specific recent event behind it."""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        return _extract_json(response)
    except Exception as e:
        logger.error(f"Claude deep analysis error: {e}")
        return {"error": str(e), "team1_win_pct": 50, "team2_win_pct": 50, "layers": [], "headline": "Analysis unavailable"}


# ─── Claude Live Match Analysis (NEW) ─────────────────────────

async def claude_live_analysis(match_info: dict, live_data: dict, algo_probs: dict, squads: dict = None) -> dict:
    """
    Claude Opus: Generate real-time analysis during a live match.
    Combines scraped live data with algorithm outputs and full squad info.
    """
    team1 = match_info.get("team1", "Team A")
    team2 = match_info.get("team2", "Team B")
    t1_short = match_info.get("team1Short", team1[:3].upper())
    t2_short = match_info.get("team2Short", team2[:3].upper())

    # Squad info
    squads = squads or {}
    squad1 = squads.get(team1, [])
    squad2 = squads.get(team2, [])

    def format_squad(players):
        if not players:
            return "  Squad not available"
        lines = []
        for p in players:
            if isinstance(p, dict):
                name = p.get("name", "?")
                role = p.get("role", "")
                lines.append(f"  {name} ({role})" if role else f"  {name}")
            else:
                lines.append(f"  {p}")
        return "\n".join(lines)

    squad1_text = format_squad(squad1)
    squad2_text = format_squad(squad2)

    # Scrape latest live data
    live_scraped = await search_cricket_live(team1, team2)

    chat = _get_claude_chat(
        f"live-analysis-{uuid.uuid4().hex[:8]}",
        """You are a live cricket match analyst providing real-time betting insights. 
Be sharp, data-driven, and reference specific player performances happening NOW.
Never hedge — give clear directional advice.

CRITICAL DATA CONSTRAINT: Only reference cricket data from 2023-2026. Do NOT cite any player stats, records, or historical performances from before 2023. Only reference players from the Expected Playing XI provided — these are the 11 players on the field, not the full squad."""
    )

    prompt = f"""Analyze this LIVE IPL 2026 match. Give me a real-time prediction update.

{team1} ({t1_short}) vs {team2} ({t2_short})

=== {team1} EXPECTED PLAYING XI ===
{squad1_text}

=== {team2} EXPECTED PLAYING XI ===
{squad2_text}

=== LIVE MATCH DATA (from our system) ===
{json.dumps(live_data, indent=2, default=str)[:4000]}

=== ALGORITHM PROBABILITIES ===
{json.dumps(algo_probs, indent=2, default=str)[:1000]}

=== LATEST SCRAPED DATA ===
{live_scraped[:4000]}

Consider the Playing XIs above — remaining batting depth, available bowling changes, and each player's IPL form. Only reference these 11 players per team.

Return JSON:
{{
  "current_state_summary": "2-3 sentence summary of where the match stands RIGHT NOW",
  "momentum": "{t1_short}" or "{t2_short}" or "EVEN",
  "momentum_reason": "Why momentum favors this team",
  "key_batsman_assessment": [
    {{"name": "Player", "assessment": "How they're playing right now", "threat_level": "HIGH/MEDIUM/LOW"}}
  ],
  "key_bowler_assessment": [
    {{"name": "Player", "assessment": "How they're bowling", "threat_level": "HIGH/MEDIUM/LOW"}}
  ],
  "phase_analysis": "What phase of the game we're in and what to expect next",
  "projected_outcome": "What's likely to happen based on current trajectory",
  "betting_advice": "Clear, direct betting advice for RIGHT NOW",
  "win_probability": {{
    "{t1_short}": number (0-100),
    "{t2_short}": number (0-100)
  }},
  "confidence": "Low/Medium/High"
}}"""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        return _extract_json(response)
    except Exception as e:
        logger.error(f"Claude live analysis error: {e}")
        return {"error": str(e), "current_state_summary": "Live analysis unavailable"}



# ─── Claude SportMonks Live Win Prediction ────────────────────

async def claude_sportmonks_prediction(sm_data: dict, algo_probs: dict, match_info: dict, squads: dict = None, weather: dict = None, news: list = None, gut_feeling: str = None, betting_odds_pct: float = None, dls_info: str = None) -> dict:
    """
    Claude Opus: Generate a live win prediction using rich SportMonks data.
    Passes full batting card, bowling card, yet-to-bat, yet-to-bowl lineups,
    and BOTH team squads so Claude can assess remaining depth and predict the outcome.
    """
    team1 = match_info.get("team1", "Team A")
    team2 = match_info.get("team2", "Team B")
    t1_short = match_info.get("team1Short", team1[:3].upper())
    t2_short = match_info.get("team2Short", team2[:3].upper())
    venue = match_info.get("venue", "")

    batting_team = sm_data.get("batting_team", team1)
    current_inn = sm_data.get("current_innings", 1)
    current_score = sm_data.get("current_score", {})
    target = sm_data.get("target")

    # ── Squad info ──
    squads = squads or {}
    squad1 = squads.get(team1, [])
    squad2 = squads.get(team2, [])

    def format_squad(players):
        if not players:
            return "  Squad not available"
        lines = []
        for p in players:
            if isinstance(p, dict):
                name = p.get("name", "?")
                role = p.get("role", "")
                lines.append(f"  {name} ({role})" if role else f"  {name}")
            else:
                lines.append(f"  {p}")
        return "\n".join(lines)

    squad1_text = format_squad(squad1)
    squad2_text = format_squad(squad2)

    current_inn = sm_data.get("current_innings", 1)
    current_score = sm_data.get("current_score", {})
    target = sm_data.get("target")

    # Active batsmen at crease
    active_bat = sm_data.get("active_batsmen", [])
    active_bat_text = "\n".join(
        f"  {b.get('name','?')} — {b.get('runs',0)}({b.get('balls',0)}) "
        f"SR:{b.get('strike_rate',0)} 4s:{b.get('fours',0)} 6s:{b.get('sixes',0)}"
        for b in active_bat
    ) or "  No active batsmen data"

    # Full batting card for current innings
    bat_key = f"batsmen_inn{current_inn}"
    all_batsmen = sm_data.get(bat_key, [])
    full_bat_text = "\n".join(
        f"  {b.get('name','?')} — {b.get('runs',0)}({b.get('balls',0)}) "
        f"SR:{b.get('strike_rate',0)} 4s:{b.get('fours',0)} 6s:{b.get('sixes',0)}"
        + (" *BATTING*" if b.get('active') else "")
        for b in all_batsmen
    ) or "  No batting data"

    # Yet to bat
    yet_to_bat = sm_data.get("yet_to_bat", [])
    ytb_text = ", ".join(p.get("name", "?") for p in yet_to_bat) or "None / tail-enders"

    # Active bowler
    active_bwl = sm_data.get("active_bowler") or {}
    active_bwl_text = (
        f"  {active_bwl.get('name','?')} — {active_bwl.get('overs',0)}-{active_bwl.get('maidens',0)}-"
        f"{active_bwl.get('runs',0)}-{active_bwl.get('wickets',0)} Econ:{active_bwl.get('economy',0)}"
        if active_bwl else "  No active bowler data"
    )

    # Full bowling card for current innings
    bowl_key = f"bowlers_inn{current_inn}"
    all_bowlers = sm_data.get(bowl_key, [])

    # Yet to bowl
    yet_to_bowl = sm_data.get("yet_to_bowl", [])
    ytbowl_text = ", ".join(p.get("name", "?") for p in yet_to_bowl) or "None / all bowled"

    # Previous innings summary (if 2nd innings)
    prev_inn_text = ""
    if current_inn == 2:
        inn1_score = sm_data.get("innings", {}).get("1", {})
        prev_inn_text = f"1st Innings: {inn1_score.get('runs',0)}/{inn1_score.get('wickets',0)} in {inn1_score.get('overs',0)} overs"
        if target:
            prev_inn_text += f" | Target: {target}"

    # Recent balls for momentum
    recent = sm_data.get("recent_balls", [])
    recent_text = " ".join(str(b) for b in recent[-12:]) if recent else "No ball-by-ball data"

    # Weather context
    weather_text = "Weather data not available"
    if weather and weather.get("available"):
        cur = weather.get("current", {})
        impact = weather.get("cricket_impact", {})
        weather_text = (
            f"Temperature: {cur.get('temperature', 'N/A')}C (Feels like {cur.get('feels_like', 'N/A')}C)\n"
            f"Humidity: {cur.get('humidity', 'N/A')}%\n"
            f"Wind: {cur.get('wind_speed_kmh', 'N/A')} km/h\n"
            f"Condition: {cur.get('condition', 'N/A')}\n"
            f"Dew Factor: {impact.get('dew_factor', 'unknown')}\n"
            f"Cricket Impact: {impact.get('summary', 'N/A')}"
        )

    # Match date/time context
    match_dt = match_info.get("dateTimeGMT", "")
    time_ist = match_info.get("timeIST", "")
    match_date_text = f"Match Date: {match_dt}" + (f" ({time_ist} IST)" if time_ist else "")

    # News context
    news_text = "No recent news available"
    if news:
        news_lines = []
        for article in news[:5]:
            title = article.get("title", "")
            body = article.get("body", "")[:150]
            if title:
                news_lines.append(f"  - {title}" + (f": {body}" if body else ""))
        if news_lines:
            news_text = "\n".join(news_lines)

    # User context (gut feeling + betting odds)
    user_context_text = ""
    if gut_feeling and gut_feeling.strip():
        user_context_text += f"\n=== USER'S GUT FEELING (weigh this as a qualitative signal) ===\n{gut_feeling}\n"
    if betting_odds_pct is not None and betting_odds_pct > 0:
        user_context_text += f"\n=== CURRENT BETTING MARKET ODDS ===\n{t1_short} implied probability: {betting_odds_pct}% | {t2_short} implied probability: {round(100 - betting_odds_pct, 1)}%\nNote: Market odds reflect live money flow and crowd sentiment. Factor this into your analysis.\n"
    if dls_info and dls_info.strip():
        user_context_text += f"\n=== DLS / OVERS REDUCED (CRITICAL — this SIGNIFICANTLY changes win probabilities) ===\n{dls_info}\nIMPORTANT: If overs are reduced, DLS par scores and revised targets fundamentally change win probabilities. A team ahead of DLS par has a significant advantage. Adjust your analysis accordingly.\n"

    chat = _get_claude_chat(
        f"sm-live-pred-{uuid.uuid4().hex[:8]}",
        """You are an expert cricket analyst providing real-time win probability assessment for IPL matches. Your role is NOT to calculate run-rate-based probability — that is handled separately by a statistical model. Your exclusive job is to identify and quantify contextual factors that the run-rate model and betting markets are likely mispricing.

You will be given:
- Current match state (score, wickets, overs, target if applicable)
- Pre-game algorithm probability (the structural baseline)
- Current betting market odds (for reference only)
- Playing XIs of both teams

Your analysis must focus ONLY on the following eight contextual layers. Do not restate the run rate or obvious match arithmetic. Assume the person reading this already knows the score.

---
LAYER 1 — BATTERS AT THE CREASE
Analyse the specific batters currently batting. For each:
- Their personal record chasing vs defending at this venue
- Their record against the specific bowling types they will face in the next 6 overs
- Whether they are a "cold bat" (just came in) or "set batter" (15+ balls faced)
- Their specific form in this IPL season so far
- Current partnership: runs scored, balls faced, and whether the run rate within this partnership is accelerating, steady, or decelerating relative to what is required
State clearly: does the current batting partnership represent an ADVANTAGE or DISADVANTAGE relative to what the run rate model assumes about average batting quality?

---
LAYER 2 — BOWLING RESOURCES REMAINING
Analyse what bowling is left for the fielding team:
- Which bowlers have overs remaining and how many
- Quality differential between bowlers already used and those still to bowl
- Whether the best bowler has already bowled their full quota
- Any specific matchup advantages — e.g. a left-arm spinner yet to bowl against a right-hand heavy batting lineup
- Specifically identify who will bowl overs 17-20 for the defending team and rate each as: [Proven death bowler / Adequate / Vulnerability] based on IPL career death-overs economy and strike rate
State clearly: is the remaining bowling attack STRONGER, WEAKER, or EQUAL to what a generic run-rate model would assume?

---
LAYER 3 — BATTING DEPTH AND TAIL RISK
Look beyond the current partnership:
- If the next 2 wickets fall, who comes in and what is their realistic scoring ability?
- Is the batting team top-heavy (danger of collapse) or deep (resilient)?
- For a chasing team specifically: do they have a finisher of proven quality at 7 or 8, or does their batting end at 6?
State clearly: does batting depth INCREASE or DECREASE the chasing or defending team's probability beyond what the current wickets-in-hand suggests?

---
LAYER 4 — PITCH AND CONDITIONS AS REVEALED BY THIS GAME
This is distinct from pre-game pitch reports. Analyse what the pitch has ACTUALLY done in this match:
- Is it playing faster or slower than the venue historical average?
- Have spinners or pacers taken wickets — and does this signal something for the remaining overs?
- Has dew arrived or is it visibly affecting grip and movement?
- Is the pitch deteriorating (helping bowlers more in innings 2) or holding up?
State clearly: do actual in-game conditions FAVOUR the batting or bowling side more than pre-game models assumed?

---
LAYER 5 — SPECIFIC HIGH-LEVERAGE MATCHUPS IN NEXT 6 OVERS
Identify 1-2 specific batter vs bowler matchups that will likely occur in the next 6 overs and that could swing the game:
- What is the historical IPL record in this specific matchup?
- Who holds the advantage and by how much?
- Is this a matchup the market is likely underpricing or overpricing?
Only include matchups where you have genuine statistical basis — do not speculate.

---
LAYER 6 — MOMENTUM AND PRESSURE ASYMMETRY
Assess one non-statistical factor:
- Is one team playing under significantly more pressure than the other (must-win situation, 0-2 in season, captain under scrutiny)?
- Has a recent event in this match (dropped catch, contentious decision, injury scare) shifted psychological momentum in a way not captured by the score?
- Is one captain making notably better or worse tactical decisions in this match?
Keep this brief — 2-3 sentences maximum. Do not overweight psychological factors.

---
LAYER 7 — IMPACT PLAYER STATUS
- Has either team used their Impact Player yet?
- If not, who are the likely Impact Player options and what does each option signal about the team's tactical read of the match?
- If yes, did the substitution strengthen batting or bowling, and has it changed the effective XI balance?
State clearly: does Impact Player availability or usage represent an ADVANTAGE for either team beyond what the current scorecard shows?

---
LAYER 8 — VERDICT
According to all the data from Layers 1-7, who is going to win this match? Pick ONE team with strong, specific reasoning. Be bold and decisive. Reference exact numbers, player names, and match situation. Do not hedge.

---
CRITICAL: Only use IPL 2023-2026 data. Only reference players from the provided squads. Be decisive — never say "too close to call." Always pick a winner."""
    )

    # Build bowling summary with overs bowled
    bowlers_summary = []
    for bw in all_bowlers:
        name = bw.get('name', '?')
        overs = bw.get('overs', 0)
        runs = bw.get('runs', 0)
        wickets = bw.get('wickets', 0)
        bowlers_summary.append(f"  {name}: {overs} overs, {runs} runs, {wickets} wickets")
    bowlers_summary_text = "\n".join(bowlers_summary) or "  No bowler data"

    # Recent 3 overs scoring
    recent_overs_text = recent_text

    # Pre-game algo probability
    algo_t1_pct = algo_probs.get("ensemble", 0.5) * 100
    algo_t2_pct = 100 - algo_t1_pct

    # Market odds text
    market_text = "Not provided"
    if betting_odds_pct is not None and betting_odds_pct > 0:
        market_text = f"{t1_short} {betting_odds_pct}% / {t2_short} {round(100 - betting_odds_pct, 1)}%"

    prompt = f"""CURRENT MATCH STATE:
- {team1} ({t1_short}) vs {team2} ({t2_short}) at {venue}
- {match_date_text}
- Innings: {"1st" if current_inn == 1 else "2nd"}, Over: {current_score.get('overs',0)}, Score: {current_score.get('runs',0)}/{current_score.get('wickets',0)}{f', Target: {target}' if target else ''}
- CRR: {sm_data.get('crr', 0)} | RRR: {sm_data.get('rrr', 'N/A')}
- {sm_data.get('note', '')}
{prev_inn_text}

=== BATSMEN AT CREASE ===
{active_bat_text}

=== FULL BATTING CARD (this innings) ===
{full_bat_text}

=== YET TO BAT ===
{ytb_text}

=== RECENT BALLS (last 12) ===
{recent_overs_text}

PRE-GAME ALGORITHM PROBABILITY: {t1_short} {round(algo_t1_pct, 1)}% / {t2_short} {round(algo_t2_pct, 1)}%
CURRENT MARKET ODDS IMPLIED PROBABILITY: {market_text}

PLAYING XIs:
{team1} ({t1_short}):
{squad1_text}

{team2} ({t2_short}):
{squad2_text}

OVERS BOWLED BY EACH BOWLER SO FAR:
{bowlers_summary_text}

=== CURRENT BOWLER ===
{active_bwl_text}

=== YET TO BOWL ===
{ytbowl_text}

=== WEATHER CONDITIONS ===
{weather_text}

=== LATEST NEWS ===
{news_text}
{user_context_text}

Analyse all 8 layers. For each layer, be specific — reference actual player names, match figures, and IPL 2023-2026 records. Do NOT restate obvious match arithmetic. Focus on what the run-rate model and market odds are MISSING.

Return JSON:
{{
  "layer_1_batters": "Your analysis of batters at crease. Conclude with: ADVANTAGE [team] or DISADVANTAGE [team] or NEUTRAL",
  "layer_2_bowling": "Your analysis of bowling resources. Conclude with: remaining attack is STRONGER / WEAKER / EQUAL vs model assumption. Include death overs 17-20 assessment.",
  "layer_3_batting_depth": "Your analysis of batting depth. Conclude with: depth INCREASES or DECREASES probability",
  "layer_4_pitch_conditions": "Your analysis of actual in-game pitch and conditions. Conclude with: conditions FAVOUR batting or bowling side",
  "layer_5_matchups": "1-2 specific high-leverage batter vs bowler matchups with IPL records",
  "layer_6_momentum": "Brief 2-3 sentence momentum/pressure assessment",
  "layer_7_impact_player": "Impact Player status and tactical implications",
  "layer_8_verdict": "Bold, decisive verdict: who wins and WHY. Reference specific numbers, players, match situation. Include predicted margin. Like: 'Bottom line: GT should win this comfortably. DC need 53 off 24 balls at 13.25 per over — their current rate is only 9.88. Rashid Khan was devastating (3/17 in 4 overs). Verdict: GT wins by 15-25 runs.'",
  "contextual_adjustment_pct": number (-30 to +30, positive = favours {t1_short}, negative = favours {t2_short}),
  "adjustment_confidence": "Low" or "Medium" or "High",
  "primary_driver": "One sentence — the single most important contextual factor driving the adjustment",
  "secondary_driver": "One sentence — second most important factor",
  "market_mispricing": "Yes" or "No" or "Possible",
  "market_mispricing_detail": "Brief explanation of what the market is missing (if applicable)",
  "predicted_winner": "{t1_short}" or "{t2_short}",
  "momentum": "BATTING" or "BOWLING" or "EVEN"
}}"""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        return _extract_json(response)
    except Exception as e:
        logger.error(f"Claude SportMonks prediction error: {e}")
        return {
            "error": str(e),
            "predicted_winner": "N/A",
            "contextual_adjustment_pct": 0,
            "adjustment_confidence": "Low",
            "layer_8_verdict": f"Claude analysis failed: {e}",
        }
