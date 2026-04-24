"""
Build structured BPR/CSA player cards for Claude Opus 7-layer pre-match (full squads, not XI-only).
"""
from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set

from services.ai_service import normalize_primary_cricket_role
from services.player_impact_bpr_csa import IMPACT_FORMULAS, compute_player_impact_profile
from services.player_impact_br_bor import CURRENT_IPL_YEAR
from services.pre_match_predictor import resolve_star_player_rating

logger = logging.getLogger(__name__)


def _mongo_doc_to_perf_row(doc: dict) -> dict:
    """Mirror server `_mongo_doc_to_perf_row` for impact scoring (no server import)."""
    return {
        "name": doc.get("name") or "",
        "player_id": doc.get("player_id"),
        "matches": int(doc.get("matches") or 0),
        "batting": dict(doc.get("batting") or {}),
        "bowling": dict(doc.get("bowling") or {}),
        "seasons": list(doc.get("seasons") or []),
        "by_season": dict(doc.get("by_season") or {}),
        "last5_bat_innings": list(doc.get("last5_bat_innings") or []),
        "last5_bowl_spells": list(doc.get("last5_bowl_spells") or []),
        "recent_bat_innings": list(doc.get("recent_bat_innings") or []),
        "recent_bowl_spells": list(doc.get("recent_bowl_spells") or []),
        "csa_season_bat_innings": list(doc.get("csa_season_bat_innings") or []),
        "csa_season_bowl_spells": list(doc.get("csa_season_bowl_spells") or []),
        "phases": dict(doc.get("phases") or {}),
        "api_profile": doc.get("api_profile"),
    }


def _infer_role_code_for_directory(perf_row: dict) -> str:
    bat = perf_row.get("batting") or {}
    bowl = perf_row.get("bowling") or {}
    bi = int(bat.get("innings") or 0)
    bwi = int(bowl.get("innings") or 0)
    ovs = float(bowl.get("overs") or 0)
    if bi >= 2 and bwi >= 2 and ovs >= 3.0:
        return "AR"
    if bwi > bi and ovs >= 4.0:
        return "BOWL"
    if bi > bwi or bwi == 0:
        return "BAT"
    return "BOWL"


def _role_code_from_squad(primary_role: Optional[str], perf_row: dict) -> str:
    if primary_role:
        pr = normalize_primary_cricket_role(str(primary_role).strip())
        if pr == "Bowler":
            return "BOWL"
        if pr == "All-rounder":
            return "AR"
        return "BAT"
    return _infer_role_code_for_directory(perf_row)


