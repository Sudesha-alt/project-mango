"""
Post-match learning: compare stored pre-match predictions + Claude analysis to the actual winner,
persist outcomes, and create **pending** calibration proposals (weight + prompt addendum).

Important: cricket outcomes are high-variance. This improves long-run calibration — not “100% accuracy”.
No automatic edits to Python source; approved changes land in ``prematch_calibration.json`` only.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from bson.errors import InvalidId

from services.pre_match_predictor import (
    FIVE_FACTOR_PREDICTION_KEYS,
    WEIGHTS as _BASE_WEIGHTS,
    sanitize_prediction_to_five_factors,
)
from services.prematch_calibration import get_effective_weights
from services import prematch_calibration

logger = logging.getLogger(__name__)

NUDGE = 0.012
PROB_MARGIN = 5.0  # minimum edge (%) to treat as a “wrong call” worth learning from


def _winner_side(schedule: Dict[str, Any]) -> Optional[str]:
    w = (schedule.get("winner") or "").strip()
    t1 = (schedule.get("team1") or "").strip()
    t2 = (schedule.get("team2") or "").strip()
    if not w:
        return None
    wl, t1l, t2l = w.lower(), t1.lower(), t2.lower()
    if t1l and (t1l in wl or wl in t1l):
        return "team1"
    if t2l and (t2l in wl or wl in t2l):
        return "team2"
    return None


def _claude_win_pcts(analysis: Any) -> Tuple[Optional[float], Optional[float]]:
    if not isinstance(analysis, dict):
        return None, None
    try:
        t1 = analysis.get("team1_win_pct")
        t2 = analysis.get("team2_win_pct")
        if t1 is None or t2 is None:
            return None, None
        return float(t1), float(t2)
    except (TypeError, ValueError):
        return None, None


def _factor_audit(
    factors: Dict[str, Any], actual_t1_won: bool
) -> List[Dict[str, Any]]:
    rows = []
    for key in FIVE_FACTOR_PREDICTION_KEYS:
        block = factors.get(key) if isinstance(factors, dict) else None
        if not isinstance(block, dict):
            continue
        try:
            raw = float(block.get("raw_logit", 0) or 0)
        except (TypeError, ValueError):
            raw = 0.0
        favours_t1 = raw > 0.01
        favours_t2 = raw < -0.01
        neutral = not favours_t1 and not favours_t2
        if neutral:
            aligned = True
        elif actual_t1_won:
            aligned = favours_t1
        else:
            aligned = favours_t2
        rows.append(
            {
                "factor": key,
                "raw_logit": round(raw, 4),
                "aligned_with_result": aligned,
            }
        )
    return rows


def _propose_weights(
    audit: List[Dict[str, Any]], current: Dict[str, float]
) -> Dict[str, float]:
    wrong = [r["factor"] for r in audit if not r["aligned_with_result"]]
    if not wrong:
        return dict(current)
    new_w = {k: float(current[k]) for k in current}
    for k in wrong:
        new_w[k] = max(0.05, new_w[k] - NUDGE)
    good = [k for k in current if k not in wrong]
    pool = NUDGE * len(wrong)
    if good:
        add = pool / len(good)
        for k in good:
            new_w[k] = min(0.55, new_w[k] + add)
    s = sum(new_w.values())
    if s <= 1e-9:
        return dict(current)
    return {k: round(new_w[k] / s, 6) for k in new_w}


def _addendum_from_audit(team1: str, team2: str, audit: List[Dict[str, Any]]) -> str:
    bad = [r["factor"] for r in audit if not r["aligned_with_result"]]
    if not bad:
        return ""
    return (
        f"Post-match calibration note (empirical): In a recent finished IPL fixture, the pre-match model’s "
        f"logit direction for these factors disagreed with the match result: {', '.join(bad)}. "
        f"Re-check squad strength vs venue/weather interaction and H2H damping when those factors conflict "
        f"with clear BPR/CSA edges for {team1} or {team2}. Prefer recency and confirmed XI over stale H2H."
    )


async def record_match_outcome(db, match_id: str) -> None:
    """Idempotent: writes ``match_prediction_outcomes`` and maybe ``learning_proposals``."""
    try:
        sched = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
        if not sched:
            return
        status = (sched.get("status") or "").lower()
        if "completed" not in status and sched.get("winner") in (None, ""):
            return
        actual = _winner_side(sched)
        if not actual:
            logger.info("prediction_learning: no resolvable winner for %s", match_id)
            return

        exists = await db.match_prediction_outcomes.find_one({"matchId": match_id}, {"_id": 1})
        if exists:
            return

        pre = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0})
        claude_doc = await db.claude_analysis.find_one({"matchId": match_id}, {"_id": 0})
        pred = sanitize_prediction_to_five_factors((pre or {}).get("prediction") or {})
        if not pred:
            await db.match_prediction_outcomes.insert_one(
                {
                    "matchId": match_id,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "actual_winner_side": actual,
                    "algo_available": False,
                    "note": "No pre-match prediction snapshot in DB",
                }
            )
            return

        try:
            t1p = float(pred.get("team1_win_prob", 50))
        except (TypeError, ValueError):
            t1p = 50.0
        predicted_fav = "team1" if t1p >= 50 else "team2"
        actual_t1_won = actual == "team1"
        algo_correct = predicted_fav == actual
        factors = pred.get("factors") or {}
        audit = _factor_audit(factors, actual_t1_won)
        c1, c2 = _claude_win_pcts((claude_doc or {}).get("analysis"))

        outcome = {
            "matchId": match_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "team1": sched.get("team1"),
            "team2": sched.get("team2"),
            "actual_winner_side": actual,
            "algo_team1_win_prob": t1p,
            "algo_predicted_favourite": predicted_fav,
            "algo_correct": algo_correct,
            "claude_team1_win_pct": c1,
            "claude_team2_win_pct": c2,
            "factor_audit": audit,
            "computed_at_pre_match": (pre or {}).get("computed_at"),
        }
        await db.match_prediction_outcomes.insert_one(outcome)

        edge_wrong = (not algo_correct) and abs(t1p - 50.0) >= PROB_MARGIN
        if not edge_wrong:
            return

        if await db.learning_proposals.find_one(
            {
                "source_match_id": match_id,
                "$or": [{"source_track": "pre_match"}, {"source_track": {"$exists": False}}],
            }
        ):
            return

        eff = get_effective_weights(_BASE_WEIGHTS)
        proposed = _propose_weights(audit, eff)
        team1 = sched.get("team1") or "Team 1"
        team2 = sched.get("team2") or "Team 2"
        addendum = _addendum_from_audit(team1, team2, audit)
        summary = (
            f"Pre-match algo favoured {predicted_fav} ({t1p:.1f}% for team1) but {actual} won. "
            f"Factors misaligned with result: {', '.join(r['factor'] for r in audit if not r['aligned_with_result']) or 'none flagged'}."
        )
        proposal = {
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_match_id": match_id,
            "source_track": "pre_match",
            "summary": summary,
            "learning_notes": [
                "Weights are nudged slightly away from factors whose logit direction disagreed with the result.",
                "Prompt addendum is descriptive guidance only; review before approving.",
                "Many losses are variance, not bad weights — use several matches before trusting large shifts.",
            ],
            "proposed_weight_overrides": proposed,
            "proposed_claude_addendum": addendum,
            "baseline_weights_used": eff,
            "outcome_ref": {k: outcome[k] for k in ("algo_team1_win_prob", "actual_winner_side", "algo_correct") if k in outcome},
        }
        await db.learning_proposals.insert_one(proposal)
        logger.info("prediction_learning: created proposal for match %s", match_id)
    except Exception as e:
        logger.warning("prediction_learning failed for %s: %s", match_id, e)


async def list_pending_proposals(db) -> List[Dict[str, Any]]:
    out = []
    async for doc in db.learning_proposals.find({"status": "pending"}).sort("created_at", -1).limit(50):
        d = dict(doc)
        d["id"] = str(d.pop("_id"))
        out.append(d)
    return out


async def list_recent_outcomes(db, limit: int = 30) -> List[Dict[str, Any]]:
    out = []
    async for doc in db.match_prediction_outcomes.find({}).sort("recorded_at", -1).limit(limit):
        d = dict(doc)
        d.pop("_id", None)
        out.append(d)
    return out


async def approve_proposal(db, proposal_id: str) -> Dict[str, Any]:
    try:
        oid = ObjectId(proposal_id)
    except InvalidId:
        return {"error": "invalid_proposal_id"}
    doc = await db.learning_proposals.find_one({"_id": oid})
    if not doc:
        return {"error": "not_found"}
    if doc.get("status") != "pending":
        return {"error": "not_pending", "status": doc.get("status")}

    weights = doc.get("proposed_weight_overrides") or {}
    addendum = str(doc.get("proposed_claude_addendum") or "")
    prematch_calibration.apply_learning_to_config(
        weight_overrides={k: float(v) for k, v in weights.items()},
        claude_addendum=addendum,
        proposal_id=proposal_id,
    )
    await db.learning_proposals.update_one(
        {"_id": oid},
        {"$set": {"status": "applied", "applied_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"status": "ok", "applied_proposal_id": proposal_id}


async def dismiss_proposal(db, proposal_id: str) -> Dict[str, Any]:
    try:
        oid = ObjectId(proposal_id)
    except InvalidId:
        return {"error": "invalid_proposal_id"}
    res = await db.learning_proposals.update_one(
        {"_id": oid, "status": "pending"},
        {"$set": {"status": "dismissed", "dismissed_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.modified_count == 0:
        return {"error": "not_found_or_not_pending"}
    return {"status": "ok"}


# ── Live snapshot learning: last stored claudePrediction / combinedPrediction vs final result ──

LIVE_PROB_MARGIN = 5.0


def _schedule_completed(sched: Dict[str, Any]) -> bool:
    st = (sched.get("status") or "").lower()
    return "completed" in st or bool((sched.get("winner") or "").strip())


def _sportmonks_snapshot_finished(snap: Dict[str, Any]) -> bool:
    """True when the persisted SportMonks blob says the fixture is done — headline Claude % is usually result-aware."""
    sm = snap.get("sportmonks") or snap.get("sportmonksData") or {}
    if not isinstance(sm, dict):
        return False
    st = (sm.get("status") or "").lower().strip()
    return st in ("finished", "aban.", "aban", "cancelled", "no result", "ft")


async def _pre_match_team1_win_pct(db, match_id: str, snap: Dict[str, Any]) -> Optional[float]:
    hist = snap.get("historicalPrediction")
    if isinstance(hist, dict) and hist.get("team1_win_prob") is not None:
        try:
            return float(hist["team1_win_prob"])
        except (TypeError, ValueError):
            pass
    doc = await db.pre_match_predictions.find_one({"matchId": match_id}, {"_id": 0, "prediction": 1})
    pred = (doc or {}).get("prediction")
    if isinstance(pred, dict) and pred.get("team1_win_prob") is not None:
        try:
            return float(pred["team1_win_prob"])
        except (TypeError, ValueError):
            pass
    return None


def _extract_claude_live_reason(cp: Dict[str, Any]) -> Dict[str, Any]:
    s10 = cp.get("section_10_final_prediction") if isinstance(cp.get("section_10_final_prediction"), dict) else {}
    return {
        "sentence_1_key_factor": s10.get("sentence_1_key_factor"),
        "sentence_2_underdog_chance": s10.get("sentence_2_underdog_chance"),
        "sentence_3_first_6_signal": s10.get("sentence_3_first_6_signal"),
        "sentence_4_confidence": s10.get("sentence_4_confidence"),
        "primary_driver": cp.get("primary_driver"),
        "secondary_driver": cp.get("secondary_driver"),
    }


def _digest_schedule_performance(sched: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "winner": sched.get("winner"),
        "team1_score": sched.get("team1_score"),
        "team2_score": sched.get("team2_score"),
        "result": sched.get("result"),
        "score": sched.get("score"),
        "toss_won_by": sched.get("toss_won_by"),
    }


def _digest_snapshot_state(snap: Dict[str, Any]) -> Dict[str, Any]:
    ld = snap.get("liveData") or {}
    score: Dict[str, Any] = {}
    if isinstance(ld.get("score"), dict):
        score = ld["score"]
    sm = snap.get("sportmonks") or snap.get("sportmonksData") or {}
    out: Dict[str, Any] = {
        "snapshot_updated_at": snap.get("updatedAt") or snap.get("fetchedAt"),
        "last_innings": ld.get("innings"),
        "last_runs": score.get("runs"),
        "last_wickets": score.get("wickets"),
        "last_overs": score.get("overs"),
        "last_target": score.get("target"),
    }
    if isinstance(sm, dict):
        for key in ("current_score_text", "note", "status"):
            if sm.get(key):
                out[f"sm_{key}"] = sm.get(key)
    return {k: v for k, v in out.items() if v is not None}


async def record_live_match_learning(
    db,
    match_id: str,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Compare the last persisted ``live_snapshots`` row (Claude refresh + combined blend) to the
    final schedule result. Stores ``live_match_learning_outcomes``; may enqueue a ``live_claude`` proposal.
    """
    sched = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
    if not sched:
        return {"error": "match_not_found", "matchId": match_id}
    if not _schedule_completed(sched):
        return {"skipped": "not_completed", "matchId": match_id}

    actual = _winner_side(sched)
    if not actual:
        return {"skipped": "no_winner", "matchId": match_id}

    if force:
        await db.learning_proposals.delete_many(
            {"source_match_id": match_id, "source_track": "live_claude", "status": "pending"}
        )
    elif await db.live_match_learning_outcomes.find_one({"matchId": match_id}, {"_id": 1}):
        return {"skipped": "already_recorded", "matchId": match_id}

    snap = await db.live_snapshots.find_one({"matchId": match_id}, {"_id": 0})
    if not snap:
        await db.live_match_learning_outcomes.update_one(
            {"matchId": match_id},
            {
                "$set": {
                    "matchId": match_id,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "actual_winner_side": actual,
                    "has_live_snapshot": False,
                    "note": "No live_snapshots document for this match.",
                    "schedule_digest": _digest_schedule_performance(sched),
                }
            },
            upsert=True,
        )
        return {"status": "recorded", "matchId": match_id, "has_live_snapshot": False}

    cp = snap.get("claudePrediction") or snap.get("claude_prediction") or {}
    if not isinstance(cp, dict):
        cp = {}
    if cp.get("error"):
        cp = {}

    comb = snap.get("combinedPrediction") or snap.get("combined_prediction") or {}
    if not isinstance(comb, dict):
        comb = {}

    claude_t1: Optional[float] = None
    if cp.get("team1_win_pct") is not None:
        try:
            claude_t1 = float(cp["team1_win_pct"])
        except (TypeError, ValueError):
            claude_t1 = None

    combined_t1: Optional[float] = None
    if comb.get("team1_pct") is not None:
        try:
            combined_t1 = float(comb["team1_pct"])
        except (TypeError, ValueError):
            combined_t1 = None

    claude_fav: Optional[str] = None
    if claude_t1 is not None:
        claude_fav = "team1" if claude_t1 >= 50 else "team2"
    comb_fav: Optional[str] = None
    if combined_t1 is not None:
        comb_fav = "team1" if combined_t1 >= 50 else "team2"

    claude_correct = claude_fav == actual if claude_fav else None
    comb_correct = comb_fav == actual if comb_fav else None

    finished_ctx = _sportmonks_snapshot_finished(snap)
    claude_eval_note: Optional[str] = None
    if finished_ctx:
        claude_eval_note = (
            "Claude headline win% vs result not scored: snapshot SportMonks status is finished — "
            "the last refresh usually saw the full scoreboard, so the model aligns with the winner by design."
        )

    pm_t1 = await _pre_match_team1_win_pct(db, match_id, snap)
    pm_fav: Optional[str] = None
    pre_match_correct: Optional[bool] = None
    if pm_t1 is not None:
        pm_fav = "team1" if pm_t1 >= 50.0 else "team2"
        pre_match_correct = pm_fav == actual

    outcome: Dict[str, Any] = {
        "matchId": match_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "team1": sched.get("team1"),
        "team2": sched.get("team2"),
        "actual_winner_side": actual,
        "has_live_snapshot": True,
        "claude_team1_win_pct": claude_t1,
        "combined_team1_win_pct": combined_t1,
        "claude_predicted_favourite": claude_fav,
        "combined_predicted_favourite": comb_fav,
        "claude_correct": None if finished_ctx else claude_correct,
        "combined_correct": None if finished_ctx else comb_correct,
        "claude_raw_correct_if_posthoc_counted": claude_correct if finished_ctx else None,
        "combined_raw_correct_if_posthoc_counted": comb_correct if finished_ctx else None,
        "snapshot_finished_context": finished_ctx,
        "claude_eval_note": claude_eval_note,
        "pre_match_team1_win_pct": pm_t1,
        "pre_match_predicted_favourite": pm_fav,
        "pre_match_correct": pre_match_correct,
        "claude_reason": _extract_claude_live_reason(cp) if cp else {},
        "snapshot_state_digest": _digest_snapshot_state(snap),
        "schedule_digest": _digest_schedule_performance(sched),
    }

    await db.live_match_learning_outcomes.update_one(
        {"matchId": match_id},
        {"$set": outcome},
        upsert=True,
    )

    edge_wrong = (
        not finished_ctx
        and claude_t1 is not None
        and claude_correct is False
        and abs(claude_t1 - 50.0) >= LIVE_PROB_MARGIN
    )
    if not edge_wrong:
        return {"status": "recorded", "matchId": match_id, "proposal": "not_needed"}

    if not force and await db.learning_proposals.find_one(
        {"source_match_id": match_id, "source_track": "live_claude"}
    ):
        return {"status": "recorded", "matchId": match_id, "proposal": "skipped_duplicate"}

    creason = outcome["claude_reason"]
    k1 = (creason.get("sentence_1_key_factor") or "") if isinstance(creason, dict) else ""
    team1 = sched.get("team1") or "Team 1"
    team2 = sched.get("team2") or "Team 2"
    summary = (
        f"Live Claude (last snapshot) favoured {claude_fav} at team1_win_pct={claude_t1:.1f}% "
        f"but {actual} won ({team1} vs {team2})."
    )
    addendum = (
        f"Live calibration note ({match_id}): Result favoured {actual}; last stored live Claude "
        f"favoured {claude_fav} (team1%={claude_t1:.1f}). Key cited factor: {k1[:400]}. "
        f"Revisit Section 10 / phase blend vs scorecard for similar match states."
    )
    proposal: Dict[str, Any] = {
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_match_id": match_id,
        "source_track": "live_claude",
        "summary": summary,
        "learning_notes": [
            "Approving updates Claude prompt addendum only (proposed_weight_overrides empty).",
            "Snapshot reflects last refresh before DB write — may be mid-innings; compare schedule_digest.",
        ],
        "proposed_weight_overrides": {},
        "proposed_claude_addendum": addendum,
        "baseline_weights_used": {},
        "outcome_ref": {
            "claude_team1_win_pct": claude_t1,
            "combined_team1_win_pct": combined_t1,
            "actual_winner_side": actual,
        },
    }
    await db.learning_proposals.insert_one(proposal)
    return {"status": "recorded", "matchId": match_id, "proposal": "created"}


