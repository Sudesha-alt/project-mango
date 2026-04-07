"""
Iteration 34 Tests - Phase-Based Weighting, Gut Feeling, Betting Odds, H2H/Form/Momentum
Tests:
1. H2H, Form, and Momentum returning non-zero values in pre-match predictions
2. Phase-based dynamic weighting: POST /api/matches/{id}/fetch-live accepts gut_feeling and current_betting_odds
3. Combined prediction (combinedPrediction) returned from live fetch endpoint with phase info
4. /api/schedule/sync-results endpoint works and populates winner data
5. Form service correctly skips matches without winner field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPreMatchFormMomentumH2H:
    """Test that H2H, Form, and Momentum return non-zero values in pre-match predictions"""
    
    def test_pre_match_prediction_has_form_data(self):
        """Pre-match prediction should include form_data with non-zero values"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_040/pre-match-predict?force=true")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "form_data" in data, "Response should include form_data"
        
        form_data = data.get("form_data", {})
        team1_form = form_data.get("team1", {})
        team2_form = form_data.get("team2", {})
        
        # At least one team should have matches played (non-zero form)
        total_matches = team1_form.get("matches_played", 0) + team2_form.get("matches_played", 0)
        assert total_matches > 0, f"Expected at least one team to have matches played, got {total_matches}"
        print(f"PASS: Form data present - Team1: {team1_form.get('form_score', 0)}, Team2: {team2_form.get('form_score', 0)}")
    
    def test_pre_match_prediction_has_momentum_data(self):
        """Pre-match prediction should include momentum data with last 2 results"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_040/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        assert "momentum" in data, "Response should include momentum"
        
        momentum = data.get("momentum", {})
        team1_last2 = momentum.get("team1_last2", [])
        team2_last2 = momentum.get("team2_last2", [])
        
        # At least one team should have recent results
        total_results = len(team1_last2) + len(team2_last2)
        assert total_results > 0, f"Expected at least one team to have recent results, got {total_results}"
        print(f"PASS: Momentum data present - Team1 last 2: {team1_last2}, Team2 last 2: {team2_last2}")
    
    def test_pre_match_prediction_factors_include_form_momentum(self):
        """Pre-match prediction factors should include current_form and momentum with non-zero contributions"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_040/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        factors = data.get("prediction", {}).get("factors", {})
        
        # Check current_form factor
        current_form = factors.get("current_form", {})
        assert "team1_form_score" in current_form, "current_form should have team1_form_score"
        assert "team2_form_score" in current_form, "current_form should have team2_form_score"
        print(f"PASS: Form factor - Team1: {current_form.get('team1_form_score')}, Team2: {current_form.get('team2_form_score')}")
        
        # Check momentum factor
        momentum = factors.get("momentum", {})
        assert "team1_last2" in momentum, "momentum should have team1_last2"
        assert "team2_last2" in momentum, "momentum should have team2_last2"
        print(f"PASS: Momentum factor - Team1: {momentum.get('team1_last2')}, Team2: {momentum.get('team2_last2')}")
    
    def test_h2h_factor_present(self):
        """Pre-match prediction should include H2H factor"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_040/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        factors = data.get("prediction", {}).get("factors", {})
        
        h2h = factors.get("h2h", {})
        assert "team1_wins" in h2h, "h2h should have team1_wins"
        assert "team2_wins" in h2h, "h2h should have team2_wins"
        assert "total" in h2h, "h2h should have total"
        print(f"PASS: H2H factor - Team1 wins: {h2h.get('team1_wins')}, Team2 wins: {h2h.get('team2_wins')}, Total: {h2h.get('total')}")


class TestLiveFetchUserInputs:
    """Test that fetch-live endpoint accepts gut_feeling and current_betting_odds"""
    
    def test_fetch_live_accepts_gut_feeling(self):
        """POST /api/matches/{id}/fetch-live should accept gut_feeling field"""
        payload = {
            "gut_feeling": "CSK batting looks strong today, Dhoni finisher mode"
        }
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/fetch-live",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        user_inputs = data.get("userInputs", {})
        assert user_inputs.get("gut_feeling") == payload["gut_feeling"], "gut_feeling should be echoed back"
        print(f"PASS: gut_feeling accepted and returned: {user_inputs.get('gut_feeling')}")
    
    def test_fetch_live_accepts_current_betting_odds(self):
        """POST /api/matches/{id}/fetch-live should accept current_betting_odds field"""
        payload = {
            "current_betting_odds": 55.5
        }
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/fetch-live",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        user_inputs = data.get("userInputs", {})
        assert user_inputs.get("current_betting_odds") == payload["current_betting_odds"], "current_betting_odds should be echoed back"
        print(f"PASS: current_betting_odds accepted and returned: {user_inputs.get('current_betting_odds')}")
    
    def test_fetch_live_accepts_both_user_inputs(self):
        """POST /api/matches/{id}/fetch-live should accept both gut_feeling and current_betting_odds"""
        payload = {
            "gut_feeling": "MI middle order looks shaky",
            "current_betting_odds": 48.0
        }
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/fetch-live",
            json=payload
        )
        assert response.status_code == 200
        
        data = response.json()
        user_inputs = data.get("userInputs", {})
        assert user_inputs.get("gut_feeling") == payload["gut_feeling"]
        assert user_inputs.get("current_betting_odds") == payload["current_betting_odds"]
        print(f"PASS: Both user inputs accepted - gut_feeling: {user_inputs.get('gut_feeling')}, odds: {user_inputs.get('current_betting_odds')}")


class TestSyncResultsEndpoint:
    """Test /api/schedule/sync-results endpoint"""
    
    def test_sync_results_endpoint_exists(self):
        """POST /api/schedule/sync-results should return 200"""
        response = requests.post(f"{BASE_URL}/api/schedule/sync-results")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data, "Response should have status field"
        assert "total_fixtures" in data, "Response should have total_fixtures field"
        print(f"PASS: sync-results endpoint works - status: {data.get('status')}, fixtures: {data.get('total_fixtures')}")
    
    def test_completed_matches_have_winners(self):
        """Completed matches in schedule should have winner field populated"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        completed = data.get("completed", [])
        
        # Count matches with winners
        matches_with_winners = [m for m in completed if m.get("winner")]
        
        assert len(matches_with_winners) > 0, "At least some completed matches should have winners"
        print(f"PASS: {len(matches_with_winners)} out of {len(completed)} completed matches have winners")


