import os
import logging
import json
import uuid
import re
from typing import Dict, List, Optional
from services.claude_client import UserMessage, get_claude_chat, DEFAULT_CLAUDE_MODEL
from services.prematch_calibration import get_claude_prompt_addendum
from services.ipl_prediction_system_prompt_v3 import (
    ipl_v3_live_system_message,
    ipl_v3_pre_match_system_message,
)
from services.web_scraper import web_search, search_cricket_live, search_match_context, search_player_data, fetch_match_news

logger = logging.getLogger(__name__)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")


def _claude_prediction_temperature() -> float:
    """Lower variance for structured JSON predictions (env CLAUDE_PREDICTION_TEMPERATURE, default 0.35)."""
    try:
        t = float(os.environ.get("CLAUDE_PREDICTION_TEMPERATURE", "0.35"))
    except (TypeError, ValueError):
        t = 0.35
    return max(0.0, min(1.0, t))


def _live_match_phase_descriptor(sm_data: dict) -> str:
    """Powerplay / middle / death label; distinguishes chase vs first innings."""
    inn = int(sm_data.get("current_innings", 1) or 1)
    cs = sm_data.get("current_score", {}) or {}
    try:
        overs = float(cs.get("overs", 0) or 0)
    except (TypeError, ValueError):
        overs = 0.0
    parts = [f"Innings {inn}", f"{overs} overs completed"]
    if inn == 1:
        if overs <= 6.0:
            parts.append("PHASE: Powerplay (1st innings)")
        elif overs <= 15.0:
            parts.append("PHASE: Middle overs — build/accelerate")
        else:
            parts.append("PHASE: Death / finish (1st innings)")
    else:
        if overs <= 6.0:
            parts.append("PHASE: Chase — powerplay")
        elif overs <= 15.0:
            parts.append("PHASE: Chase — middle overs")
        else:
            parts.append("PHASE: Chase — death / closing overs")
    t = sm_data.get("target")
    if t is not None:
        parts.append(f"Target {t}")
    return " | ".join(parts)


def _impact_hist_team_lines(block: Optional[dict]) -> List[str]:
    if not block or not isinstance(block, dict):
        return ["  (not available)"]
    if block.get("error"):
        return [f"  (unavailable: {block.get('error')})"]
    fixtures = block.get("fixtures") or []
    if not fixtures:
        return ["  No recent finished matches with substitution-flag lineups found."]
    out: List[str] = []
    for fx in fixtures:
        subs = fx.get("impact_subs") or []
        names = ", ".join(s.get("name", "?") for s in subs if isinstance(s, dict)) or "none listed"
        opp = fx.get("opponent", "?")
        started = (fx.get("starting_at") or "")[:10]
        out.append(f"  vs {opp} ({started}): {names}")
    freq = block.get("frequency") or []
    if freq:
        top = "; ".join(
            f"{f.get('name', '?')} (×{f.get('appearances', 0)})"
            for f in freq[:8]
            if isinstance(f, dict)
        )
        out.append(f"  Most frequent named subs in sample: {top}")
    return out


def format_match_impact_subs_for_prompt(
    team1: str,
    team2: str,
    t1_short: str,
    t2_short: str,
    team1_subs: Optional[list],
    team2_subs: Optional[list],
) -> str:
    """This fixture's SportMonks ``substitution=true`` rows (IPL Impact Player / named subs)."""

    def _describe_entries(rows: Optional[list]) -> List[str]:
        out: List[str] = []
        for p in rows or []:
            if not isinstance(p, dict):
                continue
            n = (p.get("name") or "").strip()
            if not n:
                continue
            src = (p.get("source") or "").strip()
            if src == "user_swap_replaced_from_xi":
                out.append(
                    f"{n} (user swap: replaced in our Expected XI by the manual Impact pick — treat as out of this XI)"
                )
            elif src == "user_selected_impact":
                rep = (p.get("replaces_xi_player") or "").strip()
                if rep:
                    out.append(f"{n} (user-selected Impact; swapped into the 11 for {rep})")
                else:
                    out.append(
                        f"{n} (user-selected Impact; depth / 12th — not counted as a listed XI starter unless model XI says otherwise)"
                    )
            else:
                out.append(n)
        return out

    n1 = _describe_entries(team1_subs)
    n2 = _describe_entries(team2_subs)
    if not n1 and not n2:
        return ""
    lines = [
        "=== NAMED IMPACT / SUBSTITUTE PLAYERS FOR THIS XI SOURCE [SPORTMONKS DATA] ===",
        "Rows below mix SportMonks substitution=true designations with optional user overrides. "
        "Squad-listed players may participate under IPL substitution rules. "
        "User swap lines explicitly state when our Expected XI replaces a starter with a manual Impact pick.",
        "Do NOT describe API-listed subs as 'not playing' solely because they are missing from the 11 starters.",
        f"{team1} ({t1_short}): {'; '.join(n1) if n1 else '(none listed in API for this source)'}",
        f"{team2} ({t2_short}): {'; '.join(n2) if n2 else '(none listed in API for this source)'}",
    ]
    return "\n".join(lines) + "\n"


def format_impact_sub_history_for_prompt(
    team1: str,
    team2: str,
    t1_short: str,
    t2_short: str,
    hist: Optional[dict],
) -> str:
    """Human-readable block for Claude: last-N match impact / named subs from SportMonks lineups."""
    if not hist or not isinstance(hist, dict):
        return ""
    h1 = hist.get("team1")
    h2 = hist.get("team2")
    if not h1 and not h2:
        return ""
    lines = [
        "=== IMPACT PLAYER / NAMED SUBSTITUTE HISTORY [SPORTMONKS DATA] ===",
        "Per team: last completed IPL matches; players with lineup.substitution=true (11+2 named subs). "
        "This is official squad sheet designation, not proof they were used in play.",
        f"{team1} ({t1_short}):",
        *_impact_hist_team_lines(h1 if isinstance(h1, dict) else None),
        f"{team2} ({t2_short}):",
        *_impact_hist_team_lines(h2 if isinstance(h2, dict) else None),
    ]
    return "\n".join(lines) + "\n"


def build_live_opening_context(
    match_info: dict,
    sm_data: Optional[dict],
    playing_xi_doc: Optional[dict],
) -> str:
    """
    Nominated openers = first two players in our Expected XI list order for the team batting
    each innings. Also echo SportMonks scorecard positions 1–2 so Claude can spot API mismatch.
    """
    if not sm_data or not isinstance(sm_data, dict):
        return ""
    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    t1_id = sm_data.get("team1_id")
    inn = sm_data.get("innings") or {}
    lines: List[str] = []

    def _xi_first_two(team_xi_key: str) -> List[str]:
        rows = (playing_xi_doc or {}).get(team_xi_key) or []
        out: List[str] = []
        for r in rows[:2]:
            if not isinstance(r, dict):
                continue
            n = (r.get("name") or r.get("fullname") or "").strip()
            if n:
                out.append(n)
        return out

    def _scorecard_top2(inn_num: int) -> List[str]:
        bats = sm_data.get(f"batsmen_inn{inn_num}") or []
        if not bats:
            return []
        ordered = sorted(
            bats,
            key=lambda x: (x.get("sort") if x.get("sort") is not None else 99),
        )
        return [b.get("name") for b in ordered[:2] if b.get("name")]

    for inn_label in (1, 2):
        block = inn.get(str(inn_label)) or inn.get(inn_label)
        if not isinstance(block, dict):
            continue
        tid = block.get("team_id")
        if not tid or t1_id is None:
            continue
        batting_side = team1 if tid == t1_id else team2
        xi_key = "team1_xi" if tid == t1_id else "team2_xi"
        pair = _xi_first_two(xi_key)
        if len(pair) >= 2:
            lines.append(
                f"Innings {inn_label} ({batting_side}): NOMINATED OPENERS (Expected XI list order, positions 1–2) — "
                f"{pair[0]}, {pair[1]}"
            )
        sc2 = _scorecard_top2(inn_label)
        if sc2:
            lines.append(
                f"  Scorecard batting rows positions 1–2 (SportMonks sort): {', '.join(sc2)}"
            )

    if not lines:
        return ""
    return "=== OPENING PARTNERSHIPS (authoritative naming — read before inferring openers) ===\n" + "\n".join(lines)


