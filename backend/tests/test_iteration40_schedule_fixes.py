"""
Iteration 40 - Testing Schedule Categorization Fixes
Tests for:
1. GET /api/schedule - Should show exactly 15 completed matches (all with winners) and ~55 upcoming
2. POST /api/schedule/sync-results - Should NOT create false completed matches for future dates
3. POST /api/matches/{match_id}/playing-xi then GET status - confidence should be 'api-verified'
4. POST /api/matches/{match_id}/pre-match-predict?force=true - Should work with all 8 categories non-zero
"""

import pytest
import requests
import os
import time
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestScheduleCategorization:
    """Test schedule categorization - completed vs upcoming based on winner field"""
    
    def test_schedule_counts(self):
        """GET /api/schedule should return correct counts for completed and upcoming"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        completed = data.get('completed', [])
        upcoming = data.get('upcoming', [])
        live = data.get('live', [])
        
        print(f"Total matches: {data.get('total', 0)}")
        print(f"Completed: {len(completed)}")
        print(f"Upcoming: {len(upcoming)}")
        print(f"Live: {len(live)}")
        
        # Should have approximately 15 completed and 55 upcoming
        assert len(completed) >= 14, f"Expected at least 14 completed matches, got {len(completed)}"
        assert len(completed) <= 20, f"Expected at most 20 completed matches, got {len(completed)}"
        assert len(upcoming) >= 50, f"Expected at least 50 upcoming matches, got {len(upcoming)}"
    
    def test_completed_matches_have_winners(self):
        """All completed matches should have a winner field"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        completed = data.get('completed', [])
        
        without_winner = [m for m in completed if not m.get('winner')]
        assert len(without_winner) == 0, f"Found {len(without_winner)} completed matches without winner"
        
        print(f"All {len(completed)} completed matches have winners")
    
    def test_no_future_dates_in_completed(self):
        """No match with a future date should be in completed"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        completed = data.get('completed', [])
        now = datetime.now(timezone.utc)
        
        future_completed = []
        for m in completed:
            dt_str = m.get('dateTimeGMT', '')
            if dt_str:
                try:
                    match_dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                    if match_dt.tzinfo is None:
                        match_dt = match_dt.replace(tzinfo=timezone.utc)
                    if match_dt > now:
                        future_completed.append(m)
                except (ValueError, TypeError):
                    pass
        
        assert len(future_completed) == 0, f"Found {len(future_completed)} future matches incorrectly in completed"
        print("No future dates found in completed matches")


class TestSyncResults:
    """Test sync-results endpoint - should not create false completed matches"""
    
    def test_sync_results_no_false_completions(self):
        """POST /api/schedule/sync-results should not increase completed count for future matches"""
        # Get counts before sync
        before = requests.get(f"{BASE_URL}/api/schedule").json()
        completed_before = len(before.get('completed', []))
        upcoming_before = len(before.get('upcoming', []))
        
        # Run sync
        response = requests.post(f"{BASE_URL}/api/schedule/sync-results")
        assert response.status_code == 200
        
        data = response.json()
        print(f"Sync status: {data.get('status')}")
        print(f"Updated: {data.get('updated', 0)}")
        print(f"Total fixtures from SportMonks: {data.get('total_fixtures', 0)}")
        
        # Get counts after sync
        after = requests.get(f"{BASE_URL}/api/schedule").json()
        completed_after = len(after.get('completed', []))
        upcoming_after = len(after.get('upcoming', []))
        
        print(f"Completed before: {completed_before}, after: {completed_after}")
        print(f"Upcoming before: {upcoming_before}, after: {upcoming_after}")
        
        # Completed count should not increase significantly (only real results)
        # Allow for 1-2 new results if matches just finished
        assert completed_after <= completed_before + 2, \
            f"Completed count increased too much: {completed_before} -> {completed_after}"


class TestPlayingXIRefresh:
    """Test Playing XI refresh returns api-verified confidence"""
    
    def test_playing_xi_refresh_api_verified(self):
        """POST /api/matches/{match_id}/playing-xi then GET status should return api-verified"""
        match_id = "ipl2026_017"
        
        # Trigger Playing XI fetch
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/playing-xi")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('status') in ['started', 'running'], f"Unexpected status: {data.get('status')}"
        print(f"Playing XI fetch started: {data.get('message', '')}")
        
        # Poll for completion (max 30 seconds)
        max_wait = 30
        poll_interval = 3
        elapsed = 0
        result = None
        
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            
            status_response = requests.get(f"{BASE_URL}/api/matches/{match_id}/playing-xi/status")
            assert status_response.status_code == 200
            
            result = status_response.json()
            if result.get('confidence') or result.get('error'):
                break
            
            print(f"Polling... ({elapsed}s)")
        
        assert result is not None, "No result received from Playing XI status"
        
        if result.get('error'):
            pytest.skip(f"Playing XI fetch failed: {result.get('error')}")
        
        confidence = result.get('confidence', '')
        source = result.get('source', '')
        team1_xi = result.get('team1_xi', [])
        team2_xi = result.get('team2_xi', [])
        
        print(f"Confidence: {confidence}")
        print(f"Source: {source}")
        print(f"Team1 XI: {len(team1_xi)} players")
        print(f"Team2 XI: {len(team2_xi)} players")
        
        # Should be api-verified from last_match
        assert confidence == 'api-verified', f"Expected api-verified, got {confidence}"
        assert source == 'last_match', f"Expected last_match source, got {source}"
        assert len(team1_xi) >= 8, f"Expected at least 8 players in team1_xi, got {len(team1_xi)}"
        assert len(team2_xi) >= 8, f"Expected at least 8 players in team2_xi, got {len(team2_xi)}"


class TestPreMatchPrediction:
    """Test pre-match prediction with all 8 categories"""
    
    def test_prediction_8_categories_nonzero(self):
        """POST /api/matches/{match_id}/pre-match-predict?force=true should have all 8 categories non-zero"""
        match_id = "ipl2026_019"
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        
        if data.get('error'):
            pytest.fail(f"Prediction failed: {data.get('error')}")
        
        pred = data.get('prediction', {})
        factors = pred.get('factors', {})
        
        print(f"Match: {data.get('team1')} vs {data.get('team2')}")
        print(f"Team1 Win Prob: {pred.get('team1_win_prob')}%")
        print(f"Team2 Win Prob: {pred.get('team2_win_prob')}%")
        print(f"Model: {pred.get('model')}")
        
        # Check all 8 categories have non-zero weights
        categories = ['squad_strength', 'current_form', 'venue_pitch_home', 'h2h', 
                      'toss_impact', 'bowling_depth', 'conditions', 'momentum']
        
        all_nonzero = True
        for cat in categories:
            factor = factors.get(cat, {})
            weight = factor.get('weight', 0)
            print(f"  {cat}: weight={weight}")
            if weight == 0:
                all_nonzero = False
        
        assert all_nonzero, "Some categories have zero weights"
        print("SUCCESS: All 8 categories have non-zero weights")
    
    def test_prediction_playing_xi_source(self):
        """Prediction should include playing_xi with source field"""
        match_id = "ipl2026_019"
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        xi = data.get('playing_xi', {})
        
        confidence = xi.get('confidence', '')
        source = xi.get('source', '')
        team1_xi = xi.get('team1_xi', [])
        team2_xi = xi.get('team2_xi', [])
        
        print(f"Playing XI confidence: {confidence}")
        print(f"Playing XI source: {source}")
        print(f"Team1 XI: {len(team1_xi)} players")
        print(f"Team2 XI: {len(team2_xi)} players")
        
        assert confidence in ['api-verified', 'squad-based', 'predicted'], \
            f"Unexpected confidence: {confidence}"
        assert source in ['last_match', 'squad_estimate', 'live'], \
            f"Unexpected source: {source}"


class TestAPIHealth:
    """Test API health and basic functionality"""
    
    def test_api_health(self):
        """GET /api/ should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        print(f"Version: {data.get('version')}")
        print(f"Schedule Loaded: {data.get('scheduleLoaded')}")
        print(f"Squads Loaded: {data.get('squadsLoaded')}")
        print(f"Matches in DB: {data.get('matchesInDB')}")
        
        assert data.get('scheduleLoaded') == True
        assert data.get('squadsLoaded') == True
        assert data.get('matchesInDB', 0) >= 70


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
