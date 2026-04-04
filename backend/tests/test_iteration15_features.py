"""
Iteration 15 Tests: Gamble Consultant IPL 2026
==============================================
Tests for:
1. Backend: POST /api/matches/ipl2026_008/consult with market odds returns realistic simulation probs
2. Backend: Simulation team1_win_prob + team2_win_prob should roughly sum to 1.0
3. Backend: Player impact players should have team names matching the match teams
4. Backend: mean_team1_score and mean_team2_score populated
5. Backend: edge_reasons array non-empty when market odds provided
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestConsultationEndpoint:
    """Test the /api/matches/{match_id}/consult endpoint"""
    
    def test_consult_returns_realistic_probabilities(self):
        """Simulation should return realistic probabilities (not 100/0)"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Check simulation exists
        assert "simulation" in data, "Response should contain simulation data"
        sim = data["simulation"]
        
        # Check probabilities are realistic (not 0.0 or 1.0)
        t1_prob = sim.get("team1_win_prob", 0)
        t2_prob = sim.get("team2_win_prob", 0)
        
        assert t1_prob > 0.0, f"team1_win_prob should be > 0, got {t1_prob}"
        assert t1_prob < 1.0, f"team1_win_prob should be < 1, got {t1_prob}"
        assert t2_prob > 0.0, f"team2_win_prob should be > 0, got {t2_prob}"
        assert t2_prob < 1.0, f"team2_win_prob should be < 1, got {t2_prob}"
        
        print(f"✓ Realistic probabilities: team1={t1_prob:.4f}, team2={t2_prob:.4f}")
    
    def test_probabilities_sum_to_one(self):
        """team1_win_prob + team2_win_prob should roughly sum to 1.0"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        sim = data.get("simulation", {})
        
        t1_prob = sim.get("team1_win_prob", 0)
        t2_prob = sim.get("team2_win_prob", 0)
        total = t1_prob + t2_prob
        
        # Should sum to approximately 1.0 (allowing small floating point error)
        assert 0.99 <= total <= 1.01, f"Probabilities should sum to ~1.0, got {total}"
        print(f"✓ Probabilities sum to {total:.4f}")
    
    def test_predicted_scores_populated(self):
        """mean_team1_score and mean_team2_score should be populated"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        sim = data.get("simulation", {})
        
        mean_t1 = sim.get("mean_team1_score")
        mean_t2 = sim.get("mean_team2_score")
        
        assert mean_t1 is not None, "mean_team1_score should be populated"
        assert mean_t2 is not None, "mean_team2_score should be populated"
        
        # Scores should be in realistic IPL range (50-300)
        assert 50 <= mean_t1 <= 300, f"mean_team1_score should be 50-300, got {mean_t1}"
        assert 50 <= mean_t2 <= 300, f"mean_team2_score should be 50-300, got {mean_t2}"
        
        print(f"✓ Predicted scores: team1={mean_t1}, team2={mean_t2}")
    
    def test_edge_reasons_non_empty(self):
        """edge_reasons array should be non-empty when market odds provided"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        edge_reasons = data.get("edge_reasons", [])
        assert isinstance(edge_reasons, list), "edge_reasons should be a list"
        assert len(edge_reasons) > 0, "edge_reasons should not be empty when market odds provided"
        
        # Each reason should be a non-empty string
        for reason in edge_reasons:
            assert isinstance(reason, str), f"Each reason should be a string, got {type(reason)}"
            assert len(reason) > 0, "Each reason should be non-empty"
        
        print(f"✓ Edge reasons populated: {len(edge_reasons)} reasons")
        for i, r in enumerate(edge_reasons[:3]):
            print(f"  - Reason {i+1}: {r[:80]}...")
    
    def test_player_impact_team_names_match(self):
        """Player impact players should have team names matching the match teams"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Get match teams
        team1 = data.get("team", "")
        team2 = data.get("opponent", "")
        
        player_impact = data.get("player_impact", [])
        
        if len(player_impact) > 0:
            for player in player_impact:
                player_team = player.get("team", "")
                assert player_team in [team1, team2], \
                    f"Player {player.get('name')} has team '{player_team}' which doesn't match match teams ({team1}, {team2})"
            print(f"✓ All {len(player_impact)} players have valid team names ({team1} or {team2})")
        else:
            print("⚠ No player_impact data returned (may be expected if no Playing XI cached)")
    
    def test_simulation_runs_50k(self):
        """Simulation should run 50,000 iterations"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        sim = data.get("simulation", {})
        
        simulations = sim.get("simulations", 0)
        assert simulations == 50000, f"Expected 50000 simulations, got {simulations}"
        print(f"✓ Simulation ran {simulations} iterations")
    
    def test_p10_p90_range_exists(self):
        """Simulation should include P10-P90 score ranges"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        sim = data.get("simulation", {})
        
        t1_scores = sim.get("team1_scores", {})
        t2_scores = sim.get("team2_scores", {})
        
        # Check P10 and P90 exist
        assert "p10" in t1_scores, "team1_scores should have p10"
        assert "p90" in t1_scores, "team1_scores should have p90"
        assert "p10" in t2_scores, "team2_scores should have p10"
        assert "p90" in t2_scores, "team2_scores should have p90"
        
        # P90 should be greater than P10
        assert t1_scores["p90"] > t1_scores["p10"], "P90 should be > P10 for team1"
        assert t2_scores["p90"] > t2_scores["p10"], "P90 should be > P10 for team2"
        
        print(f"✓ Team1 P10-P90: {t1_scores['p10']}-{t1_scores['p90']}")
        print(f"✓ Team2 P10-P90: {t2_scores['p10']}-{t2_scores['p90']}")
    
    def test_verdict_section_exists(self):
        """Verdict section should exist with winner, strength, etc."""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        verdict = data.get("verdict", {})
        assert "winner" in verdict, "verdict should have winner"
        assert "winner_short" in verdict, "verdict should have winner_short"
        assert "strength" in verdict, "verdict should have strength"
        assert "winner_probability" in verdict, "verdict should have winner_probability"
        
        # Strength should be one of the valid values
        valid_strengths = ["DOMINANT", "STRONG", "SLIGHT", "TOSS-UP"]
        assert verdict["strength"] in valid_strengths, \
            f"verdict.strength should be one of {valid_strengths}, got {verdict['strength']}"
        
        print(f"✓ Verdict: {verdict['winner_short']} WINS ({verdict['strength']}) at {verdict['winner_probability']}%")
    
    def test_value_signal_exists(self):
        """value_signal should exist with valid signal type"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        value_signal = data.get("value_signal")
        assert value_signal is not None, "value_signal should exist"
        
        valid_signals = ["STRONG_VALUE", "VALUE", "SMALL_EDGE", "NO_BET", "AVOID", "WAIT_FOR_MORE_DATA", "NO_MARKET"]
        assert value_signal in valid_signals, \
            f"value_signal should be one of {valid_signals}, got {value_signal}"
        
        print(f"✓ Value signal: {value_signal}")
    
    def test_features_for_upcoming_match(self):
        """Features should show overs=0 and score=0 for upcoming matches"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        features = data.get("features", {})
        overs = features.get("overs", -1)
        score = features.get("score", -1)
        
        # For upcoming match, overs and score should be 0
        assert overs == 0, f"For upcoming match, overs should be 0, got {overs}"
        assert score == 0, f"For upcoming match, score should be 0, got {score}"
        
        print(f"✓ Features for upcoming match: overs={overs}, score={score}")


