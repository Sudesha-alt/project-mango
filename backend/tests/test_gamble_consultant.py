"""
Gamble Consultant API Tests - IPL 2026 Prediction Platform v4.0.0
Tests for the new layered decision engine, consultation, and chat endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ipl-predictions-1.preview.emergentagent.com')

# Test match IDs
UPCOMING_MATCH_ID = "ipl2026_008"  # DC vs MI upcoming
LIVE_MATCH_ID = "ipl2026_007"  # CSK vs PBKS live


class TestHealthEndpointV4:
    """Health endpoint tests - /api/ - Version 4.0.0"""
    
    def test_health_returns_200(self):
        """Health endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        print("✓ Health endpoint returns 200")
    
    def test_health_has_version_4(self):
        """Health endpoint returns version 4.0.0"""
        response = requests.get(f"{BASE_URL}/api/")
        data = response.json()
        assert data.get("version") == "4.0.0", f"Expected version 4.0.0, got {data.get('version')}"
        print(f"✓ Version is {data.get('version')}")
    
    def test_health_has_gamble_consultant_message(self):
        """Health endpoint returns 'Gamble Consultant API' message"""
        response = requests.get(f"{BASE_URL}/api/")
        data = response.json()
        assert data.get("message") == "Gamble Consultant API", f"Expected 'Gamble Consultant API', got {data.get('message')}"
        print(f"✓ Message is '{data.get('message')}'")
    
    def test_health_has_gpt54_datasource(self):
        """Health endpoint returns GPT-5.4 Web Search as dataSource"""
        response = requests.get(f"{BASE_URL}/api/")
        data = response.json()
        assert data.get("dataSource") == "GPT-5.4 Web Search", f"Expected 'GPT-5.4 Web Search', got {data.get('dataSource')}"
        print(f"✓ DataSource is {data.get('dataSource')}")


class TestConsultEndpoint:
    """Consultation endpoint tests - POST /api/matches/{matchId}/consult"""
    
    def test_consult_returns_200(self):
        """Consult endpoint returns 200 status"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={},
            timeout=120
        )
        assert response.status_code == 200
        print("✓ Consult endpoint returns 200")
    
    def test_consult_returns_win_probability(self):
        """Consult returns win_probability field"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={},
            timeout=120
        )
        data = response.json()
        assert "win_probability" in data, "Missing win_probability"
        assert isinstance(data["win_probability"], (int, float))
        assert 0 <= data["win_probability"] <= 100
        print(f"✓ Win probability: {data['win_probability']}%")
    
    def test_consult_returns_value_signal(self):
        """Consult returns value_signal field with valid value"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={"market_team1_odds": 1.85, "market_team2_odds": 2.10},
            timeout=120
        )
        data = response.json()
        assert "value_signal" in data, "Missing value_signal"
        valid_signals = ["STRONG_VALUE", "VALUE", "SMALL_EDGE", "NO_BET", "AVOID", "WAIT_FOR_MORE_DATA", "NO_MARKET"]
        assert data["value_signal"] in valid_signals, f"Invalid signal: {data['value_signal']}"
        print(f"✓ Value signal: {data['value_signal']}")
    
    def test_consult_returns_fair_decimal_odds(self):
        """Consult returns fair_decimal_odds field"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={},
            timeout=120
        )
        data = response.json()
        assert "fair_decimal_odds" in data, "Missing fair_decimal_odds"
        assert isinstance(data["fair_decimal_odds"], (int, float))
        assert data["fair_decimal_odds"] >= 1.0
        print(f"✓ Fair decimal odds: {data['fair_decimal_odds']}")
    
    def test_consult_with_market_odds_returns_edge(self):
        """Consult with market odds returns edge_pct and overround"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={"market_team1_odds": 1.85, "market_team2_odds": 2.10},
            timeout=120
        )
        data = response.json()
        assert "edge_pct" in data, "Missing edge_pct"
        assert "overround" in data, "Missing overround"
        assert isinstance(data["edge_pct"], (int, float))
        print(f"✓ Edge: {data['edge_pct']}%, Overround: {data['overround']}%")
    
    def test_consult_returns_confidence(self):
        """Consult returns confidence field"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={},
            timeout=120
        )
        data = response.json()
        assert "confidence" in data, "Missing confidence"
        assert 0 <= data["confidence"] <= 1
        print(f"✓ Confidence: {data['confidence']}")
    
    def test_consult_returns_uncertainty_band(self):
        """Consult returns uncertainty_band with low and high"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={},
            timeout=120
        )
        data = response.json()
        assert "uncertainty_band" in data, "Missing uncertainty_band"
        assert "low" in data["uncertainty_band"]
        assert "high" in data["uncertainty_band"]
        print(f"✓ Uncertainty band: {data['uncertainty_band']['low']*100:.1f}% - {data['uncertainty_band']['high']*100:.1f}%")
    
    def test_consult_returns_top_drivers(self):
        """Consult returns top_drivers array"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={},
            timeout=120
        )
        data = response.json()
        assert "top_drivers" in data, "Missing top_drivers"
        assert isinstance(data["top_drivers"], list)
        print(f"✓ Top drivers: {len(data['top_drivers'])} factors")
    
    def test_consult_returns_simulation(self):
        """Consult returns simulation with 10000 simulations and score ranges"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={},
            timeout=120
        )
        data = response.json()
        assert "simulation" in data, "Missing simulation"
        sim = data["simulation"]
        assert sim.get("simulations") == 10000, f"Expected 10000 simulations, got {sim.get('simulations')}"
        assert "team1_scores" in sim
        assert "team2_scores" in sim
        # Check score ranges
        for team_key in ["team1_scores", "team2_scores"]:
            scores = sim[team_key]
            assert "p10" in scores, f"Missing p10 in {team_key}"
            assert "p90" in scores, f"Missing p90 in {team_key}"
            assert "mean" in scores, f"Missing mean in {team_key}"
        print(f"✓ Simulation: {sim['simulations']} runs, Team1 p10-p90: {sim['team1_scores']['p10']}-{sim['team1_scores']['p90']}")
    
    def test_consult_returns_features(self):
        """Consult returns features object with phase, pressure_index, etc."""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={},
            timeout=120
        )
        data = response.json()
        assert "features" in data, "Missing features"
        features = data["features"]
        required_features = ["phase", "pressure_index", "batting_depth_index", "collapse_risk"]
        for f in required_features:
            assert f in features, f"Missing feature: {f}"
        print(f"✓ Features: phase={features['phase']}, pressure={features['pressure_index']}, depth={features['batting_depth_index']}, collapse={features['collapse_risk']}")
    
    def test_consult_with_safe_risk_tolerance(self):
        """Consult with risk_tolerance='safe' adjusts recommendation"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/consult",
            json={"risk_tolerance": "safe"},
            timeout=120
        )
        data = response.json()
        assert data.get("risk_tolerance") == "safe"
        assert "bet_recommendation" in data
        print(f"✓ Safe risk tolerance: {data['bet_recommendation'][:50]}...")
    
    def test_consult_invalid_match_returns_error(self):
        """Consult for invalid match returns error"""
        response = requests.post(
            f"{BASE_URL}/api/matches/invalid_match_id/consult",
            json={},
            timeout=30
        )
        data = response.json()
        assert "error" in data
        print(f"✓ Invalid match returns error: {data['error']}")