async def batch_live_match_learning(
    db,
    *,
    limit: int = 500,
    force: bool = False,
) -> Dict[str, Any]:
    """Scan completed fixtures and record live-vs-actual outcomes (idempotent unless force)."""
    q = {
        "$or": [
            {"status": {"$regex": r"completed", "$options": "i"}},
            {"winner": {"$exists": True, "$nin": [None, ""]}},
        ]
    }
    processed = 0
    proposals_created = 0
    already_done = 0
    no_snapshot = 0
    errors: List[str] = []

    cursor = db.ipl_schedule.find(q, {"_id": 0, "matchId": 1}).sort("match_number", 1)
    async for row in cursor:
        if processed >= limit:
            break
        mid = row.get("matchId")
        if not mid:
            continue
        processed += 1
        try:
            r = await record_live_match_learning(db, mid, force=force)
            if r.get("proposal") == "created":
                proposals_created += 1
            if r.get("skipped") == "already_recorded":
                already_done += 1
            if r.get("has_live_snapshot") is False:
                no_snapshot += 1
        except Exception as e:
            errors.append(f"{mid}: {e}")
            logger.warning("batch_live_match_learning %s: %s", mid, e)

    return {
        "processed": processed,
        "proposals_created": proposals_created,
        "already_recorded_skips": already_done,
        "rows_without_snapshot_hint": no_snapshot,
        "errors": errors[:40],
        "force": force,
        "limit": limit,
    }


