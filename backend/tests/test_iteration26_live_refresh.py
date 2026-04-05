"""
Iteration 26 Tests: Live Match Refresh Status + Model Consensus Indicator

Features tested:
1. POST /api/matches/refresh-live-status - checks all live matches against SportMonks/CricAPI
2. GET /api/schedule - returns correct counts (0 live, 9 completed, 61 upcoming)
3. POST /api/matches/{matchId}/check-status - returns sportmonks_status, is_live, is_finished
4. GET /api/live/current - returns live_matches array
5. Frontend: Refresh Matches button on Live tab
6. Frontend: Model Consensus Indicator between Weighted and Claude predictions
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestLiveRefreshStatus:
    """Tests for the refresh-live-status endpoint and related features"""

    def test_api_health(self):
        """Test API is accessible"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"API health check passed: {data.get('message')}")

    def test_schedule_counts(self):
        """Test GET /api/schedule returns correct match counts"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "matches" in data
        assert "live" in data
        assert "upcoming" in data
        assert "completed" in data
        assert "total" in data
        
        # Verify counts match expected state (0 live, 9 completed after refresh)
        live_count = len(data.get("live", []))
        completed_count = len(data.get("completed", []))
        upcoming_count = len(data.get("upcoming", []))
        total = data.get("total", 0)
        
        print(f"Schedule counts - Live: {live_count}, Completed: {completed_count}, Upcoming: {upcoming_count}, Total: {total}")
        
        # Verify no live matches (both previously-live matches moved to completed)
        assert live_count == 0, f"Expected 0 live matches, got {live_count}"
        
        # Verify 9 completed matches
        assert completed_count == 9, f"Expected 9 completed matches, got {completed_count}"
        
        # Verify 61 upcoming matches
        assert upcoming_count == 61, f"Expected 61 upcoming matches, got {upcoming_count}"
        
        # Verify total is 70
        assert total == 70, f"Expected 70 total matches, got {total}"
        
        print("Schedule counts verified: 0 live, 9 completed, 61 upcoming, 70 total")

    def test_live_current_endpoint(self):
        """Test GET /api/live/current returns live_matches array"""
        response = requests.get(f"{BASE_URL}/api/live/current")
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "live_matches" in data
        assert "count" in data
        assert "sportmonks_count" in data
        
        # Verify live_matches is an array
        assert isinstance(data["live_matches"], list)
        
        # Currently no live matches
        assert data["count"] == 0, f"Expected 0 live matches, got {data['count']}"
        
        print(f"Live current endpoint: {data['count']} live matches, {data['sportmonks_count']} on SportMonks")

    def test_refresh_live_status_no_live_matches(self):
        """Test POST /api/matches/refresh-live-status when no live matches exist"""
        response = requests.post(f"{BASE_URL}/api/matches/refresh-live-status")
        assert response.status_code == 200
        data = response.json()
        
        # When no live matches, should return appropriate message
        if "message" in data:
            assert data["message"] == "No live matches to check"
            print("Refresh live status: No live matches to check")
        else:
            # If there were live matches, verify response structure
            assert "checked" in data
            assert "still_live" in data
            assert "completed" in data
            assert "still_live_count" in data
            assert "completed_count" in data
            print(f"Refresh live status: checked={data.get('checked')}, still_live={data.get('still_live_count')}, completed={data.get('completed_count')}")

    def test_check_status_for_completed_match(self):
        """Test POST /api/matches/{matchId}/check-status for a completed match"""
        # Use one of the completed matches (ipl2026_008 or ipl2026_009)
        match_id = "ipl2026_008"
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/check-status")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "matchId" in data
        assert data["matchId"] == match_id
        
        # Should have status fields
        assert "sportmonks_status" in data or "schedule_status" in data
        assert "is_live" in data
        assert "is_finished" in data
        
        print(f"Check status for {match_id}: is_live={data.get('is_live')}, is_finished={data.get('is_finished')}, schedule_status={data.get('schedule_status')}")
        
        # Since this match was moved to completed, schedule_status should be "completed"
        assert data.get("schedule_status") == "completed", f"Expected schedule_status='completed', got {data.get('schedule_status')}"

    def test_check_status_for_upcoming_match(self):
        """Test POST /api/matches/{matchId}/check-status for an upcoming match"""
        # Use an upcoming match
        match_id = "ipl2026_010"
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/check-status")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "matchId" in data
        assert data["matchId"] == match_id
        
        # Should not be live or finished
        assert data.get("is_live") == False, "Upcoming match should not be live"
        assert data.get("is_finished") == False, "Upcoming match should not be finished"
        
        print(f"Check status for upcoming {match_id}: is_live={data.get('is_live')}, is_finished={data.get('is_finished')}")

    def test_check_status_invalid_match(self):
        """Test POST /api/matches/{matchId}/check-status for non-existent match"""
        match_id = "invalid_match_id"
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/check-status")
        assert response.status_code == 200
        data = response.json()
        
        # Should return error
        assert "error" in data
        print(f"Check status for invalid match: {data.get('error')}")


class TestCompletedMatchesVerification:
    """Verify the previously-live matches are now in completed state"""

    def test_ipl2026_008_is_completed(self):
        """Verify ipl2026_008 is in completed status"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        
        completed = data.get("completed", [])
        match_ids = [m.get("matchId") for m in completed]
        
        assert "ipl2026_008" in match_ids, "ipl2026_008 should be in completed matches"
        print("ipl2026_008 verified in completed matches")

    def test_ipl2026_009_is_completed(self):
        """Verify ipl2026_009 is in completed status"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        
        completed = data.get("completed", [])
        match_ids = [m.get("matchId") for m in completed]
        
        assert "ipl2026_009" in match_ids, "ipl2026_009 should be in completed matches"
        print("ipl2026_009 verified in completed matches")


class TestModelConsensusBackend:
    """Test backend support for Model Consensus Indicator"""

    def test_fetch_live_returns_weighted_prediction(self):
        """Test that fetch-live endpoint returns weightedPrediction field"""
        # Use a completed match to test the endpoint structure
        match_id = "ipl2026_009"
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live")
        assert response.status_code == 200
        data = response.json()
        
        # Should have weightedPrediction field (may be null if no live data)
        # The field should exist in the response structure
        print(f"Fetch live response keys: {list(data.keys())}")
        
        # If there's no live match, it should return noLiveMatch: true
        if data.get("noLiveMatch"):
            print(f"No live match for {match_id} - expected behavior")
        else:
            # If there is data, verify weightedPrediction structure
            if "weightedPrediction" in data:
                wp = data["weightedPrediction"]
                if wp:
                    assert "team1_pct" in wp
                    assert "team2_pct" in wp
                    print(f"Weighted prediction: team1={wp.get('team1_pct')}%, team2={wp.get('team2_pct')}%")

    def test_match_state_endpoint(self):
        """Test GET /api/matches/{matchId}/state returns cached data"""
        match_id = "ipl2026_009"
        
        response = requests.get(f"{BASE_URL}/api/matches/{match_id}/state")
        assert response.status_code == 200
        data = response.json()
        
        assert "matchId" in data
        print(f"Match state for {match_id}: keys={list(data.keys())}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
