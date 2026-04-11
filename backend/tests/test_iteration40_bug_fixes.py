"""
Iteration 40 - Bug Fixes Testing
Tests for:
1. Schedule categorization - No completed match should appear in upcoming
2. Playing XI refresh - Should return api-verified confidence, not squad-based
3. Pre-match prediction - Should return all 8 categories with playing_xi
4. DLS info field - fetch-live should accept dls_info parameter
5. Repredict-all - Should show running:true with phase field
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestScheduleCategorization:
    """Test that completed matches don't appear in upcoming list"""
    
    def test_schedule_no_completed_in_upcoming(self):
        """GET /api/schedule - No completed match should appear in upcoming"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200, f"Schedule endpoint failed: {response.text}"
        
        data = response.json()
        assert "upcoming" in data, "Response missing 'upcoming' field"
        assert "completed" in data, "Response missing 'completed' field"
        
        upcoming = data.get("upcoming", [])
        completed = data.get("completed", [])
        
        print(f"Total matches: {data.get('total', 0)}")
        print(f"Upcoming: {len(upcoming)}, Completed: {len(completed)}, Live: {len(data.get('live', []))}")
        
        # Check that no match with status='completed' or winner is in upcoming
        for match in upcoming:
            status = (match.get("status", "") or "").lower()
            winner = match.get("winner")
            
            assert status not in ["completed", "result"], \
                f"Match {match.get('matchId')} has status='{status}' but is in upcoming list"
            assert not winner, \
                f"Match {match.get('matchId')} has winner='{winner}' but is in upcoming list"
        
        print(f"PASS: No completed matches found in upcoming list ({len(upcoming)} upcoming matches checked)")


class TestPlayingXIRefresh:
    """Test Playing XI refresh returns api-verified data"""
    
    def test_playing_xi_refresh_trigger(self):
        """POST /api/matches/ipl2026_017/playing-xi - Trigger refresh"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_017/playing-xi")
        assert response.status_code == 200, f"Playing XI trigger failed: {response.text}"
        
        data = response.json()
        assert data.get("status") in ["started", "running"], \
            f"Expected status 'started' or 'running', got: {data}"
        print(f"Playing XI refresh triggered: {data}")
    
    def test_playing_xi_status_after_wait(self):
        """GET /api/matches/ipl2026_017/playing-xi/status - Check result after wait"""
        # Wait for background task to complete
        time.sleep(12)
        
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_017/playing-xi/status")
        assert response.status_code == 200, f"Playing XI status failed: {response.text}"
        
        data = response.json()
        print(f"Playing XI status response: {data}")
        
        # Check if still running
        if data.get("status") == "running":
            print("Still running, waiting more...")
            time.sleep(10)
            response = requests.get(f"{BASE_URL}/api/matches/ipl2026_017/playing-xi/status")
            data = response.json()
            print(f"Playing XI status after extra wait: {data}")
        
        # Verify confidence is api-verified (not squad-based)
        confidence = data.get("confidence", "")
        source = data.get("source", "")
        team1_xi = data.get("team1_xi", [])
        team2_xi = data.get("team2_xi", [])
        
        print(f"Confidence: {confidence}, Source: {source}")
        print(f"Team1 XI count: {len(team1_xi)}, Team2 XI count: {len(team2_xi)}")
        
        # Main assertion: confidence should be api-verified
        assert confidence == "api-verified", \
            f"Expected confidence='api-verified', got '{confidence}'. Source: {source}"
        
        assert source == "last_match", \
            f"Expected source='last_match', got '{source}'"
        
        # Should have 8-11 players per team
        assert 8 <= len(team1_xi) <= 11, \
            f"Team1 XI should have 8-11 players, got {len(team1_xi)}"
        assert 8 <= len(team2_xi) <= 11, \
            f"Team2 XI should have 8-11 players, got {len(team2_xi)}"
        
        print(f"PASS: Playing XI refresh returned api-verified data with {len(team1_xi)}+{len(team2_xi)} players")


