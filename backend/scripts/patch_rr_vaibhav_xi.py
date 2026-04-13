#!/usr/bin/env python3
"""
One-off / maintenance: ensure Vaibhav Suryavanshi appears in Rajasthan Royals XI in MongoDB.

Usage (from repo root):
  python backend/scripts/patch_rr_vaibhav_xi.py [matchId]

If matchId is omitted, uses the latest SRH vs RR row in ipl_schedule (by dateTimeGMT).

Requires MONGO_URL and DB_NAME in backend/.env (or env).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

RR_VAIBHAV = "Vaibhav Suryavanshi"
RR_REPLACE_FIRST = (
    "Brijesh Sharma",
    "Vignesh Puthur",
    "Sushant Mishra",
    "Ravi Singh",
    "Yash Raj Punja",
)


def _norm(n: str) -> str:
    import re

    s = (n or "").lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _names_match(a: str, b: str) -> bool:
    from difflib import SequenceMatcher

    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ap, bp = na.split(), nb.split()
    if ap and bp and ap[-1] == bp[-1] and ap[0][:1] == bp[0][:1]:
        return True
    if ap and bp and ap[0][:1] == bp[0][:1] and SequenceMatcher(None, na, nb).ratio() >= 0.88:
        return True
    return False


def _xi_has_vaibhav(xi: list) -> bool:
    for p in xi or []:
        if not isinstance(p, dict):
            continue
        nm = p.get("name") or p.get("fullname") or ""
        if _names_match(nm, RR_VAIBHAV):
            return True
    return False


def _find_vaibhav_roster(rr_players: list) -> dict | None:
    for p in rr_players or []:
        if isinstance(p, dict) and _names_match(p.get("name", ""), RR_VAIBHAV):
            return dict(p)
    return None


def inject_rr_vaibhav(xi_rows: list, rr_roster: list) -> list:
    if not xi_rows or len(xi_rows) < 11:
        return xi_rows
    if _xi_has_vaibhav(xi_rows):
        return xi_rows
    v = _find_vaibhav_roster(rr_roster)
    if not v:
        print("Vaibhav not found in RR ipl_squads roster — run seed_squads_2026 first.")
        return xi_rows
    out = [dict(p) if isinstance(p, dict) else p for p in xi_rows]
    row = {
        "name": v.get("name", RR_VAIBHAV),
        "role": v.get("role", "Batsman"),
        "isCaptain": bool(v.get("isCaptain", False)),
        "isOverseas": bool(v.get("isOverseas", False)),
    }
    for drop in RR_REPLACE_FIRST:
        for i, p in enumerate(out):
            if not isinstance(p, dict):
                continue
            nm = p.get("name") or p.get("fullname") or ""
            if _names_match(nm, drop):
                out[i] = {**p, **row}
                print(f"Replaced {nm} with {RR_VAIBHAV}")
                return out
    last = out[-1]
    last_nm = last.get("name", "") if isinstance(last, dict) else ""
    out[-1] = {**last, **row} if isinstance(last, dict) else row
    print(f"Replaced last player ({last_nm}) with {RR_VAIBHAV}")
    return out


async def main() -> None:
    mongo_url = os.environ.get("MONGO_URL", "").strip()
    db_name = os.environ.get("DB_NAME", "").strip()
    if not mongo_url or not db_name:
        print("Set MONGO_URL and DB_NAME")
        sys.exit(1)

    match_id = sys.argv[1].strip() if len(sys.argv) > 1 else None

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    rr_doc = await db.ipl_squads.find_one({"teamShort": "RR"}, {"_id": 0})
    if not rr_doc:
        print("No RR document in ipl_squads")
        sys.exit(1)
    rr_players = rr_doc.get("players", [])

    if not match_id:
        cur = (
            db.ipl_schedule.find(
                {
                    "$or": [
                        {
                            "team1": {"$regex": "Sunrisers", "$options": "i"},
                            "team2": {"$regex": "Rajasthan", "$options": "i"},
                        },
                        {
                            "team2": {"$regex": "Sunrisers", "$options": "i"},
                            "team1": {"$regex": "Rajasthan", "$options": "i"},
                        },
                    ]
                },
                {"_id": 0, "matchId": 1, "team1": 1, "team2": 1, "dateTimeGMT": 1},
            )
            .sort("dateTimeGMT", -1)
            .limit(1)
        )
        rows = await cur.to_list(1)
        if not rows:
            print("No SRH vs RR match in ipl_schedule; pass matchId explicitly.")
            sys.exit(1)
        m = rows[0]
        match_id = m["matchId"]
        team1, team2 = m.get("team1", ""), m.get("team2", "")
        print(f"Using schedule matchId={match_id} ({team1} vs {team2})")
    else:
        m = await db.ipl_schedule.find_one({"matchId": match_id}, {"_id": 0})
        if not m:
            print(f"No match {match_id}")
            sys.exit(1)
        team1, team2 = m.get("team1", ""), m.get("team2", "")

    if "rajasthan" in team1.lower():
        field = "team1_xi"
    elif "rajasthan" in team2.lower():
        field = "team2_xi"
    else:
        print("Match does not look like RR fixture:", team1, team2)
        sys.exit(1)

    px = await db.playing_xi.find_one({"matchId": match_id}, {"_id": 0})
    if not px:
        print(f"No playing_xi doc for {match_id}")
        sys.exit(1)

    xi = list(px.get(field) or [])
    new_xi = inject_rr_vaibhav(xi, rr_players)
    if new_xi == xi and not _xi_has_vaibhav(xi):
        print("No change applied (check XI length or roster).")
        sys.exit(1)

    await db.playing_xi.update_one({"matchId": match_id}, {"$set": {field: new_xi}})
    await db.pre_match_predictions.update_one(
        {"matchId": match_id},
        {"$set": {f"playing_xi.{field}": new_xi}},
    )
    print(f"Updated playing_xi + pre_match_predictions for {match_id} ({field})")


if __name__ == "__main__":
    asyncio.run(main())
