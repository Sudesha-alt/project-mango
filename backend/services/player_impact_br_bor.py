"""
Player impact — BR / BoR / AR architecture (full BPR+CSA replacement).

Spec: recency-weighted IPL batting/bowling components, phase stats when `phases`
exists on Mongo player_performance (from ball-by-ball sync), else neutral or
career proxies. CSA uses **every** innings/spell in the current IPL season (``csa_season_*`` from sync,
else ``recent_*``/``last5_*`` filtered by ``season_year``), recency-weighted; null if none. BR/BoR baseline excludes
the old extra current-season average/SR blend. Legacy keys: BatIP, BowlIP,
BPR_bat, BPR_bowl, CSA_*, confidence_*, impact_model.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.cricket_phase_utils import PHASE_DEATH, PHASE_PP, PHASE_MID
from services.sportmonks_service import IPL_SEASON_IDS

CURRENT_IPL_YEAR = max(IPL_SEASON_IDS.keys())
# Recency weights by seasons before CURRENT_IPL_YEAR (0 = current)
_RECENCY_W = (2.0, 1.4, 0.8, 0.4)
_RECENCY_TAIL = 0.15

CSA_RECENCY_WEIGHTS = (2.0, 1.5, 1.0, 0.75, 0.5)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _season_offset(year: int, current: int) -> int:
    return max(0, int(current) - int(year))


def _recency_weight_for_year(year: int, current: int) -> float:
    off = _season_offset(year, current)
    if off < len(_RECENCY_W):
        return float(_RECENCY_W[off])
    return _RECENCY_TAIL


def _normalize_by_season_keys(by_season: Any) -> Dict[int, dict]:
    out: Dict[int, dict] = {}
    if not isinstance(by_season, dict):
        return out
    for k, v in by_season.items():
        try:
            y = int(k)
        except (TypeError, ValueError):
            continue
        if isinstance(v, dict):
            out[y] = v
    return out


def _lin(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x <= x0:
        return y0
    if x >= x1:
        return y1
    if x1 == x0:
        return y0
    return y0 + (x - x0) / (x1 - x0) * (y1 - y0)


def _norm_bat_average(avg: float) -> float:
    a = float(avg)
    if a < 10:
        return 0.0
    if a < 20:
        return _lin(a, 10, 20, 10, 30)
    if a < 30:
        return _lin(a, 20, 30, 30, 55)
    if a < 40:
        return _lin(a, 30, 40, 55, 72)
    if a < 50:
        return _lin(a, 40, 50, 72, 85)
    return _lin(min(a, 60), 50, 60, 85, 100)


def _norm_bat_sr(sr: float) -> float:
    s = float(sr)
    if s < 100:
        return 0.0
    if s < 115:
        return _lin(s, 100, 115, 10, 25)
    if s < 125:
        return _lin(s, 115, 125, 25, 45)
    if s < 135:
        return _lin(s, 125, 135, 45, 62)
    if s < 145:
        return _lin(s, 135, 145, 62, 78)
    if s < 160:
        return _lin(s, 145, 160, 78, 90)
    return _lin(min(s, 200), 160, 200, 90, 100)


def _norm_pp_bat_sr(sr: float) -> float:
    s = float(sr)
    if s < 110:
        return 0.0
    if s < 130:
        return _lin(s, 110, 130, 20, 40)
    if s < 150:
        return _lin(s, 130, 150, 40, 65)
    if s < 170:
        return _lin(s, 150, 170, 65, 82)
    return _lin(min(s, 220), 170, 220, 82, 100)


def _norm_pp_bat_avg(avg: float) -> float:
    return _norm_bat_average(avg)


def _norm_death_bat_sr(sr: float) -> float:
    s = float(sr)
    if s < 120:
        return 0.0
    if s < 140:
        return _lin(s, 120, 140, 15, 35)
    if s < 160:
        return _lin(s, 140, 160, 35, 58)
    if s < 180:
        return _lin(s, 160, 180, 58, 78)
    return _lin(min(s, 220), 180, 220, 78, 100)


def _norm_consistency_pct(frac: float) -> float:
    f = float(frac)
    p = f * 100.0 if f <= 1.0 else f
    if p < 20:
        return _lin(p, 0, 20, 0, 20)
    if p < 35:
        return _lin(p, 20, 35, 20, 40)
    if p < 50:
        return _lin(p, 35, 50, 40, 62)
    if p < 65:
        return _lin(p, 50, 65, 62, 80)
    return _lin(min(p, 100), 65, 100, 80, 100)


def _norm_bowl_economy(eco: float) -> float:
    e = float(eco)
    if e > 12:
        return 0.0
    if e > 10:
        return _lin(e, 10, 12, 10, 25)
    if e > 9:
        return _lin(e, 9, 10, 25, 45)
    if e > 8:
        return _lin(e, 8, 9, 45, 65)
    if e > 7:
        return _lin(e, 7, 8, 65, 82)
    return _lin(max(e, 3.0), 3, 7, 100, 82)


def _norm_wickets_per_match(wpm: float) -> float:
    w = float(wpm)
    if w < 0.5:
        return _lin(max(w, 0), 0, 0.5, 0, 15)
    if w < 0.8:
        return _lin(w, 0.5, 0.8, 15, 35)
    if w < 1.0:
        return _lin(w, 0.8, 1.0, 35, 55)
    if w < 1.3:
        return _lin(w, 1.0, 1.3, 55, 72)
    if w < 1.6:
        return _lin(w, 1.3, 1.6, 72, 87)
    return _lin(min(w, 3.0), 1.6, 3.0, 87, 100)


def _norm_death_bowl_eco(eco: float) -> float:
    e = float(eco)
    if e > 14:
        return 0.0
    if e > 12:
        return _lin(e, 12, 14, 10, 28)
    if e > 10:
        return _lin(e, 10, 12, 28, 50)
    if e > 9:
        return _lin(e, 9, 10, 50, 68)
    if e > 8:
        return _lin(e, 8, 9, 68, 83)
    return _lin(max(e, 4.0), 4, 8, 100, 83)


def _norm_pp_bowl_eco(eco: float) -> float:
    e = float(eco)
    if e > 10:
        return 0.0
    if e > 8:
        return _lin(e, 8, 10, 15, 35)
    if e > 7:
        return _lin(e, 7, 8, 35, 60)
    if e > 6:
        return _lin(e, 6, 7, 60, 80)
    return _lin(max(e, 3.0), 3, 6, 100, 80)


def _norm_dot_pct(pct: float) -> float:
    p = float(pct)
    if p < 30:
        return _lin(p, 0, 30, 0, 15)
    if p < 38:
        return _lin(p, 30, 38, 15, 35)
    if p < 45:
        return _lin(p, 38, 45, 35, 58)
    if p < 52:
        return _lin(p, 45, 52, 58, 75)
    return _lin(min(p, 70), 52, 70, 75, 100)


def _star_to_br_prior(star: float) -> float:
    s = _clamp(float(star or 50.0), 40.0, 99.0)
    return _clamp(40.0 + (s - 50.0) * 1.0, 18.0, 92.0)


def _star_to_bor_prior(star: float) -> float:
    s = _clamp(float(star or 50.0), 40.0, 99.0)
    return _clamp(38.0 + (s - 50.0) * 0.95, 18.0, 92.0)


def _batting_confidence(innings: int) -> Tuple[str, float]:
    n = max(0, int(innings or 0))
    if n >= 100:
        return "HIGH", 1.0
    if n >= 50:
        return "HIGH", 0.9
    if n >= 25:
        return "HIGH", 0.75
    if n >= 10:
        return "MEDIUM", 0.55
    if n > 0:
        return "LOW", 0.35
    return "LOW", 0.35


def _bowling_confidence(overs: float) -> Tuple[str, float]:
    o = max(0.0, float(overs or 0.0))
    if o >= 200:
        return "HIGH", 1.0
    if o >= 100:
        return "HIGH", 0.9
    if o >= 50:
        return "HIGH", 0.75
    if o >= 20:
        return "MEDIUM", 0.55
    if o > 0:
        return "LOW", 0.35
    return "LOW", 0.35


def _confidence_penalty_estimates(flags: List[str]) -> float:
    if not flags:
        return 1.0
    return max(0.5, 1.0 - 0.15 * len(flags))


def _weighted_season_aggregate(
    bys: Dict[int, dict],
    current_year: int,
    bat_pick: Callable[[dict], Optional[Tuple[float, float]]],
) -> Optional[Tuple[float, float]]:
    """Returns (weighted_value, sum_weights) for batting-derived scalar per season."""
    num = 0.0
    den = 0.0
    for y in sorted(bys.keys(), reverse=True):
        blk = bys[y]
        bb = blk.get("batting") if isinstance(blk, dict) else None
        if not isinstance(bb, dict):
            continue
        picked = bat_pick(bb)
        if picked is None:
            continue
        val, w_mult = picked
        w = _recency_weight_for_year(y, current_year) * w_mult
        if w <= 0:
            continue
        num += w * val
        den += w
    if den <= 0:
        return None
    return num / den, den


def _recency_bat_average(by_season: Dict[int, dict], career_avg: float, current_year: int) -> float:
    bys = by_season

    def pick(bb: dict) -> Optional[Tuple[float, float]]:
        inn = int(bb.get("innings") or 0)
        if inn <= 0:
            return None
        runs = float(bb.get("runs") or 0)
        return runs / inn, 1.0

    wa = _weighted_season_aggregate(bys, current_year, pick)
    if wa:
        return float(wa[0])
    return float(career_avg)


def _recency_bat_sr(by_season: Dict[int, dict], career_sr: float, current_year: int) -> float:
    bys = by_season

    def pick(bb: dict) -> Optional[Tuple[float, float]]:
        inn = int(bb.get("innings") or 0)
        if inn <= 0:
            return None
        sr = float(bb.get("sr") or 0)
        if sr <= 0:
            runs = float(bb.get("runs") or 0)
            balls = float(bb.get("balls") or 0)
            if balls <= 0:
                return None
            sr = runs / balls * 100.0
        return sr, 1.0

    wa = _weighted_season_aggregate(bys, current_year, pick)
    if wa:
        return float(wa[0])
    return float(career_sr)


def _recency_consistency(by_season: Dict[int, dict], current_year: int) -> Optional[float]:
    bys = by_season

    def pick(bb: dict) -> Optional[Tuple[float, float]]:
        inn = int(bb.get("innings") or 0)
        if inn <= 0:
            return None
        ge15 = int(bb.get("innings_ge15") or 0)
        return ge15 / inn, 1.0

    wa = _weighted_season_aggregate(bys, current_year, pick)
    if wa:
        return float(wa[0])
    return None


def _csa_bat_entry_source(doc: dict) -> List[dict]:
    """Prefer ``csa_season_bat_innings`` (all active-season IPL innings from sync); else recent/last5."""
    xs0 = doc.get("csa_season_bat_innings")
    if isinstance(xs0, list) and xs0:
        return xs0
    for key in ("recent_bat_innings", "last5_bat_innings"):
        xs = doc.get(key)
        if isinstance(xs, list) and xs:
            return xs
    return []


def _csa_bowl_entry_source(doc: dict) -> List[dict]:
    xs0 = doc.get("csa_season_bowl_spells")
    if isinstance(xs0, list) and xs0:
        return xs0
    for key in ("recent_bowl_spells", "last5_bowl_spells"):
        xs = doc.get(key)
        if isinstance(xs, list) and xs:
            return xs
    return []


def _csa_entries_ipl_year_only(entries: Any, year: int) -> Tuple[List[dict], Optional[str]]:
    """All batting innings / bowling spells from IPL ``year`` only (no other-season fallback).

    When entries already come from ``csa_season_*`` (sync-scoped), the filter is a no-op.
    Legacy docs without ``season_year`` still use the first five rows as a proxy
    (``csa_last5_legacy_no_season_year``).
    """
    if not isinstance(entries, list) or not entries:
        return [], None
    dicts = [e for e in entries if isinstance(e, dict)]
    if not dicts:
        return [], None
    with_sy = sum(1 for e in dicts if e.get("season_year") is not None)
    if with_sy == 0:
        return dicts[:5], "csa_last5_legacy_no_season_year"
    out: List[dict] = []
    for e in dicts:
        sy = e.get("season_year")
        if sy is None:
            continue
        try:
            if int(sy) == int(year):
                out.append(e)
        except (TypeError, ValueError):
            continue
    if not out:
        return [], "csa_no_rows_for_ipl_year"
    return out, None


def _phase_bat_block(ph: dict, phase: str) -> dict:
    if not isinstance(ph, dict):
        return {}
    bat = ph.get("bat") or {}
    return bat.get(phase) or {}


def _phase_bowl_block(ph: dict, phase: str) -> dict:
    if not isinstance(ph, dict):
        return {}
    bowl = ph.get("bowl") or {}
    return bowl.get(phase) or {}


def _pp_bat_score(
    phases: dict,
    position: Optional[int],
    career_sr: float,
    estimates: List[str],
) -> float:
    pos = int(position or 0)
    if pos >= 5:
        return 50.0
    blk = _phase_bat_block(phases, PHASE_PP)
    balls = int(blk.get("balls") or 0)
    runs = int(blk.get("runs") or 0)
    if balls < 30:
        estimates.append("pp_bat_shallow_sample")
        if career_sr > 0:
            sr = max(80.0, career_sr * 0.95)
            avg = runs / max(balls, 1) if balls else 0.0
            pp_avg_score = _norm_pp_bat_avg(avg) if balls >= 8 else 50.0
            sr_s = _norm_pp_bat_sr(sr)
            raw = 0.4 * pp_avg_score + 0.6 * sr_s
            return 50.0 + (raw - 50.0) * 0.5
        return 50.0
    sr = runs / max(balls, 1) * 100.0
    avg = runs / max(balls, 1)
    return 0.4 * _norm_pp_bat_avg(avg) + 0.6 * _norm_pp_bat_sr(sr)


def _death_bat_score(phases: dict, position: Optional[int], estimates: List[str]) -> float:
    pos = int(position or 0)
    blk = _phase_bat_block(phases, PHASE_DEATH)
    balls = int(blk.get("balls") or 0)
    runs = int(blk.get("runs") or 0)
    total_b = sum(
        int((_phase_bat_block(phases, pk).get("balls") or 0))
        for pk in (PHASE_PP, PHASE_MID, PHASE_DEATH)
    )
    freq = balls / max(total_b, 1) if total_b else 0.0
    if balls < 20:
        estimates.append("death_bat_shallow")
        return 50.0
    if pos <= 4 and freq < 0.08:
        return 0.65 * 50.0 + 0.35 * 50.0
    sr = runs / max(balls, 1) * 100.0
    sr_s = _norm_death_bat_sr(sr)
    freq_s = _norm_bat_sr(min(160.0, 80.0 + freq * 120.0))
    if freq < 0.12:
        freq_s = 50.0
    return 0.65 * sr_s + 0.35 * freq_s


def _death_bowl_overs(phases: dict) -> float:
    blk = _phase_bowl_block(phases, PHASE_DEATH)
    lb = int(blk.get("legal_balls") or 0)
    return lb / 6.0


def _economy_adjust_death_heavy(raw_eco: float, phases: dict) -> float:
    bowl = (phases or {}).get("bowl") or {}
    tot_lb = 0
    d_lb = 0
    for pk in (PHASE_PP, PHASE_MID, PHASE_DEATH):
        b = bowl.get(pk) or {}
        lb = int(b.get("legal_balls") or 0)
        tot_lb += lb
        if pk == PHASE_DEATH:
            d_lb += lb
    if tot_lb <= 0:
        return float(raw_eco)
    share = d_lb / tot_lb
    adj = float(raw_eco)
    if share > 0.5:
        adj += 0.5 * (share / max(0.5, 1.0))
    return adj


def _death_bowl_score(phases: dict, overall_eco: float, estimates: List[str]) -> float:
    ovs = _death_bowl_overs(phases)
    if ovs < 25:
        estimates.append("death_bowl_proxy_eco")
        eco = overall_eco * 1.35
        eco_s = _norm_death_bowl_eco(eco)
        return 0.5 * eco_s + 0.5 * 50.0
    blk = _phase_bowl_block(phases, PHASE_DEATH)
    rc = int(blk.get("runs_conceded") or 0)
    lb = int(blk.get("legal_balls") or 0)
    wk = int(blk.get("wickets") or 0)
    overs = lb / 6.0
    eco = rc / max(overs, 0.01)
    eco_s = _norm_death_bowl_eco(eco)
    wkr = wk / max(overs, 0.01)
    wkr_s = _norm_wickets_per_match(min(2.5, wkr * 4.0))
    return 0.5 * eco_s + 0.5 * wkr_s


def _pp_bowl_score(phases: dict, bowling_style: Optional[str], overall_eco: float, estimates: List[str]) -> float:
    st = (bowling_style or "").lower()
    if "spin" in st or "orthodox" in st or "off break" in st or "leg break" in st:
        return 50.0
    blk = _phase_bowl_block(phases, PHASE_PP)
    lb = int(blk.get("legal_balls") or 0)
    if lb < 18:
        estimates.append("pp_bowl_proxy")
        eco_s = _norm_pp_bowl_eco(min(12.0, overall_eco * 1.08))
        return 0.6 * eco_s + 0.4 * 50.0
    rc = int(blk.get("runs_conceded") or 0)
    wk = int(blk.get("wickets") or 0)
    overs = lb / 6.0
    eco = rc / max(overs, 0.01)
    wpm = wk / max(overs / 4.0, 0.25)
    return 0.6 * _norm_pp_bowl_eco(eco) + 0.4 * _norm_wickets_per_match(wpm)


def _dot_score_from_doc(doc: dict) -> float:
    bowl = doc.get("bowling") or {}
    pct = bowl.get("dot_ball_pct")
    if pct is not None:
        return _norm_dot_pct(float(pct))
    dots = int(bowl.get("dot_balls") or 0)
    legal = int(bowl.get("legal_balls_bowled") or 0)
    if legal <= 0:
        return 45.0
    return _norm_dot_pct(100.0 * dots / legal)


def _mini_br_innings(runs: int, balls: int) -> float:
    if balls <= 0:
        return 0.0
    avg = float(runs)
    sr = runs / max(balls, 1) * 100.0
    return 0.55 * _norm_bat_average(avg) + 0.45 * _norm_bat_sr(sr)


def _weighted_last5_br(last5: List[dict]) -> Optional[float]:
    """Recency-weighted mini-BR over every innings in ``last5`` (full season or filtered list)."""
    if not last5:
        return None
    num = den = 0.0
    for i, inn in enumerate(last5):
        w = CSA_RECENCY_WEIGHTS[i] if i < len(CSA_RECENCY_WEIGHTS) else 0.5
        balls = max(int(inn.get("balls") or 0), 1)
        runs = int(inn.get("runs") or 0)
        m = _mini_br_innings(runs, balls)
        num += w * m
        den += w
    return num / den if den > 0 else None


def _mini_bor_spell(ovs: float, wk: int, rc: int) -> float:
    if ovs <= 0:
        return 0.0
    eco = rc / max(ovs, 0.01)
    wpm = wk / max(ovs / 4.0, 0.25)
    return 0.55 * _norm_bowl_economy(eco) + 0.45 * _norm_wickets_per_match(min(2.2, wpm))


def _weighted_last5_bor(last5: List[dict]) -> Optional[float]:
    """Recency-weighted mini-BoR over every spell in ``last5``."""
    if not last5:
        return None
    num = den = 0.0
    for i, sp in enumerate(last5):
        w = CSA_RECENCY_WEIGHTS[i] if i < len(CSA_RECENCY_WEIGHTS) else 0.5
        ovs = float(sp.get("overs") or 0)
        wk = int(sp.get("wickets") or 0)
        rc = int(sp.get("runs_conceded") or 0)
        m = _mini_bor_spell(ovs, wk, rc)
        num += w * m
        den += w
    return num / den if den > 0 else None


def _ar_weights(position: Optional[int], role_code: str, doc: dict, bys: Dict[int, dict]) -> Tuple[float, float]:
    if role_code != "AR":
        return 1.0, 1.0
    pos = int(position or 6)
    bowl = doc.get("bowling") or {}
    ovs_career = float(bowl.get("overs") or 0)
    inn_b = max(int(bowl.get("innings") or 0), 1)
    avg_ov = ovs_career / inn_b
    cur_blk = (bys.get(CURRENT_IPL_YEAR) or {}).get("bowling") or {}
    cur_ov = float(cur_blk.get("overs") or 0)
    cur_inn = max(int(cur_blk.get("innings") or 0), 1)
    avg_ov_eff = (cur_ov / cur_inn) if cur_ov > 0 else avg_ov

    if pos >= 7 and avg_ov_eff >= 3.0:
        return 0.35, 0.65
    if pos in (5, 6) and avg_ov_eff <= 3.5:
        return 0.65, 0.35
    return 0.5, 0.5


def compute_batter_rating(
    doc: dict,
    star_rating: float,
    batting_position: Optional[int],
) -> Tuple[float, List[str], Dict[str, float]]:
    estimates: List[str] = []
    bat = doc.get("batting") or {}
    inn_c = int(bat.get("innings") or 0)
    if inn_c <= 0:
        br = _star_to_br_prior(star_rating)
        return br, estimates, {"br_raw": br}

    runs_c = float(bat.get("runs") or 0)
    career_avg = runs_c / inn_c
    career_sr = float(bat.get("sr") or 0)
    if career_sr <= 0:
        career_sr = runs_c / max(float(bat.get("balls") or 0), 1.0) * 100.0

    bys = _normalize_by_season_keys(doc.get("by_season"))
    avg_rec = _recency_bat_average(bys, career_avg, CURRENT_IPL_YEAR)
    sr_rec = _recency_bat_sr(by_season=bys, career_sr=career_sr, current_year=CURRENT_IPL_YEAR)
    # Current-season short-sample form belongs in CSA (last5 current year), not in BR baseline.
    comp_avg = _norm_bat_average(avg_rec)
    comp_sr = _norm_bat_sr(sr_rec)

    phases = doc.get("phases") if isinstance(doc.get("phases"), dict) else {}
    comp_pp = _pp_bat_score(phases, batting_position, career_sr, estimates)
    comp_death = _death_bat_score(phases, batting_position, estimates)

    cons_frac = _recency_consistency(bys, CURRENT_IPL_YEAR)
    if cons_frac is None:
        ge15 = int(bat.get("innings_ge15") or 0)
        cons_frac = ge15 / max(inn_c, 1)
    comp_cons = _norm_consistency_pct(cons_frac)

    br = (
        0.35 * comp_avg
        + 0.30 * comp_sr
        + 0.15 * comp_pp
        + 0.10 * comp_death
        + 0.10 * comp_cons
    )
    br = _clamp(br, 0.0, 100.0)
    dbg = {
        "br_raw": br,
        "comp_avg": comp_avg,
        "comp_sr": comp_sr,
        "comp_pp": comp_pp,
        "comp_death": comp_death,
        "comp_cons": comp_cons,
    }
    return br, estimates, dbg


def compute_bowler_rating(
    doc: dict,
    star_rating: float,
    bowling_style: Optional[str],
) -> Tuple[float, List[str], Dict[str, float]]:
    estimates: List[str] = []
    bowl = doc.get("bowling") or {}
    overs = float(bowl.get("overs") or 0)
    inn_b = int(bowl.get("innings") or 0)
    if overs <= 0 and inn_b <= 0:
        bor = _star_to_bor_prior(star_rating)
        return bor, estimates, {"bor_raw": bor}

    matches = max(int(doc.get("matches") or 0), 1)
    wk = int(bowl.get("wickets") or 0)
    eco_c = float(bowl.get("economy") or 0)
    if eco_c <= 0 and overs > 0:
        eco_c = float(bowl.get("runs_conceded") or 0) / max(overs, 0.01)

    bys = _normalize_by_season_keys(doc.get("by_season"))

    def eco_pick(bb: dict) -> Optional[Tuple[float, float]]:
        o = float(bb.get("overs") or 0)
        if o <= 0:
            return None
        rc = float(bb.get("runs_conceded") or 0)
        return rc / max(o, 0.01), 1.0

    def wpm_pick(bb: dict) -> Optional[Tuple[float, float]]:
        w = int(bb.get("wickets") or 0)
        o = float(bb.get("overs") or 0)
        if o <= 0:
            return None
        m_est = max(o / 4.0, 1.0)
        return w / m_est, 1.0

    eco_num = den = 0.0
    for y in sorted(bys.keys(), reverse=True):
        blk = bys[y]
        bw = blk.get("bowling") if isinstance(blk, dict) else None
        if not isinstance(bw, dict):
            continue
        picked = eco_pick(bw)
        if not picked:
            continue
        w = _recency_weight_for_year(y, CURRENT_IPL_YEAR)
        eco_num += w * picked[0]
        den += w
    eco_rec = eco_num / den if den > 0 else eco_c

    wpm_num = wpm_den = 0.0
    for y in sorted(bys.keys(), reverse=True):
        blk = bys[y]
        bw = blk.get("bowling") if isinstance(blk, dict) else None
        if not isinstance(bw, dict):
            continue
        picked = wpm_pick(bw)
        if not picked:
            continue
        w = _recency_weight_for_year(y, CURRENT_IPL_YEAR)
        wpm_num += w * picked[0]
        wpm_den += w
    wpm_rec = wpm_num / wpm_den if wpm_den > 0 else wk / max(overs / 4.0, 1.0)

    phases = doc.get("phases") if isinstance(doc.get("phases"), dict) else {}
    eco_adj = _economy_adjust_death_heavy(eco_rec, phases)

    comp_eco = _norm_bowl_economy(eco_adj)
    comp_wkr = _norm_wickets_per_match(wpm_rec)
    comp_death = _death_bowl_score(phases, eco_c, estimates)
    comp_pp = _pp_bowl_score(phases, bowling_style, eco_c, estimates)
    comp_dot = _dot_score_from_doc(doc)

    bor = (
        0.30 * comp_eco
        + 0.30 * comp_wkr
        + 0.20 * comp_death
        + 0.10 * comp_pp
        + 0.10 * comp_dot
    )
    bor = _clamp(bor, 0.0, 100.0)
    dbg = {
        "bor_raw": bor,
        "comp_eco": comp_eco,
        "comp_wkr": comp_wkr,
        "comp_death": comp_death,
        "comp_pp": comp_pp,
        "comp_dot": comp_dot,
    }
    return bor, estimates, dbg


def _effective_ip(raw: float, csa: float, conf: float) -> float:
    return _clamp(float(raw) * (1.0 + float(csa)) * float(conf), 0.0, 100.0)


def compute_player_impact_profile(
    perf_row: Optional[dict],
    role_code: str,
    star_rating: float,
    *,
    batting_position: Optional[int] = None,
    bowling_style: Optional[str] = None,
) -> Dict[str, Any]:
    doc = perf_row if isinstance(perf_row, dict) else {}
    bat = doc.get("batting") or {}
    bowl = doc.get("bowling") or {}
    inn_c = int(bat.get("innings") or 0)
    overs = float(bowl.get("overs") or 0)

    br_est: List[str] = []
    bor_est: List[str] = []
    br, br_est, br_dbg = compute_batter_rating(doc, star_rating, batting_position)
    bor, bor_est, bor_dbg = compute_bowler_rating(doc, star_rating, bowling_style)

    last5b = _csa_bat_entry_source(doc)
    last5o = _csa_bowl_entry_source(doc)
    last5b_cs, csa_note_b = _csa_entries_ipl_year_only(last5b, CURRENT_IPL_YEAR)
    last5o_cs, csa_note_o = _csa_entries_ipl_year_only(last5o, CURRENT_IPL_YEAR)
    form_br = _weighted_last5_br(last5b_cs)
    form_bor = _weighted_last5_bor(last5o_cs)
    csa_notes: List[str] = [n for n in (csa_note_b, csa_note_o) if n]

    csa_bat: Optional[float] = None
    if br > 1e-6 and form_br is not None:
        csa_bat = _clamp((form_br - br) / br, -0.45, 0.45)

    csa_bowl: Optional[float] = None
    if bor > 1e-6 and form_bor is not None:
        csa_bowl = _clamp((form_bor - bor) / bor, -0.45, 0.45)

    b_label, cm_bat = _batting_confidence(inn_c)
    o_label, cm_bowl = _bowling_confidence(overs)
    pen_b = _confidence_penalty_estimates(br_est)
    pen_o = _confidence_penalty_estimates(bor_est)
    cm_bat *= pen_b
    cm_bowl *= pen_o

    bat_ip = _effective_ip(br, float(csa_bat if csa_bat is not None else 0.0), cm_bat)
    bowl_ip = _effective_ip(bor, float(csa_bowl if csa_bowl is not None else 0.0), cm_bowl)

    if role_code == "BAT":
        bowl_ip *= 0.55
    elif role_code == "BOWL":
        bat_ip *= 0.60
    # AR: full batting + bowling IPs (team AR index mixes them with alpha downstream)

    out: Dict[str, Any] = {
        "BatIP": round(_clamp(bat_ip, 0.0, 100.0), 4),
        "BowlIP": round(_clamp(bowl_ip, 0.0, 100.0), 4),
        "BPR_bat": round(br, 4),
        "BPR_bowl": round(bor, 4),
        "CSA_bat": None if csa_bat is None else round(csa_bat, 4),
        "CSA_bowl": None if csa_bowl is None else round(csa_bowl, 4),
        "batting_confidence": b_label,
        "batting_confidence_mult": round(cm_bat, 4),
        "batting_innings_sample": inn_c,
        "bowling_confidence": o_label,
        "bowling_confidence_mult": round(cm_bowl, 4),
        "bowling_overs_sample": round(overs, 2),
        "impact_model": "br_bor_v1",
        "impact_estimates": list(dict.fromkeys(br_est + bor_est + csa_notes)),
        "br_bor_debug": {**br_dbg, **{f"bowl_{k}": v for k, v in bor_dbg.items()}},
    }
    if role_code == "AR":
        bys_ar = _normalize_by_season_keys(doc.get("by_season"))
        w_b, w_o = _ar_weights(batting_position, role_code, doc, bys_ar)
        out["ar_role_weights"] = {"bat": round(w_b, 4), "bowl": round(w_o, 4)}
    return out
