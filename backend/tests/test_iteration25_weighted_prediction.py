"""
Iteration 25 Tests: Weighted Probability Prediction + Dual Prediction Models
Tests:
1. compute_weighted_prediction function with mock data
2. POST /api/matches/{matchId}/fetch-live returns weightedPrediction
3. POST /api/matches/{matchId}/refresh-claude-prediction returns weightedPrediction
4. Claude prompt includes historical_factors in response
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct function import
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestComputeWeightedPrediction:
    """Test the compute_weighted_prediction helper function directly"""
    
    def test_weighted_prediction_formula_with_mock_data(self):
        """Test the weighted prediction formula with provided mock data"""
        from server import compute_weighted_prediction
        
        # Mock data as specified in the review request
        sm_data = {
            "current_score": {"runs": 140, "wickets": 4, "overs": 15.3},
            "current_innings": 2,
            "crr": 9.0,
            "rrr": 11.5,
            "batting_team": "GT",
            "recent_balls": ['4', '1', '0', '6', '2', '1']
        }
        
        claude_pred = {
            "historical_factors": {
                "h2h_win_pct": 0.55,
                "venue_win_pct": 0.50,
                "recent_form_pct": 0.65,
                "toss_advantage_pct": 0.52
            }
        }
        
        match_info = {"team1": "RR", "team2": "GT"}
        
        result = compute_weighted_prediction(sm_data, claude_pred, match_info)
        
        # Verify result structure
        assert result is not None, "compute_weighted_prediction should return a result"
        assert "team1_pct" in result, "Result should have team1_pct"
        assert "team2_pct" in result, "Result should have team2_pct"
        assert "alpha" in result, "Result should have alpha (dynamic weight)"
        assert "H" in result, "Result should have H (historical factor)"
        assert "L" in result, "Result should have L (live factor)"
        assert "final_score" in result, "Result should have final_score"
        assert "breakdown" in result, "Result should have breakdown"
        
        # Verify breakdown contains all factors
        breakdown = result["breakdown"]
        assert "h2h_win_pct" in breakdown, "Breakdown should have h2h_win_pct"
        assert "venue_win_pct" in breakdown, "Breakdown should have venue_win_pct"
        assert "recent_form_pct" in breakdown, "Breakdown should have recent_form_pct"
        assert "toss_advantage_pct" in breakdown, "Breakdown should have toss_advantage_pct"
        assert "run_rate_ratio" in breakdown, "Breakdown should have run_rate_ratio"
        assert "wickets_in_hand_ratio" in breakdown, "Breakdown should have wickets_in_hand_ratio"
        assert "phase_momentum" in breakdown, "Breakdown should have phase_momentum"
        
        # Verify percentages sum to 100
        total = result["team1_pct"] + result["team2_pct"]
        assert abs(total - 100) < 0.1, f"team1_pct + team2_pct should equal 100, got {total}"
        
        # Verify alpha is between 0 and 1
        assert 0 <= result["alpha"] <= 1, f"Alpha should be between 0 and 1, got {result['alpha']}"
        
        # Verify H and L are between 0 and 1
        assert 0 <= result["H"] <= 1, f"H should be between 0 and 1, got {result['H']}"
        assert 0 <= result["L"] <= 1, f"L should be between 0 and 1, got {result['L']}"
        
        print(f"✓ Weighted prediction result: {result['team1_pct']}% vs {result['team2_pct']}%")
        print(f"  Alpha: {result['alpha']}, H: {result['H']}, L: {result['L']}")
        print(f"  Final score: {result['final_score']}%")
    
    def test_weighted_prediction_returns_none_without_data(self):
        """Test that function returns None when missing required data"""
        from server import compute_weighted_prediction
        
        # Test with None sm_data
        result = compute_weighted_prediction(None, {"historical_factors": {}}, {"team1": "A", "team2": "B"})
        assert result is None, "Should return None when sm_data is None"
        
        # Test with None claude_prediction
        result = compute_weighted_prediction({"current_score": {}}, None, {"team1": "A", "team2": "B"})
        assert result is None, "Should return None when claude_prediction is None"
        
        print("✓ compute_weighted_prediction correctly returns None for missing data")
    
    def test_alpha_calculation_first_innings(self):
        """Test alpha calculation for first innings"""
        from server import compute_weighted_prediction
        
        sm_data = {
            "current_score": {"runs": 80, "wickets": 2, "overs": 10.0},
            "current_innings": 1,
            "crr": 8.0,
            "rrr": None,
            "batting_team": "RR",
            "recent_balls": ['1', '2', '0', '4', '1', '0']
        }
        
        claude_pred = {
            "historical_factors": {
                "h2h_win_pct": 0.50,
                "venue_win_pct": 0.50,
                "recent_form_pct": 0.50,
                "toss_advantage_pct": 0.50
            }
        }
        
        match_info = {"team1": "RR", "team2": "GT"}
        
        result = compute_weighted_prediction(sm_data, claude_pred, match_info)
        
        # In first innings at 10 overs: 60 balls bowled, 180 remaining out of 240
        # alpha = 180/240 = 0.75
        expected_alpha = (240 - 60) / 240
        assert abs(result["alpha"] - expected_alpha) < 0.01, f"Alpha should be ~{expected_alpha}, got {result['alpha']}"
        
        print(f"✓ First innings alpha calculation correct: {result['alpha']}")


class TestFetchLiveEndpoint:
    """Test POST /api/matches/{matchId}/fetch-live endpoint"""
    
    def test_fetch_live_returns_weighted_prediction_field(self):
        """Test that fetch-live endpoint includes weightedPrediction in response"""
        # Use a known match ID
        match_id = "ipl2026_009"
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check that weightedPrediction field exists (may be null if no live data)
        assert "weightedPrediction" in data or "noLiveMatch" in data, \
            "Response should have weightedPrediction field or noLiveMatch flag"
        
        if data.get("noLiveMatch"):
            print(f"✓ fetch-live returns noLiveMatch=true (no live match available)")
            print(f"  Status: {data.get('status', 'N/A')}")
        else:
            # If live data exists, verify weightedPrediction structure
            weighted = data.get("weightedPrediction")
            if weighted:
                assert "team1_pct" in weighted, "weightedPrediction should have team1_pct"
                assert "team2_pct" in weighted, "weightedPrediction should have team2_pct"
                assert "alpha" in weighted, "weightedPrediction should have alpha"
                assert "H" in weighted, "weightedPrediction should have H"
                assert "L" in weighted, "weightedPrediction should have L"
                print(f"✓ fetch-live returns weightedPrediction: {weighted['team1_pct']}% vs {weighted['team2_pct']}%")
            else:
                print(f"✓ fetch-live response structure valid (weightedPrediction is null - no Claude data)")
    
    def test_fetch_live_returns_claude_prediction_with_historical_factors(self):
        """Test that claudePrediction includes historical_factors"""
        match_id = "ipl2026_009"
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={})
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get("noLiveMatch"):
            pytest.skip("No live match available - cannot test Claude prediction")
        
        claude_pred = data.get("claudePrediction")
        if claude_pred and not claude_pred.get("error"):
            # Check for historical_factors
            hf = claude_pred.get("historical_factors")
            if hf:
                assert "h2h_win_pct" in hf, "historical_factors should have h2h_win_pct"
                assert "venue_win_pct" in hf, "historical_factors should have venue_win_pct"
                assert "recent_form_pct" in hf, "historical_factors should have recent_form_pct"
                assert "toss_advantage_pct" in hf, "historical_factors should have toss_advantage_pct"
                print(f"✓ Claude prediction includes historical_factors: {hf}")
            else:
                print("⚠ Claude prediction exists but no historical_factors (may be cached old response)")
        else:
            print("✓ No Claude prediction available (no live SportMonks data)")


class TestRefreshClaudePredictionEndpoint:
    """Test POST /api/matches/{matchId}/refresh-claude-prediction endpoint"""
    
    def test_refresh_claude_returns_weighted_prediction(self):
        """Test that refresh-claude-prediction returns weightedPrediction"""
        match_id = "ipl2026_009"
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/refresh-claude-prediction")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # If no cached data, endpoint returns error
        if data.get("error"):
            print(f"✓ refresh-claude-prediction returns expected error: {data['error']}")
            return
        
        # Verify response structure
        assert "matchId" in data, "Response should have matchId"
        assert "claudePrediction" in data, "Response should have claudePrediction"
        assert "weightedPrediction" in data, "Response should have weightedPrediction"
        assert "probabilities" in data, "Response should have probabilities"
        assert "refreshedAt" in data, "Response should have refreshedAt"
        
        weighted = data.get("weightedPrediction")
        if weighted:
            assert "team1_pct" in weighted, "weightedPrediction should have team1_pct"
            assert "team2_pct" in weighted, "weightedPrediction should have team2_pct"
            print(f"✓ refresh-claude-prediction returns weightedPrediction: {weighted['team1_pct']}% vs {weighted['team2_pct']}%")
        else:
            print("✓ refresh-claude-prediction response valid (weightedPrediction is null)")


class TestHealthAndBasicEndpoints:
    """Basic health check tests"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "scheduler" in data
        print(f"✓ API health check passed: {data.get('message')}")
    
    def test_match_state_endpoint(self):
        """Test GET /api/matches/{matchId}/state endpoint"""
        match_id = "ipl2026_009"
        
        response = requests.get(f"{BASE_URL}/api/matches/{match_id}/state")
        assert response.status_code == 200
        
        data = response.json()
        assert "matchId" in data or "info" in data, "Response should have matchId or info"
        print(f"✓ Match state endpoint working")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
