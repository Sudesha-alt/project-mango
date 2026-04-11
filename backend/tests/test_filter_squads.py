"""Tests for _filter_squads_to_playing_xi in server.py.
Validates the hard cap at 12 players and correct fallback behavior."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import the function from server module
from server import _filter_squads_to_playing_xi


def _make_db_player(name):
    return {"name": name, "role": "Batsman"}


def test_hard_cap_applied():
    """If SportMonks returns 15 playing_xi names and DB has 15 matches,
    the function should cap at 12."""
    match_squads = {
        "Team A": [_make_db_player(f"Player A{i}") for i in range(1, 25)],
        "Team B": [_make_db_player(f"Player B{i}") for i in range(1, 25)],
    }
    sm_data = {
        "team1_playing_xi": [{"name": f"Player A{i}"} for i in range(1, 16)],
        "team2_playing_xi": [{"name": f"Player B{i}"} for i in range(1, 16)],
    }
    result = _filter_squads_to_playing_xi(match_squads, sm_data, "Team A", "Team B")
    assert len(result["Team A"]) <= 12, f"Expected <=12, got {len(result['Team A'])}"
    assert len(result["Team B"]) <= 12, f"Expected <=12, got {len(result['Team B'])}"


def test_normal_11_passes_through():
    """Standard 11 playing XI should pass through without capping."""
    t1_names = ["Virat Kohli", "Rohit Sharma", "KL Rahul", "Jasprit Bumrah", "Ravindra Jadeja",
                "Shubman Gill", "Rishabh Pant", "Hardik Pandya", "Yuzvendra Chahal", "Mohammed Siraj", "Axar Patel"]
    t1_squad = t1_names + ["Shreyas Iyer", "Kuldeep Yadav", "Suryakumar Yadav", "Ishan Kishan"]
    t2_names = ["David Warner", "Steve Smith", "Pat Cummins", "Mitchell Starc", "Glenn Maxwell",
                "Travis Head", "Marnus Labuschagne", "Josh Hazlewood", "Adam Zampa", "Cameron Green", "Alex Carey"]
    t2_squad = t2_names + ["Marcus Stoinis", "Nathan Lyon", "Josh Inglis", "Sean Abbott"]

    match_squads = {
        "Team A": [_make_db_player(n) for n in t1_squad],
        "Team B": [_make_db_player(n) for n in t2_squad],
    }
    sm_data = {
        "team1_playing_xi": [{"name": n} for n in t1_names],
        "team2_playing_xi": [{"name": n} for n in t2_names],
    }
    result = _filter_squads_to_playing_xi(match_squads, sm_data, "Team A", "Team B")
    assert len(result["Team A"]) == 11, f"Expected 11, got {len(result['Team A'])}"
    assert len(result["Team B"]) == 11, f"Expected 11, got {len(result['Team B'])}"


def test_empty_playing_xi_falls_back_to_lineup():
    """If playing_xi is empty but lineup exists, uses lineup (still capped)."""
    match_squads = {
        "Team A": [_make_db_player(f"Player A{i}") for i in range(1, 25)],
        "Team B": [_make_db_player(f"Player B{i}") for i in range(1, 25)],
    }
    sm_data = {
        "team1_playing_xi": [],  # Empty
        "team1_lineup": [{"name": f"Player A{i}"} for i in range(1, 17)],
        "team2_playing_xi": [],
        "team2_lineup": [{"name": f"Player B{i}"} for i in range(1, 17)],
    }
    result = _filter_squads_to_playing_xi(match_squads, sm_data, "Team A", "Team B")
    # Falls back to lineup, should still cap at 12
    assert len(result["Team A"]) <= 12
    assert len(result["Team B"]) <= 12


def test_no_data_returns_full_squads():
    """If no SportMonks data at all, returns full squads."""
    match_squads = {
        "Team A": [_make_db_player(f"Player A{i}") for i in range(1, 25)],
        "Team B": [_make_db_player(f"Player B{i}") for i in range(1, 25)],
    }
    result = _filter_squads_to_playing_xi(match_squads, None, "Team A", "Team B")
    assert len(result["Team A"]) == 24
    assert len(result["Team B"]) == 24


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
