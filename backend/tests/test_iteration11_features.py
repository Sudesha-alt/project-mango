"""
Iteration 11 Feature Tests:
1. CricApiLivePanel only on Live tab (not on Upcoming)
2. Old PlayingXI removed from PreMatch, only PlayingXIPerformance kept
3. Venue fix: No TBD venues in schedule
4. POST /api/schedule/resolve-venues endpoint
5. Playing XI with venue_stats and buzz_confidence in GPT prompt
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestVenueResolution:
    """Test venue resolution features - TBD venues should be resolved"""
    
    def test_schedule_has_no_tbd_venues(self):
        """GET /api/schedule should return matches with real venue names, NOT 'TBD'"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        matches = data.get("matches", [])
        assert len(matches) > 0, "Schedule should have matches"
        
        # Count TBD venues
        tbd_venues = [m for m in matches if not m.get("venue") or m.get("venue") == "TBD" or m.get("venue") == ""]
        assert len(tbd_venues) == 0, f"Found {len(tbd_venues)} matches with TBD/empty venues: {[m.get('matchId') for m in tbd_venues[:5]]}"
        
        # Verify sample venues are real stadium names
        sample_venues = [m.get("venue") for m in matches[:10]]
        for venue in sample_venues:
            assert venue is not None, "Venue should not be None"
            assert venue != "TBD", "Venue should not be TBD"
            assert len(venue) > 5, f"Venue name too short: {venue}"
        
        print(f"SUCCESS: All {len(matches)} matches have real venues")
        print(f"Sample venues: {sample_venues[:5]}")
    
    def test_resolve_venues_endpoint_exists(self):
        """POST /api/schedule/resolve-venues should exist and return proper response"""
        response = requests.post(f"{BASE_URL}/api/schedule/resolve-venues")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should return no_tbd since all venues are already resolved
        assert "status" in data, "Response should have status field"
        
        if data.get("status") == "no_tbd":
            assert "message" in data, "no_tbd response should have message"
            print(f"SUCCESS: resolve-venues returned 'no_tbd' - all venues already resolved")
        else:
            # If there were TBD venues, it should return resolved status
            assert data.get("status") == "resolved", f"Unexpected status: {data.get('status')}"
            print(f"SUCCESS: resolve-venues resolved {data.get('updated', 0)} venues")
    
    def test_upcoming_matches_have_real_venues(self):
        """Upcoming matches should have real venue names"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        upcoming = data.get("upcoming", [])
        
        if len(upcoming) == 0:
            pytest.skip("No upcoming matches to test")
        
        for match in upcoming[:10]:
            venue = match.get("venue")
            assert venue is not None, f"Match {match.get('matchId')} has no venue"
            assert venue != "TBD", f"Match {match.get('matchId')} has TBD venue"
            assert len(venue) > 5, f"Match {match.get('matchId')} has invalid venue: {venue}"
        
        print(f"SUCCESS: All {len(upcoming)} upcoming matches have real venues")


class TestPlayingXIWithVenueStats:
    """Test Playing XI endpoint returns venue_stats and buzz_confidence"""
    
    def test_playing_xi_endpoint_returns_venue_stats(self):
        """POST /api/matches/{match_id}/playing-xi should return venue_stats for players"""
        # Use a match that exists - ipl2026_011 (CSK vs RCB at M Chinnaswamy Stadium)
        match_id = "ipl2026_011"
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/playing-xi", timeout=120)
        
        if response.status_code == 404:
            pytest.skip(f"Match {match_id} not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        
        # Check structure
        assert "team1_xi" in data, "Response should have team1_xi"
        assert "team2_xi" in data, "Response should have team2_xi"
        
        team1_xi = data.get("team1_xi", [])
        team2_xi = data.get("team2_xi", [])
        
        if len(team1_xi) == 0 and len(team2_xi) == 0:
            pytest.skip("No Playing XI data available yet")
        
        # Check first player has venue_stats and buzz_confidence
        if len(team1_xi) > 0:
            player = team1_xi[0]
            print(f"Sample player: {player.get('name')}")
            
            # Check for venue_stats (may be present or not depending on GPT response)
            if "venue_stats" in player:
                venue_stats = player["venue_stats"]
                print(f"  venue_stats: {venue_stats}")
                # Verify venue_stats structure
                assert isinstance(venue_stats, dict), "venue_stats should be a dict"
            
            # Check for buzz_confidence
            if "buzz_confidence" in player:
                buzz = player["buzz_confidence"]
                print(f"  buzz_confidence: {buzz}")
                assert isinstance(buzz, (int, float)), "buzz_confidence should be numeric"
                assert 0 <= buzz <= 100, f"buzz_confidence should be 0-100, got {buzz}"
            
            # Check for expected_runs and expected_wickets (always present)
            assert "expected_runs" in player, "Player should have expected_runs"
            assert "expected_wickets" in player, "Player should have expected_wickets"
            assert "luck_factor" in player, "Player should have luck_factor"
            
            print(f"  expected_runs: {player.get('expected_runs')}")
            print(f"  expected_wickets: {player.get('expected_wickets')}")
            print(f"  luck_factor: {player.get('luck_factor')}")
        
        print(f"SUCCESS: Playing XI endpoint returns proper structure with {len(team1_xi)} + {len(team2_xi)} players")
    
    def test_playing_xi_header_columns(self):
        """PlayingXIPerformance header should show 'Runs | Wkts | Buzz | Luck' columns"""
        # This is a frontend test - we verify the backend returns the data needed for these columns
        match_id = "ipl2026_008"  # MI vs DC - already has prediction
        
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert response.status_code == 200
        
        data = response.json()
        predictions = data.get("predictions", [])
        
        # Find the match prediction
        match_pred = next((p for p in predictions if p.get("matchId") == match_id), None)
        
        if not match_pred:
            pytest.skip(f"No prediction found for {match_id}")
        
        playing_xi = match_pred.get("playing_xi", {})
        team1_xi = playing_xi.get("team1_xi", [])
        
        if len(team1_xi) == 0:
            pytest.skip("No Playing XI data in prediction")
        
        # Verify each player has the fields needed for the header columns
        for player in team1_xi[:3]:
            assert "expected_runs" in player, f"Player {player.get('name')} missing expected_runs"
            assert "expected_wickets" in player, f"Player {player.get('name')} missing expected_wickets"
            assert "luck_factor" in player, f"Player {player.get('name')} missing luck_factor"
            # buzz_confidence may or may not be present depending on when prediction was made
        
        print(f"SUCCESS: Playing XI data has required columns (Runs, Wkts, Luck)")


class TestScheduleEndpoints:
    """Test schedule-related endpoints"""
    
    def test_schedule_returns_all_matches(self):
        """GET /api/schedule should return all 70 matches"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("loaded") == True, "Schedule should be loaded"
        assert data.get("total") == 70, f"Expected 70 matches, got {data.get('total')}"
        
        matches = data.get("matches", [])
        assert len(matches) == 70, f"Expected 70 matches in array, got {len(matches)}"
        
        print(f"SUCCESS: Schedule has {len(matches)} matches")
    
    def test_schedule_categorization(self):
        """Schedule should properly categorize live, upcoming, completed matches"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        live = data.get("live", [])
        upcoming = data.get("upcoming", [])
        completed = data.get("completed", [])
        
        total_categorized = len(live) + len(upcoming) + len(completed)
        total_matches = data.get("total", 0)
        
        # All matches should be categorized
        assert total_categorized == total_matches, f"Categorized {total_categorized} but total is {total_matches}"
        
        print(f"SUCCESS: Schedule categorization - Live: {len(live)}, Upcoming: {len(upcoming)}, Completed: {len(completed)}")


class TestMatchState:
    """Test match state endpoint"""
    
    def test_match_state_returns_info(self):
        """GET /api/matches/{match_id}/state should return match info"""
        match_id = "ipl2026_008"  # MI vs DC
        
        response = requests.get(f"{BASE_URL}/api/matches/{match_id}/state")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have match info
        if "info" in data:
            info = data["info"]
            assert info.get("team1") is not None, "Match should have team1"
            assert info.get("team2") is not None, "Match should have team2"
            assert info.get("venue") is not None, "Match should have venue"
            assert info.get("venue") != "TBD", "Venue should not be TBD"
            print(f"SUCCESS: Match state for {match_id}: {info.get('team1Short')} vs {info.get('team2Short')} at {info.get('venue')}")
        else:
            # May have live data instead
            assert data.get("matchId") == match_id
            print(f"SUCCESS: Match state returned for {match_id}")


class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_root(self):
        """GET /api/ should return API info"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("message") == "Gamble Consultant API"
        assert data.get("scheduleLoaded") == True
        assert data.get("matchesInDB") == 70
        
        print(f"SUCCESS: API healthy - {data.get('matchesInDB')} matches loaded")
    
    def test_predictions_upcoming(self):
        """GET /api/predictions/upcoming should return predictions"""
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert response.status_code == 200
        
        data = response.json()
        predictions = data.get("predictions", [])
        
        print(f"SUCCESS: {len(predictions)} predictions available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