async def batch_sync_completed_learning(
    db,
    *,
    limit: int = 500,
    force_live: bool = False,
) -> Dict[str, Any]:
    """
    For each completed fixture: run pre-match ``record_match_outcome`` (idempotent), then
    ``record_live_match_learning`` (idempotent unless ``force_live``).

    Use after importing schedule/results so ``match_prediction_outcomes``, live outcomes, and
    pending proposals are backfilled without opening each match manually.
    """
    cap = max(1, min(int(limit), 2000))
    q = {
        "$or": [
            {"status": {"$regex": r"completed", "$options": "i"}},
            {"winner": {"$exists": True, "$nin": [None, ""]}},
        ]
    }
    processed = 0
    pre_match_outcomes_new = 0
    live_proposals_created = 0
    live_already_done = 0
    live_no_snapshot = 0
    errors: List[str] = []

    cursor = db.ipl_schedule.find(q, {"_id": 0, "matchId": 1}).sort("match_number", 1)
    async for row in cursor:
        if processed >= cap:
            break
        mid = row.get("matchId")
        if not mid:
            continue
        processed += 1
        try:
            had_pre_outcome = await db.match_prediction_outcomes.find_one({"matchId": mid}, {"_id": 1})
            await record_match_outcome(db, mid)
            if not had_pre_outcome and await db.match_prediction_outcomes.find_one({"matchId": mid}, {"_id": 1}):
                pre_match_outcomes_new += 1

            lr = await record_live_match_learning(db, mid, force=force_live)
            if lr.get("proposal") == "created":
                live_proposals_created += 1
            if lr.get("skipped") == "already_recorded":
                live_already_done += 1
            if lr.get("has_live_snapshot") is False:
                live_no_snapshot += 1
        except Exception as e:
            errors.append(f"{mid}: {e}")
            logger.warning("batch_sync_completed_learning %s: %s", mid, e)

    return {
        "processed": processed,
        "pre_match_outcomes_new": pre_match_outcomes_new,
        "live_proposals_created": live_proposals_created,
        "live_already_recorded_skips": live_already_done,
        "live_rows_without_snapshot_hint": live_no_snapshot,
        "force_live": force_live,
        "limit": cap,
        "errors": errors[:40],
    }