def _compact_sm_for_prompt(sm_data: dict, max_chars: int = 8000) -> str:
    if not sm_data:
        return ""
    keys = (
        "current_innings", "current_score", "innings", "crr", "rrr", "batting_team", "bowling_team",
        "target", "note", "status", "recent_balls", "active_batsmen", "active_bowler",
        "batsmen_inn1", "batsmen_inn2", "bowlers_inn1", "bowlers_inn2",
        "yet_to_bat", "yet_to_bowl", "toss",
    )
    try:
        payload = {k: sm_data[k] for k in keys if k in sm_data}
        s = json.dumps(payload, indent=2, default=str)
        if len(s) > max_chars:
            s = s[:max_chars] + "\n... [truncated]"
        return s
    except Exception:
        return "{}"


def _algo_probs_json_block(algo_probs: dict, max_chars: int = 3500) -> str:
    if not algo_probs:
        return "{}"
    try:
        s = json.dumps(algo_probs, indent=2, default=str)
        if len(s) > max_chars:
            s = s[:max_chars] + "\n... [truncated]"
        return s
    except Exception:
        return "{}"


# ─── Claude Opus helpers ──────────────────────────────────────

def _get_claude_chat(session_id: str, system_msg: str):
    """Create a Claude Opus chat instance."""
    if not ANTHROPIC_KEY:
        raise ValueError("ANTHROPIC_API_KEY not configured in .env")
    chat = get_claude_chat(session_id, system_msg)
    return chat.with_model("anthropic", DEFAULT_CLAUDE_MODEL)


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


