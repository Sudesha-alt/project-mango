"""
T20 phase tagging (powerplay / middle / death) from ball-by-ball data.

Powerplay: overs [0, 6)
Middle:     [6, 16)
Death:      [16, 20]

SportMonks ball shapes vary; parsing is defensive. Missing over → skip ball for phase stats.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

PHASE_PP = "pp"
PHASE_MID = "mid"
PHASE_DEATH = "death"


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def parse_ball_over_number(row: Dict[str, Any]) -> Optional[float]:
    """Return continuous over number (e.g. 12.3 → 12.5) or None."""
    for k in ("over", "current_over", "ov"):
        v = row.get(k)
        if v is None:
            continue
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and v.strip():
            s = v.strip()
            if "." in s:
                parts = s.split(".", 1)
                try:
                    o = int(parts[0])
                    tail = parts[1][:1] if parts[1] else "0"
                    b = int(tail) if tail.isdigit() else 0
                    b = min(max(b, 0), 5)
                    return float(o) + b / 6.0
                except ValueError:
                    continue
            try:
                return float(s)
            except ValueError:
                continue
    b = row.get("ball")
    if isinstance(b, str) and "." in b:
        return parse_ball_over_number({"over": b})
    return None


def phase_key_from_over(over: float) -> str:
    if over < 6.0:
        return PHASE_PP
    if over < 16.0:
        return PHASE_MID
    return PHASE_DEATH


def ball_runs_off_bat(row: Dict[str, Any]) -> int:
    for k in ("score", "batsman_run", "batsman_runs", "runs", "run"):
        v = row.get(k)
        if v is None:
            continue
        try:
            return max(0, int(v))
        except (TypeError, ValueError):
            continue
    return 0


def ball_total_runs(row: Dict[str, Any]) -> int:
    """Prefer total runs on delivery (including extras) for bowler economy."""
    for k in ("runs", "total_runs", "team_runs", "score"):
        v = row.get(k)
        if v is None:
            continue
        try:
            return max(0, int(v))
        except (TypeError, ValueError):
            continue
    return ball_runs_off_bat(row)


def empty_phase_bat_block() -> dict:
    return {"runs": 0, "balls": 0}


def empty_phase_bowl_block() -> dict:
    return {"runs_conceded": 0, "legal_balls": 0, "wickets": 0, "dots": 0}


def empty_phases_root() -> dict:
    return {
        "bat": {PHASE_PP: empty_phase_bat_block(), PHASE_MID: empty_phase_bat_block(), PHASE_DEATH: empty_phase_bat_block()},
        "bowl": {PHASE_PP: empty_phase_bowl_block(), PHASE_MID: empty_phase_bowl_block(), PHASE_DEATH: empty_phase_bowl_block()},
    }


def ensure_phases_on_player(ps: dict) -> dict:
    if "phases" not in ps or not isinstance(ps.get("phases"), dict):
        ps["phases"] = empty_phases_root()
        return ps["phases"]
    ph = ps["phases"]
    ph.setdefault("bat", {})
    ph.setdefault("bowl", {})
    for pk in (PHASE_PP, PHASE_MID, PHASE_DEATH):
        ph["bat"].setdefault(pk, empty_phase_bat_block())
        ph["bowl"].setdefault(pk, empty_phase_bowl_block())
    return ph


def normalize_balls_payload(raw: Any) -> List[dict]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = raw.get("data", [])
    if not isinstance(raw, list):
        return []
    return [b for b in raw if isinstance(b, dict)]


def accumulate_phases_from_balls(all_player_stats: dict, balls: List[dict]) -> int:
    """
    Mutates all_player_stats[*]['phases'] for batsman and bowler on each ball.
    Returns count of balls applied (skipped if over unknown).
    """
    used = 0
    for row in balls:
        over = parse_ball_over_number(row)
        if over is None or over < 0 or over > 24:  # sanity for T20
            continue
        pk = phase_key_from_over(over)
        bid = row.get("batsman_id") or row.get("batsman", {}).get("id") if isinstance(row.get("batsman"), dict) else None
        if bid is None:
            bid = row.get("player_id")
        bow_id = row.get("bowler_id") or row.get("bowler", {}).get("id") if isinstance(row.get("bowler"), dict) else None
        rob = ball_runs_off_bat(row)
        tot = ball_total_runs(row)
        is_w = bool(row.get("wicket")) or str(row.get("is_wicket", "")).lower() in ("1", "true", "yes")

        if bid is not None:
            try:
                pid = int(bid)
            except (TypeError, ValueError):
                pid = None
            if pid is not None:
                ps = all_player_stats.setdefault(pid, _stub_player(pid))
                ph = ensure_phases_on_player(ps)
                blk = ph["bat"][pk]
                blk["runs"] = int(blk.get("runs") or 0) + rob
                blk["balls"] = int(blk.get("balls") or 0) + 1

        if bow_id is not None:
            try:
                bpid = int(bow_id)
            except (TypeError, ValueError):
                bpid = None
            if bpid is not None:
                ps = all_player_stats.setdefault(bpid, _stub_player(bpid))
                ph = ensure_phases_on_player(ps)
                bb = ph["bowl"][pk]
                bb["runs_conceded"] = int(bb.get("runs_conceded") or 0) + tot
                bb["legal_balls"] = int(bb.get("legal_balls") or 0) + 1
                if is_w:
                    bb["wickets"] = int(bb.get("wickets") or 0) + 1
                if not is_w and rob == 0:
                    bb["dots"] = int(bb.get("dots") or 0) + 1
        used += 1
    return used


def _stub_player(pid: int) -> dict:
    """Minimal shell when phase-only events appear before card row."""
    return {
        "player_id": pid,
        "name": "",
        "batting": {"runs": 0, "balls": 0, "innings": 0, "fours": 0, "sixes": 0, "fifties": 0, "hundreds": 0},
        "bowling": {"overs": 0, "wickets": 0, "runs_conceded": 0, "innings": 0, "maidens": 0, "three_fers": 0},
        "matches": 0,
        "seasons": [],
        "by_season": {},
        "_bat_entries": [],
        "_bowl_entries": [],
    }


def finalize_phase_derived(phases: dict) -> None:
    """Add SR / economy summaries on each phase block for API consumers."""
    if not isinstance(phases, dict):
        return
    for pk, blk in (phases.get("bat") or {}).items():
        if not isinstance(blk, dict):
            continue
        r, b = int(blk.get("runs") or 0), int(blk.get("balls") or 0)
        blk["sr"] = round(r / max(b, 1) * 100.0, 2) if b else 0.0
    for pk, blk in (phases.get("bowl") or {}).items():
        if not isinstance(blk, dict):
            continue
        rc = int(blk.get("runs_conceded") or 0)
        lb = int(blk.get("legal_balls") or 0)
        overs = lb / 6.0
        blk["economy"] = round(rc / max(overs, 0.01), 2) if lb else 0.0


def phase_bat_index(block: dict) -> float:
    r = int(block.get("runs") or 0)
    b = int(block.get("balls") or 0)
    if b < 8:
        return 50.0
    sr = r / max(b, 1) * 100.0
    sr_part = _clamp(sr / 130.0, 0.4, 1.5) * 62.0
    dens = _clamp(r / max(b / 6.0, 0.01), 0, 36) / 36.0 * 38.0
    return _clamp(sr_part * 0.65 + dens * 0.35, 12.0, 96.0)


def phase_bowl_index(block: dict) -> float:
    rc = int(block.get("runs_conceded") or 0)
    lb = int(block.get("legal_balls") or 0)
    wk = int(block.get("wickets") or 0)
    if lb < 12:
        return 50.0
    overs = lb / 6.0
    eco = rc / max(overs, 0.01)
    eco_part = _clamp((11.5 - eco) / 5.5 * 100.0, 0, 100)
    wpi = wk / max(overs, 0.01)
    wk_part = _clamp(wpi / 0.55 * 100.0, 0, 100)
    return _clamp(0.55 * eco_part + 0.45 * wk_part, 12.0, 96.0)


def team_phase_quality(rows: List[dict]) -> Tuple[Optional[dict], bool]:
    """
    Build powerplay / death composite indices from XI rows' phase_profile.
    Returns (payload, has_real_data).
    """
    if not rows:
        return None, False

    def sorted_rows():
        return sorted(rows, key=lambda x: int(x.get("batting_position", 99) or 99))

    bat_phases: List[dict] = []
    for r in sorted_rows():
        if str(r.get("player_role", "")).upper() not in ("BAT", "AR"):
            continue
        prof = r.get("phase_profile") or {}
        if isinstance(prof, dict) and prof.get("bat"):
            bat_phases.append(prof["bat"])
        if len(bat_phases) >= 5:
            break

    bowl_phases: List[dict] = []
    for r in sorted(rows, key=lambda x: int(x.get("bowling_order", 99) or 99)):
        if int(r.get("bowling_order") or 0) < 1:
            continue
        prof = r.get("phase_profile") or {}
        if isinstance(prof, dict) and prof.get("bowl"):
            bowl_phases.append(prof["bowl"])
        if len(bowl_phases) >= 5:
            break

    if not bat_phases and not bowl_phases:
        return None, False

    pp_bats = [phase_bat_index(x.get(PHASE_PP) or {}) for x in bat_phases[:3]]
    death_bats = [phase_bat_index(x.get(PHASE_DEATH) or {}) for x in bat_phases[:3]]
    pp_bowls = [phase_bowl_index(x.get(PHASE_PP) or {}) for x in bowl_phases[:3]]
    death_bowls = [phase_bowl_index(x.get(PHASE_DEATH) or {}) for x in bowl_phases[:3]]

    def mean(vals: List[float]) -> float:
        return float(sum(vals) / len(vals)) if vals else 50.0

    pp_balls = sum(int((x.get(PHASE_PP) or {}).get("balls") or 0) for x in bat_phases[:3])
    d_balls = sum(int((x.get(PHASE_DEATH) or {}).get("balls") or 0) for x in bat_phases[:3])
    pp_legal = sum(int((x.get(PHASE_PP) or {}).get("legal_balls") or 0) for x in bowl_phases[:3])

    powerplay_index = round(0.55 * mean(pp_bats) + 0.45 * mean(pp_bowls), 3)
    death_index = round(0.52 * mean(death_bats) + 0.48 * mean(death_bowls), 3)

    has_real = (pp_balls + d_balls) >= 24 or pp_legal >= 36

    return {
        "powerplay_index": powerplay_index,
        "death_index": death_index,
        "pp_bat_balls_sample": pp_balls,
        "death_bat_balls_sample": d_balls,
        "pp_bowl_balls_sample": pp_legal,
        "phase_samples_ok": has_real,
    }, has_real