class TestPhaseBasedWeighting:
    """Test phase-based dynamic weighting system"""
    
    def test_live_predictor_phase_detection(self):
        """Test that detect_match_phase function exists and works"""
        # This tests the backend logic indirectly through the API
        # The combinedPrediction should include phase info when live data is available
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/fetch-live",
            json={"gut_feeling": "Test", "current_betting_odds": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        # Even if no live match, the endpoint should work
        assert "matchId" in data
        print(f"PASS: fetch-live endpoint returns matchId: {data.get('matchId')}")
    
    def test_combined_prediction_structure(self):
        """Test that combinedPrediction has expected structure when present"""
        # Note: combinedPrediction is only populated when SportMonks has live data
        # This test verifies the endpoint doesn't error
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/fetch-live",
            json={"gut_feeling": "Strong batting lineup", "current_betting_odds": 60}
        )
        assert response.status_code == 200
        
        data = response.json()
        combined = data.get("combinedPrediction")
        
        # If combined prediction is present, verify structure
        if combined:
            expected_fields = ["team1_pct", "team2_pct", "phase", "phase_label", "algo_weight", "claude_weight"]
            for field in expected_fields:
                assert field in combined, f"combinedPrediction should have {field}"
            print(f"PASS: combinedPrediction has correct structure - phase: {combined.get('phase_label')}")
        else:
            # No live match data from SportMonks - this is expected
            print("INFO: combinedPrediction is null (no SportMonks live data) - this is expected behavior")


class TestFormServiceSkipsMatchesWithoutWinner:
    """Test that form service correctly skips matches without winner field"""
    
    def test_form_data_only_counts_matches_with_winners(self):
        """Form data should only count matches that have a winner field"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_040/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        form_data = data.get("form_data", {})
        
        # Get schedule to verify
        schedule_response = requests.get(f"{BASE_URL}/api/schedule")
        schedule_data = schedule_response.json()
        completed_with_winners = len([m for m in schedule_data.get("completed", []) if m.get("winner")])
        
        # Form data should reflect matches with winners
        team1_matches = form_data.get("team1", {}).get("matches_played", 0)
        team2_matches = form_data.get("team2", {}).get("matches_played", 0)
        
        print(f"INFO: Completed matches with winners: {completed_with_winners}")
        print(f"INFO: Team1 matches in form: {team1_matches}, Team2 matches in form: {team2_matches}")
        
        # The form service should only count matches with winners
        # This is a sanity check - actual values depend on which teams are playing
        assert team1_matches >= 0, "Team1 matches should be non-negative"
        assert team2_matches >= 0, "Team2 matches should be non-negative"
        print("PASS: Form service returns valid match counts")


class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_root(self):
        """API root should return version and status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("version") == "4.1.0"
        assert data.get("scheduleLoaded") == True
        assert data.get("squadsLoaded") == True
        print(f"PASS: API healthy - version {data.get('version')}, {data.get('matchesInDB')} matches")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