def _to_float_or_none(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _validate_pre_match_opus_payload(
    payload: dict,
    *,
    algo_prediction: Optional[dict],
    team1_short: str,
    team2_short: str,
) -> None:
    """
    Hard-validate critical guardrails for pre-match Opus JSON.
    Raises ValueError with concise violations when output is non-compliant.
    """
    violations: List[str] = []
    if not isinstance(payload, dict):
        raise ValueError("pre_match_payload_not_object")

    t1 = _to_float_or_none(payload.get("team1_win_pct"))
    t2 = _to_float_or_none(payload.get("team2_win_pct"))
    if t1 is None or t2 is None:
        violations.append("missing_team_win_pct")
    else:
        if abs((t1 + t2) - 100.0) > 0.2:
            violations.append("team_win_pct_not_100")
        if t1 < 0 or t2 < 0 or t1 > 100 or t2 > 100:
            violations.append("team_win_pct_out_of_bounds")

    conf_raw = str(payload.get("confidence", "") or "").strip().lower()
    conf_norm = conf_raw.replace("_", "-").replace(" ", "-")
    maxp = max(t1 or 0.0, t2 or 0.0)
    if conf_norm:
        if 50.0 <= maxp < 55.0 and conf_norm != "low":
            violations.append("confidence_band_50_54_must_low")
        elif 55.0 <= maxp < 62.0 and conf_norm != "medium":
            violations.append("confidence_band_55_61_must_medium")
        elif maxp >= 62.0 and conf_norm not in {"medium", "medium-high"}:
            violations.append("confidence_band_62_plus_must_medium_or_medium_high")
        if "high" in conf_norm and maxp < 62.0:
            violations.append("high_confidence_below_62")
    else:
        violations.append("missing_confidence")

    algo_t1 = None
    pred = (algo_prediction or {}).get("prediction") if isinstance(algo_prediction, dict) else None
    if isinstance(pred, dict):
        algo_t1 = _to_float_or_none(pred.get("team1_win_prob"))
    if algo_t1 is None and isinstance(algo_prediction, dict):
        algo_t1 = _to_float_or_none(algo_prediction.get("team1_win_prob"))

    if algo_t1 is not None and t1 is not None:
        if abs(t1 - algo_t1) > 5.0:
            div_note = payload.get("algo_divergence_note")
            txt = str(div_note or "").strip()
            if len(txt) < 24:
                violations.append("algo_divergence_note_required_gt5")
            else:
                ltxt = txt.lower()
                if not any(k in ltxt for k in ("algorithm", "algo", "miss", "baseline")):
                    violations.append("algo_divergence_note_not_specific")

    deciding_logic = str(payload.get("deciding_logic", "") or "")
    for marker in ("BOWLING_SWING_CAP_CHECK:", "BATTING_COLLAPSE_GATE:", "VENUE_CORRECTION_CHECK:"):
        if marker not in deciding_logic:
            violations.append(f"missing_marker_{marker[:-1].lower()}")

    if violations:
        raise ValueError("pre_match_contract_violation: " + ", ".join(violations[:12]))


async def _claude_json(prompt: str, system_msg: str = "You are a precise data parser. Output ONLY valid JSON with no markdown formatting, no code blocks, no explanation.") -> dict:
    """Send a prompt to Claude and parse the JSON response."""
    chat = _get_claude_chat(f"parse-{uuid.uuid4().hex[:8]}", system_msg)
    response = await chat.send_message(UserMessage(text=prompt))
    return _extract_json(response)


def normalize_primary_cricket_role(raw: Optional[str]) -> str:
    """Map free-text role labels to Batsman | Bowler | All-rounder | Wicketkeeper (predictor + UI)."""
    if not raw:
        return "Batsman"
    s = raw.strip().lower().replace("-", " ").replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    if "wicket" in s or s in ("wk", "keeper", "wk batsman") or s.startswith("wk "):
        return "Wicketkeeper"
    if "all" in s and "round" in s:
        return "All-rounder"
    if "bowl" in s or s in ("spin", "pace"):
        return "Bowler"
    if "bat" in s and "bowl" not in s:
        return "Batsman"
    if s in ("ar",):
        return "All-rounder"
    return "Batsman"


def _normalize_claude_team_role_map(raw_block) -> Dict[str, str]:
    """Player name -> canonical role (keys trimmed)."""
    out: Dict[str, str] = {}
    if not isinstance(raw_block, dict):
        return out
    for k, v in raw_block.items():
        name = str(k).strip()
        if name:
            out[name] = normalize_primary_cricket_role(v)
    return out


async def claude_infer_playing_xi_roles(team1: str, team2: str, squads: dict) -> dict:
    """
    One batched Claude call: primary T20 role per Expected XI player.

    Input style (in prompt): team_a={{ name, name2, ... }}  team_b={{ ... }}
    Expected response JSON:
      {{ "team_a": {{ "Full Name": "Batsman", ... }}, "team_b": {{ ... }} }}

    squads: {{ team1_full_name: [ player dicts ], team2_full_name: [...] }}
    Returns dict with team_a and team_b as name->role maps (canonical roles).
    """
    if not ANTHROPIC_KEY:
        raise ValueError("ANTHROPIC_API_KEY not configured in .env")

    def _first_eleven_named(rows) -> list:
        out: List[dict] = []
        for p in rows or []:
            if not isinstance(p, dict):
                continue
            if (p.get("name") or "").strip():
                out.append(p)
            if len(out) >= 11:
                break
        return out

    t1_rows = _first_eleven_named(squads.get(team1))
    t2_rows = _first_eleven_named(squads.get(team2))
    if len(t1_rows) < 11 or len(t2_rows) < 11:
        raise ValueError("Need 11 players per side for role inference")

    lines_a = []
    for p in t1_rows:
        nm = (p.get("name") or "").strip()
        if nm:
            lines_a.append(nm)
    lines_b = []
    for p in t2_rows:
        nm = (p.get("name") or "").strip()
        if nm:
            lines_b.append(nm)
    if len(lines_a) < 11 or len(lines_b) < 11:
        raise ValueError("Need 11 named players per side for role inference")

    block_a = ",\n".join(lines_a)
    block_b = ",\n".join(lines_b)

    prompt = f"""You assign each IPL T20 player exactly ONE primary role for a typical XI.

Allowed roles ONLY (exact spelling): Batsman, Bowler, All-rounder, Wicketkeeper.

Rules:
- Batsman: batting is the main job; little or no bowling expected.
- Bowler: bowling is the main job.
- All-rounder: regularly bowls meaningful overs AND bats in T20 (not a one-over part-timer only).
- Wicketkeeper: the player who keeps wickets for this XI when applicable.

INPUT — use these exact full names as JSON object keys in your answer (same spelling and spacing):

team_a={{
{block_a}
}}

team_b={{
{block_b}
}}

Meaning: team_a is "{team1}". team_b is "{team2}".

OUTPUT — JSON ONLY, no markdown, no commentary. Shape:

{{
  "team_a": {{ "<exact name from team_a input>": "Batsman"|"Bowler"|"All-rounder"|"Wicketkeeper", ... }},
  "team_b": {{ "<exact name from team_b input>": "Batsman"|"Bowler"|"All-rounder"|"Wicketkeeper", ... }}
}}

You MUST include every name from the team_a input block under "team_a" and every name from the team_b input block under "team_b" (11 keys each). Keys must match the INPUT name strings exactly.
"""
    raw = await _claude_json(
        prompt,
        system_msg=(
            "You output ONLY one valid JSON object. Keys: team_a and team_b only. "
            "Each value is an object mapping player name strings to role strings. "
            "No markdown, no arrays, no extra keys."
        ),
    )
    if not isinstance(raw, dict):
        raise ValueError("Claude roles: expected JSON object")

    ta = raw.get("team_a") or raw.get("teamA")
    tb = raw.get("team_b") or raw.get("teamB")
    if isinstance(ta, list) or isinstance(tb, list):
        raise ValueError("Claude roles: expected team_a and team_b to be objects (name -> role), not arrays")

    map_a = _normalize_claude_team_role_map(ta if isinstance(ta, dict) else {})
    map_b = _normalize_claude_team_role_map(tb if isinstance(tb, dict) else {})

    if len(map_a) < 9 or len(map_b) < 9:
        logger.warning(
            "Claude XI roles: thin maps (team_a=%s team_b=%s keys); check name matching",
            len(map_a),
            len(map_b),
        )

    return {"team_a": map_a, "team_b": map_b}


async def claude_generate_player_impact_points(team1: str, team2: str, players: List[dict]) -> Dict[str, dict]:
    """
    Generate missing BatIP/BowlIP estimates with Claude for a small player set.

    Returns:
      {
        "Player Name": {"BatIP": float, "BowlIP": float, "player_role": "BAT|BOWL|AR"}
      }
    """
    if not players:
        return {}
    if not ANTHROPIC_KEY:
        return {}

    rows = []
    for p in players:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        role = (p.get("player_role") or "").strip().upper() or "BAT"
        batting_style = (p.get("batting_style") or "").strip()
        bowling_style = (p.get("bowling_style") or "").strip()
        rows.append(
            f'- name: "{name}", role_hint: "{role}", batting_style: "{batting_style}", bowling_style: "{bowling_style}"'
        )
    if not rows:
        return {}

    prompt = f"""Estimate T20 player impact points for an IPL match context.
Output JSON ONLY.

Teams: {team1} vs {team2}
Players:
{chr(10).join(rows)}

Return exact shape:
{{
  "players": [
    {{"name":"...", "player_role":"BAT|BOWL|AR", "BatIP": 0-100 float, "BowlIP": 0-100 float}}
  ]
}}

Rules:
- BatIP and BowlIP must be floats in [0,100].
- BAT: BowlIP can be low but non-negative.
- BOWL: BatIP can be low but non-negative.
- AR: both should be meaningful.
- Keep names exactly as provided.
"""
    try:
        data = await _claude_json(prompt)
        out: Dict[str, dict] = {}
        for row in (data.get("players") or []):
            if not isinstance(row, dict):
                continue
            nm = (row.get("name") or "").strip()
            if not nm:
                continue
            try:
                bat_ip = float(row.get("BatIP", 0.0))
            except (TypeError, ValueError):
                bat_ip = 0.0
            try:
                bowl_ip = float(row.get("BowlIP", 0.0))
            except (TypeError, ValueError):
                bowl_ip = 0.0
            role = (row.get("player_role") or "").strip().upper()
            if role not in {"BAT", "BOWL", "AR"}:
                role = "BAT"
            out[nm] = {
                "BatIP": max(0.0, min(100.0, bat_ip)),
                "BowlIP": max(0.0, min(100.0, bowl_ip)),
                "player_role": role,
            }
        return out
    except Exception as e:
        logger.warning(f"claude_generate_player_impact_points failed: {e}")
        return {}


async def validate_factor_reasons_with_claude(
    team1: str,
    team2: str,
    prediction: dict,
) -> Dict[str, dict]:
    """
    Validate factor one-liners against numeric factor values using Claude.
    If Claude marks a factor false, re-check that factor once and return corrected reason.
    """
    if not ANTHROPIC_KEY:
        return {}
    if not prediction:
        return {}
    factors = prediction.get("factors") or {}
    lines = prediction.get("factor_one_liners") or {}
    if not factors or not lines:
        return {}

    items = []
    for k, f in factors.items():
        if not isinstance(f, dict):
            continue
        l = lines.get(k) if isinstance(lines.get(k), dict) else {}
        items.append(
            {
                "factor": k,
                "weight": f.get("weight"),
                "logit_contribution": f.get("logit_contribution"),
                "raw_logit": f.get("raw_logit"),
                "one_liner": l.get("one_liner", ""),
                "favours": l.get("favours", "neutral"),
            }
        )
    if not items:
        return {}

    async def _validate_once(batch: List[dict]) -> Dict[str, dict]:
        prompt = f"""You are validating pre-match factor explanations.
Team1={team1}, Team2={team2}

For each factor below, judge whether one_liner is supported by numeric signals.
Rules:
- verdict = true if reason aligns with weight/logit sign/magnitude.
- verdict = false if reason contradicts numbers or overstates edge.
- reason must be 1 concise sentence.
- if verdict=false, corrected_reason must be 1 sentence that matches numbers.
Return JSON only:
{{
  "factors": [
    {{"factor":"...", "verdict":"true|false", "reason":"...", "corrected_reason":"... or empty"}}
  ]
}}

DATA:
{json.dumps(batch, ensure_ascii=True)}
"""
        data = await _claude_json(prompt)
        out = {}
        for row in (data.get("factors") or []):
            if not isinstance(row, dict):
                continue
            fk = row.get("factor")
            if not fk:
                continue
            verdict = str(row.get("verdict", "true")).lower()
            out[fk] = {
                "verdict": "false" if verdict == "false" else "true",
                "reason": str(row.get("reason", "")).strip(),
                "corrected_reason": str(row.get("corrected_reason", "")).strip(),
            }
        return out

    try:
        first = await _validate_once(items)
        false_keys = [k for k, v in first.items() if v.get("verdict") == "false"]
        if false_keys:
            second_input = [x for x in items if x.get("factor") in false_keys]
            second = await _validate_once(second_input)
            for k in false_keys:
                if k in second:
                    first[k] = second[k]
        result = {}
        for item in items:
            fk = item["factor"]
            row = first.get(fk, {})
            verdict = row.get("verdict", "true")
            reason = (
                row.get("corrected_reason")
                if verdict == "false" and row.get("corrected_reason")
                else row.get("reason")
            )
            if not reason:
                reason = item.get("one_liner", "")
            result[fk] = {"verdict": verdict, "reason": reason}
        return result
    except Exception as e:
        logger.warning(f"Claude factor validation skipped: {e}")
        return {}


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
                                     weather: dict = None, form_data: dict = None,
                                     impact_sub_history: dict = None,
                                     match_impact_subs: dict = None,
                                     opus_squad_player_cards_json: str = "") -> dict:
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
                for p in players[:11]:
                    name = p.get("name", "?")
                    role = p.get("role", "Unknown")
                    overseas = " [OVERSEAS]" if p.get("isOverseas") else ""
                    captain = " [C]" if p.get("isCaptain") else ""
                    player_lines.append(f"  - {name} ({role}){overseas}{captain}")
                squad_block += (
                    f"\n{team_name} EXPECTED PLAYING XI ({len(player_lines)} players):\n"
                    + "\n".join(player_lines)
                    + "\n"
                )

    # ── Build player performance section: prefer full-squad BPR/CSA cards; else legacy XI-only lines ──
    perf_block = ""
    if opus_squad_player_cards_json and str(opus_squad_player_cards_json).strip():
        perf_block = f"""
=== FULL SQUAD — PLAYER INPUT CARDS (same JSON schema for every listed player) [BPR/CSA MODEL + MONGO] ===
Each object includes BOTH baseline and season-form numerics:
- BPR_primary, BPR_bat, BPR_bowl (baseline quality)
- BatIP, BowlIP (post-CSA impact points used for team strength construction)
- CSA_primary_output_pct / CSA_primary_effective_pct and discipline splits (form vs BPR)
- csa_scope + current_season_sample (CSA rows used from current IPL season)
- recent_form_this_ipl_season: every batting innings and bowling spell recorded for this player in **ipl_season_year** (chronological), from the same Mongo rows as CSA; each row may include **team_result** \"W\" or \"L\" (that player’s franchise in that fixture vs SportMonks winner). Use W/L together with runs/wickets as momentum context. If team_result is absent, the row predates sync enrichment — don’t invent results. If data_quality_note mentions legacy_last5_proxy, season_year was missing and rows are a short proxy — say so briefly.
Use BPR+CSA together (correlation), not CSA in isolation.
CSA is scoped to current IPL season rows from Mongo sync (full available season set, recency-weighted), with explicit legacy/no-row flags when incomplete.
Use team1_strength_from_ip / team2_strength_from_ip (batting_strength, bowling_strength, allrounder_strength) as the primary numeric summary for strength calls.
This covers entire franchise squads (not only the expected XI). replacement* are null unless stated elsewhere — you may infer replacements from news in narrative only.
For who **starts** this match, the authoritative list is EXPECTED PLAYING XIs above; use these cards for bench depth, injury context, form, and impact-sub options.

{opus_squad_player_cards_json.strip()}
"""
    elif player_performance:
        for team_key, label in [("team1", team1), ("team2", team2)]:
            team_perf = player_performance.get(team_key, {})
            if team_perf:
                perf_lines = []
                count = 0
                for pid, ps in team_perf.items():
                    if count >= 11:
                        break
                    if not isinstance(ps, dict):
                        continue
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
                    count += 1
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
- Squad Strength (11%): {t1_short} bat {factors.get('squad_strength',{}).get('team1_batting','?')}/bowl {factors.get('squad_strength',{}).get('team1_bowling','?')} | {t2_short} bat {factors.get('squad_strength',{}).get('team2_batting','?')}/bowl {factors.get('squad_strength',{}).get('team2_bowling','?')} | Logit: {factors.get('squad_strength',{}).get('logit_contribution',0)}
- Current Form (11%): {t1_short} score {factors.get('current_form',{}).get('team1_form_score','?')} ({factors.get('current_form',{}).get('team1_wins',0)}W) | {t2_short} score {factors.get('current_form',{}).get('team2_form_score','?')} ({factors.get('current_form',{}).get('team2_wins',0)}W) | Logit: {factors.get('current_form',{}).get('logit_contribution',0)}
- Venue-Pitch Fit (8%): Pitch: {factors.get('venue_pitch',{}).get('pitch_type','?')}, Pace: {factors.get('venue_pitch',{}).get('pace_assist','?')}, Spin: {factors.get('venue_pitch',{}).get('spin_assist','?')} | Logit: {factors.get('venue_pitch',{}).get('logit_contribution',0)}
- Home Ground Advantage (5%): Home side: {factors.get('home_ground_advantage',{}).get('home_team','neutral')} | Logit: {factors.get('home_ground_advantage',{}).get('logit_contribution',0)}
- H2H (7%): {t1_short} {factors.get('h2h',{}).get('team1_wins',0)} wins / {t2_short} {factors.get('h2h',{}).get('team2_wins',0)} wins (total {factors.get('h2h',{}).get('total',0)}) | Logit: {factors.get('h2h',{}).get('logit_contribution',0)}
- Toss is excluded from algorithm score; evaluate toss/dew in Claude contextual sections.
- Bowling Depth (5%): {t1_short} VQ:{factors.get('bowling_depth',{}).get('team1_venue_quality','?')} ({factors.get('bowling_depth',{}).get('team1_variety','?')}) | {t2_short} VQ:{factors.get('bowling_depth',{}).get('team2_venue_quality','?')} ({factors.get('bowling_depth',{}).get('team2_variety','?')}) | Logit: {factors.get('bowling_depth',{}).get('logit_contribution',0)}
- Bowling Strength (6%): {t1_short} bowl {factors.get('bowling_strength',{}).get('team1_bowling_rating','?')} | {t2_short} bowl {factors.get('bowling_strength',{}).get('team2_bowling_rating','?')} | Logit: {factors.get('bowling_strength',{}).get('logit_contribution',0)}
- Batting Depth (8%): Middle/lower-order resilience signal | Logit: {factors.get('batting_depth',{}).get('logit_contribution',0)}
- Powerplay Performance (6%): First-6-overs bat+ball edge | Logit: {factors.get('powerplay_performance',{}).get('logit_contribution',0)}
- Death Overs Performance (6%): Overs 16-20 execution edge | Logit: {factors.get('death_overs_performance',{}).get('logit_contribution',0)}
- Key Players Availability (6%): XI availability risk edge | Logit: {factors.get('key_players_availability',{}).get('logit_contribution',0)}
- All-rounder Depth (5%): Multi-skill bench/XI flexibility | Logit: {factors.get('allrounder_depth',{}).get('logit_contribution',0)}
- Top Order Consistency (3%): Recent top-order stability edge | Logit: {factors.get('top_order_consistency',{}).get('logit_contribution',0)}
- Conditions (4%): {factors.get('conditions',{}).get('conditions_edge_text','Neutral')} | Logit: {factors.get('conditions',{}).get('logit_contribution',0)}
- Momentum: {t1_short} last 4: {factors.get('momentum',{}).get('team1_last4') or factors.get('momentum',{}).get('team1_last2',[])} | {t2_short} last 4: {factors.get('momentum',{}).get('team2_last4') or factors.get('momentum',{}).get('team2_last2',[])} | Logit: {factors.get('momentum',{}).get('logit_contribution',0)}

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

    match_subs_block = ""
    if match_impact_subs and isinstance(match_impact_subs, dict):
        match_subs_block = format_match_impact_subs_for_prompt(
            team1,
            team2,
            t1_short,
            t2_short,
            match_impact_subs.get("team1"),
            match_impact_subs.get("team2"),
        )

    impact_block = format_impact_sub_history_for_prompt(
        team1, team2, t1_short, t2_short, impact_sub_history
    )

    cal_addendum = get_claude_prompt_addendum()
    addendum_block = ""
    if cal_addendum:
        addendum_block = (
            "\n\n=== CALIBRATED ANALYST ADDENDUM (from approved post-match learning) ===\n"
            f"{cal_addendum}\n"
        )

    chat = _get_claude_chat(
        f"deep-{uuid.uuid4().hex[:8]}",
        ipl_v3_pre_match_system_message(),
    )

    prompt = f"""Analyze this IPL 2026 match using the data below. Produce a full 7-layer contextual analysis.

Match: {team1} ({t1_short}) vs {team2} ({t2_short})
Match #{match_num} | Venue: {venue} | City: {city}
Date: {date_str} | Time (IST): {time_ist}

=== EXPECTED PLAYING XIs [SPORTMONKS DATA] ===
{squad_block}
{match_subs_block}{impact_block}{perf_block}
{algo_block}
{h2h_block}
{weather_block}
{news_section}
=== END DATA ===

MANDATORY: team1_xi_display and team2_xi_display must list exactly the 11 player names from EXPECTED PLAYING XIs above (same names). Do not add anyone from news, other franchises, or algorithm summaries if they are missing from those lists.
If NAMED IMPACT / SUBSTITUTE PLAYERS FOR THIS XI SOURCE lists a player, mention them in xi_availability_notes or Layer 7 as a named impact / substitute option — not as "not playing".

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
      "analysis": "Assess likely impact sub choices given pitch and match demands. If IMPACT PLAYER / NAMED SUBSTITUTE HISTORY is present, anchor on who has recently been the named sub (lineup substitution flag). Evaluate fit for this specific game. 2-4 sentences.",
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
  "deciding_logic": "3-7 sentences — your complete reasoning chain for the final probability. Must include these exact marker lines: 'BOWLING_SWING_CAP_CHECK: ...', 'BATTING_COLLAPSE_GATE: ...', 'VENUE_CORRECTION_CHECK: ...'.",
  "prediction_summary": "1-2 sentence bold prediction with percentage",
  "algo_divergence_note": "If your prediction differs from the algorithm by >5%, mandatory 2-3 sentence reconciliation with specific misses in algorithm. Otherwise null.",
  "confidence": "Low" or "Medium" or "Medium-high",
  "confidence_reason": "Why this confidence level"
}}
{addendum_block}
RULES:
- All 7 layers MUST have an ADVANTAGE verdict. No ties.
- Starters and matchups: only players in the Expected Playing XI. Squad cards may inform injuries, depth, and Layer 7 impact subs.
- Win probabilities must add to 100.
- Confidence bands are strict: 50-54 => Low; 55-61 => Medium; 62+ => Medium-high allowed.
- If |team1_win_pct - algo_team1_win_pct| > 5, algo_divergence_note is mandatory and specific.
- Include deciding_logic markers exactly: BOWLING_SWING_CAP_CHECK, BATTING_COLLAPSE_GATE, VENUE_CORRECTION_CHECK.
- Be opinionated and bold. If one team is structurally superior, reflect it (e.g. 65/35).
- Every claim needs a stat or specific recent event behind it."""

    try:
        response = await chat.send_message(UserMessage(text=prompt))
        parsed = _extract_json(response)
        _validate_pre_match_opus_payload(
            parsed,
            algo_prediction=algo_prediction,
            team1_short=t1_short,
            team2_short=t2_short,
        )
        return parsed
    except Exception as e:
        logger.error(f"Claude deep analysis error: {e}")
        return {"error": str(e), "team1_win_pct": 50, "team2_win_pct": 50, "layers": [], "headline": "Analysis unavailable"}


