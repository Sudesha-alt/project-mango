import argparse
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient


def _winner_label(schedule_doc: dict) -> str:
    w = (schedule_doc.get("winner") or "").lower().strip()
    t1 = (schedule_doc.get("team1") or "").lower().strip()
    t2 = (schedule_doc.get("team2") or "").lower().strip()
    if not w:
        return ""
    if t1 and (t1 in w or w in t1):
        return "team1"
    if t2 and (t2 in w or w in t2):
        return "team2"
    return ""


def _clamp_prob(p: float) -> float:
    return min(1.0 - 1e-8, max(1e-8, float(p)))


def _logloss(p: float, y: int) -> float:
    p = _clamp_prob(p)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def _ece(rows: List[Tuple[float, int]], bins: int = 10) -> Tuple[float, List[dict]]:
    bucket = defaultdict(list)
    for p, y in rows:
        idx = min(bins - 1, int(p * bins))
        bucket[idx].append((p, y))
    total = len(rows) or 1
    ece = 0.0
    details = []
    for i in range(bins):
        pts = bucket.get(i, [])
        if not pts:
            continue
        conf = sum(p for p, _ in pts) / len(pts)
        acc = sum(y for _, y in pts) / len(pts)
        w = len(pts) / total
        gap = abs(acc - conf)
        ece += w * gap
        details.append(
            {
                "bin": i,
                "count": len(pts),
                "avg_confidence": round(conf, 4),
                "empirical_accuracy": round(acc, 4),
                "gap": round(gap, 4),
            }
        )
    return ece, details


def _metrics(rows: List[Tuple[float, int]]) -> Optional[Dict]:
    if not rows:
        return None
    n = len(rows)
    brier = sum((p - y) ** 2 for p, y in rows) / n
    logloss = sum(_logloss(p, y) for p, y in rows) / n
    ece, bins = _ece(rows, bins=10)
    return {
        "sample_size": n,
        "brier": round(brier, 6),
        "logloss": round(logloss, 6),
        "ece_10bin": round(ece, 6),
        "calibration_bins": bins,
    }


def _get_track_prob(
    track: str,
    pre_doc: Optional[dict],
    live_doc: Optional[dict],
) -> Optional[float]:
    if track == "algo_only":
        p = ((pre_doc or {}).get("prediction") or {}).get("team1_win_prob")
    elif track == "claude_only":
        cp = (live_doc or {}).get("claudePrediction") or (live_doc or {}).get("claude_prediction") or {}
        p = cp.get("team1_win_pct")
    elif track == "hybrid":
        hp = (live_doc or {}).get("combinedPrediction") or (live_doc or {}).get("combined_prediction") or {}
        p = hp.get("team1_pct")
    else:
        return None

    if p is None:
        return None
    try:
        return _clamp_prob(float(p) / 100.0)
    except (TypeError, ValueError):
        return None


def _gate_verdict(
    metrics: Dict[str, Optional[Dict]],
    min_samples: int,
    ece_threshold: float,
) -> Dict:
    reasons = []
    passed = True

    algo = metrics.get("algo_only")
    claude = metrics.get("claude_only")
    hybrid = metrics.get("hybrid")

    if not hybrid or hybrid["sample_size"] < min_samples:
        passed = False
        reasons.append(
            f"hybrid sample size too low ({0 if not hybrid else hybrid['sample_size']}, min {min_samples})"
        )

    if algo and hybrid:
        if hybrid["brier"] > algo["brier"]:
            passed = False
            reasons.append(f"hybrid brier {hybrid['brier']} > algo {algo['brier']}")
        if hybrid["logloss"] > algo["logloss"]:
            passed = False
            reasons.append(f"hybrid logloss {hybrid['logloss']} > algo {algo['logloss']}")

    if claude and hybrid:
        if hybrid["brier"] > claude["brier"]:
            passed = False
            reasons.append(f"hybrid brier {hybrid['brier']} > claude {claude['brier']}")
        if hybrid["logloss"] > claude["logloss"]:
            passed = False
            reasons.append(f"hybrid logloss {hybrid['logloss']} > claude {claude['logloss']}")

    if hybrid and hybrid["ece_10bin"] > ece_threshold:
        passed = False
        reasons.append(
            f"hybrid ece {hybrid['ece_10bin']} exceeds threshold {ece_threshold}"
        )

    return {"passed": passed, "reasons": reasons}


def main():
    parser = argparse.ArgumentParser(description="Evaluate algo/claude/hybrid prediction tracks.")
    parser.add_argument("--min-samples", type=int, default=10)
    parser.add_argument("--ece-threshold", type=float, default=0.08)
    parser.add_argument("--save", action="store_true", help="Persist report to model_eval_metrics collection.")
    args = parser.parse_args()

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    client = MongoClient(os.getenv("MONGO_URL"))
    db = client[os.getenv("DB_NAME")]

    schedule = {
        d["matchId"]: d
        for d in db.ipl_schedule.find(
            {"status": {"$in": ["completed", "Completed"]}},
            {"_id": 0, "matchId": 1, "winner": 1, "team1": 1, "team2": 1},
        )
    }
    pre_by_mid = {
        d["matchId"]: d
        for d in db.pre_match_predictions.find({}, {"_id": 0})
        if d.get("matchId")
    }
    live_by_mid = {
        d["matchId"]: d
        for d in db.live_snapshots.find({}, {"_id": 0})
        if d.get("matchId")
    }

    rows_by_track: Dict[str, List[Tuple[float, int]]] = {
        "algo_only": [],
        "claude_only": [],
        "hybrid": [],
    }

    for mid, sched_doc in schedule.items():
        ylab = _winner_label(sched_doc)
        if not ylab:
            continue
        y = 1 if ylab == "team1" else 0
        pre_doc = pre_by_mid.get(mid)
        live_doc = live_by_mid.get(mid)
        for track in rows_by_track:
            p = _get_track_prob(track, pre_doc, live_doc)
            if p is not None:
                rows_by_track[track].append((p, y))

    metrics = {k: _metrics(v) for k, v in rows_by_track.items()}
    gate = _gate_verdict(metrics, args.min_samples, args.ece_threshold)

    report = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "tracks": metrics,
        "gate": {
            **gate,
            "min_samples": args.min_samples,
            "ece_threshold": args.ece_threshold,
        },
    }

    if args.save:
        db.model_eval_metrics.insert_one(report)

    print(json.dumps(report, indent=2))
    if not gate["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

