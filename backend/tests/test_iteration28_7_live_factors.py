"""
Iteration 28 - Test 7 Granular Live Factors in Weighted Prediction

Tests the enhanced Live factors (L) in the weighted prediction formula:
- 7 factors: CRR/RRR Pressure, Wickets in Hand, Recent Wicket Penalty, 
  Batter Confidence, New Batsman Factor, Bowler Threat, Phase Momentum
- Each factor uses real-time SportMonks data
- Backend returns them in `breakdown` dict + a new `live_context` dict
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSevenLiveFactors:
    """Test the 7 granular live factors in weighted prediction"""
    
    def test_api_health(self):
        """Test API is running"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        print(f"API version: {data['version']}")
    
    def test_get_live_match(self):
        """Find a live match to test"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        live_matches = data.get("live", [])
        print(f"Found {len(live_matches)} live matches")
        if live_matches:
            print(f"Live match: {live_matches[0].get('matchId')} - {live_matches[0].get('team1')} vs {live_matches[0].get('team2')}")
        return live_matches
    
    def test_fetch_live_returns_7_factors(self):
        """Test that fetch-live endpoint returns all 7 live factors in breakdown"""
        # First get a live match
        schedule_resp = requests.get(f"{BASE_URL}/api/schedule")
        assert schedule_resp.status_code == 200
        live_matches = schedule_resp.json().get("live", [])
        
        if not live_matches:
            pytest.skip("No live matches available for testing")
        
        match_id = live_matches[0].get("matchId")
        print(f"Testing with match: {match_id}")
        
        # Fetch live data
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={})
        assert response.status_code == 200
        data = response.json()
        
        # Check weighted prediction exists
        weighted_pred = data.get("weightedPrediction")
        assert weighted_pred is not None, "weightedPrediction should be present"
        print(f"Weighted prediction: team1={weighted_pred.get('team1_pct')}%, team2={weighted_pred.get('team2_pct')}%")
        
        # Check breakdown exists
        breakdown = weighted_pred.get("breakdown")
        assert breakdown is not None, "breakdown should be present in weightedPrediction"
        
        # Verify all 7 live factors are present
        required_live_factors = [
            "crr_pressure",
            "wickets_in_hand_ratio",
            "recent_wicket_penalty",
            "batter_confidence",
            "new_batsman_factor",
            "bowler_threat",
            "phase_momentum"
        ]
        
        for factor in required_live_factors:
            assert factor in breakdown, f"Missing live factor: {factor}"
            value = breakdown[factor]
            assert isinstance(value, (int, float)), f"{factor} should be numeric"
            assert 0.0 <= value <= 1.0, f"{factor} should be between 0 and 1, got {value}"
            print(f"  {factor}: {value}")
        
        print("All 7 live factors present and valid!")
    
    def test_live_context_returned(self):
        """Test that live_context dict is returned with active batsmen, bowler, CRR, RRR"""
        schedule_resp = requests.get(f"{BASE_URL}/api/schedule")
        live_matches = schedule_resp.json().get("live", [])
        
        if not live_matches:
            pytest.skip("No live matches available for testing")
        
        match_id = live_matches[0].get("matchId")
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={})
        assert response.status_code == 200
        data = response.json()
        
        weighted_pred = data.get("weightedPrediction")
        assert weighted_pred is not None
        
        # Check live_context exists
        live_context = weighted_pred.get("live_context")
        assert live_context is not None, "live_context should be present in weightedPrediction"
        
        # Verify live_context fields
        assert "active_batsmen" in live_context, "active_batsmen should be in live_context"
        assert "active_bowler" in live_context, "active_bowler should be in live_context"
        assert "crr" in live_context, "crr should be in live_context"
        assert "rrr" in live_context, "rrr should be in live_context"
        assert "recent_wickets_in_12" in live_context, "recent_wickets_in_12 should be in live_context"
        
        print(f"Live context:")
        print(f"  Active batsmen: {live_context.get('active_batsmen')}")
        print(f"  Active bowler: {live_context.get('active_bowler')}")
        print(f"  CRR: {live_context.get('crr')}")
        print(f"  RRR: {live_context.get('rrr')}")
        print(f"  Recent wickets in 12: {live_context.get('recent_wickets_in_12')}")
    
    def test_factor_values_in_range(self):
        """Test all factor values are between 0.0 and 1.0"""
        schedule_resp = requests.get(f"{BASE_URL}/api/schedule")
        live_matches = schedule_resp.json().get("live", [])
        
        if not live_matches:
            pytest.skip("No live matches available for testing")
        
        match_id = live_matches[0].get("matchId")
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={})
        assert response.status_code == 200
        data = response.json()
        
        weighted_pred = data.get("weightedPrediction")
        breakdown = weighted_pred.get("breakdown", {})
        
        all_factors = [
            # Historical factors
            "h2h_win_pct", "venue_win_pct", "recent_form_pct", "toss_advantage_pct",
            # Live factors
            "crr_pressure", "wickets_in_hand_ratio", "recent_wicket_penalty",
            "batter_confidence", "new_batsman_factor", "bowler_threat", "phase_momentum"
        ]
        
        for factor in all_factors:
            if factor in breakdown:
                value = breakdown[factor]
                assert 0.0 <= value <= 1.0, f"{factor} = {value} is out of range [0, 1]"
                print(f"✓ {factor}: {value}")
    
    def test_l_value_formula(self):
        """Test that L value = weighted sum of 7 live factors"""
        schedule_resp = requests.get(f"{BASE_URL}/api/schedule")
        live_matches = schedule_resp.json().get("live", [])
        
        if not live_matches:
            pytest.skip("No live matches available for testing")
        
        match_id = live_matches[0].get("matchId")
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={})
        assert response.status_code == 200
        data = response.json()
        
        weighted_pred = data.get("weightedPrediction")
        breakdown = weighted_pred.get("breakdown", {})
        
        # Calculate expected L value
        # L = 0.20*crr_pressure + 0.15*wickets_in_hand + 0.15*recent_wicket_penalty
        #   + 0.15*batter_confidence + 0.10*new_batsman + 0.10*bowler_threat + 0.15*phase_momentum
        expected_L = (
            0.20 * breakdown.get("crr_pressure", 0) +
            0.15 * breakdown.get("wickets_in_hand_ratio", 0) +
            0.15 * breakdown.get("recent_wicket_penalty", 0) +
            0.15 * breakdown.get("batter_confidence", 0) +
            0.10 * breakdown.get("new_batsman_factor", 0) +
            0.10 * breakdown.get("bowler_threat", 0) +
            0.15 * breakdown.get("phase_momentum", 0)
        )
        
        actual_L = weighted_pred.get("L", 0)
        
        print(f"Expected L: {expected_L:.4f}")
        print(f"Actual L: {actual_L:.4f}")
        
        # Allow small floating point tolerance
        assert abs(expected_L - actual_L) < 0.01, f"L value mismatch: expected {expected_L}, got {actual_L}"
        print("✓ L value formula verified!")
    
    def test_historical_factors_present(self):
        """Test that historical factors (H) are also present in breakdown"""
        schedule_resp = requests.get(f"{BASE_URL}/api/schedule")
        live_matches = schedule_resp.json().get("live", [])
        
        if not live_matches:
            pytest.skip("No live matches available for testing")
        
        match_id = live_matches[0].get("matchId")
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={})
        assert response.status_code == 200
        data = response.json()
        
        weighted_pred = data.get("weightedPrediction")
        breakdown = weighted_pred.get("breakdown", {})
        
        historical_factors = ["h2h_win_pct", "venue_win_pct", "recent_form_pct", "toss_advantage_pct"]
        
        for factor in historical_factors:
            assert factor in breakdown, f"Missing historical factor: {factor}"
            print(f"✓ {factor}: {breakdown[factor]}")
    
    def test_alpha_and_h_l_values(self):
        """Test that alpha, H, and L values are present and valid"""
        schedule_resp = requests.get(f"{BASE_URL}/api/schedule")
        live_matches = schedule_resp.json().get("live", [])
        
        if not live_matches:
            pytest.skip("No live matches available for testing")
        
        match_id = live_matches[0].get("matchId")
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={})
        assert response.status_code == 200
        data = response.json()
        
        weighted_pred = data.get("weightedPrediction")
        
        # Check alpha (dynamic weight)
        alpha = weighted_pred.get("alpha")
        assert alpha is not None, "alpha should be present"
        assert 0.0 <= alpha <= 1.0, f"alpha should be between 0 and 1, got {alpha}"
        print(f"alpha (dynamic weight): {alpha}")
        
        # Check H (historical)
        H = weighted_pred.get("H")
        assert H is not None, "H should be present"
        assert 0.0 <= H <= 1.0, f"H should be between 0 and 1, got {H}"
        print(f"H (historical): {H}")
        
        # Check L (live)
        L = weighted_pred.get("L")
        assert L is not None, "L should be present"
        assert 0.0 <= L <= 1.0, f"L should be between 0 and 1, got {L}"
        print(f"L (live): {L}")
        
        # Check final score
        final_score = weighted_pred.get("final_score")
        assert final_score is not None, "final_score should be present"
        assert 0.0 <= final_score <= 100.0, f"final_score should be between 0 and 100, got {final_score}"
        print(f"Final score: {final_score}%")
    
    def test_team_percentages_sum_to_100(self):
        """Test that team1_pct + team2_pct = 100"""
        schedule_resp = requests.get(f"{BASE_URL}/api/schedule")
        live_matches = schedule_resp.json().get("live", [])
        
        if not live_matches:
            pytest.skip("No live matches available for testing")
        
        match_id = live_matches[0].get("matchId")
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={})
        assert response.status_code == 200
        data = response.json()
        
        weighted_pred = data.get("weightedPrediction")
        
        team1_pct = weighted_pred.get("team1_pct", 0)
        team2_pct = weighted_pred.get("team2_pct", 0)
        
        total = team1_pct + team2_pct
        print(f"Team1: {team1_pct}%, Team2: {team2_pct}%, Total: {total}%")
        
        assert abs(total - 100.0) < 0.5, f"Team percentages should sum to 100, got {total}"
        print("✓ Team percentages sum to 100%")


class TestEdgeCases:
    """Test edge cases for the 7 live factors"""
    
    def test_first_innings_no_rrr(self):
        """Test that 1st innings has no RRR (should be None)"""
        schedule_resp = requests.get(f"{BASE_URL}/api/schedule")
        live_matches = schedule_resp.json().get("live", [])
        
        if not live_matches:
            pytest.skip("No live matches available for testing")
        
        match_id = live_matches[0].get("matchId")
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={})
        assert response.status_code == 200
        data = response.json()
        
        weighted_pred = data.get("weightedPrediction")
        live_context = weighted_pred.get("live_context", {})
        innings = weighted_pred.get("innings", 1)
        
        print(f"Current innings: {innings}")
        print(f"RRR: {live_context.get('rrr')}")
        
        if innings == 1:
            # In 1st innings, RRR should be None
            assert live_context.get("rrr") is None, "RRR should be None in 1st innings"
            print("✓ RRR is None in 1st innings as expected")
        else:
            # In 2nd innings, RRR should be a number
            assert live_context.get("rrr") is not None, "RRR should be present in 2nd innings"
            print(f"✓ RRR is {live_context.get('rrr')} in 2nd innings")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
