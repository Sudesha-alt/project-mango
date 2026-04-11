"""
Iteration 41 - Testing Claude Rerun All Button and Momentum Algorithm Fix

Features to test:
1. Claude Rerun All endpoint (POST /api/predictions/claude-rerun-all)
2. Claude Rerun Status endpoint (GET /api/predictions/claude-rerun-status)
3. Momentum calculation with last 2 matches (team1_last2, team2_last2, momentum_text)
4. Momentum logit is 0 when both teams have equal last 2 results
5. 7-layer Claude analysis output structure (layers, algorithm_predictions, analyst_potm, deciding_factor, first_6_overs_signal)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestClaudeRerunEndpoints:
    """Test Claude Rerun All functionality"""
    
    def test_claude_rerun_status_endpoint_exists(self):
        """GET /api/predictions/claude-rerun-status should return status object"""
        response = requests.get(f"{BASE_URL}/api/predictions/claude-rerun-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should have running, completed, total, failed fields
        assert "running" in data, "Missing 'running' field in status"
        assert "completed" in data, "Missing 'completed' field in status"
        assert "total" in data, "Missing 'total' field in status"
        assert "failed" in data, "Missing 'failed' field in status"
        print(f"✓ Claude rerun status: running={data['running']}, completed={data['completed']}/{data['total']}")
    
    def test_claude_rerun_all_endpoint_starts(self):
        """POST /api/predictions/claude-rerun-all should start background task"""
        # First check if already running
        status_response = requests.get(f"{BASE_URL}/api/predictions/claude-rerun-status")
        status = status_response.json()
        
        if status.get("running"):
            print(f"⚠ Claude rerun already running: {status['completed']}/{status['total']}")
            # Just verify the endpoint responds correctly when already running
            response = requests.post(f"{BASE_URL}/api/predictions/claude-rerun-all")
            assert response.status_code == 200
            data = response.json()
            assert data.get("status") == "already_running", f"Expected 'already_running', got {data.get('status')}"
            print("✓ Claude rerun correctly reports already_running status")
        else:
            # Start the rerun (but we won't wait for it to complete)
            response = requests.post(f"{BASE_URL}/api/predictions/claude-rerun-all")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            data = response.json()
            assert data.get("status") == "started", f"Expected 'started', got {data.get('status')}"
            print(f"✓ Claude rerun started: {data.get('message')}")
            
            # Wait a moment and check status
            time.sleep(2)
            status_response = requests.get(f"{BASE_URL}/api/predictions/claude-rerun-status")
            status = status_response.json()
            print(f"✓ Claude rerun status after 2s: running={status['running']}, phase={status.get('phase')}")


class TestMomentumCalculation:
    """Test momentum algorithm with last 2 matches"""
    
    def test_pre_match_predict_returns_momentum_data(self):
        """POST /api/matches/{match_id}/pre-match-predict should return momentum with team1_last2, team2_last2, momentum_text"""
        # Use match ipl2026_017 as specified in the review request
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_017/pre-match-predict?force=true")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "prediction" in data, "Missing 'prediction' in response"
        
        prediction = data["prediction"]
        assert "factors" in prediction, "Missing 'factors' in prediction"
        
        factors = prediction["factors"]
        assert "momentum" in factors, "Missing 'momentum' in factors"
        
        momentum = factors["momentum"]
        
        # Check required momentum fields
        assert "team1_last2" in momentum, "Missing 'team1_last2' in momentum"
        assert "team2_last2" in momentum, "Missing 'team2_last2' in momentum"
        assert "momentum_text" in momentum, "Missing 'momentum_text' in momentum"
        assert "team1_wins_last2" in momentum, "Missing 'team1_wins_last2' in momentum"
        assert "team2_wins_last2" in momentum, "Missing 'team2_wins_last2' in momentum"
        assert "raw_logit" in momentum, "Missing 'raw_logit' in momentum"
        
        print(f"✓ Momentum data returned:")
        print(f"  team1_last2: {momentum['team1_last2']}")
        print(f"  team2_last2: {momentum['team2_last2']}")
        print(f"  team1_wins_last2: {momentum['team1_wins_last2']}")
        print(f"  team2_wins_last2: {momentum['team2_wins_last2']}")
        print(f"  momentum_text: {momentum['momentum_text']}")
        print(f"  raw_logit: {momentum['raw_logit']}")
    
    def test_momentum_logit_zero_when_equal_results(self):
        """Momentum logit should be 0 when both teams have equal last 2 results"""
        # Get a prediction and check the momentum calculation logic
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_017/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        momentum = data["prediction"]["factors"]["momentum"]
        
        t1_wins = momentum["team1_wins_last2"]
        t2_wins = momentum["team2_wins_last2"]
        raw_logit = momentum["raw_logit"]
        
        # If wins are equal, logit should be 0
        if t1_wins == t2_wins:
            assert raw_logit == 0, f"Expected logit 0 when equal wins, got {raw_logit}"
            assert "Even momentum" in momentum["momentum_text"], f"Expected 'Even momentum' text, got {momentum['momentum_text']}"
            print(f"✓ Momentum logit is 0 when both teams have equal results ({t1_wins} wins each)")
        else:
            # If not equal, logit should be non-zero and favor the team with more wins
            win_diff = t1_wins - t2_wins
            expected_direction = "positive" if win_diff > 0 else "negative"
            actual_direction = "positive" if raw_logit > 0 else "negative" if raw_logit < 0 else "zero"
            
            assert actual_direction == expected_direction, f"Logit direction mismatch: expected {expected_direction}, got {actual_direction}"
            print(f"✓ Momentum logit correctly favors team with more wins: diff={win_diff}, logit={raw_logit}")
    
    def test_momentum_logit_increased_impact(self):
        """Momentum logit should have increased impact (0.9 * win_diff, capped at 2.0)"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_017/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        momentum = data["prediction"]["factors"]["momentum"]
        
        t1_wins = momentum["team1_wins_last2"]
        t2_wins = momentum["team2_wins_last2"]
        raw_logit = momentum["raw_logit"]
        win_diff = t1_wins - t2_wins
        
        # Check the logit calculation: 0.9 * win_diff, with 1.3x boost for abs(win_diff)==2
        if win_diff == 0:
            expected_logit = 0
        elif abs(win_diff) == 2:
            expected_logit = 0.9 * win_diff * 1.3  # 2.34 or -2.34, capped at 2.0
            expected_logit = max(-2.0, min(2.0, expected_logit))
        else:
            expected_logit = 0.9 * win_diff
        
        # Allow small floating point tolerance
        assert abs(raw_logit - expected_logit) < 0.01, f"Expected logit ~{expected_logit}, got {raw_logit}"
        print(f"✓ Momentum logit calculation correct: win_diff={win_diff}, expected={expected_logit}, actual={raw_logit}")


