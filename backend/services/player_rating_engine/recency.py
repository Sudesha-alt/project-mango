"""Recency-weighted aggregates from `by_season` + career totals."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .constants import (
    CURRENT_IPL_YEAR,
    RECENCY_OFFSET_WEIGHTS,
    RECENCY_OLDER_POOL_WEIGHT,
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def normalize_by_season_keys(by_season: Any) -> Dict[int, dict]:
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


def _weight_for_year(year: int, current: int) -> Optional[float]:
    """None = belongs to older pool (year < current - 3)."""
    if year > current:
        return 0.0
    off = current - year
    if off < 0:
        return 0.0
    if off < len(RECENCY_OFFSET_WEIGHTS):
        return RECENCY_OFFSET_WEIGHTS[off]
    return None  # older pool


def recency_weighted_season_stats(
    by_season: Dict[int, dict],
    current_year: int = CURRENT_IPL_YEAR,
    *,
    bat_extractor: Optional[Callable[[dict], Tuple[float, float]]] = None,
    bowl_extractor: Optional[Callable[[dict], Tuple[float, float, float]]] = None,
) -> Tuple[float, float, float, float, float, float]:
    """
    Returns (bat_num, bat_den, bat_w_sum, bowl_eco_num, bowl_wkt_num, bowl_w_sum)
    where weighted batting average� bat_num/max(bat_den,1e-6) after normalizing den weights,
    and weighted bowl eco uses sum(w*eco)/sum(w), wkt rate sum(w*wpm)/sum(w) with wpm = wk/innings per season.
    """
    older_bat_runs = older_bat_inn =0.0
    older_bowl_rc = older_bowl_ovs = older_bowl_wk = older_bowl_inn = 0.0

    bat_num = bat_den = bat_w = 0.0
    eco_parts: List[Tuple[float, float]] = []
    wpm_parts: List[Tuple[float, float]] = []

    for y, blk in sorted(by_season.items()):
        w = _weight_for_year(y, current_year)
        if w is None:
            w = RECENCY_OLDER_POOL_WEIGHT
            if bat_extractor:
                bruns, binn = bat_extractor(blk)
                older_bat_runs += bruns
                older_bat_inn += max(binn, 1.0)
            if bowl_extractor:
                eco, wk, inn = bowl_extractor(blk)
                if inn > 0 and eco >= 0:
                    older_bowl_rc += eco * (wk *0 + 1)  # wrong # handle older pool as merged block below
            continue
        if w <= 0:
            continue
        if bat_extractor:
            bruns, binn = bat_extractor(blk)
            if binn > 0:
                avg = bruns / binn
                bat_num += w * avg
                bat_den += w if bowl_extractor:
            eco, wk, inn = bowl_extractor(blk)
            if inn > 0:
                wpm = wk / inn
                eco_parts.append((w, eco))
                wpm_parts.append((w, wpm))

    # Older pool: single blended stat with RECENCY_OLDER_POOL_WEIGHT
    if older_bat_inn > 0 and bat_extractor:
        o_avg = older_bat_runs / older_bat_inn
        bat_num += RECENCY_OLDER_POOL_WEIGHT * o_avg
        bat_den += RECENCY_OLDER_POOL_WEIGHT

    # Recompute older bowl from merged seasons
    ob_runs = ob_ovs = ob_wk = ob_inn = 0.0
    for y, blk in by_season.items():
        if _weight_for_year(y, current_year) is not None:
            continue
        if not bowl_extractor:
            break
        bw = (blk.get("bowling") or {}) if isinstance(blk, dict) else {}
        ob_runs += float(bw.get("runs_conceded") or 0)
        ob_ovs += float(bw.get("overs") or 0)
        ob_wk += float(bw.get("wickets") or 0)
        ob_inn += float(bw.get("innings") or 0)
    if bowl_extractor and ob_inn > 0:
        o_eco = ob_runs / max(ob_ovs, 0.01)
        o_wpm = ob_wk / ob_inn
        eco_parts.append((RECENCY_OLDER_POOL_WEIGHT, o_eco))
        wpm_parts.append((RECENCY_OLDER_POOL_WEIGHT, o_wpm))

    bowl_eco = sum(w * e for w, e in eco_parts) / max(sum(w for w, _ in eco_parts), 1e-6) if eco_parts else 8.0
    bowl_wpm = sum(w * v for w, v in wpm_parts) / max(sum(w for w, _ in wpm_parts), 1e-6) if wpm_parts else 0.8

    return bat_num, bat_den, bat_w, bowl_eco, bowl_wpm, sum(w for w, _ in eco_parts)


def career_bat_avg_sr(doc: dict) -> Tuple[float, float, int]:
    bat = doc.get("batting") or {}
    inn = int(bat.get("innings") or 0)
    if inn <= 0:
        return 0.0, 0.0, 0
    runs = float(bat.get("runs") or 0)
    sr = float(bat.get("sr") or 0)
    if sr <= 0 and bat.get("balls"):
        sr = runs / max(float(bat.get("balls") or 1), 1.0) * 100.0
    return runs / inn, sr, inn


def season_bat_avg_sr(blk: dict) -> Tuple[float, float]:
    bb = (blk.get("batting") or {}) if isinstance(blk, dict) else {}
    inn = int(bb.get("innings") or 0)
    if inn <= 0:
        return 0.0, 0.0
    runs = float(bb.get("runs") or 0)
    sr = float(bb.get("sr") or 0)
    if sr <= 0 and bb.get("balls"):
        sr = runs / max(float(bb.get("balls") or 1), 1.0) * 100.0
    return runs / inn, sr


def season_bowl_eco_wpm(blk: dict) -> Tuple[float, float, float]:
    bw = (blk.get("bowling") or {}) if isinstance(blk, dict) else {}
    inn = int(bw.get("innings") or 0)
    ovs = float(bw.get("overs") or 0)
    wk = float(bw.get("wickets") or 0)
    rc = float(bw.get("runs_conceded") or 0)
    eco = float(bw.get("economy") or 0)
    if eco <= 0 and ovs > 0:
        eco = rc / max(ovs, 0.01)
    wpm = wk / max(inn, 1.0) if inn > 0 else 0.0
    return eco, wk, inn


def recency_batting_averages(doc: dict, current_year: int = CURRENT_IPL_YEAR) -> Tuple[float, float]:
    """Weighted (avg, sr) using season blocks + older pool."""
    bys = normalize_by_season_keys(doc.get("by_season"))

    def ext(blk: dict) -> Tuple[float, float]:
        a, s = season_bat_avg_sr(blk)
        return a, 1.0  # second val unused — we use separate SR weighting

    # Custom: separate recency for avg and sr
    avg_num = avg_den = 0.0
    sr_num = sr_den = 0.0
    older_runs = older_balls = 0.0
    for y, blk in bys.items():
        w = _weight_for_year(y, current_year)
        bb = (blk.get("batting") or {}) if isinstance(blk, dict) else {}
        inn = int(bb.get("innings") or 0)
        if inn <= 0:
            continue
        runs = float(bb.get("runs") or 0)
        balls = float(bb.get("balls") or 1)
        sr = float(bb.get("sr") or 0) or (runs / max(balls, 1.0) * 100.0)
        av = runs / inn
        if w is None:
            older_runs += runs
            older_balls += balls
            continue
        if w <= 0:
            continue
        avg_num += w * av
        avg_den += w
        sr_num += w * sr
        sr_den += w

    if older_balls > 0 or older_runs > 0:
        # older pool weight on merged SR/avg
        o_inn = sum(
            int((bys[y].get("batting") or {}).get("innings") or 0)
            for y in bys
            if _weight_for_year(y, current_year) is None
        )
        if o_inn > 0:
            o_runs = sum(float((bys[y].get("batting") or {}).get("runs") or 0) for y in bys if _weight_for_year(y, current_year) is None)
            o_balls = sum(float((bys[y].get("batting") or {}).get("balls") or 0) for y in bys if _weight_for_year(y, current_year) is None)
            o_avg = o_runs / o_inn
            o_sr = o_runs / max(o_balls, 1.0) * 100.0
            avg_num += RECENCY_OLDER_POOL_WEIGHT * o_avg
            avg_den += RECENCY_OLDER_POOL_WEIGHT
            sr_num += RECENCY_OLDER_POOL_WEIGHT * o_sr
            sr_den += RECENCY_OLDER_POOL_WEIGHT

    w_avg = avg_num / max(avg_den, 1e-6) if avg_den > 0 else 0.0
    w_sr = sr_num / max(sr_den, 1e-6) if sr_den > 0 else 0.0
    if avg_den == 0 and sr_den == 0:
        w_avg, w_sr, _ = career_bat_avg_sr(doc)
    return w_avg, w_sr


def recency_bowling_economy(doc: dict, current_year: int = CURRENT_IPL_YEAR) -> float:
    bys = normalize_by_season_keys(doc.get("by_season"))
    eco_num = eco_den = 0.0
    older_rc = older_ovs = 0.0
    for y, blk in bys.items():
        w = _weight_for_year(y, current_year)
        eco, _wk, inn = season_bowl_eco_wpm(blk)
        if inn <= 0:
            continue
        bw = (blk.get("bowling") or {}) if isinstance(blk, dict) else {}
        if w is None:
            older_rc += float(bw.get("runs_conceded") or 0)
            older_ovs += float(bw.get("overs") or 0)
            continue
        if w <= 0:
            continue
        eco_num += w * eco
        eco_den += w
    if older_ovs > 0:
        o_eco = older_rc / older_ovs
        eco_num += RECENCY_OLDER_POOL_WEIGHT * o_eco
        eco_den += RECENCY_OLDER_POOL_WEIGHT
    if eco_den <= 0:
        bowl = doc.get("bowling") or {}
        ovs = float(bowl.get("overs") or 0)
        if ovs > 0:
            return float(bowl.get("runs_conceded") or 0) / ovs
        return float(bowl.get("economy") or 8.0)
    return eco_num / eco_den


def recency_consistency_ratio(doc: dict, current_year: int = CURRENT_IPL_YEAR) -> float:
    """Fraction of innings with 15+ runs, recency-weighted by season."""
    bys = normalize_by_season_keys(doc.get("by_season"))
    num = den = 0.0
    older_ge = older_inn = 0.0
    for y, blk in bys.items():
        w = _weight_for_year(y, current_year)
        bb = (blk.get("batting") or {}) if isinstance(blk, dict) else {}
        inn = int(bb.get("innings") or 0)
        if inn <= 0:
            continue
        ge = int(bb.get("innings_ge15") or 0)
        ratio = ge / max(inn, 1)
        if w is None:
            older_ge += ge
            older_inn += inn
            continue
        if w <= 0:
            continue
        num += w * ratio
        den += w
    if older_inn > 0:
        num += RECENCY_OLDER_POOL_WEIGHT * (older_ge / older_inn)
        den += RECENCY_OLDER_POOL_WEIGHT
    if den <= 0:
        bat = doc.get("batting") or {}
        inn = int(bat.get("innings") or 0)
        if inn <= 0:
            return 0.0
        ge = int(bat.get("innings_ge15") or 0)
        return ge / max(inn, 1)
    return num / den