# ─── Claude Live Match Analysis (NEW) ─────────────────────────

async def claude_live_analysis(
    match_info: dict,
    live_data: dict,
    algo_probs: dict,
    squads: dict = None,
    sm_data: Optional[dict] = None,
    playing_xi_doc: Optional[dict] = None,
    impact_sub_history: Optional[dict] = None,
    match_impact_subs: Optional[dict] = None,
) -> dict:
    """
    Claude Opus: Generate real-time analysis during a live match.
    Combines scraped live data with algorithm outputs and full squad info.
    When sm_data is set, it is authoritative for scores and lineups vs scraped text.
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

    sm_data = sm_data if isinstance(sm_data, dict) else None
    sm_authoritative = _compact_sm_for_prompt(sm_data) if sm_data else ""
    phase_line = _live_match_phase_descriptor(sm_data) if sm_data else ""

    # Scrape latest live data (secondary when SportMonks snapshot exists)
    live_scraped = await search_cricket_live(team1, team2)
    scrape_limit = 2500 if sm_authoritative else 4000

    chat = _get_claude_chat(
        f"live-analysis-{uuid.uuid4().hex[:8]}",
        ipl_v3_live_system_message(),
    )

    sm_block = ""
    if sm_authoritative:
        sm_block = f"""
=== AUTHORITATIVE SPORTMONKS SNAPSHOT (ground truth for live state) ===
Match phase: {phase_line}
{sm_authoritative}

