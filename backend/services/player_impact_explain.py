"""
Transparent CSA / BPR breakdown for a single player row (debug / verification).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.player_impact_br_bor import (
    CSA_RECENCY_WEIGHTS,
    CURRENT_IPL_YEAR,
    _clamp,
    _csa_bat_entry_source,
    _csa_bowl_entry_source,
    _csa_entries_ipl_year_only,
    _mini_bor_spell,
    _mini_br_innings,
    _norm_bat_average,
    _norm_bat_sr,
    compute_batter_rating,
    compute_bowler_rating,
)
from services.player_impact_classic_bpr import (
    _classic_bat_bpr_core,
    _classic_bowl_bpr_core,
    _log_sample_conf,
    _weighted_form_bat_core,
    _weighted_form_bowl_core,
)
from services.player_impact_bpr_csa import IMPACT_FORMULAS, compute_player_impact_profile


def _bat_rows_br_bor(last5_cs: List[dict]) -> tuple:
    rows: List[Dict[str, Any]] = []
    num = den = 0.0
    for i, inn in enumerate(last5_cs):
        w = CSA_RECENCY_WEIGHTS[i] if i < len(CSA_RECENCY_WEIGHTS) else 0.5
        balls = max(int(inn.get("balls") or 0), 1)
        runs = int(inn.get("runs") or 0)
        sr = round(runs / balls * 100.0, 2)
        na = _norm_bat_average(float(runs))
        ns = _norm_bat_sr(sr)
        mini = _mini_br_innings(runs, balls)
        num += w * mini
        den += w
        rows.append(
            {
                "index": i,
                "recency_weight": w,
                "runs": runs,
                "balls": balls,
                "strike_rate": sr,
                "norm_avg_component_0_55": round(0.55 * na, 4),
                "norm_sr_component_0_45": round(0.45 * ns, 4),
                "mini_br_innings_0_100_scale": round(mini, 4),
                "weighted_contrib": round(w * mini, 4),
                "season_year": inn.get("season_year"),
                "date": inn.get("date"),
            }
        )
    form = num / den if den > 0 else None
    return rows, form, num, den


def _bowl_rows_br_bor(last5_cs: List[dict]) -> tuple:
    rows: List[Dict[str, Any]] = []
    num = den = 0.0
    for i, sp in enumerate(last5_cs):
        w = CSA_RECENCY_WEIGHTS[i] if i < len(CSA_RECENCY_WEIGHTS) else 0.5
        ovs = float(sp.get("overs") or 0)
        wk = int(sp.get("wickets") or 0)
        rc = int(sp.get("runs_conceded") or 0)
        if ovs <= 0:
            rows.append(
                {
                    "index": i,
                    "recency_weight": w,
                    "skipped": True,
                    "reason": "overs<=0",
                    "season_year": sp.get("season_year"),
                    "date": sp.get("date"),
                }
            )
            continue
        mini = _mini_bor_spell(ovs, wk, rc)
        num += w * mini
        den += w
        rows.append(
            {
                "index": i,
                "recency_weight": w,
                "overs": ovs,
                "wickets": wk,
                "runs_conceded": rc,
                "economy": round(rc / max(ovs, 0.01), 3),
                "mini_bor_spell_0_100_scale": round(mini, 4),
                "weighted_contrib": round(w * mini, 4),
                "season_year": sp.get("season_year"),
                "date": sp.get("date"),
            }
        )
    form = num / den if den > 0 else None
    return rows, form, num, den


def _bat_rows_classic(last5_cs: List[dict], conf_bat: float) -> tuple:
    rows: List[Dict[str, Any]] = []
    num = den = 0.0
    for i, inn in enumerate(last5_cs):
        w = CSA_RECENCY_WEIGHTS[i] if i < len(CSA_RECENCY_WEIGHTS) else 0.5
        runs = int(inn.get("runs") or 0)
        balls = max(int(inn.get("balls") or 0), 1)
        sr = runs / balls * 100.0
        sr_idx = _clamp(sr / 130.0, 0.5, 1.5)
        term = runs * sr_idx
        num += w * term
        den += w
        rows.append(
            {
                "index": i,
                "recency_weight": w,
                "runs": runs,
                "balls": balls,
                "strike_rate": round(sr, 2),
                "sr_index_clamped_sr_over_130": round(sr_idx, 4),
                "runs_times_sr_index": round(term, 4),
                "weighted_contrib_before_conf": round(w * term, 4),
                "season_year": inn.get("season_year"),
                "date": inn.get("date"),
            }
        )
    core = (num / den) * conf_bat if den > 0 else None
    return rows, core, num, den, conf_bat


def _bowl_rows_classic(last5_cs: List[dict], conf_bowl: float) -> tuple:
    rows: List[Dict[str, Any]] = []
    num = den = 0.0
    for i, sp in enumerate(last5_cs):
        w = CSA_RECENCY_WEIGHTS[i] if i < len(CSA_RECENCY_WEIGHTS) else 0.5
        ovs = float(sp.get("overs") or 0)
        if ovs <= 0:
            rows.append(
                {
                    "index": i,
                    "recency_weight": w,
                    "skipped": True,
                    "reason": "overs<=0",
                    "season_year": sp.get("season_year"),
                    "date": sp.get("date"),
                }
            )
            continue
        wk = int(sp.get("wickets") or 0)
        rc = int(sp.get("runs_conceded") or 0)
        eco = rc / max(ovs, 0.01)
        wpo = wk / max(ovs, 0.01)
        eco_q = _clamp(11.5 - _clamp(eco, 4.0, 14.0), 0.0, 11.5)
        wkt_idx = _clamp(wpo / 0.5, 0.35, 1.75)
        term = eco_q * wkt_idx
        num += w * term
        den += w
        rows.append(
            {
                "index": i,
                "recency_weight": w,
                "overs": ovs,
                "wickets": wk,
                "runs_conceded": rc,
                "economy": round(eco, 3),
                "eco_quality": round(eco_q, 4),
                "wicket_rate_index": round(wkt_idx, 4),
                "eco_q_times_wkt_idx": round(term, 4),
                "weighted_contrib_before_conf": round(w * term, 4),
                "season_year": sp.get("season_year"),
                "date": sp.get("date"),
            }
        )
    core = (num / den) * conf_bowl if den > 0 else None
    return rows, core, num, den, conf_bowl


def explain_csa_for_perf_row(
    perf_row: dict,
    *,
    star_rating: float,
    role_code: str = "BAT",
    batting_position: Optional[int] = None,
    bowling_style: Optional[str] = None,
    formula: str = "br_bor_v1",
) -> Dict[str, Any]:
    f = (formula or "br_bor_v1").strip()
    if f not in IMPACT_FORMULAS:
        f = "br_bor_v1"

    doc = perf_row if isinstance(perf_row, dict) else {}
    name = (doc.get("name") or "").strip()
    pid = doc.get("player_id")

    bat_src = _csa_bat_entry_source(doc)
    bowl_src = _csa_bowl_entry_source(doc)
    bat_pre_len = len(bat_src)
    bowl_pre_len = len(bowl_src)
    bat_cs, note_b = _csa_entries_ipl_year_only(bat_src, CURRENT_IPL_YEAR)
    bowl_cs, note_o = _csa_entries_ipl_year_only(bowl_src, CURRENT_IPL_YEAR)

    profile = compute_player_impact_profile(
        doc,
        role_code,
        float(star_rating),
        batting_position=batting_position,
        bowling_style=bowling_style,
        formula=f,
    )

    out: Dict[str, Any] = {
        "player_name": name,
        "player_id": pid,
        "formula": f,
        "current_ipl_year": CURRENT_IPL_YEAR,
        "role_code_used": role_code,
        "star_rating_prior": round(float(star_rating), 4),
        "recency_weights_newest_to_oldest": list(CSA_RECENCY_WEIGHTS),
        "batting_entries": {
            "mongo_source_list": (
                "csa_season_bat_innings"
                if doc.get("csa_season_bat_innings")
                else ("recent_bat_innings" if doc.get("recent_bat_innings") else "last5_bat_innings")
            ),
            "rows_in_source": bat_pre_len,
            "rows_after_ipl_year_filter": len(bat_cs),
            "csa_year_filter_note": note_b,
            "profile_CSA_bat": profile.get("CSA_bat"),
            "profile_BPR_bat": profile.get("BPR_bat"),
        },
        "bowling_entries": {
            "mongo_source_list": (
                "csa_season_bowl_spells"
                if doc.get("csa_season_bowl_spells")
                else ("recent_bowl_spells" if doc.get("recent_bowl_spells") else "last5_bowl_spells")
            ),
            "rows_in_source": bowl_pre_len,
            "rows_after_ipl_year_filter": len(bowl_cs),
            "csa_year_filter_note": note_o,
            "profile_CSA_bowl": profile.get("CSA_bowl"),
            "profile_BPR_bowl": profile.get("BPR_bowl"),
        },
        "full_profile": profile,
    }

    if f == "br_bor_v1":
        br, _, br_dbg = compute_batter_rating(doc, float(star_rating), batting_position)
        bor, _, bor_dbg = compute_bowler_rating(doc, float(star_rating), bowling_style)
        bat_rows, form_br, b_num, b_den = _bat_rows_br_bor(bat_cs)
        bowl_rows, form_bor, o_num, o_den = _bowl_rows_br_bor(bowl_cs)
        csa_b_raw = (form_br - br) / br if br > 1e-6 and form_br is not None else None
        csa_o_raw = (form_bor - bor) / bor if bor > 1e-6 and form_bor is not None else None
        out["br_bor_v1"] = {
            "batting": {
                "BPR_bat_BR": round(br, 4),
                "form_br_weighted_avg_mini_br": None if form_br is None else round(form_br, 4),
                "numerator_sum_w_times_mini_br": round(b_num, 6),
                "denominator_sum_w": round(b_den, 6),
                "CSA_bat_formula": "(form_br - BPR_bat) / BPR_bat, then clamp to [-0.45, 0.45]",
                "CSA_bat_before_clamp": None if csa_b_raw is None else round(csa_b_raw, 6),
                "CSA_bat_after_clamp": profile.get("CSA_bat"),
                "per_innings_newest_first": bat_rows,
                "br_batter_rating_debug": br_dbg,
            },
            "bowling": {
                "BPR_bowl_BoR": round(bor, 4),
                "form_bor_weighted_avg_mini_bor": None if form_bor is None else round(form_bor, 4),
                "numerator_sum_w_times_mini_bor": round(o_num, 6),
                "denominator_sum_w": round(o_den, 6),
                "CSA_bowl_before_clamp": None if csa_o_raw is None else round(csa_o_raw, 6),
                "CSA_bowl_after_clamp": profile.get("CSA_bowl"),
                "per_spell_newest_first": bowl_rows,
                "bor_debug": bor_dbg,
            },
        }
    else:
        bat = doc.get("batting") or {}
        bowl = doc.get("bowling") or {}
        inn_c = int(bat.get("innings") or 0)
        overs = float(bowl.get("overs") or 0)
        conf_bat = _log_sample_conf(float(inn_c)) if inn_c > 0 else 0.5
        conf_bowl = (
            _log_sample_conf(max(overs, float(int(bowl.get("innings") or 0))))
            if (overs > 0 or int(bowl.get("innings") or 0) > 0)
            else 0.5
        )
        bpr_bat_core, bpr_bat_scaled = _classic_bat_bpr_core(doc, float(star_rating))
        bpr_bowl_core, bpr_bowl_scaled = _classic_bowl_bpr_core(doc, float(star_rating))
        bat_r, form_core_b, bn, bd, _ = _bat_rows_classic(bat_cs, conf_bat)
        bowl_r, form_core_o, on, od, _ = _bowl_rows_classic(bowl_cs, conf_bowl)
        fcb = _weighted_form_bat_core(bat_cs, conf_bat)
        fco = _weighted_form_bowl_core(bowl_cs, conf_bowl)
        csa_b_raw = (
            (fcb - bpr_bat_core) / bpr_bat_core if bpr_bat_core > 1e-6 and fcb is not None else None
        )
        csa_o_raw = (
            (fco - bpr_bowl_core) / bpr_bowl_core if bpr_bowl_core > 1e-6 and fco is not None else None
        )
        out["classic_bpr_csa"] = {
            "batting": {
                "BPR_bat_core_unscaled": round(bpr_bat_core, 6),
                "BPR_bat_scaled_0_100": round(bpr_bat_scaled, 4),
                "sample_confidence_mult_conf_bat": round(conf_bat, 6),
                "form_bat_core_weighted_runs_sridx_times_conf": None if fcb is None else round(fcb, 6),
                "inner_avg_runs_sridx_before_conf": None if bd <= 0 else round(bn / bd, 6),
                "CSA_bat_before_clamp": None if csa_b_raw is None else round(csa_b_raw, 6),
                "CSA_bat_after_clamp": profile.get("CSA_bat"),
                "per_innings_newest_first": bat_r,
            },
            "bowling": {
                "BPR_bowl_core_unscaled": round(bpr_bowl_core, 6),
                "BPR_bowl_scaled_0_100": round(bpr_bowl_scaled, 4),
                "sample_confidence_mult_conf_bowl": round(conf_bowl, 6),
                "form_bowl_core": None if fco is None else round(fco, 6),
                "CSA_bowl_before_clamp": None if csa_o_raw is None else round(csa_o_raw, 6),
                "CSA_bowl_after_clamp": profile.get("CSA_bowl"),
                "per_spell_newest_first": bowl_r,
            },
        }

    return out