async def list_live_learning_outcomes(db, limit: int = 50) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    async for doc in db.live_match_learning_outcomes.find({}).sort("recorded_at", -1).limit(limit):
        d = dict(doc)
        d.pop("_id", None)
        out.append(d)
    return out


async def completed_matches_learning_report(db, *, limit: int = 500) -> Dict[str, Any]:
    """
    All completed schedule rows with pre-match %, last stored live combined %, score lines,
    winner resolution, correctness flags, pending proposals (for Incorporate in UI).
    """
    cap = max(1, min(int(limit), 2000))
    q = {
        "$or": [
            {"status": {"$regex": r"completed", "$options": "i"}},
            {"winner": {"$exists": True, "$nin": [None, ""]}},
        ]
    }
    cur = db.ipl_schedule.find(q, {"_id": 0}).sort("match_number", 1).limit(cap)
    schedules = await cur.to_list(length=cap)
    ids = [s["matchId"] for s in schedules if s.get("matchId")]
    if not ids:
        return {"rows": [], "count": 0, "limit": cap}

    pre_table: Dict[str, Any] = {}
    async for doc in db.pre_match_predictions.find({"matchId": {"$in": ids}}, {"_id": 0}):
        pre_table[doc["matchId"]] = doc

    snap_table: Dict[str, Any] = {}
    async for doc in db.live_snapshots.find(
        {"matchId": {"$in": ids}},
        {"_id": 0, "matchId": 1, "combinedPrediction": 1, "sportmonks": 1, "sportmonksData": 1},
    ):
        snap_table[doc["matchId"]] = doc

    outcome_table: Dict[str, Any] = {}
    async for doc in db.match_prediction_outcomes.find({"matchId": {"$in": ids}}, {"_id": 0}):
        outcome_table[doc["matchId"]] = doc

    live_table: Dict[str, Any] = {}
    async for doc in db.live_match_learning_outcomes.find({"matchId": {"$in": ids}}, {"_id": 0}):
        live_table[doc["matchId"]] = doc

    proposals_by_mid: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    async for doc in db.learning_proposals.find(
        {"status": "pending", "source_match_id": {"$in": ids}},
        {"_id": 1, "source_match_id": 1, "source_track": 1, "summary": 1},
    ):
        mid = doc.get("source_match_id")
        if not mid:
            continue
        proposals_by_mid[mid].append(
            {
                "id": str(doc["_id"]),
                "source_track": doc.get("source_track") or "pre_match",
                "summary": (doc.get("summary") or "")[:240],
            }
        )

    track_order = {"pre_match": 0, "live_claude": 1}
    for mid in proposals_by_mid:
        proposals_by_mid[mid].sort(key=lambda p: track_order.get(p.get("source_track") or "", 9))

    rows: List[Dict[str, Any]] = []
    for sched in schedules:
        mid = sched.get("matchId")
        if not mid:
            continue
        actual = _winner_side(sched)
        mo = outcome_table.get(mid)
        pre_doc = pre_table.get(mid)
        snap = snap_table.get(mid)
        lo = live_table.get(mid)

        t1_pre: Optional[float] = None
        pre_correct: Optional[bool] = None
        if mo and mo.get("algo_team1_win_prob") is not None:
            try:
                t1_pre = float(mo["algo_team1_win_prob"])
            except (TypeError, ValueError):
                t1_pre = None
            if mo.get("algo_correct") is not None:
                pre_correct = bool(mo["algo_correct"])
        if t1_pre is None and pre_doc:
            pred = sanitize_prediction_to_five_factors((pre_doc.get("prediction") or {}))
            if pred.get("team1_win_prob") is not None:
                try:
                    t1_pre = float(pred["team1_win_prob"])
                except (TypeError, ValueError):
                    t1_pre = None

        pre_fav: Optional[str] = None
        if t1_pre is not None:
            pre_fav = "team1" if t1_pre >= 50.0 else "team2"
        if pre_correct is None and pre_fav is not None and actual:
            pre_correct = pre_fav == actual

        t1_comb: Optional[float] = None
        if lo and lo.get("combined_team1_win_pct") is not None:
            try:
                t1_comb = float(lo["combined_team1_win_pct"])
            except (TypeError, ValueError):
                t1_comb = None
        if t1_comb is None and snap:
            c = snap.get("combinedPrediction") or {}
            if c.get("team1_pct") is not None:
                try:
                    t1_comb = float(c["team1_pct"])
                except (TypeError, ValueError):
                    t1_comb = None

        lc_correct: Optional[bool] = None
        lc_na_reason: Optional[str] = None
        if lo:
            lc_correct = lo.get("combined_correct")
            if lo.get("combined_correct") is None and lo.get("snapshot_finished_context"):
                lc_na_reason = "finished_snapshot"
        elif t1_comb is not None and actual:
            if snap and _sportmonks_snapshot_finished(snap):
                lc_correct = None
                lc_na_reason = "finished_snapshot"
            else:
                cf = "team1" if t1_comb >= 50.0 else "team2"
                lc_correct = cf == actual

        props = proposals_by_mid.get(mid, [])

        summary_parts: List[str] = []
        if t1_pre is None:
            summary_parts.append("No pre-match % in DB")
        else:
            if pre_correct is True:
                summary_parts.append(f"Pre ✓ ({t1_pre:.1f}% t1)")
            elif pre_correct is False:
                summary_parts.append(f"Pre ✗ ({t1_pre:.1f}% t1)")
            else:
                summary_parts.append(f"Pre {t1_pre:.1f}% t1")
        if t1_comb is None:
            summary_parts.append("No live combined %")
        elif lc_na_reason == "finished_snapshot":
            summary_parts.append(f"Live combined {t1_comb:.1f}% t1 (not scored vs result — finished snapshot)")
        elif lc_correct is True:
            summary_parts.append(f"Combined ✓ ({t1_comb:.1f}% t1)")
        elif lc_correct is False:
            summary_parts.append(f"Combined ✗ ({t1_comb:.1f}% t1)")
        else:
            summary_parts.append(f"Live combined {t1_comb:.1f}% t1")
        if props:
            summary_parts.append(f"{len(props)} pending proposal(s)")
        else:
            summary_parts.append("No pending proposals")

        rows.append(
            {
                "matchId": mid,
                "match_number": sched.get("match_number"),
                "team1": sched.get("team1"),
                "team2": sched.get("team2"),
                "team1_score": sched.get("team1_score") or "",
                "team2_score": sched.get("team2_score") or "",
                "schedule_score": sched.get("score") or "",
                "result_note": sched.get("result") or "",
                "winner_name": sched.get("winner") or "",
                "winner_side": actual or "",
                "pre_match_team1_pct": round(t1_pre, 2) if t1_pre is not None else None,
                "live_combined_team1_pct": round(t1_comb, 2) if t1_comb is not None else None,
                "pre_match_predicted_favourite": pre_fav,
                "pre_match_correct": pre_correct,
                "live_combined_correct": lc_correct,
                "live_combined_eval_note": lc_na_reason,
                "learning_summary": " | ".join(summary_parts),
                "pending_proposals": props,
            }
        )

    return {"rows": rows, "count": len(rows), "limit": cap}
