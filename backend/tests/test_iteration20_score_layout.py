"""
Iteration 20 Tests: Score on Match Cards + ConsultantDashboard Layout
Tests:
1. GET /api/schedule returns 'score' field for matches with live data
2. POST /api/scheduler/promote-now syncs live scores to schedule
3. Backend startup syncs existing live snapshot scores to schedule
4. Match ipl2026_008 has score 'MI 41/2 (6 ov)' on schedule
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestScoreOnMatchCards:
    """Test that scores appear on match cards after live data fetch"""
    
    def test_schedule_returns_score_field(self):
        """GET /api/schedule should return 'score' field for matches with live data"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        assert "matches" in data
        assert "live" in data
        
        # Find ipl2026_008 (MI vs DC) which should have score
        live_matches = data.get("live", [])
        mi_dc_match = None
        for match in live_matches:
            if match.get("matchId") == "ipl2026_008":
                mi_dc_match = match
                break
        
        assert mi_dc_match is not None, "Match ipl2026_008 not found in live matches"
        assert "score" in mi_dc_match, "Score field missing from match ipl2026_008"
        assert mi_dc_match["score"] is not None, "Score is None for match ipl2026_008"
        print(f"Score for ipl2026_008: {mi_dc_match['score']}")
    
    def test_mi_dc_match_has_correct_score(self):
        """Match ipl2026_008 should have score 'MI 41/2 (6 ov)'"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        live_matches = data.get("live", [])
        
        mi_dc_match = None
        for match in live_matches:
            if match.get("matchId") == "ipl2026_008":
                mi_dc_match = match
                break
        
        assert mi_dc_match is not None
        score = mi_dc_match.get("score", "")
        
        # Score should contain MI, 41/2, and 6 ov
        assert "MI" in score, f"Score should contain 'MI', got: {score}"
        assert "41/2" in score, f"Score should contain '41/2', got: {score}"
        assert "6 ov" in score, f"Score should contain '6 ov', got: {score}"
        print(f"Verified score: {score}")
    
    def test_rr_gt_match_no_score(self):
        """Match ipl2026_009 (RR vs GT) should have no score yet"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        live_matches = data.get("live", [])
        
        rr_gt_match = None
        for match in live_matches:
            if match.get("matchId") == "ipl2026_009":
                rr_gt_match = match
                break
        
        assert rr_gt_match is not None, "Match ipl2026_009 not found in live matches"
        score = rr_gt_match.get("score")
        # Score should be None or empty for RR vs GT
        assert score is None or score == "", f"RR vs GT should have no score, got: {score}"
        print(f"RR vs GT score (expected empty): {score}")


class TestSchedulerPromoteNow:
    """Test POST /api/scheduler/promote-now syncs live scores"""
    
    def test_promote_now_returns_success(self):
        """POST /api/scheduler/promote-now should return status='done'"""
        response = requests.post(f"{BASE_URL}/api/scheduler/promote-now")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "done", f"Expected status='done', got: {data}"
        assert "live_matches" in data
        print(f"Promote now result: {data}")
    
    def test_promote_now_syncs_scores(self):
        """After promote-now, schedule should have synced scores"""
        # First call promote-now
        promote_response = requests.post(f"{BASE_URL}/api/scheduler/promote-now")
        assert promote_response.status_code == 200
        
        # Then check schedule
        schedule_response = requests.get(f"{BASE_URL}/api/schedule")
        assert schedule_response.status_code == 200
        
        data = schedule_response.json()
        live_matches = data.get("live", [])
        
        # Find MI vs DC match
        mi_dc_match = None
        for match in live_matches:
            if match.get("matchId") == "ipl2026_008":
                mi_dc_match = match
                break
        
        assert mi_dc_match is not None
        assert mi_dc_match.get("score") is not None, "Score should be synced after promote-now"
        print(f"Score after promote-now: {mi_dc_match.get('score')}")


class TestMatchState:
    """Test match state endpoint returns score data"""
    
    def test_match_state_has_live_data(self):
        """GET /api/matches/{matchId}/state should return cached live data"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_008/state")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("matchId") == "ipl2026_008"
        
        # Should have liveData with score
        live_data = data.get("liveData", {})
        if live_data:
            score = live_data.get("score", {})
            if isinstance(score, dict):
                assert "runs" in score or score.get("runs") is not None
                print(f"Match state score: {score}")
            else:
                print(f"Match state liveData: {live_data}")
        else:
            # May have noLiveData flag if not fetched yet
            print(f"Match state: {data}")


class TestLiveMatchesCount:
    """Test that live matches are correctly identified"""
    
    def test_two_live_matches(self):
        """Should have 2 live matches (ipl2026_008 and ipl2026_009)"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        live_matches = data.get("live", [])
        
        assert len(live_matches) == 2, f"Expected 2 live matches, got {len(live_matches)}"
        
        match_ids = [m.get("matchId") for m in live_matches]
        assert "ipl2026_008" in match_ids, "ipl2026_008 should be live"
        assert "ipl2026_009" in match_ids, "ipl2026_009 should be live"
        print(f"Live matches: {match_ids}")


class TestHealthEndpoint:
    """Test health endpoint shows scheduler info"""
    
    def test_health_shows_scheduler_active(self):
        """GET /api/ should show scheduler is active"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        scheduler = data.get("scheduler", {})
        
        assert scheduler.get("active") == True, "Scheduler should be active"
        assert "next_runs" in scheduler
        print(f"Scheduler info: {scheduler}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
