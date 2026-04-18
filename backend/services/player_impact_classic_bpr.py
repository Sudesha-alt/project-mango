"""
Classic BPR + CSA (explicit blend formulas for Players "recalculate" mode).

Bat BPR = (0.3·career_avg + 0.5·L3_avg + 0.2·cur_avg [if 5+ innings])
 × min(1.5, SR/130) × min(1, log(inn)/log(50))

Bowl BPR = inverted economy blend (lower eco is better) with same 0.3/0.5/0.2 weights,
          × (wpo_blend / 0.5) capped × log(overs)/log(50)

CSA = recency-weighted innings/spells (2, 1.5, 1, 0.75, 0.5, then 0.5…) from **full current IPL season**
(Mongo ``csa_season_*`` or filtered ``recent_*``) vs same-discipline BPR: (form - BPR) / BPR, clamped.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from services.player_impact_br_bor import (
    CSA_RECENCY_WEIGHTS,
    CURRENT_IPL_YEAR,
    _normalize_by_season_keys,
    _star_to_bor_prior,
    _star_to_br_prior,
    _csa_bat_entry_source,
    _csa_bowl_entry_source,
    _csa_entries_ipl_year_only,
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _log_sample_conf(inn_or_overs: float) -> float:
    n = max(2.0, float(inn_or_overs))
    return _clamp(math.log(n) / math.log(50.0), 0.35, 1.0)


def _bat_l3_runs_innings(by_season: Dict[int, dict]) -> Tuple[float, int]:
    years = sorted([y for y in by_season.keys() if isinstance(y, int)], reverse=True)[:3]
    runs = inn = 0
    for y in years:
        bb = (by_season.get(y) or {}).get("batting") or {}
        runs += int(bb.get("runs") or 0)
        inn += int(bb.get("innings") or 0)
    return float(runs), inn


def _bowl_l3_rc_ovs_wk(by_season: Dict[int, dict]) -> Tuple[float, float, int]:
    years = sorted([y for y in by_season.keys() if isinstance(y, int)], reverse=True)[:3]
    rc = ovs = 0.0
    wk = 0
    for y in years:
        bw = (by_season.get(y) or {}).get("bowling") or {}
        rc += float(bw.get("runs_conceded") or 0)
        ovs += float(bw.get("overs") or 0)
        wk += int(bw.get("wickets") or 0)
    return rc, ovs, wk


def _classic_bat_bpr_core(doc: dict, star: float) -> Tuple[float, float]:
    """Returns (unscaled core for CSA, scaled0–100 BPR for display)."""
    bat = doc.get("batting") or {}
    inn_c = int(bat.get("innings") or 0)
    if inn_c <= 0:
        s = _star_to_br_prior(star)
        return s, s
    runs_c = float(bat.get("runs") or 0)
    avg_c = runs_c / max(inn_c, 1)
    sr = float(bat.get("sr") or 0)
    if sr <= 0:
        sr = runs_c / max(float(bat.get("balls") or 0), 1.0) * 100.0

    bys = _normalize_by_season_keys(doc.get("by_season"))
    r3, i3 = _bat_l3_runs_innings(bys)
    avg_l3 = r3 / max(i3, 1) if i3 else avg_c

    bb_cur = (bys.get(CURRENT_IPL_YEAR) or {}).get("batting") or {}
    inn_cur = int(bb_cur.get("innings") or 0)
    avg_cur = float(bb_cur.get("runs") or 0) / max(inn_cur, 1) if inn_cur else 0.0

    if inn_cur >= 5:
        avg_m = 0.3 * avg_c + 0.5 * avg_l3 + 0.2 * avg_cur
    else:
        avg_m = (0.3 * avg_c + 0.5 * avg_l3) / 0.8

    sr_idx = _clamp(sr / 130.0, 0.5, 1.5)
    conf = _log_sample_conf(float(inn_c))
    core = avg_m * sr_idx * conf
    scaled = _clamp(core * 2.05, 0.0, 100.0)
    return core, scaled


def _classic_bowl_bpr_core(doc: dict, star: float) -> Tuple[float, float]:
    """Returns (unscaled core for CSA, scaled 0–100 BPR for display)."""
    bowl = doc.get("bowling") or {}
    overs = float(bowl.get("overs") or 0)
    inn_b = int(bowl.get("innings") or 0)
    if overs <= 0 and inn_b <= 0:
        s = _star_to_bor_prior(star)
        return s, s
    wk = int(bowl.get("wickets") or 0)
    eco_c = float(bowl.get("economy") or 0)
    if eco_c <= 0 and overs > 0:
        eco_c = float(bowl.get("runs_conceded") or 0) / max(overs, 0.01)
    wpo_c = wk / max(overs, 0.01)

    bys = _normalize_by_season_keys(doc.get("by_season"))
    rc3, ovs3, wk3 = _bowl_l3_rc_ovs_wk(bys)
    eco_l3 = rc3 / max(ovs3, 0.01) if ovs3 > 0 else eco_c
    wpo_l3 = wk3 / max(ovs3, 0.01) if ovs3 > 0 else wpo_c

    bw_cur = (bys.get(CURRENT_IPL_YEAR) or {}).get("bowling") or {}
    ovs_cur = float(bw_cur.get("overs") or 0)
    rc_cur = float(bw_cur.get("runs_conceded") or 0)
    wk_cur = int(bw_cur.get("wickets") or 0)
    eco_cur = rc_cur / max(ovs_cur, 0.01) if ovs_cur > 0 else eco_c
    wpo_cur = wk_cur / max(ovs_cur, 0.01) if ovs_cur > 0 else wpo_c

    if ovs_cur >= 5.0:
        eco_m = 0.3 * eco_c + 0.5 * eco_l3 + 0.2 * eco_cur
        wpo_m = 0.3 * wpo_c + 0.5 * wpo_l3 + 0.2 * wpo_cur
    else:
        eco_m = (0.3 * eco_c + 0.5 * eco_l3) / 0.8
        wpo_m = (0.3 * wpo_c + 0.5 * wpo_l3) / 0.8

    eco_quality = _clamp(11.5 - _clamp(eco_m, 4.0, 14.0), 0.0, 11.5)
    wkt_idx = _clamp(wpo_m / 0.5, 0.35, 1.75)
    conf = _log_sample_conf(max(overs, float(inn_b)))
    core = eco_quality * wkt_idx * conf
    scaled = _clamp(core * 1.55, 0.0, 100.0)
    return core, scaled


def _weighted_form_bat_core(last5: List[dict], conf: float) -> Optional[float]:
    """Same units as bat BPR core: weighted (runs × SR index) × confidence."""
    if not last5:
        return None
    num = den = 0.0
    for i, inn in enumerate(last5):
        w = CSA_RECENCY_WEIGHTS[i] if i < len(CSA_RECENCY_WEIGHTS) else 0.5
        runs = int(inn.get("runs") or 0)
        balls = max(int(inn.get("balls") or 0), 1)
        sr = runs / balls * 100.0
        sr_idx = _clamp(sr / 130.0, 0.5, 1.5)
        num += w * (runs * sr_idx)
        den += w
    if den <= 0:
        return None
    return (num / den) * conf


def _weighted_form_bowl_core(last5: List[dict], conf: float) -> Optional[float]:
    """Same units as bowl BPR core: weighted (eco_quality × wkt_idx) × confidence."""
    if not last5:
        return None
    num = den = 0.0
    for i, sp in enumerate(last5):
        w = CSA_RECENCY_WEIGHTS[i] if i < len(CSA_RECENCY_WEIGHTS) else 0.5
        ovs = float(sp.get("overs") or 0)
        if ovs <= 0:
            continue
        wk = int(sp.get("wickets") or 0)
        rc = int(sp.get("runs_conceded") or 0)
        eco = rc / max(ovs, 0.01)
        wpo = wk / max(ovs, 0.01)
        eco_q = _clamp(11.5 - _clamp(eco, 4.0, 14.0), 0.0, 11.5)
        wkt_idx = _clamp(wpo / 0.5, 0.35, 1.75)
        num += w * (eco_q * wkt_idx)
        den += w
    if den <= 0:
        return None
    return (num / den) * conf


def compute_classic_player_impact_profile(
    perf_row: Optional[dict],
    role_code: str,
    star_rating: float,
    *,
    batting_position: Optional[int] = None,
    bowling_style: Optional[str] = None,
) -> Dict[str, Any]:
    _ = (batting_position, bowling_style)
    doc = perf_row if isinstance(perf_row, dict) else {}
    bat = doc.get("batting") or {}
    bowl = doc.get("bowling") or {}
    inn_c = int(bat.get("innings") or 0)
    overs = float(bowl.get("overs") or 0)

    bpr_bat_core, bpr_bat = _classic_bat_bpr_core(doc, star_rating)
    bpr_bowl_core, bpr_bowl = _classic_bowl_bpr_core(doc, star_rating)

    conf_bat = _log_sample_conf(float(inn_c)) if inn_c > 0 else 0.5
    conf_bowl = _log_sample_conf(max(overs, float(int(bowl.get("innings") or 0)))) if (overs > 0 or int(bowl.get("innings") or 0) > 0) else 0.5

    bat_src = _csa_bat_entry_source(doc)
    bowl_src = _csa_bowl_entry_source(doc)
    last5b_cs, _ = _csa_entries_ipl_year_only(bat_src, CURRENT_IPL_YEAR)
    last5o_cs, _ = _csa_entries_ipl_year_only(bowl_src, CURRENT_IPL_YEAR)

    form_bat_core = _weighted_form_bat_core(last5b_cs, conf_bat)
    form_bowl_core = _weighted_form_bowl_core(last5o_cs, conf_bowl)

    csa_bat: Optional[float] = None
    if bpr_bat_core > 1e-6 and form_bat_core is not None:
        csa_bat = _clamp((form_bat_core - bpr_bat_core) / bpr_bat_core, -0.45, 0.45)

    csa_bowl: Optional[float] = None
    if bpr_bowl_core > 1e-6 and form_bowl_core is not None:
        csa_bowl = _clamp((form_bowl_core - bpr_bowl_core) / bpr_bowl_core, -0.45, 0.45)

    bat_ip = _clamp(bpr_bat * (1.0 + float(csa_bat or 0.0)), 0.0, 100.0)
    bowl_ip = _clamp(bpr_bowl * (1.0 + float(csa_bowl or 0.0)), 0.0, 100.0)

    if role_code == "BAT":
        bowl_ip *= 0.55
    elif role_code == "BOWL":
        bat_ip *= 0.60

    b_lbl = "HIGH" if inn_c >= 25 else ("MEDIUM" if inn_c >= 10 else "LOW")
    o_lbl = "HIGH" if overs >= 50 else ("MEDIUM" if overs >= 20 else "LOW")

    return {
        "BatIP": round(bat_ip, 4),
        "BowlIP": round(bowl_ip, 4),
        "BPR_bat": round(bpr_bat, 4),
        "BPR_bowl": round(bpr_bowl, 4),
        "CSA_bat": None if csa_bat is None else round(csa_bat, 4),
        "CSA_bowl": None if csa_bowl is None else round(csa_bowl, 4),
        "batting_confidence": b_lbl,
        "batting_confidence_mult": round(conf_bat, 4),
        "batting_innings_sample": inn_c,
        "bowling_confidence": o_lbl,
        "bowling_confidence_mult": round(conf_bowl, 4),
        "bowling_overs_sample": round(overs, 2),
        "impact_model": "classic_bpr_csa_v1",
    }
