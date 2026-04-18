"""0–100 maps from the BR / BoR specification (piecewise linear)."""
from __future__ import annotations

from typing import List, Tuple

Seg = Tuple[float, float, float, float]  # x0, x1, y0, y1


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def ladder(x: float, below_y: float, segments: List[Seg], above_from: Tuple[float, float, float]) -> float:
    """
    `below_y` if x <= segments[0][0] (first x0).
    For each segment [x0,x1] linear y0→y1.
    If x >= above_from[0]: linear from (x_a, y_a) to cap at y_cap for large x.
    """
    if not segments:
        return below_y
    if x < segments[0][0]:
        return below_y
    for x0, x1, y0, y1 in segments:
        if x <= x1:
            if x1 <= x0:
                return y1
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    xa, ya, y_cap = above_from
    if x <= xa:
        return segments[-1][3]
    # extend ray — cap at y_cap
    span = 20.0  # generic tail
    t = _clamp((x - xa) / span, 0.0, 1.0)
    return ya + t * (y_cap - ya)


def batting_average_score(avg: float) -> float:
    return ladder(
        avg,
        0.0,
        [(10, 20, 10, 30), (20, 30, 30, 55), (30, 40, 55, 72), (40, 50, 72, 85)],
        (50, 85, 100),
    )


def batting_sr_score(sr: float) -> float:
    return ladder(
        sr,
        0.0,
        [
            (100, 115, 10, 25),
            (115, 125, 25, 45),
            (125, 135, 45, 62),
            (135, 145, 62, 78),
            (145, 160, 78, 90),
        ],
        (160, 90, 100),
    )


def pp_bat_sr_score(sr: float) -> float:
    return ladder(
        sr,
        0.0,
        [(110, 130, 20, 40), (130, 150, 40, 65), (150, 170, 65, 82)],
        (170, 82, 100),
    )


def death_bat_sr_score(sr: float) -> float:
    return ladder(
        sr,
        0.0,
        [(120, 140, 15, 35), (140, 160, 35, 58), (160, 180, 58, 78)],
        (180, 78, 100),
    )


def consistency_pct_score(pct: float) -> float:
    """pct = fraction of innings with 15+ (0–1)."""
    p = pct * 100.0
    return ladder(
        p,
        0.0,
        [(20, 35, 20, 40), (35, 50, 40, 62), (50, 65, 62, 80)],
        (65, 80, 100),
    )


def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x1 == x0:
        return y1
    t = (x - x0) / (x1 - x0)
    t = _clamp(t, 0.0, 1.0)
    return y0 + t * (y1 - y0)


def economy_score(eco: float) -> float:
    """Lower economy → higher score. Piecewise per spec (economy on X descending in quality left to right)."""
    e = float(eco)
    if e >= 12:
        return 0.0
    if e >= 10:
        return _lerp(e, 12, 10, 10, 25)
    if e >= 9:
        return _lerp(e, 10, 9, 25, 45)
    if e >= 8:
        return _lerp(e, 9, 8, 45, 65)
    if e >= 7:
        return _lerp(e, 8, 7, 65, 82)
    if e >= 6:
        return _lerp(e, 7, 6, 82, 90)
    return _clamp(90.0 + (6.0 - e) * 1.67, 90.0, 100.0)


def death_economy_score(eco: float) -> float:
    e = float(eco)
    if e >= 14:
        return 0.0
    if e >= 12:
        return _lerp(e, 14, 12, 10, 28)
    if e >= 10:
        return _lerp(e, 12, 10, 28, 50)
    if e >= 9:
        return _lerp(e, 10, 9, 50, 68)
    if e >= 8:
        return _lerp(e, 9, 8, 68, 83)
    if e >= 7:
        return _lerp(e, 8, 7, 83, 92)
    return _clamp(92.0 + (7.0 - e) * 2.0, 92.0, 100.0)


def pp_bowl_economy_score(eco: float) -> float:
    e = float(eco)
    if e >= 10:
        return 0.0
    if e >= 8:
        return _lerp(e, 10, 8, 15, 35)
    if e >= 7:
        return _lerp(e, 8, 7, 35, 60)
    if e >= 6:
        return _lerp(e, 7, 6, 60, 80)
    return _clamp(80.0 + (6.0 - e) * 5.0, 80.0, 100.0)


def wickets_per_match_score(wpm: float) -> float:
    return ladder(
        wpm,
        0.0,
        [(0.5, 0.8, 0, 15), (0.8, 1.0, 15, 35), (1.0, 1.3, 35, 55), (1.3, 1.6, 55, 72), (1.6, 2.0, 72, 87)],
        (2.0, 87, 100),
    )


def dot_ball_pct_score(pct: float) -> float:
    """pct0–100."""
    return ladder(
        pct,
        0.0,
        [(30, 38, 15, 35), (38, 45, 35, 58), (45, 52, 58, 75)],
        (52, 75, 100),
    )