class TestScheduleEndpoint:
    """Test the /api/schedule endpoint"""
    
    def test_schedule_loads(self):
        """Schedule should load with matches"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        
        assert "matches" in data, "Response should contain matches"
        assert len(data["matches"]) > 0, "Should have at least one match"
        
        print(f"✓ Schedule loaded with {len(data['matches'])} matches")
    
    def test_match_ipl2026_008_exists(self):
        """Match ipl2026_008 (MI vs DC) should exist"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        
        match = next((m for m in data["matches"] if m.get("matchId") == "ipl2026_008"), None)
        assert match is not None, "Match ipl2026_008 should exist"
        
        # Verify it's MI vs DC
        team1 = match.get("team1", "")
        team2 = match.get("team2", "")
        assert "Mumbai" in team1 or "MI" in team1, f"team1 should be Mumbai Indians, got {team1}"
        assert "Delhi" in team2 or "DC" in team2, f"team2 should be Delhi Capitals, got {team2}"
        
        print(f"✓ Match ipl2026_008 found: {team1} vs {team2}")


class TestPreMatchPrediction:
    """Test the pre-match prediction endpoint"""
    
    def test_pre_match_prediction_exists(self):
        """Pre-match prediction should exist for ipl2026_008"""
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert response.status_code == 200
        data = response.json()
        
        predictions = data.get("predictions", [])
        match_pred = next((p for p in predictions if p.get("matchId") == "ipl2026_008"), None)
        
        if match_pred:
            pred = match_pred.get("prediction", {})
            t1_prob = pred.get("team1_win_prob", 0)
            t2_prob = pred.get("team2_win_prob", 0)
            print(f"✓ Pre-match prediction exists: {match_pred.get('team1Short')} {t1_prob}% vs {match_pred.get('team2Short')} {t2_prob}%")
        else:
            print("⚠ No pre-match prediction cached for ipl2026_008 (may need to run prediction first)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
