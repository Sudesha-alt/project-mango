"""
IPL 2026 Match Prediction Engine — system prompt v3.0 (text + API contracts).

Body: ``ipl_prediction_engine_v3_system.txt`` (editable without touching Python).
"""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent


def load_ipl_prediction_engine_v3_system_text() -> str:
    p = _DIR / "ipl_prediction_engine_v3_system.txt"
    return p.read_text(encoding="utf-8")


# Appended so Claude returns the host's JSON shape, not the prose template in Section 7.

PRE_MATCH_JSON_API_CONTRACT = """
═══════════════════════════════════════════════════════
HOST APPLICATION — PRE-MATCH RESPONSE CONTRACT (OVERRIDES SECTION 7 PROSE)
═══════════════════════════════════════════════════════
The USER message requires exactly ONE JSON object with a fixed schema: seven "layers" (fixed titles and order), match_header, team1_xi_display, team2_xi_display, team1_win_pct, team2_win_pct, batting_first_scenario, algorithm_predictions, etc.

Rules:
1. Output ONLY that JSON. No markdown code fence. Do not substitute the Section 7 prose template for JSON.
2. Treat the algorithm block in the USER message as the Historical Baseline reference; your team1_win_pct / team2_win_pct reflect contextual judgment and may diverge modestly. If |Δ| > 5pp vs algorithm, add a mandatory reconciliation paragraph in algo_divergence_note stating specifically what the algorithm misses (not assertion-only).
3. Map Sections 3–6 of the system prompt into the seven layer "analysis" strings, deciding_logic, deciding_factor, xi_availability_notes, key_injuries, prediction_summary, and confidence_reason.
4. Layer 6 data integrity audit: prefix deciding_logic with one line "DATA_INTEGRITY_AUDIT: C1 PASS|FAIL — note; … C7 PASS|FAIL — note;" then continue with the reasoning chain. Do not emit final JSON until all seven are PASS.
5. batting_first_scenario: when venue chasing data exists in the USER message, keep scenario shifts within ~8pp of that chasing expectation unless slow-pitch or absence rules justify more (still cap single-toss swing at Section 5 Rule 6).
6. Exactly three measurable mid-game triggers: end prediction_summary or deciding_logic with a paragraph starting "MID_GAME_TRIGGERS:" and three bullets (each trigger + implied probability shift).
7. Expected XI in the USER message is pipeline-authoritative unless news explicitly contradicts; still apply confirmed-XI discipline from Section 4 when citing starters.
8. When FULL SQUAD PLAYER CARDS include csa_two_layer, use with Section 3; hybrid override when trusted observation contradicts the tag.
9. Enforce confidence calibration from the system prompt: 50-54 LOW only, 55-61 MEDIUM only, 62+ may be MEDIUM-HIGH. Never output HIGH below 62%.
"""


LIVE_SPORTMONKS_AND_XI_PREFIX = """LIVE HOST RULES (non-negotiable):
When an AUTHORITATIVE SPORTMONKS SNAPSHOT block is present in the USER message, treat it as ground truth for runs, wickets, overs, and who is batting/bowling. If scraped text disagrees, ignore scrape for scorecard facts.

OPENING BATSMEN: When an "OPENING PARTNERSHIPS" block is present, use its NOMINATED OPENERS line as the opening pair. Do NOT infer openers from Playing XI list order, alphabetization, reputation, or from current strikers after wickets.

IMPACT SUBS: When "IMPACT PLAYER / NAMED SUBSTITUTE HISTORY" is present, use it for bench context only; substitution flag does not prove they batted.

CRITICAL DATA CONSTRAINT: Only IPL 2023–2026 evidence for stats narratives; starters are the Expected XI unless snapshot says otherwise.
"""


LIVE_JSON_API_CONTRACT = """
═══════════════════════════════════════════════════════
HOST APPLICATION — LIVE RESPONSE CONTRACT
═══════════════════════════════════════════════════════
The USER message requires exactly ONE JSON object with keys: current_state_summary, momentum, momentum_reason, key_batsman_assessment, key_bowler_assessment, phase_analysis, projected_outcome, betting_advice, win_probability (two team short codes), confidence.

Embed the MID-GAME UPDATE checklist from Section 7 (STATE, REQUIRED RATE, SLOW PITCH CHECK, RATE RULE CHECK — required rate >14 from over 9 ⇒ 25–30% chase floor, DEATH FINISHER CHECK, MARKET DIVERGENCE) inside those strings — especially current_state_summary, phase_analysis, projected_outcome, and betting_advice.

Output ONLY JSON. No markdown fence.
"""


def ipl_v3_pre_match_system_message() -> str:
    return (
        load_ipl_prediction_engine_v3_system_text().strip()
        + "\n\n"
        + PRE_MATCH_JSON_API_CONTRACT.strip()
    )


def ipl_v3_live_system_message() -> str:
    return (
        LIVE_SPORTMONKS_AND_XI_PREFIX.strip()
        + "\n\n"
        + load_ipl_prediction_engine_v3_system_text().strip()
        + "\n\n"
        + LIVE_JSON_API_CONTRACT.strip()
    )
