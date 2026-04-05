"""
Iteration 27 Tests: Live Match Discovery + Dual Prediction Models
Tests the full end-to-end live match flow:
- POST /api/matches/refresh-live-status discovers live matches from SportMonks
- GET /api/schedule shows promoted match as 'live'
- POST /api/matches/{matchId}/fetch-live returns SportMonks data with dual predictions
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestLiveMatchDiscovery:
    """Test refresh-live-status endpoint for discovering live matches"""
    
    def test_refresh_live_status_returns_correct_structure(self):
        """POST /api/matches/refresh-live-status returns expected arrays"""
        response = requests.post(f"{BASE_URL}/api/matches/refresh-live-status", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        # Verify response structure
        assert "newly_promoted" in data
        assert "still_live" in data
        assert "completed" in data
        assert "still_live_count" in data
        assert "promoted_count" in data
        assert "completed_count" in data
        assert "sportmonks_live" in data
        
        # Verify arrays are lists
        assert isinstance(data["newly_promoted"], list)
        assert isinstance(data["still_live"], list)
        assert isinstance(data["completed"], list)
        
        print(f"Refresh result: {data['still_live_count']} still live, {data['promoted_count']} promoted, {data['completed_count']} completed")
    
    def test_refresh_live_status_finds_csk_vs_srh(self):
        """Verify CSK vs SRH (ipl2026_027) is detected as live"""
        response = requests.post(f"{BASE_URL}/api/matches/refresh-live-status", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        all_live = data.get("still_live", []) + data.get("newly_promoted", [])
        
        # Find CSK vs SRH match
        csk_srh = None
        for m in all_live:
            if m.get("matchId") == "ipl2026_027":
                csk_srh = m
                break
        
        assert csk_srh is not None, "CSK vs SRH (ipl2026_027) should be in live matches"
        assert "Chennai" in csk_srh.get("team1", "") or "CSK" in csk_srh.get("team1", "")
        print(f"Found live match: {csk_srh}")


class TestScheduleLiveStatus:
    """Test that schedule reflects live match status"""
    
    def test_schedule_shows_live_match(self):
        """GET /api/schedule shows ipl2026_027 as 'live'"""
        response = requests.get(f"{BASE_URL}/api/schedule", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        live_matches = data.get("live", [])
        
        # Find CSK vs SRH
        csk_srh = None
        for m in live_matches:
            if m.get("matchId") == "ipl2026_027":
                csk_srh = m
                break
        
        assert csk_srh is not None, "ipl2026_027 should be in live matches"
        assert csk_srh.get("status") == "live"
        assert csk_srh.get("team1Short") == "CSK"
        assert csk_srh.get("team2Short") == "SRH"
        print(f"Schedule shows live: {csk_srh.get('team1Short')} vs {csk_srh.get('team2Short')} - {csk_srh.get('score')}")
    
    def test_schedule_counts(self):
        """Verify schedule returns correct counts"""
        response = requests.get(f"{BASE_URL}/api/schedule", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "live" in data
        assert "upcoming" in data
        assert "completed" in data
        assert "total" in data
        
        live_count = len(data.get("live", []))
        upcoming_count = len(data.get("upcoming", []))
        completed_count = len(data.get("completed", []))
        
        print(f"Schedule counts: {live_count} live, {upcoming_count} upcoming, {completed_count} completed, {data['total']} total")
        assert live_count >= 1, "Should have at least 1 live match"


class TestFetchLiveData:
    """Test fetch-live endpoint for live match data"""
    
    def test_fetch_live_returns_sportmonks_data(self):
        """POST /api/matches/ipl2026_027/fetch-live returns SportMonks data"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_027/fetch-live", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("matchId") == "ipl2026_027"
        assert data.get("source") == "sportmonks"
        assert "liveData" in data
        assert "sportmonks" in data
        
        print(f"Fetch live source: {data.get('source')}")
    
    def test_fetch_live_returns_claude_prediction(self):
        """Verify claudePrediction contains required fields"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_027/fetch-live", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        claude = data.get("claudePrediction")
        
        assert claude is not None, "claudePrediction should be present"
        assert "team1_win_pct" in claude, "claudePrediction should have team1_win_pct"
        assert "team2_win_pct" in claude, "claudePrediction should have team2_win_pct"
        assert "historical_factors" in claude, "claudePrediction should have historical_factors"
        
        hf = claude.get("historical_factors", {})
        assert "h2h_win_pct" in hf, "historical_factors should have h2h_win_pct"
        assert "venue_win_pct" in hf, "historical_factors should have venue_win_pct"
        assert "recent_form_pct" in hf, "historical_factors should have recent_form_pct"
        assert "toss_advantage_pct" in hf, "historical_factors should have toss_advantage_pct"
        
        print(f"Claude prediction: CSK {claude.get('team1_win_pct')}% vs SRH {claude.get('team2_win_pct')}%")
        print(f"Historical factors: {hf}")
    
    def test_fetch_live_returns_weighted_prediction(self):
        """Verify weightedPrediction contains required fields"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_027/fetch-live", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        weighted = data.get("weightedPrediction")
        
        assert weighted is not None, "weightedPrediction should be present"
        assert "team1_pct" in weighted, "weightedPrediction should have team1_pct"
        assert "team2_pct" in weighted, "weightedPrediction should have team2_pct"
        assert "alpha" in weighted, "weightedPrediction should have alpha"
        assert "H" in weighted, "weightedPrediction should have H (historical)"
        assert "L" in weighted, "weightedPrediction should have L (live)"
        assert "breakdown" in weighted, "weightedPrediction should have breakdown"
        
        breakdown = weighted.get("breakdown", {})
        assert "h2h_win_pct" in breakdown
        assert "venue_win_pct" in breakdown
        assert "run_rate_ratio" in breakdown
        assert "wickets_in_hand_ratio" in breakdown
        assert "phase_momentum" in breakdown
        
        print(f"Weighted prediction: CSK {weighted.get('team1_pct')}% vs SRH {weighted.get('team2_pct')}%")
        print(f"Alpha: {weighted.get('alpha')}, H: {weighted.get('H')}, L: {weighted.get('L')}")
    
    def test_fetch_live_returns_yet_to_bat_bowl(self):
        """Verify yetToBat and yetToBowl arrays are present"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_027/fetch-live", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert "yetToBat" in data
        assert "yetToBowl" in data
        assert isinstance(data["yetToBat"], list)
        assert isinstance(data["yetToBowl"], list)
        
        print(f"Yet to bat: {len(data['yetToBat'])} players")
        print(f"Yet to bowl: {len(data['yetToBowl'])} players")


class TestCheckStatus:
    """Test check-status endpoint"""
    
    def test_check_status_for_live_match(self):
        """POST /api/matches/ipl2026_027/check-status returns live status"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_027/check-status", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("matchId") == "ipl2026_027"
        assert "sportmonks_status" in data
        assert "is_live" in data
        assert "is_finished" in data
        
        print(f"Check status: is_live={data.get('is_live')}, is_finished={data.get('is_finished')}, status={data.get('sportmonks_status')}")


class TestLiveCurrentEndpoint:
    """Test /api/live/current endpoint"""
    
    def test_live_current_returns_live_matches(self):
        """GET /api/live/current returns live_matches array"""
        response = requests.get(f"{BASE_URL}/api/live/current", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "live_matches" in data
        assert "count" in data
        assert isinstance(data["live_matches"], list)
        
        # Should have at least 1 live match
        assert data["count"] >= 1, "Should have at least 1 live match"
        
        # Find CSK vs SRH
        csk_srh = None
        for m in data["live_matches"]:
            if m.get("matchId") == "ipl2026_027":
                csk_srh = m
                break
        
        assert csk_srh is not None, "ipl2026_027 should be in live_matches"
        print(f"Live current: {data['count']} matches - {csk_srh}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
