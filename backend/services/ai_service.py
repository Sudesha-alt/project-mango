import os
import logging
import json
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

def get_chat(session_id, system_msg):
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=session_id,
        system_message=system_msg
    )
    chat.with_model("anthropic", "claude-sonnet-4-5-20250929")
    return chat

async def get_match_prediction(match_data):
    try:
        chat = get_chat(
            f"prediction-{match_data.get('matchId', 'unknown')}",
            "You are an expert cricket analyst. Provide concise match predictions based on data. Always respond in valid JSON format."
        )
        prompt = f"""Analyze this cricket match and predict:
Match: {match_data.get('team1', 'Team A')} vs {match_data.get('team2', 'Team B')}
Venue: {match_data.get('venue', 'Unknown')}
Score: {match_data.get('score', 'Not started')}
Status: {match_data.get('status', 'Unknown')}

Respond ONLY with this JSON structure:
{{
  "prediction": {{
    "team1WinProb": 0.55,
    "team2WinProb": 0.45,
    "analysis": "Brief 1-2 sentence analysis",
    "keyFactors": ["factor1", "factor2", "factor3"],
    "projectedScore": 175,
    "manOfTheMatch": "Player Name"
  }}
}}"""
        response = await chat.send_message(UserMessage(text=prompt))
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "prediction": {
                    "team1WinProb": 0.5,
                    "team2WinProb": 0.5,
                    "analysis": response[:200] if response else "Analysis unavailable",
                    "keyFactors": [],
                    "projectedScore": 0,
                    "manOfTheMatch": "TBD"
                }
            }
    except Exception as e:
        logger.error(f"AI prediction error: {e}")
        return {
            "prediction": {
                "team1WinProb": 0.5,
                "team2WinProb": 0.5,
                "analysis": "AI prediction temporarily unavailable",
                "keyFactors": [],
                "projectedScore": 0,
                "manOfTheMatch": "TBD"
            }
        }

async def get_player_prediction(player_name, team, opponent, venue, match_type="T20"):
    try:
        chat = get_chat(
            f"player-pred-{player_name}",
            "You are a cricket stats expert. Provide player performance predictions. Always respond in valid JSON."
        )
        prompt = f"""Predict performance for:
Player: {player_name}
Team: {team}
Against: {opponent}
Venue: {venue}
Format: {match_type}

Respond ONLY with JSON:
{{
  "batting": {{
    "predictedRuns": 35,
    "strikeRate": 140,
    "boundaryProb": 0.7,
    "fiftyProb": 0.3,
    "confidence": 0.6
  }},
  "bowling": {{
    "predictedWickets": 1,
    "economy": 8.5,
    "dotBallPerc": 35,
    "confidence": 0.5
  }}
}}"""
        response = await chat.send_message(UserMessage(text=prompt))
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            return json.loads(response)
        except json.JSONDecodeError:
            return _default_player_prediction()
    except Exception as e:
        logger.error(f"AI player prediction error: {e}")
        return _default_player_prediction()

def _default_player_prediction():
    return {
        "batting": {
            "predictedRuns": 25,
            "strikeRate": 130,
            "boundaryProb": 0.5,
            "fiftyProb": 0.2,
            "confidence": 0.4
        },
        "bowling": {
            "predictedWickets": 0,
            "economy": 9.0,
            "dotBallPerc": 30,
            "confidence": 0.3
        }
    }