def _normalize_name_key(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _fmt_csa_line(prof: dict, role_code: str) -> str:
    cb = prof.get("CSA_bat")
    co = prof.get("CSA_bowl")
    ce_b = prof.get("CSA_effective_bat")
    ce_o = prof.get("CSA_effective_bowl")
    parts: List[str] = []

    def one(label: str, v: Optional[float], eff: Optional[float]) -> None:
        if v is None and eff is None:
            return
        if v is not None:
            pct = float(v) * 100.0
            if v > 0.02:
                adj = "better than base BPR this IPL season (output CSA)"
            elif v < -0.02:
                adj = "below base BPR this IPL season (output CSA)"
            else:
                adj = "in line with base BPR (output CSA)"
            seg = f"{label} output {pct:+.1f}% ({adj})"
            if eff is not None and abs(float(eff) - float(v)) > 0.004:
                seg += f"; effective {float(eff) * 100.0:+.1f}% (60% output + 40% input CSA + category blend)"
            parts.append(seg)
        elif eff is not None:
            parts.append(f"{label} effective {float(eff) * 100.0:+.1f}% (two-layer)")

    if role_code == "BOWL":
        one("bowl", co, ce_o)
    elif role_code == "BAT":
        one("bat", cb, ce_b)
    else:
        one("bat", cb, ce_b)
        one("bowl", co, ce_o)
    if not parts:
        return "— (no current-season CSA — sync player stats or insufficient IPL 2026 rows)"
    return " | ".join(parts)


def _fmt_csa_category_flags(prof: dict, role_code: str) -> str:
    """Compact Category 1–4 + mean reversion for Opus."""
    tl = prof.get("csa_two_layer") or {}
    keys = []
    if role_code == "BAT":
        keys = ["bat"]
    elif role_code == "BOWL":
        keys = ["bowl"]
    else:
        keys = ["bat", "bowl"]
    bits: List[str] = []
    for k in keys:
        m = tl.get(k)
        if not isinstance(m, dict):
            continue
        cat = m.get("category")
        lab = m.get("category_label")
        if cat is None:
            continue
        fl = m.get("floor_weight")
        ce = m.get("ceiling_weight")
        seg = f"{k.upper()} CAT{cat} ({lab}) floor/cap {fl}/{ce}"
        if m.get("mean_reversion_candidate"):
            seg += " MEAN_REVERSION_CANDIDATE"
        bits.append(seg)
    return " · ".join(bits) if bits else ""


def _fmt_sample_size(prof: dict, role_code: str) -> str:
    bat_n = prof.get("batting_innings_sample")
    bowl_o = prof.get("bowling_overs_sample")
    bconf = prof.get("batting_confidence") or "—"
    oconf = prof.get("bowling_confidence") or "—"
    if role_code == "BOWL":
        return f"{oconf} ({float(bowl_o or 0):.0f} overs in DB)"
    if role_code == "BAT":
        return f"{bconf} ({int(bat_n or 0)} innings in DB)"
    return f"bat {bconf} ({int(bat_n or 0)} inn) / bowl {oconf} ({float(bowl_o or 0):.0f} ov)"


def _primary_bpr_number(prof: dict, role_code: str) -> float:
    bb = float(prof.get("BPR_bat") or 0.0)
    bo = float(prof.get("BPR_bowl") or 0.0)
    if role_code == "BOWL":
        return round(bo, 1)
    if role_code == "BAT":
        return round(bb, 1)
    return round((bb + bo) / 2.0, 1)


def _pct(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    try:
        return round(float(v) * 100.0, 2)
    except (TypeError, ValueError):
        return None


def _primary_csa_numbers(prof: dict, role_code: str) -> Dict[str, Optional[float]]:
    out_bat = _pct(prof.get("CSA_bat"))
    out_bowl = _pct(prof.get("CSA_bowl"))
    eff_bat = _pct(prof.get("CSA_effective_bat"))
    eff_bowl = _pct(prof.get("CSA_effective_bowl"))
    if role_code == "BAT":
        return {
            "primary_output_pct": out_bat,
            "primary_effective_pct": eff_bat,
            "bat_output_pct": out_bat,
            "bat_effective_pct": eff_bat,
            "bowl_output_pct": out_bowl,
            "bowl_effective_pct": eff_bowl,
        }
    if role_code == "BOWL":
        return {
            "primary_output_pct": out_bowl,
            "primary_effective_pct": eff_bowl,
            "bat_output_pct": out_bat,
            "bat_effective_pct": eff_bat,
            "bowl_output_pct": out_bowl,
            "bowl_effective_pct": eff_bowl,
        }
    # AR: primary is blended effective signal when available.
    pe = None
    vals = [x for x in (eff_bat, eff_bowl) if x is not None]
    if vals:
        pe = round(sum(vals) / len(vals), 2)
    po = None
    vals2 = [x for x in (out_bat, out_bowl) if x is not None]
    if vals2:
        po = round(sum(vals2) / len(vals2), 2)
    return {
        "primary_output_pct": po,
        "primary_effective_pct": pe,
        "bat_output_pct": out_bat,
        "bat_effective_pct": eff_bat,
        "bowl_output_pct": out_bowl,
        "bowl_effective_pct": eff_bowl,
    }


def _manual_impact_name_matches(selected: str, card_name: str) -> bool:
    """Loose match for user bench pick vs roster display name (same intent as server XI matching)."""
    sa = _normalize_name_key(selected)
    sb = _normalize_name_key(card_name)
    if not sa or not sb:
        return False
    if sa == sb or sa in sb or sb in sa:
        return True
    return SequenceMatcher(None, sa, sb).ratio() >= 0.88


def _status_line(
    name_key: str,
    in_xi: bool,
    override_by_name: Dict[str, dict],
    *,
    manual_selected_name: Optional[str] = None,
    card_display_name: str = "",
) -> str:
    o = override_by_name.get(name_key)
    if o:
        reason = (o.get("reason") or "availability uncertain").strip()
        return f"ABSENT / DOUBTFUL — {reason}"
    manual_match = bool(
        manual_selected_name
        and card_display_name
        and _manual_impact_name_matches(manual_selected_name, card_display_name)
    )
    if manual_match and in_xi:
        return (
            "MANUAL IPL IMPACT — user swapped into Expected XI for this match "
            "(replaces a listed starter; BPR/CSA below)"
        )
    if manual_match:
        return (
            "MANUAL IPL IMPACT — user bench pick for this match "
            "(BPR/CSA below; counted in pre-match depth, not a listed XI starter)"
        )
    if in_xi:
        return "AVAILABLE — expected XI"
    return "SQUAD — not in expected XI (depth / bench)"


async def build_opus_player_cards_for_claude(
    db,
    *,
    team1: str,
    team2: str,
    team1_short: str,
    team2_short: str,
    match_id: str,
    match_squads: dict,
    playing_xi_squads: dict,
    formula: str = "br_bor_v1",
    manual_impact_by_team: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    One JSON-serializable object per squad player (both teams), same keys as Opus contract.
    """
    f = (formula or "br_bor_v1").strip()
    if f not in IMPACT_FORMULAS:
        f = "br_bor_v1"

    override_by_name: Dict[str, dict] = {}
    try:
        async for odoc in db.injury_overrides.find({"matchId": match_id}, {"_id": 0}):
            pl = (odoc.get("player") or "").strip()
            if pl:
                override_by_name[_normalize_name_key(pl)] = odoc
    except Exception as e:
        logger.warning(f"injury_overrides read for opus cards: {e}")

    def xi_name_set(sched_team: str) -> Set[str]:
        out: Set[str] = set()
        for p in playing_xi_squads.get(sched_team) or []:
            if isinstance(p, dict):
                nm = (p.get("name") or "").strip()
                if nm:
                    out.add(_normalize_name_key(nm))
        return out

    xi_t1 = xi_name_set(team1)
    xi_t2 = xi_name_set(team2)

    pids: List[int] = []
    for sched in (team1, team2):
        for p in match_squads.get(sched) or []:
            if not isinstance(p, dict):
                continue
            for key in ("id", "player_id", "sm_player_id", "sportmonks_id"):
                raw = p.get(key)
                if raw is None:
                    continue
                try:
                    pids.append(int(raw))
                except (TypeError, ValueError):
                    continue
    pids = list({x for x in pids if x})

    by_pid: Dict[int, dict] = {}
    if pids:
        try:
            async for doc in db.player_performance.find({"player_id": {"$in": pids}}, {"_id": 0}):
                pk = doc.get("player_id")
                try:
                    by_pid[int(pk)] = doc
                except (TypeError, ValueError):
                    pass
        except Exception as e:
            logger.warning(f"player_performance batch for opus: {e}")

    async def find_doc_for_row(p: dict) -> Optional[dict]:
        for key in ("id", "player_id", "sm_player_id", "sportmonks_id"):
            raw = p.get(key)
            if raw is None:
                continue
            try:
                pid = int(raw)
                if pid in by_pid:
                    return by_pid[pid]
            except (TypeError, ValueError):
                continue
        nm = (p.get("name") or "").strip()
        if not nm:
            return None
        try:
            return await db.player_performance.find_one(
                {"name": {"$regex": f"^{re.escape(nm)}$", "$options": "i"}},
                {"_id": 0},
            )
        except Exception:
            return None

    async def cards_for_side(sched_team: str, xi_names: Set[str]) -> List[dict]:
        manual_sel = (
            (manual_impact_by_team or {}).get(sched_team) or ""
        ).strip() or None
        rows_out: List[dict] = []
        seen: Set[str] = set()
        for p in match_squads.get(sched_team) or []:
            if not isinstance(p, dict):
                continue
            nm = (p.get("name") or "").strip()
            if not nm:
                continue
            nk = _normalize_name_key(nm)
            if nk in seen:
                continue
            seen.add(nk)

            doc = await find_doc_for_row(p)
            perf = _mongo_doc_to_perf_row(doc) if doc else {}
            star = float(resolve_star_player_rating(nm))
            primary = (p.get("role") or p.get("primary_role") or "").strip() or None
            role_code = _role_code_from_squad(primary, perf)

            if doc:
                prof = compute_player_impact_profile(
                    perf,
                    role_code,
                    star,
                    formula=f,
                )
                bpr = _primary_bpr_number(prof, role_code)
                csa = _fmt_csa_line(prof, role_code)
                csa_flags = _fmt_csa_category_flags(prof, role_code)
                sample = _fmt_sample_size(prof, role_code)
                csa_nums = _primary_csa_numbers(prof, role_code)
                csa_scope = "current_ipl_season_all_rows"
                est = prof.get("impact_estimates") or []
                if "csa_last5_legacy_no_season_year" in est:
                    csa_scope = "legacy_last5_proxy_no_season_year"
                elif "csa_no_rows_for_ipl_year" in est:
                    csa_scope = "no_current_ipl_year_rows"
            else:
                bpr = round(star, 1)
                csa = "— (no Mongo player_performance row — run Sync player stats)"
                csa_flags = None
                sample = "UNKNOWN (no DB row)"
                csa_nums = {
                    "primary_output_pct": None,
                    "primary_effective_pct": None,
                    "bat_output_pct": None,
                    "bat_effective_pct": None,
                    "bowl_output_pct": None,
                    "bowl_effective_pct": None,
                }
                csa_scope = "no_player_performance_row"

            in_xi = nk in xi_names
            st = _status_line(
                nk,
                in_xi,
                override_by_name,
                manual_selected_name=manual_sel,
                card_display_name=nm,
            )

            rows_out.append(
                {
                    "player": nm,
                    "BPR": bpr,
                    "BPR_primary": bpr,
                    "BPR_bat": round(float(prof.get("BPR_bat") or bpr), 2) if doc else bpr,
                    "BPR_bowl": round(float(prof.get("BPR_bowl") or bpr), 2) if doc else bpr,
                    "CSA": csa,
                    "CSA_primary_output_pct": csa_nums["primary_output_pct"],
                    "CSA_primary_effective_pct": csa_nums["primary_effective_pct"],
                    "CSA_bat_output_pct": csa_nums["bat_output_pct"],
                    "CSA_bat_effective_pct": csa_nums["bat_effective_pct"],
                    "CSA_bowl_output_pct": csa_nums["bowl_output_pct"],
                    "CSA_bowl_effective_pct": csa_nums["bowl_effective_pct"],
                    "csa_scope": csa_scope,
                    "csa_category_flags": csa_flags or None,
                    "csa_two_layer": prof.get("csa_two_layer") if doc else None,
                    "current_season_sample": {
                        "bat_innings": len(_csa_entries_ipl_year_only(_csa_bat_entry_source(doc), CURRENT_IPL_YEAR)[0]) if doc else 0,
                        "bowl_spells": len(_csa_entries_ipl_year_only(_csa_bowl_entry_source(doc), CURRENT_IPL_YEAR)[0]) if doc else 0,
                    },
                    "sample_size_confidence": sample,
                    "status": st,
                    "replacement": None,
                    "replacement_BPR": None,
                    "replacement_CSA": None,
                }
            )
        return rows_out

    team1_cards = await cards_for_side(team1, xi_t1)
    team2_cards = await cards_for_side(team2, xi_t2)

    return {
        "formula": f,
        "team1_short": team1_short,
        "team2_short": team2_short,
        "team1_players": team1_cards,
        "team2_players": team2_cards,
    }


def format_opus_player_cards_for_prompt(cards: Dict[str, Any]) -> str:
    """Pretty JSON block for the Claude user prompt."""
    return json.dumps(cards, indent=2, ensure_ascii=False)