"""

    opening_block = build_live_opening_context(match_info, sm_data, playing_xi_doc)
    if opening_block:
        opening_block = opening_block + "\n\n"

    impact_block = format_impact_sub_history_for_prompt(
        team1, team2, t1_short, t2_short, impact_sub_history
    )
    if impact_block:
        impact_block = impact_block + "\n"

    match_subs_block = ""
    if match_impact_subs and isinstance(match_impact_subs, dict):
        match_subs_block = format_match_impact_subs_for_prompt(
            team1,
            team2,
            t1_short,
            t2_short,
            match_impact_subs.get("team1"),
            match_impact_subs.get("team2"),
        )
    if match_subs_block:
        match_subs_block = match_subs_block + "\n"

    prompt = f"""Analyze this LIVE IPL 2026 match. Give me a real-time prediction update.

{team1} ({t1_short}) vs {team2} ({t2_short})
{sm_block}{opening_block}{match_subs_block}{impact_block}=== {team1} EXPECTED PLAYING XI ===
{squad1_text}

=== {team2} EXPECTED PLAYING XI ===
{squad2_text}

=== LIVE MATCH DATA (from our system) ===
{json.dumps(live_data, indent=2, default=str)[:6000]}

=== ALGORITHM PROBABILITIES (full model output; anchor win_probability near ensemble unless scorecard justifies a shift) ===
{json.dumps(algo_probs, indent=2, default=str)[:3500]}

