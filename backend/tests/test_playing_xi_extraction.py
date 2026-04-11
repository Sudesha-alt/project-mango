"""Tests for Playing XI extraction logic in sportmonks_service.parse_fixture()
and _filter_squads_to_playing_xi() in server.py.

Validates the multi-layer fix:
- Layer 1: Pivot-based team_id + substitution parsing
- Layer 2: Scorecard-based resolution for unassigned players
- Layer 3: Pruning oversized XI using confirmed player IDs
- Layer 4: Hard cap in _filter_squads_to_playing_xi
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.sportmonks_service import parse_fixture


def _make_player(pid, name, team_id, substitution=False):
    """Helper: create a player dict mimicking SportMonks lineup structure."""
    return {
        "id": pid,
        "fullname": name,
        "battingstyle": "Right Hand Bat",
        "bowlingstyle": "",
        "position": {"name": "Batsman"},
        "image_path": "",
        "lineup": {
            "team_id": team_id,
            "substitution": substitution,
            "captain": False,
            "wicketkeeper": False,
        }
    }


def _make_player_no_pivot(pid, name):
    """Helper: player with NO lineup pivot data (team_id unknown)."""
    return {
        "id": pid,
        "fullname": name,
        "battingstyle": "",
        "bowlingstyle": "",
        "position": {},
        "image_path": "",
        # No lineup pivot!
    }


def _build_fixture(lineup, runs=None, batting=None, bowling=None,
                   team1_id=100, team2_id=200):
    """Build a minimal SportMonks fixture dict for testing."""
    return {
        "id": 99999,
        "status": "1st Innings",
        "note": "",
        "localteam": {"id": team1_id, "name": "Team Alpha", "code": "ALP"},
        "visitorteam": {"id": team2_id, "name": "Team Beta", "code": "BET"},
        "localteam_id": team1_id,
        "visitorteam_id": team2_id,
        "venue": {"name": "Test Stadium", "city": "TestCity"},
        "toss_won_team_id": team1_id,
        "elected": "batting",
        "runs": runs or [
            {"inning": 1, "team_id": team1_id, "score": 180, "wickets": 5, "overs": 20},
        ],
        "batting": batting or [],
        "bowling": bowling or [],
        "lineup": lineup,
        "scoreboards": [],
        "balls": [],
    }


# ═══════════════════════════════════════════════════════
# TEST 1: Normal case — pivot data works, 11+subs per team
# ═══════════════════════════════════════════════════════
def test_normal_xi_extraction():
    """11 non-subs + 5 subs per team → playing_xi should have exactly 11 each."""
    lineup = []
    for i in range(1, 12):
        lineup.append(_make_player(i, f"Alpha Player {i}", team_id=100, substitution=False))
    for i in range(12, 17):
        lineup.append(_make_player(i, f"Alpha Sub {i}", team_id=100, substitution=True))
    for i in range(101, 112):
        lineup.append(_make_player(i, f"Beta Player {i}", team_id=200, substitution=False))
    for i in range(112, 117):
        lineup.append(_make_player(i, f"Beta Sub {i}", team_id=200, substitution=True))

    fixture = _build_fixture(lineup)
    result = parse_fixture(fixture)

    assert result is not None
    assert len(result["team1_playing_xi"]) == 11, f"Expected 11, got {len(result['team1_playing_xi'])}"
    assert len(result["team2_playing_xi"]) == 11, f"Expected 11, got {len(result['team2_playing_xi'])}"
    assert len(result["team1_lineup"]) == 16  # 11 + 5 subs
    assert len(result["team2_lineup"]) == 16


# ═══════════════════════════════════════════════════════
# TEST 2: Substitution flag unreliable (all False) → >12 per team
# With scorecard data, should prune correctly
# ═══════════════════════════════════════════════════════
def test_substitution_flag_unreliable_with_scorecard():
    """All 16 players have substitution=False. Scorecard data identifies 8 confirmed players.
    Playing XI should be pruned to max 12."""
    lineup = []
    for i in range(1, 17):
        lineup.append(_make_player(i, f"Alpha Player {i}", team_id=100, substitution=False))
    for i in range(101, 117):
        lineup.append(_make_player(i, f"Beta Player {i}", team_id=200, substitution=False))

    # Scorecard: 8 Alpha batsmen confirmed, 6 Beta bowlers confirmed
    batting = [
        {"player_id": i, "score": 30, "ball": 20, "four_x": 3, "six_x": 1,
         "active": False, "scoreboard": "S1", "sort": i, "fow_score": None, "fow_balls": None}
        for i in range(1, 9)
    ]
    bowling = [
        {"player_id": i, "overs": 4, "medians": 0, "runs": 30, "wickets": 1,
         "rate": 7.5, "wide": 0, "noball": 0, "active": False, "scoreboard": "S1", "sort": i}
        for i in range(101, 107)
    ]
    runs = [{"inning": 1, "team_id": 100, "score": 180, "wickets": 5, "overs": 20}]

    fixture = _build_fixture(lineup, runs=runs, batting=batting, bowling=bowling)
    result = parse_fixture(fixture)

    assert result is not None
    # Should be capped at 12 max
    assert len(result["team1_playing_xi"]) <= 12, \
        f"T1 XI should be <=12, got {len(result['team1_playing_xi'])}"
    assert len(result["team2_playing_xi"]) <= 12, \
        f"T2 XI should be <=12, got {len(result['team2_playing_xi'])}"

    # All 8 confirmed Alpha players must be in the XI
    t1_ids = {p["id"] for p in result["team1_playing_xi"]}
    for pid in range(1, 9):
        assert pid in t1_ids, f"Confirmed player {pid} missing from T1 XI"

    # All 6 confirmed Beta bowlers must be in the XI
    t2_ids = {p["id"] for p in result["team2_playing_xi"]}
    for pid in range(101, 107):
        assert pid in t2_ids, f"Confirmed player {pid} missing from T2 XI"


# ═══════════════════════════════════════════════════════
# TEST 3: No pivot data at all → unassigned players
# Scorecard resolves them
# ═══════════════════════════════════════════════════════
def test_no_pivot_data_scorecard_resolves():
    """All players missing team_id in pivot. Scorecard data assigns them to correct teams."""
    lineup = []
    for i in range(1, 12):
        lineup.append(_make_player_no_pivot(i, f"Alpha Player {i}"))
    for i in range(101, 112):
        lineup.append(_make_player_no_pivot(i, f"Beta Player {i}"))

    batting = [
        {"player_id": i, "score": 30, "ball": 20, "four_x": 3, "six_x": 1,
         "active": False, "scoreboard": "S1", "sort": i, "fow_score": None, "fow_balls": None}
        for i in range(1, 6)  # 5 Alpha batsmen
    ]
    bowling = [
        {"player_id": i, "overs": 4, "medians": 0, "runs": 30, "wickets": 1,
         "rate": 7.5, "wide": 0, "noball": 0, "active": False, "scoreboard": "S1", "sort": i}
        for i in range(101, 106)  # 5 Beta bowlers
    ]
    runs = [{"inning": 1, "team_id": 100, "score": 180, "wickets": 5, "overs": 20}]

    fixture = _build_fixture(lineup, runs=runs, batting=batting, bowling=bowling)
    result = parse_fixture(fixture)

    assert result is not None
    # Scorecard confirms 5 from each team
    t1_ids = {p["id"] for p in result["team1_playing_xi"]}
    t2_ids = {p["id"] for p in result["team2_playing_xi"]}

    for pid in range(1, 6):
        assert pid in t1_ids, f"Alpha player {pid} should be in T1 XI"
    for pid in range(101, 106):
        assert pid in t2_ids, f"Beta player {pid} should be in T2 XI"

    # Players not on scorecard remain unassigned (not in either XI)
    for pid in range(6, 12):
        assert pid not in t1_ids and pid not in t2_ids, \
            f"Unconfirmed player {pid} should NOT be in any XI"


# ═══════════════════════════════════════════════════════
# TEST 4: 12 players per team (11 + 1 impact sub marked non-sub)
# Should still pass (within cap)
# ═══════════════════════════════════════════════════════
def test_impact_sub_within_cap():
    """12 non-subs per team (impact player rule). Should pass without pruning."""
    lineup = []
    for i in range(1, 13):
        lineup.append(_make_player(i, f"Alpha Player {i}", team_id=100, substitution=False))
    for i in range(101, 113):
        lineup.append(_make_player(i, f"Beta Player {i}", team_id=200, substitution=False))

    fixture = _build_fixture(lineup)
    result = parse_fixture(fixture)

    assert result is not None
    assert len(result["team1_playing_xi"]) == 12
    assert len(result["team2_playing_xi"]) == 12


# ═══════════════════════════════════════════════════════
# TEST 5: Empty lineup → both playing_xi should be empty
# ═══════════════════════════════════════════════════════
def test_empty_lineup():
    """No lineup data at all."""
    fixture = _build_fixture([])
    result = parse_fixture(fixture)

    assert result is not None
    assert len(result["team1_playing_xi"]) == 0
    assert len(result["team2_playing_xi"]) == 0


# ═══════════════════════════════════════════════════════
# TEST 6: Second innings scorecard — bowling resolves to correct team
# ═══════════════════════════════════════════════════════
def test_second_innings_resolution():
    """In 2nd innings, batting team = team2, bowling team = team1.
    Verify scorecard correctly identifies team membership."""
    lineup = []
    # All players without pivot
    for i in range(1, 12):
        lineup.append(_make_player_no_pivot(i, f"Alpha Player {i}"))
    for i in range(101, 112):
        lineup.append(_make_player_no_pivot(i, f"Beta Player {i}"))

    runs = [
        {"inning": 1, "team_id": 100, "score": 180, "wickets": 10, "overs": 20},
        {"inning": 2, "team_id": 200, "score": 90, "wickets": 4, "overs": 10},
    ]
    batting_inn1 = [
        {"player_id": i, "score": 20, "ball": 15, "four_x": 2, "six_x": 0,
         "active": False, "scoreboard": "S1", "sort": i, "fow_score": None, "fow_balls": None}
        for i in range(1, 6)
    ]
    batting_inn2 = [
        {"player_id": i, "score": 20, "ball": 15, "four_x": 2, "six_x": 0,
         "active": True, "scoreboard": "S2", "sort": i, "fow_score": None, "fow_balls": None}
        for i in range(101, 105)
    ]
    bowling_inn1 = [
        {"player_id": i, "overs": 4, "medians": 0, "runs": 36, "wickets": 2,
         "rate": 9.0, "wide": 0, "noball": 0, "active": False, "scoreboard": "S1", "sort": i}
        for i in range(101, 107)
    ]
    bowling_inn2 = [
        {"player_id": i, "overs": 2, "medians": 0, "runs": 18, "wickets": 1,
         "rate": 9.0, "wide": 0, "noball": 0, "active": True, "scoreboard": "S2", "sort": i}
        for i in range(1, 5)
    ]

    fixture = _build_fixture(
        lineup, runs=runs,
        batting=batting_inn1 + batting_inn2,
        bowling=bowling_inn1 + bowling_inn2,
    )
    result = parse_fixture(fixture)

    assert result is not None
    t1_ids = {p["id"] for p in result["team1_playing_xi"]}
    t2_ids = {p["id"] for p in result["team2_playing_xi"]}

    # Alpha players (1-5 bat inn1, 1-4 bowl inn2) → all team1
    for pid in range(1, 6):
        assert pid in t1_ids, f"Alpha batter {pid} should be in T1"

    # Beta players (101-106 bowl inn1, 101-104 bat inn2) → all team2
    for pid in range(101, 107):
        assert pid in t2_ids, f"Beta bowler {pid} should be in T2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
