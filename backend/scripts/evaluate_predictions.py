import math
import os
from collections import defaultdict
from datetime import datetime, timezone

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


def _logloss(p: float, y: int) -> float:
    p = min(1 - 1e-8, max(1e-8, p))
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def _ece(rows, bins=10):
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
        ece += w * abs(acc - conf)
        details.append(
            {
                "bin": i,
                "count": len(pts),
                "avg_confidence": round(conf, 4),
                "empirical_accuracy": round(acc, 4),
                "gap": round(abs(acc - conf), 4),
            }
        )
    return ece, details


def main():
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

    rows = []
    for doc in db.pre_match_predictions.find({}, {"_id": 0, "matchId": 1, "prediction.team1_win_prob": 1}):
        mid = doc.get("matchId")
        if mid not in schedule:
            continue
        winner = _winner_label(schedule[mid])
        if not winner:
            continue
        p = float((doc.get("prediction") or {}).get("team1_win_prob", 50)) / 100.0
        y = 1 if winner == "team1" else 0
        rows.append((p, y))

    if not rows:
        print("No completed matches with predictions found.")
        return

    n = len(rows)
    brier = sum((p - y) ** 2 for p, y in rows) / n
    logloss = sum(_logloss(p, y) for p, y in rows) / n
    ece, details = _ece(rows, bins=10)

    out = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": n,
        "metrics": {
            "brier": round(brier, 5),
            "logloss": round(logloss, 5),
            "ece_10bin": round(ece, 5),
        },
        "calibration_bins": details,
    }
    print(out)


if __name__ == "__main__":
    main()