class TestChatEndpoint:
    """Chat endpoint tests - POST /api/matches/{matchId}/chat"""
    
    def test_chat_returns_200(self):
        """Chat endpoint returns 200 status"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/chat",
            json={"question": "Should I bet?"},
            timeout=120
        )
        assert response.status_code == 200
        print("✓ Chat endpoint returns 200")
    
    def test_chat_returns_answer(self):
        """Chat returns answer in plain language"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/chat",
            json={"question": "Is this a good bet?"},
            timeout=120
        )
        data = response.json()
        assert "answer" in data, "Missing answer"
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 20  # Should be a meaningful response
        print(f"✓ Chat answer: {data['answer'][:80]}...")
    
    def test_chat_returns_consultation_summary(self):
        """Chat returns consultation_summary with win_probability and value_signal"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/chat",
            json={"question": "What are the odds?"},
            timeout=120
        )
        data = response.json()
        assert "consultation_summary" in data, "Missing consultation_summary"
        summary = data["consultation_summary"]
        assert "win_probability" in summary
        assert "value_signal" in summary
        print(f"✓ Consultation summary: {summary['win_probability']}% win, signal={summary['value_signal']}")
    
    def test_chat_with_market_odds(self):
        """Chat with market odds includes edge in response"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/chat",
            json={
                "question": "Should I bet on the favorite?",
                "market_team1_odds": 1.85,
                "market_team2_odds": 2.10
            },
            timeout=120
        )
        data = response.json()
        assert "consultation_summary" in data
        assert "edge_pct" in data["consultation_summary"]
        print(f"✓ Chat with odds: edge={data['consultation_summary']['edge_pct']}%")
    
    def test_chat_with_risk_tolerance(self):
        """Chat respects risk_tolerance parameter"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/chat",
            json={
                "question": "Is this safe?",
                "risk_tolerance": "safe"
            },
            timeout=120
        )
        data = response.json()
        assert data.get("risk_tolerance") == "safe"
        print(f"✓ Chat with safe risk tolerance")


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still function after revamp"""
    
    def test_schedule_still_works(self):
        """GET /api/schedule still returns matches"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        assert len(data["matches"]) > 0
        print(f"✓ Schedule works: {len(data['matches'])} matches")
    
    def test_fetch_live_still_works(self):
        """POST /api/matches/{matchId}/fetch-live still works"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/fetch-live",
            json={},
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        assert "matchId" in data
        print(f"✓ Fetch live works: matchId={data['matchId']}")
    
    def test_squads_still_works(self):
        """GET /api/squads still returns squads"""
        response = requests.get(f"{BASE_URL}/api/squads")
        assert response.status_code == 200
        data = response.json()
        assert "squads" in data
        print(f"✓ Squads works: {len(data['squads'])} teams")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