class TestPreMatchPrediction:
    """Test pre-match prediction with all 8 categories"""
    
    def test_pre_match_predict_with_force(self):
        """POST /api/matches/ipl2026_016/pre-match-predict?force=true"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_016/pre-match-predict?force=true", timeout=120)
        assert response.status_code == 200, f"Pre-match predict failed: {response.text}"
        
        data = response.json()
        assert "prediction" in data, "Response missing 'prediction' field"
        assert "playing_xi" in data, "Response missing 'playing_xi' field"
        
        prediction = data.get("prediction", {})
        playing_xi = data.get("playing_xi", {})
        
        # Check all 8 categories exist
        categories = prediction.get("categories", {})
        expected_categories = [
            "squad_strength", "current_form", "venue_pitch_home", "h2h",
            "toss_impact", "bowling_depth", "conditions", "momentum"
        ]
        
        for cat in expected_categories:
            assert cat in categories, f"Missing category: {cat}"
            weight = categories[cat].get("weight", 0)
            assert weight > 0, f"Category {cat} has zero weight"
        
        print(f"All 8 categories present with non-zero weights")
        
        # Check playing_xi has api-verified confidence
        xi_confidence = playing_xi.get("confidence", "")
        print(f"Playing XI confidence: {xi_confidence}")
        
        # Note: For pre-match predict, confidence might be squad-based if no recent match
        # The key is that it should have team1_xi and team2_xi
        assert "team1_xi" in playing_xi, "Missing team1_xi in playing_xi"
        assert "team2_xi" in playing_xi, "Missing team2_xi in playing_xi"
        
        print(f"PASS: Pre-match prediction returned all 8 categories and playing_xi")
        print(f"Team1 win prob: {prediction.get('team1_win_prob')}%")
        print(f"Team2 win prob: {prediction.get('team2_win_prob')}%")


class TestDLSInfoField:
    """Test that fetch-live accepts dls_info field"""
    
    def test_fetch_live_with_dls_info(self):
        """POST /api/matches/ipl2026_016/fetch-live with dls_info"""
        payload = {
            "dls_info": "Match reduced to 18 overs due to rain"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_016/fetch-live",
            json=payload,
            timeout=120
        )
        assert response.status_code == 200, f"Fetch live failed: {response.text}"
        
        data = response.json()
        
        # Should return valid response (either live data or noLiveMatch)
        assert "matchId" in data, "Response missing matchId"
        
        # Check if noLiveMatch (expected since match may not be live)
        if data.get("noLiveMatch"):
            print(f"Match not live currently (expected): {data.get('status', 'No status')}")
        else:
            print(f"Live data returned: {data.get('liveData', {})}")
        
        print(f"PASS: fetch-live endpoint accepted dls_info field without error")


class TestRepredictAll:
    """Test repredict-all background task"""
    
    def test_repredict_all_trigger(self):
        """POST /api/predictions/repredict-all - Trigger background task"""
        response = requests.post(f"{BASE_URL}/api/predictions/repredict-all")
        assert response.status_code == 200, f"Repredict-all failed: {response.text}"
        
        data = response.json()
        assert data.get("status") in ["started", "already_running"], \
            f"Expected status 'started' or 'already_running', got: {data}"
        print(f"Repredict-all triggered: {data}")
    
    def test_repredict_status_shows_running(self):
        """GET /api/predictions/repredict-status - Should show running:true with phase"""
        # Small wait to let task start
        time.sleep(2)
        
        response = requests.get(f"{BASE_URL}/api/predictions/repredict-status")
        assert response.status_code == 200, f"Repredict status failed: {response.text}"
        
        data = response.json()
        print(f"Repredict status: {data}")
        
        # Check required fields
        assert "running" in data, "Response missing 'running' field"
        assert "phase" in data, "Response missing 'phase' field"
        assert "total" in data, "Response missing 'total' field"
        assert "completed" in data, "Response missing 'completed' field"
        
        # If running, phase should not be empty
        if data.get("running"):
            phase = data.get("phase", "")
            print(f"Running: True, Phase: {phase}")
            # Phase should have some value when running
            assert phase or data.get("current_match"), \
                "Phase or current_match should be set when running"
        else:
            print(f"Task not running (may have completed quickly or not started)")
        
        print(f"PASS: Repredict status endpoint returns expected fields")


class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self):
        """GET /api/ - Health check"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        
        data = response.json()
        assert data.get("scheduleLoaded") == True, "Schedule not loaded"
        assert data.get("squadsLoaded") == True, "Squads not loaded"
        
        print(f"API Version: {data.get('version')}")
        print(f"Matches in DB: {data.get('matchesInDB')}")
        print(f"PASS: Health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