=== LATEST SCRAPED DATA (rumor / context only if SportMonks snapshot above is present) ===
{live_scraped[:scrape_limit]}

Consider the Playing XIs above — remaining batting depth, available bowling changes, and each player's IPL form. Starters: the 11 per team above; if NAMED IMPACT / SUBSTITUTE PLAYERS block is present, treat those names as available impact options (not "absent").

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
        response = await chat.send_message(
            UserMessage(text=prompt),
            temperature=_claude_prediction_temperature(),
        )
        return _extract_json(response)
    except Exception as e:
        logger.error(f"Claude live analysis error: {e}")
        return {"error": str(e), "current_state_summary": "Live analysis unavailable"}



# ─── Claude SportMonks Live Win Prediction ────────────────────

async def claude_sportmonks_prediction(sm_data: dict, algo_probs: dict, match_info: dict, squads: dict = None, weather: dict = None, news: list = None, gut_feeling: str = None, betting_odds_pct: float = None, dls_info: str = None, enrichment: dict = None) -> dict:
    """
    Claude Opus: Generate a live win prediction using rich SportMonks data.
    11-section structured analysis with data integrity checks, toss scenarios,
    mid-game revision triggers, and committed final prediction.
    """
    team1 = match_info.get("team1", "Team A")
    team2 = match_info.get("team2", "Team B")
    t1_short = match_info.get("team1Short", team1[:3].upper())
    t2_short = match_info.get("team2Short", team2[:3].upper())
    venue = match_info.get("venue", "")

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

    def _fmt_bat_rows(rows: list) -> str:
        if not rows:
            return "  (no data)"
        return "\n".join(
            f"  {b.get('name', '?')} — {b.get('runs', 0)}({b.get('balls', 0)}) "
            f"SR:{b.get('strike_rate', 0)} 4s:{b.get('fours', 0)} 6s:{b.get('sixes', 0)}"
            + (" *AT_CREASE*" if b.get("active") else "")
            for b in rows
        )

    def _fmt_bowl_rows(rows: list) -> str:
        if not rows:
            return "  (no data)"
        lines = []
        for bw in rows:
            lines.append(
                f"  {bw.get('name', '?')}: {bw.get('overs', 0)} ov, "
                f"{bw.get('runs', 0)} runs, {bw.get('wickets', 0)} wkts, Econ:{bw.get('economy', 0)}"
            )
        return "\n".join(lines)

    bat_inn1_full = _fmt_bat_rows(sm_data.get("batsmen_inn1", []) or [])
    bat_inn2_full = _fmt_bat_rows(sm_data.get("batsmen_inn2", []) or [])
    bowl_inn1_full = _fmt_bowl_rows(sm_data.get("bowlers_inn1", []) or [])
    bowl_inn2_full = _fmt_bowl_rows(sm_data.get("bowlers_inn2", []) or [])

    _sc_keys = (
        "current_innings", "current_score", "innings", "crr", "rrr", "batting_team", "bowling_team",
        "target", "note", "status", "recent_balls", "team1_playing_xi", "team2_playing_xi",
        "active_batsmen", "active_bowler", "batsmen_inn1", "batsmen_inn2", "bowlers_inn1", "bowlers_inn2",
        "yet_to_bat", "yet_to_bowl",
    )
    try:
        scorecard_payload = {k: sm_data[k] for k in _sc_keys if k in sm_data}
        scorecard_json = json.dumps(scorecard_payload, indent=2, default=str)
        if len(scorecard_json) > 14000:
            scorecard_json = scorecard_json[:14000] + "\n... [truncated]"
    except Exception:
        scorecard_json = "{}"

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

    # ── ENRICHMENT DATA: Real stats from SportMonks ──
    enrichment = enrichment or {}

    # Venue stats
    vs = enrichment.get("venue_stats", {})
    if vs and vs.get("sample_size", 0) > 0:
        venue_stats_text = (
            f"Venue: {vs.get('venue', venue)}\n"
            f"  Sample: {vs['sample_size']} IPL matches ({', '.join(str(y) for y in vs.get('seasons', []))})\n"
            f"  Avg 1st Innings Score: {vs.get('avg_first_innings_score', 'N/A')}\n"
            f"  Bat-First Win %: {vs.get('bat_first_win_pct', 'N/A')}%\n"
            f"  Highest 1st Innings: {vs.get('highest_1st_innings', 'N/A')}\n"
            f"  Lowest 1st Innings: {vs.get('lowest_1st_innings', 'N/A')}"
        )
    else:
        venue_stats_text = "No venue stats available from SportMonks"

    # H2H record
    h2h = enrichment.get("h2h", {})
    if h2h and h2h.get("matches_played", 0) > 0:
        h2h_text = (
            f"{h2h['team1']} vs {h2h['team2']} (last {len(h2h.get('seasons_covered', []))} seasons)\n"
            f"  Matches: {h2h['matches_played']}\n"
            f"  {h2h['team1']} wins: {h2h['team1_wins']} | {h2h['team2']} wins: {h2h['team2_wins']}"
            + (f" | No result: {h2h['no_result']}" if h2h.get('no_result') else "") +
            f"\n  Last meeting: {h2h.get('last_meeting_winner', 'N/A')} won ({h2h.get('last_meeting_date', 'N/A')})"
            + (f"\n  Result: {h2h['last_meeting_note']}" if h2h.get('last_meeting_note') else "")
        )
    else:
        h2h_text = "No H2H data available"

    # Team standings
    standings = enrichment.get("standings", [])
    if standings:
        standings_lines = ["IPL 2026 Points Table:"]
        for i, s in enumerate(standings):
            if isinstance(s, dict):
                standings_lines.append(
                    f"  {i+1}. {s.get('team', '?')} — P:{s.get('played',0)} W:{s.get('won',0)} "
                    f"L:{s.get('lost',0)} Pts:{s.get('points',0)}"
                    + (f" NRR:{s['nrr']}" if s.get('nrr') else "")
                )
        standings_text = "\n".join(standings_lines)
    else:
        standings_text = "Standings data not available"

    # Player season stats for Team 1 XI
    t1_enriched = enrichment.get("team1_enriched_xi", [])
    t1_stats_lines = []
    for p in t1_enriched:
        if not isinstance(p, dict):
            continue
        name = p.get("name", "?")
        ss = p.get("season_stats")
        if ss:
            bat_line = f"Bat: {ss['bat_runs']}r in {ss['bat_innings']}inn, Avg:{ss['bat_avg']}, SR:{ss['bat_sr']}" if ss.get("bat_innings", 0) > 0 else "Bat: no innings"
            bowl_line = f"Bowl: {ss['bowl_wickets']}wkts in {ss['bowl_innings']}inn, Econ:{ss['bowl_economy']}, {ss['bowl_overs']}ov" if ss.get("bowl_innings", 0) > 0 else ""
            t1_stats_lines.append(f"  {name} ({ss['matches']}m) — {bat_line}" + (f" | {bowl_line}" if bowl_line else ""))
        else:
            t1_stats_lines.append(f"  {name} — No IPL 2026 stats available")
    t1_season_stats_text = "\n".join(t1_stats_lines) or "  No player stats available"

    # Player season stats for Team 2 XI
    t2_enriched = enrichment.get("team2_enriched_xi", [])
    t2_stats_lines = []
    for p in t2_enriched:
        if not isinstance(p, dict):
            continue
        name = p.get("name", "?")
        ss = p.get("season_stats")
        if ss:
            bat_line = f"Bat: {ss['bat_runs']}r in {ss['bat_innings']}inn, Avg:{ss['bat_avg']}, SR:{ss['bat_sr']}" if ss.get("bat_innings", 0) > 0 else "Bat: no innings"
            bowl_line = f"Bowl: {ss['bowl_wickets']}wkts in {ss['bowl_innings']}inn, Econ:{ss['bowl_economy']}, {ss['bowl_overs']}ov" if ss.get("bowl_innings", 0) > 0 else ""
            t2_stats_lines.append(f"  {name} ({ss['matches']}m) — {bat_line}" + (f" | {bowl_line}" if bowl_line else ""))
        else:
            t2_stats_lines.append(f"  {name} — No IPL 2026 stats available")
    t2_season_stats_text = "\n".join(t2_stats_lines) or "  No player stats available"

    _ish = enrichment.get("impact_sub_history") if isinstance(enrichment, dict) else None
    impact_sub_hist_text = format_impact_sub_history_for_prompt(
        team1, team2, t1_short, t2_short, _ish if isinstance(_ish, dict) else None
    )
    impact_sub_hist_display = impact_sub_hist_text.strip() or (
        "Not available for this request."
    )

    # User context (gut feeling + betting odds + DLS)
    user_context_text = ""
    if gut_feeling and gut_feeling.strip():
        user_context_text += f"\n=== USER'S GUT FEELING (weigh as qualitative signal) ===\n{gut_feeling}\n"
    if betting_odds_pct is not None and betting_odds_pct > 0:
        user_context_text += f"\n=== CURRENT BETTING MARKET ODDS ===\n{t1_short} implied: {betting_odds_pct}% | {t2_short} implied: {round(100 - betting_odds_pct, 1)}%\n"
    if dls_info and dls_info.strip():
        user_context_text += f"\n=== DLS / OVERS REDUCED (CRITICAL) ===\n{dls_info}\nIMPORTANT: DLS par scores fundamentally change win probabilities.\n"

    # Build bowling summary
    bowlers_summary = []
    for bw in all_bowlers:
        name = bw.get('name', '?')
        overs = bw.get('overs', 0)
        runs = bw.get('runs', 0)
        wickets = bw.get('wickets', 0)
        econ = bw.get('economy', 0)
        bowlers_summary.append(f"  {name}: {overs}ov, {runs}runs, {wickets}wkts, Econ:{econ}")
    bowlers_summary_text = "\n".join(bowlers_summary) or "  No bowler data"

    # Pre-game algo probability
    algo_t1_pct = algo_probs.get("ensemble", 0.5) * 100
    algo_t2_pct = 100 - algo_t1_pct
    phase_line = _live_match_phase_descriptor(sm_data)
    algo_detail_json = _algo_probs_json_block(algo_probs)

    # Market odds text
    market_text = "Not provided"
    if betting_odds_pct is not None and betting_odds_pct > 0:
        market_text = f"{t1_short} {betting_odds_pct}% / {t2_short} {round(100 - betting_odds_pct, 1)}%"

    # Toss info
    toss_info = sm_data.get("toss", {})
    toss_text = "Toss data not available"
    if toss_info:
        toss_winner = toss_info.get("winner", "Unknown")
        toss_decision = toss_info.get("decision", "unknown")
        toss_text = f"Toss: {toss_winner} won and chose to {toss_decision}"

    chat = _get_claude_chat(
        f"sm-live-pred-{uuid.uuid4().hex[:8]}",
        f"""You are an expert IPL cricket match prediction analyst with live data access.

CRITICAL RULES:

Rule 1 — Current season data overrides reputation.
Only IPL 2026 stats drive player threat ratings. Last season's numbers are historical context only, never primary evidence.

Rule 2 — Confirmed absences are highest-priority input.
Cross-check confirmed XI against full squad. Any expected player missing gets a standalone impact assessment: batting impact, bowling impact, leadership impact — separately.

Rule 3 — Venue data is IPL 2023-2026 only.
State sample size. If fewer than 6 matches in sample, flag "small sample — reduced venue confidence."

Rule 4 — H2H must pass two filters: last 3 seasons only, and check if squads that produced that record still exist.

Rule 5 — Never invent factors from missing information. Only confirmed data drives analysis.

Rule 6 — Toss scenarios must be mathematically consistent with venue data.

Rule 7 — No cross-format stats as primary evidence. IPL and international T20 only.

Rule 8 — Statistical anchor: Treat the PRE-GAME ensemble and full model JSON as a prior. Move section_10 win percentages more than ~12 points away from ensemble {t1_short} {round(algo_t1_pct, 1)}% only when the live scorecard or a confirmed XI fact clearly justifies it; otherwise stay close and express uncertainty in confidence, not arbitrary swings.

Rule 9 — Impact / named subs: When IMPACT PLAYER / NAMED SUBSTITUTE HISTORY is present, use it for bench-sheet patterns (lineup substitution flag in last completed matches). It does not prove a player actually substituted into the game.

FORMAT RULES:
- All probabilities: whole numbers only. No ranges.
- Every stat tagged with its source season.
- Word "unpredictable" is banned. Express all uncertainty as probability or confidence level.
- Both teams sum to exactly 100%.
- This is a committed prediction. State it like one.""",
    )

    prompt = f"""ANALYSE THIS LIVE IPL 2026 MATCH. Produce ALL 11 sections.

AUTHORITATIVE DATA: The STRUCTURED LIVE SCORECARD JSON and full inning-wise tables below are the single source of truth for
current runs/wickets/overs, CRR/RRR, who is batting/bowling and their figures, and both teams' Playing XIs. Do not contradict them.

=== LIVE MATCH STATE ===
- {team1} ({t1_short}) vs {team2} ({t2_short}) at {venue}
- {match_date_text}
- {toss_text}
- Innings: {"1st" if current_inn == 1 else "2nd"}, Score: {current_score.get('runs',0)}/{current_score.get('wickets',0)} in {current_score.get('overs',0)} overs
{f"- Target: {target}" if target else ""}
- CRR: {sm_data.get('crr', 0)} | RRR: {sm_data.get('rrr', 'N/A')}
- Match phase: {phase_line}
- {sm_data.get('note', '')}
{prev_inn_text}

=== STRUCTURED LIVE SCORECARD (JSON) ===
{scorecard_json}

=== COMPLETE INNINGS 1 BATTING ===
{bat_inn1_full}

=== COMPLETE INNINGS 2 BATTING ===
{bat_inn2_full}

=== COMPLETE INNINGS 1 BOWLING ===
{bowl_inn1_full}

=== COMPLETE INNINGS 2 BOWLING ===
{bowl_inn2_full}

=== BATSMEN AT CREASE ===
{active_bat_text}

=== FULL BATTING CARD (CURRENT INNINGS) ===
{full_bat_text}

=== YET TO BAT ===
{ytb_text}

=== BOWLING CARD (CURRENT INNINGS) ===
{bowlers_summary_text}

=== CURRENT BOWLER ===
{active_bwl_text}

=== YET TO BOWL ===
{ytbowl_text}

=== RECENT BALLS (last 12) ===
{recent_text}

=== CONFIRMED PLAYING XIs ===
{team1} ({t1_short}):
{squad1_text}

{team2} ({t2_short}):
{squad2_text}

=== {t1_short} PLAYER IPL 2026 SEASON STATS (last 5 matches) ===
{t1_season_stats_text}

=== {t2_short} PLAYER IPL 2026 SEASON STATS (last 5 matches) ===
{t2_season_stats_text}

=== VENUE STATS (SportMonks data) ===
{venue_stats_text}

=== HEAD-TO-HEAD RECORD ===
{h2h_text}

=== IPL 2026 STANDINGS ===
{standings_text}

=== IMPACT PLAYER / NAMED SUBSTITUTE HISTORY (SportMonks — last 4 completed IPL matches per team, lineup substitution flag) ===
{impact_sub_hist_display}

=== PRE-GAME ENSEMBLE (team1 win % summary) ===
{t1_short} {round(algo_t1_pct, 1)}% / {t2_short} {round(algo_t2_pct, 1)}%

=== BALL-BY-BALL / ENSEMBLE MODEL OUTPUT (JSON — statistical anchor) ===
{algo_detail_json}

Anchor: section_10 team1_win_pct + team2_win_pct = 100 (integers). If Section 10 for {t1_short} differs from ensemble {round(algo_t1_pct, 1)}% by more than 12 points, cite a concrete fact from THIS scorecard (runs/wickets/overs, RRR, batter/bowler today) or a confirmed XI gap — not reputation alone.

=== MARKET ODDS ===
{market_text}

=== WEATHER ===
{weather_text}

=== NEWS ===
{news_text}
{user_context_text}

Return JSON with this EXACT structure:
{{
  "section_0_data_dump": "State all key data: match details, toss, confirmed XIs, current standings, last 5 results, venue stats, H2H. Flag any missing data explicitly.",

  "section_1_match_context": "Teams, venue, date, time, toss result and decision. Day or evening? Dew probability and toss strategy validity.",

  "section_2_squad_strength": {{
    "analysis": "Confirmed XIs quality. For every absence: batting impact, bowling impact, leadership impact. Rate each XI 1-10.",
    "team1_xi_rating": number (1-10),
    "team2_xi_rating": number (1-10),
    "weight": 22
  }},

  "section_3_current_form": {{
    "analysis": "IPL 2026 data ONLY. Per team: W/L/Points/NRR. Per key player: 2026 stats. Flag small sample sizes. Exponential decay: most recent match counts double.",
    "weight": 18
  }},

  "section_4_venue_pitch": {{
    "analysis": "Average first innings score, batting-first win %, powerplay avg, pace vs spin split. Sample size stated. Afternoon=no dew. Evening=state dew probability.",
    "avg_first_innings": "N/A or number",
    "bat_first_win_pct": "N/A or number",
    "sample_size": "N/A or number",
    "weight": 16
  }},

  "section_5_h2h": {{
    "analysis": "Last 3 seasons only. Squad validity check. If key players gone, label 'structurally invalid.' Does H2H favour either team?",
    "weight": 10
  }},

  "section_6_key_matchups": {{
    "analysis": "Exactly 3 matchups most likely to decide this game. Per matchup: batter vs bowler, IPL career record (balls/runs/dismissals), who holds edge, likelihood matchup occurs.",
    "matchups": [
      {{"batter": "name", "bowler": "name", "edge": "{t1_short}" or "{t2_short}", "detail": "brief stat-backed reason"}},
      {{"batter": "name", "bowler": "name", "edge": "{t1_short}" or "{t2_short}", "detail": "brief stat-backed reason"}},
      {{"batter": "name", "bowler": "name", "edge": "{t1_short}" or "{t2_short}", "detail": "brief stat-backed reason"}}
    ],
    "weight": 8
  }},

  "section_7_bowling_death": {{
    "analysis": "Per team: all bowlers, overs allocation. Who bowls 17,18,19,20? Rate each: Proven (death econ <9) / Adequate (9-10.5) / Vulnerability (>10.5). Total quality bowling overs per team. Under 16 = structural weakness.",
    "team1_death_rating": "Proven/Adequate/Vulnerability",
    "team2_death_rating": "Proven/Adequate/Vulnerability",
    "weight": 7
  }},

  "section_8_data_integrity": {{
    "form_vs_reputation": "Every player labelled a threat — verify IPL 2026 stats support it. Under 80 runs or under 2 wickets = 'reputational, unproven in 2026.'",
    "absence_verification": "Name every absent player. Rate: Low/Medium/High/Critical impact.",
    "venue_recency": "Season range and sample size. Flag pre-2023 as 'potentially outdated.'",
    "h2h_validity": "Squads intact? State explicitly.",
    "toss_consistency": "Toss probabilities match venue batting-first win %?",
    "invented_factors_removed": "List any factors removed from speculation/missing data.",
    "passed": true or false
  }},

  "section_9_toss_scenarios": {{
    "team1_bats_first_win_pct": number,
    "team2_bats_first_win_pct": number,
    "toss_sensitivity": "Low (<5% swing) / Moderate (5-10%) / High (>10%)"
  }},

  "section_10_final_prediction": {{
    "team1_win_pct": number (0-100),
    "team2_win_pct": number (0-100),
    "sentence_1_key_factor": "The single factor most responsible for the favoured team's edge.",
    "sentence_2_underdog_chance": "The single factor keeping the underdog competitive.",
    "sentence_3_first_6_signal": "The specific event in first 6 overs that confirms which team is on track.",
    "sentence_4_confidence": "Confidence level — Low/Medium/High — and the one reason for it."
  }},

  "section_11_revision_triggers": [
    {{"trigger": "Exact event description", "revise_favour": "{t1_short}" or "{t2_short}", "revise_pct": number}},
    {{"trigger": "Exact event description", "revise_favour": "{t1_short}" or "{t2_short}", "revise_pct": number}},
    {{"trigger": "Exact event description", "revise_favour": "{t1_short}" or "{t2_short}", "revise_pct": number}}
  ],

  "historical_factors": {{
    "h2h_win_pct": number (0-1, {t1_short} head-to-head edge vs {t2_short} in this fixture),
    "venue_win_pct": number (0-1, how venue/pitch conditions favour {t1_short} over {t2_short}),
    "recent_form_pct": number (0-1, {t1_short} IPL 2026 form edge vs {t2_short}),
    "toss_advantage_pct": number (0-1, toss + dew edge for {t1_short})
  }},

  "contextual_adjustment_pct": number (-30 to +30, positive = favours {t1_short}),
  "adjustment_confidence": "Low" or "Medium" or "High",
  "primary_driver": "One sentence — single most important contextual factor",
  "secondary_driver": "One sentence — second most important factor",
  "predicted_winner": "{t1_short}" or "{t2_short}",
  "momentum": "BATTING" or "BOWLING" or "EVEN",
  "market_mispricing": "Yes" or "No" or "Possible",
  "market_mispricing_detail": "What the market is missing (if applicable)"
}}

CRITICAL: All sections must be completed. No skipping. Be decisive — never say "too close to call." Own the prediction."""

    try:
        response = await chat.send_message(
            UserMessage(text=prompt),
            temperature=_claude_prediction_temperature(),
        )
        return _extract_json(response)
    except Exception as e:
        logger.error(f"Claude SportMonks prediction error: {e}")
        return {
            "error": str(e),
            "predicted_winner": "N/A",
            "contextual_adjustment_pct": 0,
            "adjustment_confidence": "Low",
            "section_10_final_prediction": {"team1_win_pct": 50, "team2_win_pct": 50, "sentence_1_key_factor": f"Analysis failed: {e}"},
        }
