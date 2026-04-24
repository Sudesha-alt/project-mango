"""
Two-layer CSA: Output CSA (recency-weighted results vs BPR) + Input CSA (process proxies).

Proxies use only Mongo/SportMonks fields we already sync (no team score at dismissal).
Categories 1–4 adjust how much we trust negative output, per spec:
  Cat 2: halve negative output penalty before blending; mean-reversion flag for quality players.
  Cat 4: thin sample or volatile runs — shrink effective CSA and confidence.
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional, Tuple

_CSA_W = (2.0, 1.5, 1.0, 0.75, 0.5)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _quality_batter(doc: dict) -> bool:
    bat = doc.get("batting") or {}
    inn = max(int(bat.get("innings") or 0), 1)
    avg = float(bat.get("runs") or 0) / inn
    return avg >= 28.0


def _quality_bowler(doc: dict) -> bool:
    bowl = doc.get("bowling") or {}
    eco = float(bowl.get("economy") or 0)
    ovs = float(bowl.get("overs") or 0)
    return ovs >= 20.0 and 0 < eco <= 8.35


def _runs_volatile(runs: List[int]) -> bool:
    if len(runs) < 4:
        return False
    m = sum(runs) / len(runs)
    if m < 3:
        return True
    try:
        sd = statistics.pstdev([float(x) for x in runs])
        return (sd / max(m, 1.0)) > 1.05
    except statistics.StatisticsError:
        return False


def _consecutive_low_bat_entries(entries: List[dict], *, threshold: int = 20, need: int = 4) -> bool:
    if len(entries) < need:
        return False
    for e in entries[:need]:
        if int(e.get("runs") or 0) >= threshold:
            return False
    return True


def input_csa_bat_from_innings(last5_cs: List[dict], doc: dict) -> Tuple[float, List[str]]:
    notes: List[str] = []
    if not last5_cs:
        return 0.0, notes
    bat = doc.get("batting") or {}
    inn = max(int(bat.get("innings") or 0), 1)
    career_runs = float(bat.get("runs") or 0)
    career_sr = float(bat.get("sr") or 0)
    if career_sr <= 0:
        career_sr = career_runs / max(float(bat.get("balls") or 0), 1.0) * 100.0
    runs = [int(x.get("runs") or 0) for x in last5_cs]
    balls = [max(int(x.get("balls") or 0), 1) for x in last5_cs]
    srs = [r / b * 100.0 for r, b in zip(runs, balls)]
    mean_sr = sum(srs) / len(srs)
    mean_r = sum(runs) / len(runs)
    sig = 0.0
    # Low totals but SR held near career → process arguably fine (drought / context)
    if mean_r < 20 and career_sr >= 105 and mean_sr >= career_sr * 0.88:
        sig += 0.12
        notes.append("input_bat_sr_held_vs_career")
    if mean_r < 15 and mean_sr < career_sr * 0.72 and career_sr >= 100:
        sig -= 0.11
        notes.append("input_bat_sr_collapse")
    if _runs_volatile(runs):
        sig *= 0.55
        notes.append("input_bat_volatile_innings")
    return _clamp(sig, -0.25, 0.25), notes


def input_csa_bowl_from_spells(last5_cs: List[dict], doc: dict) -> Tuple[float, List[str]]:
    notes: List[str] = []
    if not last5_cs:
        return 0.0, notes
    num = den = 0.0
    for i, s in enumerate(last5_cs):
        w = _CSA_W[i] if i < len(_CSA_W) else 0.5
        ovs = float(s.get("overs") or 0)
        if ovs <= 0:
            continue
        rc = int(s.get("runs_conceded") or 0)
        eco = rc / ovs
        num += w * eco
        den += w
    if den <= 0:
        return 0.0, notes
    recent_eco = num / den
    wk_total = sum(int(s.get("wickets") or 0) for s in last5_cs)
    n = len(last5_cs)
    sig = 0.0
    if wk_total == 0 and n >= 3 and recent_eco <= 9.25:
        sig += 0.14
        notes.append("input_bowl_good_eco_zero_wickets")
    if recent_eco >= 10.6 and wk_total < max(1, n // 2):
        sig -= 0.12
        notes.append("input_bowl_expensive_low_wickets")
    bowl = doc.get("bowling") or {}
    career_eco = float(bowl.get("economy") or 0)
    if career_eco > 0 and recent_eco <= career_eco * 0.92 and wk_total <= n:
        sig += 0.05
        notes.append("input_bowl_eco_vs_career")
    return _clamp(sig, -0.25, 0.25), notes


def classify_csa_two_layer(
    csa_output: Optional[float],
    input_csa: float,
    n_innings: int,
    runs_list: Optional[List[int]],
) -> Tuple[int, str]:
    if csa_output is None:
        return 4, "no_output_csa"
    if n_innings < 3:
        return 4, "insufficient_sample"
    if runs_list and _runs_volatile(runs_list):
        return 4, "volatile_outputs"
    out = float(csa_output)
    inp = float(input_csa)
    if out > 0.02 and inp > 0.02:
        return 1, "form_confirmed"
    if out > 0.02 and inp >= -0.05:
        return 1, "form_confirmed_mild_input"
    if out < -0.025 and inp < -0.05:
        return 3, "genuine_decline"
    if out < -0.025 and inp >= -0.05:
        return 2, "statistical_drought"
    return 1, "neutral_band"


def floor_ceiling_weights(category: int) -> Tuple[float, float]:
    if category == 1:
        return 0.70, 0.30
    if category == 2:
        return 0.45, 0.55
    if category == 3:
        return 0.75, 0.25
    return 0.50, 0.50


def apply_csa_two_layer_bat(
    csa_output: Optional[float],
    last5_cs: List[dict],
    doc: dict,
    cm_bat: float,
    _br: float,
) -> Tuple[Optional[float], float, Dict[str, Any]]:
    """Returns (CSA effective for BatIP, adjusted confidence mult, meta)."""
    inp, in_notes = input_csa_bat_from_innings(last5_cs, doc)
    runs_list = [int(x.get("runs") or 0) for x in last5_cs]
    cat, label = classify_csa_two_layer(csa_output, inp, len(last5_cs), runs_list)
    fl, ce = floor_ceiling_weights(cat)

    out_adj: Optional[float] = None if csa_output is None else float(csa_output)
    if out_adj is not None and cat == 2 and out_adj < 0:
        out_adj = 0.5 * out_adj

    eff: Optional[float] = None
    if out_adj is not None:
        eff = _clamp(0.6 * out_adj + 0.4 * inp, -0.45, 0.45)

    cm2 = float(cm_bat)
    if cat == 4 and eff is not None:
        eff = _clamp(eff * 0.5, -0.45, 0.45)
        cm2 *= 0.5

    mean_rev = (
        cat == 2
        and _quality_batter(doc)
        and _consecutive_low_bat_entries(last5_cs)
        and (csa_output or 0) < -0.02
    )

    meta = {
        "CSA_output": None if csa_output is None else round(float(csa_output), 4),
        "CSA_input": round(inp, 4),
        "CSA_effective": None if eff is None else round(eff, 4),
        "category": cat,
        "category_label": label,
        "floor_weight": fl,
        "ceiling_weight": ce,
        "mean_reversion_candidate": mean_rev,
        "mean_reversion_ceiling_pct": 0.35 if mean_rev else None,
        "input_notes": in_notes,
    }
    return eff, cm2, meta


def _spell_economies_volatile(last5_cs: List[dict]) -> bool:
    if len(last5_cs) < 4:
        return False
    ecos: List[float] = []
    for s in last5_cs:
        ovs = float(s.get("overs") or 0)
        if ovs <= 0:
            continue
        rc = int(s.get("runs_conceded") or 0)
        ecos.append(rc / max(ovs, 0.01))
    if len(ecos) < 4:
        return False
    m = sum(ecos) / len(ecos)
    try:
        sd = statistics.pstdev(ecos)
    except statistics.StatisticsError:
        return False
    return sd > 2.0 and m > 6.0


def apply_csa_two_layer_bowl(
    csa_output: Optional[float],
    last5_cs: List[dict],
    doc: dict,
    cm_bowl: float,
    _bor: float,
) -> Tuple[Optional[float], float, Dict[str, Any]]:
    inp, in_notes = input_csa_bowl_from_spells(last5_cs, doc)
    cat, label = classify_csa_two_layer(csa_output, inp, len(last5_cs), None)
    if len(last5_cs) >= 4 and _spell_economies_volatile(last5_cs):
        cat, label = 4, "volatile_spell_outputs"
    fl, ce = floor_ceiling_weights(cat)

    out_adj: Optional[float] = None if csa_output is None else float(csa_output)
    if out_adj is not None and cat == 2 and out_adj < 0:
        out_adj = 0.5 * out_adj

    eff: Optional[float] = None
    if out_adj is not None:
        eff = _clamp(0.6 * out_adj + 0.4 * inp, -0.45, 0.45)

    cm2 = float(cm_bowl)
    if cat == 4 and eff is not None:
        eff = _clamp(eff * 0.5, -0.45, 0.45)
        cm2 *= 0.5

    n = len(last5_cs)
    wk_total = sum(int(s.get("wickets") or 0) for s in last5_cs)
    num = den = 0.0
    for i, s in enumerate(last5_cs):
        w = _CSA_W[i] if i < len(_CSA_W) else 0.5
        ovs = float(s.get("overs") or 0)
        if ovs <= 0:
            continue
        rc = int(s.get("runs_conceded") or 0)
        eco = rc / ovs
        num += w * eco
        den += w
    recent_eco = num / den if den > 0 else 99.0
    mean_rev = (
        cat == 2
        and _quality_bowler(doc)
        and n >= 4
        and wk_total == 0
        and recent_eco <= 9.3
        and (csa_output or 0) < -0.02
    )

    meta = {
        "CSA_output": None if csa_output is None else round(float(csa_output), 4),
        "CSA_input": round(inp, 4),
        "CSA_effective": None if eff is None else round(eff, 4),
        "category": cat,
        "category_label": label,
        "floor_weight": fl,
        "ceiling_weight": ce,
        "mean_reversion_candidate": mean_rev,
        "mean_reversion_ceiling_pct": 0.35 if mean_rev else None,
        "input_notes": in_notes,
    }
    return eff, cm2, meta