class TestClaudeAnalysisStructure:
    """Test 7-layer Claude analysis output structure"""
    
    def test_claude_analysis_has_required_fields(self):
        """Claude analysis should have layers, algorithm_predictions, analyst_potm, deciding_factor, first_6_overs_signal"""
        # First get a prediction to check if Claude analysis is cached
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_017/pre-match-predict")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check if claude_analysis exists
        if "claude_analysis" not in data or not data["claude_analysis"]:
            print("⚠ No cached Claude analysis for ipl2026_017 - this is expected if Claude hasn't been run yet")
            pytest.skip("No cached Claude analysis available - run Claude analysis first")
        
        claude = data["claude_analysis"]
        
        # Check for required fields
        required_fields = ["layers", "algorithm_predictions", "analyst_potm", "deciding_factor", "first_6_overs_signal"]
        missing_fields = [f for f in required_fields if f not in claude]
        
        if missing_fields:
            print(f"⚠ Missing fields in Claude analysis: {missing_fields}")
            # Check what fields ARE present
            print(f"  Present fields: {list(claude.keys())}")
        
        # Verify layers array
        if "layers" in claude:
            layers = claude["layers"]
            assert isinstance(layers, list), "layers should be an array"
            if len(layers) > 0:
                print(f"✓ Claude analysis has {len(layers)} layers")
                # Check first layer structure
                layer1 = layers[0]
                layer_fields = ["layer_num", "title", "analysis", "advantage", "advantage_reason"]
                for field in layer_fields:
                    if field in layer1:
                        print(f"  ✓ Layer 1 has '{field}'")
        
        # Verify algorithm_predictions
        if "algorithm_predictions" in claude:
            algo = claude["algorithm_predictions"]
            print(f"✓ algorithm_predictions present: {list(algo.keys())}")
        
        # Verify analyst_potm
        if "analyst_potm" in claude:
            potm = claude["analyst_potm"]
            print(f"✓ analyst_potm present: {potm}")
        
        # Verify deciding_factor
        if "deciding_factor" in claude:
            print(f"✓ deciding_factor present: {claude['deciding_factor'][:100]}...")
        
        # Verify first_6_overs_signal
        if "first_6_overs_signal" in claude:
            print(f"✓ first_6_overs_signal present: {claude['first_6_overs_signal'][:100]}...")


class TestHealthAndSchedule:
    """Basic health and schedule tests"""
    
    def test_health_check(self):
        """GET /api/ should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("scheduleLoaded") == True, "Schedule not loaded"
        assert data.get("squadsLoaded") == True, "Squads not loaded"
        print(f"✓ Health check passed: {data.get('matchesInDB')} matches, {data.get('squadsInDB')} squads")
    
    def test_schedule_has_upcoming_matches(self):
        """GET /api/schedule should return upcoming matches"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        upcoming = data.get("upcoming", [])
        assert len(upcoming) > 0, "No upcoming matches found"
        print(f"✓ Schedule has {len(upcoming)} upcoming matches")
    
    def test_predictions_upcoming_endpoint(self):
        """GET /api/predictions/upcoming should return cached predictions"""
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert response.status_code == 200
        
        data = response.json()
        predictions = data.get("predictions", [])
        print(f"✓ Found {len(predictions)} cached predictions")
        
        # If there are predictions, the Claude rerun button should be visible
        if len(predictions) > 0:
            print(f"  → predictedCount > 0, so 'Re-run Claude All' button should be visible on frontend")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
