"""
Iteration 14 Backend Tests - Gamble Consultant Bug Fixes
Tests for:
1. Realistic simulation probabilities (not 100/0)
2. Predicted scores (mean_team1_score, mean_team2_score)
3. Edge reasons populated when market odds provided
4. Features.overs=0 and features.score=0 for upcoming matches
5. Verdict section with winner, strength, signal, edge_reasons
6. Player Impact from cached Playing XI
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestConsultEndpointSimulation:
    """Test simulation returns realistic probabilities and scores"""
    
    def test_simulation_not_100_0_probability(self):
        """Simulation should return realistic probabilities, not 100/0"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        sim = data.get("simulation", {})
        assert sim, "Simulation object should exist"
        
        t1_prob = sim.get("team1_win_prob", 0)
        t2_prob = sim.get("team2_win_prob", 0)
        
        # Probabilities should NOT be 100/0 or 0/100
        assert t1_prob < 1.0, f"Team1 win prob should not be 100%, got {t1_prob}"
        assert t2_prob < 1.0, f"Team2 win prob should not be 100%, got {t2_prob}"
        assert t1_prob > 0.0, f"Team1 win prob should not be 0%, got {t1_prob}"
        assert t2_prob > 0.0, f"Team2 win prob should not be 0%, got {t2_prob}"
        
        # Probabilities should sum to ~1
        assert abs(t1_prob + t2_prob - 1.0) < 0.01, f"Probabilities should sum to 1, got {t1_prob + t2_prob}"
        
        print(f"✓ Simulation probabilities realistic: {t1_prob*100:.1f}% vs {t2_prob*100:.1f}%")
    
    def test_simulation_has_predicted_scores(self):
        """Simulation should include mean_team1_score and mean_team2_score"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        sim = data.get("simulation", {})
        
        # Check mean scores exist
        assert "mean_team1_score" in sim, "mean_team1_score should exist in simulation"
        assert "mean_team2_score" in sim, "mean_team2_score should exist in simulation"
        
        t1_score = sim["mean_team1_score"]
        t2_score = sim["mean_team2_score"]
        
        # Scores should be realistic cricket totals (50-300)
        assert 50 <= t1_score <= 300, f"Team1 score {t1_score} should be between 50-300"
        assert 50 <= t2_score <= 300, f"Team2 score {t2_score} should be between 50-300"
        
        print(f"✓ Predicted scores: {t1_score} vs {t2_score}")
    
    def test_simulation_50k_simulations(self):
        """Simulation should run 50,000 simulations"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        sim = data.get("simulation", {})
        assert sim.get("simulations") == 50000, f"Expected 50000 simulations, got {sim.get('simulations')}"
        
        print("✓ 50,000 simulations confirmed")
    
    def test_simulation_batting_first_win_pct(self):
        """Simulation should include batting_first_win_pct"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        sim = data.get("simulation", {})
        assert "batting_first_win_pct" in sim, "batting_first_win_pct should exist"
        
        pct = sim["batting_first_win_pct"]
        assert 0 <= pct <= 100, f"batting_first_win_pct {pct} should be 0-100"
        
        print(f"✓ Batting first wins {pct}% of simulations")


class TestEdgeReasons:
    """Test edge_reasons array is populated with explanation strings"""
    
    def test_edge_reasons_populated_with_market_odds(self):
        """edge_reasons should be populated when market odds provided"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        edge_reasons = data.get("edge_reasons", [])
        assert isinstance(edge_reasons, list), "edge_reasons should be a list"
        assert len(edge_reasons) > 0, "edge_reasons should not be empty when market odds provided"
        
        # Each reason should be a non-empty string
        for reason in edge_reasons:
            assert isinstance(reason, str), f"Each reason should be a string, got {type(reason)}"
            assert len(reason) > 10, f"Reason should be meaningful, got: {reason}"
        
        print(f"✓ Edge reasons populated: {len(edge_reasons)} reasons")
        for r in edge_reasons:
            print(f"  - {r[:80]}...")
    
    def test_edge_reasons_explain_model_vs_market(self):
        """edge_reasons should explain model vs market discrepancy"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        edge_reasons = data.get("edge_reasons", [])
        reasons_text = " ".join(edge_reasons).lower()
        
        # Should mention model, market, or edge
        has_explanation = any(word in reasons_text for word in ["model", "market", "edge", "undervalued", "overvalued"])
        assert has_explanation, f"Edge reasons should explain model vs market: {edge_reasons}"
        
        print("✓ Edge reasons contain model/market explanation")


class TestUpcomingMatchFeatures:
    """Test features.overs=0 and features.score=0 for upcoming matches"""
    
    def test_upcoming_match_overs_zero(self):
        """Upcoming match should have features.overs=0"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        features = data.get("features", {})
        assert features.get("overs") == 0 or features.get("overs") == 0.0, \
            f"Upcoming match should have overs=0, got {features.get('overs')}"
        
        print("✓ Upcoming match has overs=0")
    
    def test_upcoming_match_score_zero(self):
        """Upcoming match should have features.score=0"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        features = data.get("features", {})
        assert features.get("score") == 0, f"Upcoming match should have score=0, got {features.get('score')}"
        
        print("✓ Upcoming match has score=0")


class TestVerdictSection:
    """Test verdict section with winner, strength, signal, edge_reasons"""
    
    def test_verdict_has_winner_and_strength(self):
        """Verdict should have winner, winner_short, strength"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        verdict = data.get("verdict", {})
        assert verdict, "Verdict object should exist"
        
        assert "winner" in verdict, "verdict.winner should exist"
        assert "winner_short" in verdict, "verdict.winner_short should exist"
        assert "strength" in verdict, "verdict.strength should exist"
        
        # Strength should be one of the valid values
        valid_strengths = ["DOMINANT", "STRONG", "SLIGHT", "TOSS-UP"]
        assert verdict["strength"] in valid_strengths, \
            f"verdict.strength should be one of {valid_strengths}, got {verdict['strength']}"
        
        print(f"✓ Verdict: {verdict['winner_short']} wins ({verdict['strength']})")
    
    def test_verdict_has_probability(self):
        """Verdict should have winner_probability"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        verdict = data.get("verdict", {})
        assert "winner_probability" in verdict, "verdict.winner_probability should exist"
        
        prob = verdict["winner_probability"]
        assert 0 < prob < 100, f"winner_probability should be 0-100, got {prob}"
        
        print(f"✓ Winner probability: {prob}%")
    
    def test_value_signal_exists(self):
        """value_signal should exist with valid signal type"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        valid_signals = ["STRONG_VALUE", "VALUE", "SMALL_EDGE", "NO_BET", "AVOID", "WAIT_FOR_MORE_DATA", "NO_MARKET"]
        signal = data.get("value_signal")
        assert signal in valid_signals, f"value_signal should be one of {valid_signals}, got {signal}"
        
        print(f"✓ Value signal: {signal}")


