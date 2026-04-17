"""
Hybrid player impact — Option C specification (BPR + CSA + confidence).

- BPR: career / last-3-season / current-season IPL averages (SportMonks aggregates),
  × SR index (bat) or economy + wicket-rate index (bowl), × log sample confidence.
- CSA: last 5 innings (bat) or spells (bowl) with weights 2, 1.5, 1, 0.75, 0.5 (most recent first),
  normalized as (form - BPR) / BPR on the same 0–100 scale.
- Team assembly uses batting_confidence_mult: <10 bat innings or <20 bowl overs → 50% weight (LOW).

Mongo sync must populate by_season + last5_bat_innings / last5_bowl_spells (see sync_player_performance_to_db).
Live aggregate-only rows fall back to career-only BPR and weaker CSA.
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional, Tuple

from services.sportmonks_service import IPL_SEASON_IDS

# ── Spec thresholds ───────────────────────────────────────────
MIN_BAT_INNINGS_HIGH = 10
MIN_BOWL_OVERS_HIGH = 20.0
MIN_BAT_INNINGS_CURRENT_BLEND = 5
MIN_BOWL_OVERS_CURRENT_BLEND = 5.0  # spec: current-season slice when enough overs in that season
SR_REF = 130.0
LOG_CONF_INNINGS_REF = 50.0
LOG_CONF_OVERS_REF = 50.0
CSA_RECENCY_WEIGHTS = (2.0, 1.5, 1.0, 0.75, 0.5)
CURRENT_IPL_YEAR = max(IPL_SEASON_IDS.keys())
LAST_N_SEASONS_FOR_L3 = 3


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _star_to_bat_prior(star_rating: float) -> float:
    s = _clamp(float(star_rating or 50.0), 40.0, 99.0)
    return _clamp(38.0 + (s - 50.0) * 1.05, 15.0, 97.0)


def _star_to_bowl_prior(star_rating: float) -> float:
    s = _clamp(float(star_rating or 50.0), 40.0, 99.0)
    return _clamp(36.0 + (s - 50.0) * 1.0, 15.0, 97.0)


def _batting_stat_score(bat: Dict[str, Any]) -> float:
    if not bat or not bat.get("innings"):
        return 0.0
    avg = float(bat.get("avg", 0) or 0)
    sr = float(bat.get("sr", 0) or 0)
    runs = float(bat.get("runs", 0) or 0)
    inn = max(1.0, float(bat.get("innings", 1) or 1))
    if avg == 0 and runs and inn:
        avg = runs / inn
    if sr == 0 and runs and bat.get("balls"):
        sr = float(runs) / max(float(bat.get("balls", 1)), 1.0) * 100.0
    avg_part = _clamp((avg / 42.0) * 100.0, 0.0, 100.0)
    sr_idx = _clamp(sr / SR_REF, 0.55, 1.5)
    runs_part = _clamp((runs / inn) / 35.0 * 100.0, 0.0, 100.0)
    raw = 0.55 * avg_part + 0.35 * _clamp(sr_idx * 55.0, 0.0, 100.0) + 0.10 * runs_part
    return _clamp(raw, 0.0, 100.0)


def _bowling_stat_score(bowl: Dict[str, Any]) -> float:
    if not bowl or not bowl.get("innings"):
        return 0.0
    eco = float(bowl.get("economy", 12.0) or 12.0)
    inns = max(1.0, float(bowl.get("innings", 0) or 0))
    wkts = float(bowl.get("wickets", 0) or 0)
    ovs = float(bowl.get("overs", 0) or 0)
    if eco == 0 and ovs > 0:
        eco = float(bowl.get("runs_conceded", 0) or 0) / max(ovs, 0.01)
    wpo = wkts / max(1.0, ovs if ovs > 0 else inns)
    eco_part = _clamp((11.5 - eco) / 5.5 * 100.0, 0.0, 100.0)
    wpi = wkts / inns
    wpi_part = _clamp((wpi / 1.8) * 100.0, 0.0, 100.0)
    wpo_part = _clamp((wpo / 0.45) * 100.0, 0.0, 100.0)
    return _clamp(0.45 * eco_part + 0.35 * wpi_part + 0.20 * wpo_part, 0.0, 100.0)


def _log_sample_confidence_count(n: float, ref: float) -> float:
    n = max(0.0, float(n))
    if n <= 0:
        return 0.35
    return _clamp(math.log(max(2.0, n)) / math.log(max(2.0, ref)), 0.35, 1.0)


def _normalize_by_season_keys(by_season: Any) -> dict:
    out = {}
    if not isinstance(by_season, dict):
        return out
    for k, v in by_season.items():
        try:
            y = int(k)
        except (TypeError, ValueError):
            continue
        out[y] = v
    return out


def _merge_last_k_seasons_batting(by_season: dict, k: int) -> Tuple[float, int]:
    years = sorted(
        [y for y in (by_season or {}).keys() if isinstance(y, int)],
        reverse=True,
    )[:k]
    runs = inn = 0
    for y in years:
        bb = (by_season.get(y) or {}).get("batting") or {}
        runs += int(bb.get("runs") or 0)
        inn += int(bb.get("innings") or 0)
    return runs / max(inn, 1), inn


def _merge_last_k_seasons_bowling(by_season: dict, k: int) -> Tuple[float, float, int]:
    years = sorted(
        [y for y in (by_season or {}).keys() if isinstance(y, int)],
        reverse=True,
    )[:k]
    rc = ovs = wk = inn = 0
    for y in years:
        bw = (by_season.get(y) or {}).get("bowling") or {}
        rc += int(bw.get("runs_conceded") or 0)
        ovs += float(bw.get("overs") or 0)
        wk += int(bw.get("wickets") or 0)
        inn += int(bw.get("innings") or 0)
    eco = rc / max(ovs, 0.01)
    wpo = wk / max(ovs, 0.01)
    return eco, wpo, inn


def _current_season_batting(by_season: dict, year: int) -> Tuple[float, int]:
    bb = (by_season.get(year) or {}).get("batting") or {}
    inn = int(bb.get("innings") or 0)
    if inn <= 0:
        return 0.0, 0
    return float(bb.get("runs") or 0) / inn, inn


def _current_season_bowling(by_season: dict, year: int) -> Tuple[float, float, int, float]:
    bw = (by_season.get(year) or {}).get("bowling") or {}
    ovs = float(bw.get("overs") or 0)
    inn = int(bw.get("innings") or 0)
    rc = int(bw.get("runs_conceded") or 0)
    wk = int(bw.get("wickets") or 0)
    eco = rc / max(ovs, 0.01)
    wpo = wk / max(ovs, 0.01)
    return eco, wpo, inn, ovs


def _batting_bpr_components_from_doc(doc: Optional[dict]) -> Tuple[float, float, float, int, int]:
    """
    avg_career, avg_l3, avg_cur, innings_career, innings_current_season.
    """
    d = doc if isinstance(doc, dict) else {}
    bat = d.get("batting") or {}
    inn_c = int(bat.get("innings") or 0)
    avg_c = float(bat.get("runs") or 0) / max(inn_c, 1) if inn_c else 0.0

    bys = _normalize_by_season_keys(d.get("by_season"))
    if not bys:
        return avg_c, avg_c, avg_c, inn_c, inn_c

    avg_l3, _inn_l3 = _merge_last_k_seasons_batting(bys, LAST_N_SEASONS_FOR_L3)
    avg_cur, inn_cur = _current_season_batting(bys, CURRENT_IPL_YEAR)
    if avg_l3 == 0 and inn_c:
        avg_l3 = avg_c
    if avg_cur == 0 and inn_c:
        avg_cur = avg_c
        inn_cur = inn_c
    return avg_c, avg_l3, avg_cur, inn_c, inn_cur


def _weighted_last5_bat_form(last5: List[dict]) -> Optional[float]:
    if not last5:
        return None
    num = den = 0.0
    for i, inn in enumerate(last5[:5]):
        w = CSA_RECENCY_WEIGHTS[i] if i < len(CSA_RECENCY_WEIGHTS) else 0.5
        balls = max(int(inn.get("balls") or 0), 1)
        runs = int(inn.get("runs") or 0)
        sr = float(inn.get("sr") or (runs / balls * 100.0))
        mini = _batting_stat_score({
            "innings": 1,
            "runs": runs,
            "balls": balls,
            "avg": float(runs),
            "sr": sr,
        })
        num += w * mini
        den += w
    return num / den if den > 0 else None


def _weighted_last5_bowl_form(last5: List[dict]) -> Optional[float]:
    if not last5:
        return None
    num = den = 0.0
    for i, sp in enumerate(last5[:5]):
        w = CSA_RECENCY_WEIGHTS[i] if i < len(CSA_RECENCY_WEIGHTS) else 0.5
        ovs = float(sp.get("overs") or 0)
        wk = int(sp.get("wickets") or 0)
        rc = int(sp.get("runs_conceded") or 0)
        eco = float(sp.get("economy") or (rc / max(ovs, 0.01)))
        mini = _bowling_stat_score({
            "innings": 1,
            "overs": ovs,
            "wickets": wk,
            "runs_conceded": rc,
            "economy": eco,
        })
        num += w * mini
        den += w
    return num / den if den > 0 else None


def _batting_confidence_label_mult(innings: int) -> Tuple[str, float]:
    n = max(0, int(innings or 0))
    if n >= MIN_BAT_INNINGS_HIGH:
        return "HIGH", _clamp(math.log(max(2.0, n)) / math.log(LOG_CONF_INNINGS_REF), 0.5, 1.0)
    if n <= 0:
        return "LOW", 0.5
    label = "MEDIUM" if n >= 4 else "LOW"
    return label, 0.5


def _bowling_confidence_label_mult(overs: float, spell_innings: int) -> Tuple[str, float]:
    o = max(0.0, float(overs or 0.0))
    n = o if o > 0 else float(spell_innings) * 4.0
    if n >= MIN_BOWL_OVERS_HIGH:
        return "HIGH", _clamp(math.log(max(2.0, n)) / math.log(LOG_CONF_OVERS_REF), 0.5, 1.0)
    if n <= 0:
        return "LOW", 0.5
    label = "MEDIUM" if n >= 8.0 else "LOW"
    return label, 0.5


def compute_batting_bpr_csa(
    perf_row: Optional[dict],
    star_rating: float,
) -> Dict[str, Any]:
    doc = perf_row if isinstance(perf_row, dict) else {}
    bat = doc.get("batting") or {}
    inn_c = int(bat.get("innings") or 0)
    sr_career = float(bat.get("sr") or 0)
    if sr_career == 0 and inn_c > 0:
        sr_career = float(bat.get("runs") or 0) / max(float(bat.get("balls") or 1), 1.0) * 100.0

    avg_c, avg_l3, avg_cur, _, inn_cur = _batting_bpr_components_from_doc(doc)

    if inn_c <= 0:
        bpr = _star_to_bat_prior(star_rating)
        sr_idx = 1.0
        conf_bpr = 0.85
    else:
        if inn_cur >= MIN_BAT_INNINGS_CURRENT_BLEND:
            avg_mix = 0.3 * avg_c + 0.5 * avg_l3 + 0.2 * avg_cur
        else:
            avg_mix = (0.3 * avg_c + 0.5 * avg_l3) / 0.8
        sr_idx = _clamp(sr_career / SR_REF, 0.5, 1.5)
        conf_bpr = _clamp(math.log(max(2.0, inn_c)) / math.log(LOG_CONF_INNINGS_REF), 0.35, 1.0)
        bpr_raw = avg_mix * sr_idx * conf_bpr
        bpr = _clamp(bpr_raw * 2.05, 0.0, 100.0)

    last5 = doc.get("last5_bat_innings") or []
    form5 = _weighted_last5_bat_form(last5 if isinstance(last5, list) else [])
    if form5 is None:
        form5 = _batting_stat_score(bat if inn_c else {})
    csa = 0.0
    if bpr > 1e-6 and form5 is not None:
        csa = (form5 - bpr) / bpr
    csa = _clamp(csa, -0.45, 0.45)

    conf_label, conf_mult = _batting_confidence_label_mult(inn_c)
    return {
        "BPR_bat": round(bpr, 4),
        "CSA_bat": round(csa, 4),
        "batting_confidence": conf_label,
        "batting_confidence_mult": round(conf_mult, 4),
        "batting_innings_sample": inn_c,
    }


def compute_bowling_bpr_csa(
    perf_row: Optional[dict],
    star_rating: float,
) -> Dict[str, Any]:
    doc = perf_row if isinstance(perf_row, dict) else {}
    bowl = doc.get("bowling") or {}
    overs = float(bowl.get("overs") or 0)
    inn_b = int(bowl.get("innings") or 0)
    eco_c = float(bowl.get("economy") or 0)
    if eco_c == 0 and overs > 0:
        eco_c = float(bowl.get("runs_conceded") or 0) / max(overs, 0.01)
    wpo_c = float(bowl.get("wickets") or 0) / max(overs, 0.01) if overs > 0 else 0.0

    bys = _normalize_by_season_keys(doc.get("by_season"))
    cur_season_overs = 0.0
    if bys:
        eco_l3, wpo_l3, _ = _merge_last_k_seasons_bowling(bys, LAST_N_SEASONS_FOR_L3)
        eco_cur, wpo_cur, inn_cur_sp, cur_season_overs = _current_season_bowling(bys, CURRENT_IPL_YEAR)
        if eco_l3 == 0 and overs > 0:
            eco_l3, wpo_l3 = eco_c, wpo_c
        if eco_cur == 0 and overs > 0:
            eco_cur, wpo_cur, inn_cur_sp = eco_c, wpo_c, inn_b
            cur_season_overs = overs
    else:
        eco_l3, wpo_l3 = eco_c, wpo_c
        eco_cur, wpo_cur, inn_cur_sp = eco_c, wpo_c, inn_b
        cur_season_overs = overs

    if inn_b <= 0 and overs <= 0:
        bpr = _star_to_bowl_prior(star_rating)
        wkt_idx = 1.0
        conf_bpr = 0.85
    else:
        if cur_season_overs >= MIN_BOWL_OVERS_CURRENT_BLEND:
            eco_mix = 0.3 * eco_c + 0.5 * eco_l3 + 0.2 * eco_cur
            wpo_mix = 0.3 * wpo_c + 0.5 * wpo_l3 + 0.2 * wpo_cur
        else:
            eco_mix = (0.3 * eco_c + 0.5 * eco_l3) / 0.8
            wpo_mix = (0.3 * wpo_c + 0.5 * wpo_l3) / 0.8
        wkt_idx = _clamp(wpo_mix / 0.5, 0.35, 1.75)
        conf_bpr = _clamp(math.log(max(2.0, max(overs, 1.0))) / math.log(LOG_CONF_OVERS_REF), 0.35, 1.0)
        bpr_raw = (11.5 - _clamp(eco_mix, 4.0, 14.0)) * wkt_idx * conf_bpr
        bpr = _clamp(bpr_raw * 1.55, 0.0, 100.0)

    last5 = doc.get("last5_bowl_spells") or []
    form5 = _weighted_last5_bowl_form(last5 if isinstance(last5, list) else [])
    if form5 is None:
        form5 = _bowling_stat_score(bowl if (inn_b or overs) else {})
    csa = 0.0
    if bpr > 1e-6 and form5 is not None:
        csa = (form5 - bpr) / bpr
    csa = _clamp(csa, -0.45, 0.45)

    conf_label, conf_mult = _bowling_confidence_label_mult(overs, inn_b)
    return {
        "BPR_bowl": round(bpr, 4),
        "CSA_bowl": round(csa, 4),
        "bowling_confidence": conf_label,
        "bowling_confidence_mult": round(conf_mult, 4),
        "bowling_overs_sample": round(overs, 2),
    }


def effective_impact_ip(bpr: float, csa: float, conf_mult: float) -> float:
    eff = float(bpr) * (1.0 + float(csa)) * float(conf_mult)
    return _clamp(eff, 0.0, 100.0)


def compute_player_impact_profile(
    perf_row: Optional[dict],
    role_code: str,
    star_rating: float,
) -> Dict[str, Any]:
    bat_block = compute_batting_bpr_csa(perf_row, star_rating)
    bowl_block = compute_bowling_bpr_csa(perf_row, star_rating)

    bat_ip = effective_impact_ip(
        bat_block["BPR_bat"], bat_block["CSA_bat"], bat_block["batting_confidence_mult"]
    )
    bowl_ip = effective_impact_ip(
        bowl_block["BPR_bowl"], bowl_block["CSA_bowl"], bowl_block["bowling_confidence_mult"]
    )

    if role_code == "BAT":
        bowl_ip *= 0.55
    elif role_code == "BOWL":
        bat_ip *= 0.60

    return {
        "BatIP": round(_clamp(bat_ip, 0.0, 100.0), 4),
        "BowlIP": round(_clamp(bowl_ip, 0.0, 100.0), 4),
        **bat_block,
        **bowl_block,
        "impact_model": "bpr_csa_spec_option_c",
    }


def claude_impact_fallback_allowed() -> bool:
    return os.environ.get("ALLOW_CLAUDE_PLAYER_IMPACT_FALLBACK", "").lower() in (
        "1",
        "true",
        "yes",
    )
