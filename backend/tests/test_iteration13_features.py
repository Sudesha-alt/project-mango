"""
Iteration 13 Backend Tests
==========================
Testing new features:
1. POST /api/matches/{id}/consult returns verdict object with winner, winner_short, strength, text
2. POST /api/matches/{id}/consult returns betting_scenarios array with type, title, description, confidence, timing
3. POST /api/matches/{id}/consult returns odds_visual object with team1_model_pct, team1_market_pct, edge_team1
4. POST /api/matches/{id}/consult simulation.simulations = 50000 (upgraded from 10000)
5. POST /api/matches/{id}/consult team1Short and team2Short are correct (CSK, RCB, not CHE, ROY)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MATCH_ID = "ipl2026_011"  # CSK vs RCB


class TestConsultEndpointVerdictObject:
    """Test verdict object in consult response"""
    
    @pytest.fixture(scope="class")
    def consult_response(self):
        """Run consultation once and cache for all tests in this class"""
        url = f"{BASE_URL}/api/matches/{MATCH_ID}/consult"
        payload = {
            "risk_tolerance": "balanced",
            "market_pct_team1": 30,
            "market_pct_team2": 70
        }
        # Long timeout due to GPT processing
        response = requests.post(url, json=payload, timeout=120)
        assert response.status_code == 200, f"Consult failed: {response.text}"
        return response.json()
    
    def test_verdict_object_exists(self, consult_response):
        """Verdict object should exist in response"""
        assert "verdict" in consult_response, "verdict object missing from response"
        verdict = consult_response["verdict"]
        assert isinstance(verdict, dict), "verdict should be a dict"
    
    def test_verdict_has_winner(self, consult_response):
        """Verdict should have winner field"""
        verdict = consult_response["verdict"]
        assert "winner" in verdict, "verdict.winner missing"
        assert verdict["winner"] in ["Chennai Super Kings", "Royal Challengers Bengaluru"], f"Unexpected winner: {verdict['winner']}"
    
    def test_verdict_has_winner_short(self, consult_response):
        """Verdict should have winner_short field (CSK or RCB)"""
        verdict = consult_response["verdict"]
        assert "winner_short" in verdict, "verdict.winner_short missing"
        assert verdict["winner_short"] in ["CSK", "RCB"], f"Unexpected winner_short: {verdict['winner_short']}"
    
    def test_verdict_has_strength(self, consult_response):
        """Verdict should have strength field (DOMINANT, STRONG, SLIGHT, TOSS-UP)"""
        verdict = consult_response["verdict"]
        assert "strength" in verdict, "verdict.strength missing"
        valid_strengths = ["DOMINANT", "STRONG", "SLIGHT", "TOSS-UP"]
        assert verdict["strength"] in valid_strengths, f"Unexpected strength: {verdict['strength']}"
    
    def test_verdict_has_text(self, consult_response):
        """Verdict should have text field with explanation"""
        verdict = consult_response["verdict"]
        assert "text" in verdict, "verdict.text missing"
        assert len(verdict["text"]) > 20, "verdict.text should be a meaningful explanation"
    
    def test_verdict_has_winner_probability(self, consult_response):
        """Verdict should have winner_probability field"""
        verdict = consult_response["verdict"]
        assert "winner_probability" in verdict, "verdict.winner_probability missing"
        assert 0 < verdict["winner_probability"] <= 100, f"Invalid probability: {verdict['winner_probability']}"


class TestConsultEndpointBettingScenarios:
    """Test betting_scenarios array in consult response"""
    
    @pytest.fixture(scope="class")
    def consult_response(self):
        """Run consultation once and cache for all tests in this class"""
        url = f"{BASE_URL}/api/matches/{MATCH_ID}/consult"
        payload = {
            "risk_tolerance": "balanced",
            "market_pct_team1": 30,
            "market_pct_team2": 70
        }
        response = requests.post(url, json=payload, timeout=120)
        assert response.status_code == 200, f"Consult failed: {response.text}"
        return response.json()
    
    def test_betting_scenarios_exists(self, consult_response):
        """betting_scenarios array should exist in response"""
        assert "betting_scenarios" in consult_response, "betting_scenarios missing from response"
        assert isinstance(consult_response["betting_scenarios"], list), "betting_scenarios should be a list"
    
    def test_betting_scenarios_has_items(self, consult_response):
        """betting_scenarios should have at least 1 item when market odds provided"""
        scenarios = consult_response["betting_scenarios"]
        # With market odds provided, we should get at least 1 scenario
        assert len(scenarios) >= 1, f"Expected at least 1 betting scenario, got {len(scenarios)}"
    
    def test_betting_scenario_structure(self, consult_response):
        """Each betting scenario should have required fields"""
        scenarios = consult_response["betting_scenarios"]
        if len(scenarios) > 0:
            scenario = scenarios[0]
            required_fields = ["type", "title", "description", "confidence", "timing"]
            for field in required_fields:
                assert field in scenario, f"betting_scenario missing field: {field}"
    
    def test_betting_scenario_type_values(self, consult_response):
        """Scenario type should be one of the valid types"""
        scenarios = consult_response["betting_scenarios"]
        valid_types = ["PRE_MATCH", "IN_PLAY_POWERPLAY", "PLAYER_OUTBURST", "CHASE_DYNAMIC"]
        for scenario in scenarios:
            assert scenario["type"] in valid_types, f"Invalid scenario type: {scenario['type']}"
    
    def test_betting_scenario_confidence_values(self, consult_response):
        """Scenario confidence should be HIGH or MEDIUM"""
        scenarios = consult_response["betting_scenarios"]
        valid_confidence = ["HIGH", "MEDIUM"]
        for scenario in scenarios:
            assert scenario["confidence"] in valid_confidence, f"Invalid confidence: {scenario['confidence']}"


class TestConsultEndpointOddsVisual:
    """Test odds_visual object in consult response"""
    
    @pytest.fixture(scope="class")
    def consult_response(self):
        """Run consultation once and cache for all tests in this class"""
        url = f"{BASE_URL}/api/matches/{MATCH_ID}/consult"
        payload = {
            "risk_tolerance": "balanced",
            "market_pct_team1": 30,
            "market_pct_team2": 70
        }
        response = requests.post(url, json=payload, timeout=120)
        assert response.status_code == 200, f"Consult failed: {response.text}"
        return response.json()
    
    def test_odds_visual_exists(self, consult_response):
        """odds_visual object should exist in response"""
        assert "odds_visual" in consult_response, "odds_visual missing from response"
        assert isinstance(consult_response["odds_visual"], dict), "odds_visual should be a dict"
    
    def test_odds_visual_has_model_pct(self, consult_response):
        """odds_visual should have team1_model_pct and team2_model_pct"""
        odds_visual = consult_response["odds_visual"]
        assert "team1_model_pct" in odds_visual, "odds_visual.team1_model_pct missing"
        assert "team2_model_pct" in odds_visual, "odds_visual.team2_model_pct missing"
        # Should sum to ~100
        total = odds_visual["team1_model_pct"] + odds_visual["team2_model_pct"]
        assert 99 <= total <= 101, f"Model percentages should sum to ~100, got {total}"
    
    def test_odds_visual_has_market_pct(self, consult_response):
        """odds_visual should have team1_market_pct and team2_market_pct when market odds provided"""
        odds_visual = consult_response["odds_visual"]
        assert "team1_market_pct" in odds_visual, "odds_visual.team1_market_pct missing"
        assert "team2_market_pct" in odds_visual, "odds_visual.team2_market_pct missing"
        # Should match input (30, 70)
        assert odds_visual["team1_market_pct"] == 30, f"Expected team1_market_pct=30, got {odds_visual['team1_market_pct']}"
        assert odds_visual["team2_market_pct"] == 70, f"Expected team2_market_pct=70, got {odds_visual['team2_market_pct']}"
    
    def test_odds_visual_has_edge(self, consult_response):
        """odds_visual should have edge_team1"""
        odds_visual = consult_response["odds_visual"]
        assert "edge_team1" in odds_visual, "odds_visual.edge_team1 missing"
        # Edge should be a number
        assert isinstance(odds_visual["edge_team1"], (int, float)), "edge_team1 should be numeric"
    
    def test_odds_visual_has_fair_odds(self, consult_response):
        """odds_visual should have team1_fair_odds and team2_fair_odds"""
        odds_visual = consult_response["odds_visual"]
        assert "team1_fair_odds" in odds_visual, "odds_visual.team1_fair_odds missing"
        assert "team2_fair_odds" in odds_visual, "odds_visual.team2_fair_odds missing"
    
    def test_odds_visual_has_overround(self, consult_response):
        """odds_visual should have overround when market odds provided"""
        odds_visual = consult_response["odds_visual"]
        assert "overround" in odds_visual, "odds_visual.overround missing"


class TestConsultEndpointSimulations:
    """Test simulation count is 50000"""
    
    @pytest.fixture(scope="class")
    def consult_response(self):
        """Run consultation once and cache for all tests in this class"""
        url = f"{BASE_URL}/api/matches/{MATCH_ID}/consult"
        payload = {
            "risk_tolerance": "balanced",
            "market_pct_team1": 30,
            "market_pct_team2": 70
        }
        response = requests.post(url, json=payload, timeout=120)
        assert response.status_code == 200, f"Consult failed: {response.text}"
        return response.json()
    
    def test_simulation_object_exists(self, consult_response):
        """simulation object should exist in response"""
        assert "simulation" in consult_response, "simulation missing from response"
        assert isinstance(consult_response["simulation"], dict), "simulation should be a dict"
    
    def test_simulation_count_is_50000(self, consult_response):
        """simulation.simulations should be 50000 (upgraded from 10000)"""
        simulation = consult_response["simulation"]
        assert "simulations" in simulation, "simulation.simulations missing"
        assert simulation["simulations"] == 50000, f"Expected 50000 simulations, got {simulation['simulations']}"


class TestConsultEndpointTeamShortNames:
    """Test team short names are correct (CSK, RCB not CHE, ROY)"""
    
    @pytest.fixture(scope="class")
    def consult_response(self):
        """Run consultation once and cache for all tests in this class"""
        url = f"{BASE_URL}/api/matches/{MATCH_ID}/consult"
        payload = {
            "risk_tolerance": "balanced",
            "market_pct_team1": 30,
            "market_pct_team2": 70
        }
        response = requests.post(url, json=payload, timeout=120)
        assert response.status_code == 200, f"Consult failed: {response.text}"
        return response.json()
    
    def test_team1short_is_csk(self, consult_response):
        """team1Short should be CSK (not CHE)"""
        assert "team1Short" in consult_response, "team1Short missing from response"
        assert consult_response["team1Short"] == "CSK", f"Expected team1Short=CSK, got {consult_response['team1Short']}"
    
    def test_team2short_is_rcb(self, consult_response):
        """team2Short should be RCB (not ROY)"""
        assert "team2Short" in consult_response, "team2Short missing from response"
        assert consult_response["team2Short"] == "RCB", f"Expected team2Short=RCB, got {consult_response['team2Short']}"
    
    def test_odds_visual_team_shorts(self, consult_response):
        """odds_visual should have correct team short names"""
        odds_visual = consult_response["odds_visual"]
        assert odds_visual.get("team1_short") == "CSK", f"Expected odds_visual.team1_short=CSK, got {odds_visual.get('team1_short')}"
        assert odds_visual.get("team2_short") == "RCB", f"Expected odds_visual.team2_short=RCB, got {odds_visual.get('team2_short')}"
    
    def test_verdict_winner_short_is_valid(self, consult_response):
        """verdict.winner_short should be CSK or RCB"""
        verdict = consult_response["verdict"]
        assert verdict["winner_short"] in ["CSK", "RCB"], f"Expected winner_short to be CSK or RCB, got {verdict['winner_short']}"


class TestHealthAndBasicEndpoints:
    """Basic health and endpoint tests"""
    
    def test_api_health(self):
        """API root should return health info"""
        response = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Gamble Consultant" in data["message"]
    
    def test_match_exists(self):
        """Match ipl2026_011 should exist in schedule"""
        response = requests.get(f"{BASE_URL}/api/schedule", timeout=10)
        assert response.status_code == 200
        data = response.json()
        matches = data.get("matches", [])
        match_ids = [m.get("matchId") for m in matches]
        assert MATCH_ID in match_ids, f"Match {MATCH_ID} not found in schedule"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