class TestOddsVisual:
    """Test odds_visual with team1/team2 model vs market percentages"""
    
    def test_odds_visual_has_model_percentages(self):
        """odds_visual should have team1_model_pct and team2_model_pct"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        odds_visual = data.get("odds_visual", {})
        assert odds_visual, "odds_visual should exist"
        
        assert "team1_model_pct" in odds_visual, "team1_model_pct should exist"
        assert "team2_model_pct" in odds_visual, "team2_model_pct should exist"
        
        t1_pct = odds_visual["team1_model_pct"]
        t2_pct = odds_visual["team2_model_pct"]
        
        # Should sum to ~100
        assert abs(t1_pct + t2_pct - 100) < 1, f"Model percentages should sum to 100, got {t1_pct + t2_pct}"
        
        print(f"✓ Model percentages: {t1_pct}% vs {t2_pct}%")
    
    def test_odds_visual_has_market_percentages(self):
        """odds_visual should have team1_market_pct and team2_market_pct"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        odds_visual = data.get("odds_visual", {})
        
        assert "team1_market_pct" in odds_visual, "team1_market_pct should exist"
        assert "team2_market_pct" in odds_visual, "team2_market_pct should exist"
        
        # Should match input
        assert odds_visual["team1_market_pct"] == 55.0, f"team1_market_pct should be 55, got {odds_visual['team1_market_pct']}"
        assert odds_visual["team2_market_pct"] == 45.0, f"team2_market_pct should be 45, got {odds_visual['team2_market_pct']}"
        
        print("✓ Market percentages match input: 55% vs 45%")


class TestBettingScenarios:
    """Test betting scenarios with HIGH/MEDIUM confidence badges"""
    
    def test_betting_scenarios_exist(self):
        """betting_scenarios array should exist"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        scenarios = data.get("betting_scenarios", [])
        assert isinstance(scenarios, list), "betting_scenarios should be a list"
        assert len(scenarios) > 0, "betting_scenarios should not be empty"
        
        print(f"✓ {len(scenarios)} betting scenarios found")
    
    def test_betting_scenarios_have_confidence(self):
        """Each betting scenario should have HIGH or MEDIUM confidence"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        scenarios = data.get("betting_scenarios", [])
        valid_confidence = ["HIGH", "MEDIUM"]
        
        for sc in scenarios:
            assert "confidence" in sc, f"Scenario should have confidence: {sc}"
            assert sc["confidence"] in valid_confidence, \
                f"Confidence should be HIGH or MEDIUM, got {sc['confidence']}"
        
        print("✓ All scenarios have valid confidence badges")


class TestPlayerImpact:
    """Test player impact from cached Playing XI"""
    
    def test_player_impact_exists(self):
        """player_impact should exist in response"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        players = data.get("player_impact", [])
        assert isinstance(players, list), "player_impact should be a list"
        assert len(players) > 0, "player_impact should not be empty"
        
        print(f"✓ {len(players)} players in impact list")
    
    def test_player_impact_has_required_fields(self):
        """Each player should have name, team, role, predicted_runs, predicted_wickets"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        players = data.get("player_impact", [])
        required_fields = ["name", "team", "role", "predicted_runs", "predicted_wickets"]
        
        for p in players[:5]:  # Check first 5 players
            for field in required_fields:
                assert field in p, f"Player should have {field}: {p}"
        
        print("✓ Players have required fields")


class TestDifferentMatches:
    """Test with different match IDs to ensure consistency"""
    
    def test_match_ipl2026_011_csk_vs_rcb(self):
        """Test CSK vs RCB match (used in previous iteration)"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_011/consult",
            json={"market_pct_team1": 30, "market_pct_team2": 70}
        )
        assert response.status_code == 200
        data = response.json()
        
        sim = data.get("simulation", {})
        assert sim.get("team1_win_prob", 0) < 1.0, "Should not be 100%"
        assert sim.get("team2_win_prob", 0) < 1.0, "Should not be 100%"
        assert "mean_team1_score" in sim, "Should have predicted scores"
        
        print(f"✓ CSK vs RCB: {sim.get('mean_team1_score')} vs {sim.get('mean_team2_score')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
