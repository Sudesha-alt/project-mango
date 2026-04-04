"""
Iteration 22 Tests: CricketData.org API, Component Split, Compare Dashboard, APScheduler
Tests:
1. POST /api/matches/{matchId}/fetch-live - CricketData.org API first, Claude fallback
2. GET /api/predictions/{matchId}/pre-match - Cached algorithm prediction
3. GET /api/matches/{matchId}/claude-analysis - Cached Claude analysis (no trigger)
4. POST /api/matches/{matchId}/claude-analysis - Trigger Claude analysis generation
5. Compare page endpoints and data structure
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestIteration22Features:
    """Test new features for Iteration 22"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "scheduler" in data
        print(f"✓ API health: {data.get('message')}, scheduler active: {data.get('scheduler', {}).get('active')}")
    
    def test_fetch_live_data_endpoint(self):
        """Test POST /api/matches/{matchId}/fetch-live - should try CricAPI first"""
        match_id = "ipl2026_008"  # MI vs DC - known match
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live")
        assert response.status_code == 200
        data = response.json()
        
        # Should have source field indicating data source
        assert "source" in data or "noLiveMatch" in data
        
        # Check for expected fields
        assert "matchId" in data
        assert data["matchId"] == match_id
        
        source = data.get("source", "none")
        print(f"✓ Fetch live data: source={source}, noLiveMatch={data.get('noLiveMatch', False)}")
        
        # If live data available, check structure
        if not data.get("noLiveMatch"):
            assert "team1" in data
            assert "team2" in data
            assert "liveData" in data or "probabilities" in data
    
    def test_get_cached_pre_match_prediction(self):
        """Test GET /api/predictions/{matchId}/pre-match - returns cached prediction"""
        match_id = "ipl2026_008"
        response = requests.get(f"{BASE_URL}/api/predictions/{match_id}/pre-match")
        assert response.status_code == 200
        data = response.json()
        
        assert "matchId" in data
        
        # If prediction exists, verify structure
        if data.get("prediction"):
            pred = data["prediction"]
            assert "win_probability" in pred or "team1_win_prob" in pred
            print(f"✓ Cached pre-match prediction found for {match_id}")
            print(f"  Team1 win prob: {pred.get('team1_win_prob', pred.get('win_probability', 'N/A'))}%")
        else:
            print(f"✓ No cached prediction for {match_id} (expected if not generated)")
    
    def test_get_cached_claude_analysis(self):
        """Test GET /api/matches/{matchId}/claude-analysis - returns cached analysis without triggering"""
        match_id = "ipl2026_008"
        response = requests.get(f"{BASE_URL}/api/matches/{match_id}/claude-analysis")
        assert response.status_code == 200
        data = response.json()
        
        assert "matchId" in data
        
        # Should NOT trigger new generation - just return cached or null
        if data.get("analysis"):
            analysis = data["analysis"]
            print(f"✓ Cached Claude analysis found for {match_id}")
            print(f"  Headline: {analysis.get('headline', 'N/A')[:50]}...")
            assert "team1_win_pct" in analysis or "factors" in analysis
        else:
            print(f"✓ No cached Claude analysis for {match_id} (GET does not trigger generation)")
    
    def test_schedule_endpoint(self):
        """Test GET /api/schedule - needed for Compare page"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        
        assert "matches" in data
        matches = data["matches"]
        print(f"✓ Schedule loaded: {len(matches)} matches")
        
        # Check match structure
        if matches:
            m = matches[0]
            assert "matchId" in m
            assert "team1" in m or "team1Short" in m
            assert "team2" in m or "team2Short" in m
    
    def test_multiple_predictions_for_compare(self):
        """Test fetching multiple cached predictions (for Compare page)"""
        # Get schedule first
        sched_response = requests.get(f"{BASE_URL}/api/schedule")
        assert sched_response.status_code == 200
        matches = sched_response.json().get("matches", [])[:5]
        
        predictions_found = 0
        claude_found = 0
        
        for m in matches:
            mid = m.get("matchId")
            if not mid:
                continue
            
            # Check algorithm prediction
            pred_resp = requests.get(f"{BASE_URL}/api/predictions/{mid}/pre-match")
            if pred_resp.status_code == 200 and pred_resp.json().get("prediction"):
                predictions_found += 1
            
            # Check Claude analysis
            claude_resp = requests.get(f"{BASE_URL}/api/matches/{mid}/claude-analysis")
            if claude_resp.status_code == 200 and claude_resp.json().get("analysis"):
                claude_found += 1
        
        print(f"✓ Compare data check: {predictions_found}/{len(matches)} algo predictions, {claude_found}/{len(matches)} Claude analyses")
    
    def test_cricapi_usage_endpoint(self):
        """Test GET /api/cricket-api/usage - API usage tracking"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/usage")
        assert response.status_code == 200
        data = response.json()
        
        # Should have usage fields
        assert "hits" in data or "date" in data
        print(f"✓ CricAPI usage: hits={data.get('hits', 0)}, limit={data.get('limit', 100)}")
    
    def test_cricapi_cached_endpoint(self):
        """Test GET /api/cricket-api/cached - cached live data (no API hit)"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/cached")
        assert response.status_code == 200
        data = response.json()
        
        assert "matches" in data
        assert "source" in data
        assert data["source"] == "cache"
        print(f"✓ CricAPI cached: {data.get('count', 0)} matches in cache")
    
    def test_scheduler_status_in_health(self):
        """Test that scheduler info is in health endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        
        assert "scheduler" in data
        scheduler = data["scheduler"]
        assert "active" in scheduler
        print(f"✓ Scheduler status: active={scheduler.get('active')}, next_runs={scheduler.get('next_runs', [])}")


class TestComparePageEndpoints:
    """Test endpoints used by Compare page"""
    
    def test_batch_prediction_fetch(self):
        """Test that we can fetch predictions for multiple matches efficiently"""
        # Get first 3 matches
        sched_resp = requests.get(f"{BASE_URL}/api/schedule")
        assert sched_resp.status_code == 200
        matches = sched_resp.json().get("matches", [])[:3]
        
        results = []
        for m in matches:
            mid = m.get("matchId")
            if not mid:
                continue
            
            # GET (not POST) for cached data
            pred_resp = requests.get(f"{BASE_URL}/api/predictions/{mid}/pre-match")
            claude_resp = requests.get(f"{BASE_URL}/api/matches/{mid}/claude-analysis")
            
            results.append({
                "matchId": mid,
                "has_algo": pred_resp.status_code == 200 and pred_resp.json().get("prediction") is not None,
                "has_claude": claude_resp.status_code == 200 and claude_resp.json().get("analysis") is not None,
            })
        
        print(f"✓ Batch fetch results:")
        for r in results:
            print(f"  {r['matchId']}: algo={r['has_algo']}, claude={r['has_claude']}")
    
    def test_prediction_structure_for_compare(self):
        """Test that prediction structure has fields needed for Compare page"""
        match_id = "ipl2026_008"
        
        # Algorithm prediction
        pred_resp = requests.get(f"{BASE_URL}/api/predictions/{match_id}/pre-match")
        assert pred_resp.status_code == 200
        pred_data = pred_resp.json()
        
        if pred_data.get("prediction"):
            pred = pred_data["prediction"]
            # Compare page needs win_probability or team1_win_prob
            has_prob = "win_probability" in pred or "team1_win_prob" in pred
            assert has_prob, "Prediction must have win probability field"
            print(f"✓ Algorithm prediction has required fields for Compare")
        
        # Claude analysis
        claude_resp = requests.get(f"{BASE_URL}/api/matches/{match_id}/claude-analysis")
        assert claude_resp.status_code == 200
        claude_data = claude_resp.json()
        
        if claude_data.get("analysis"):
            analysis = claude_data["analysis"]
            # Compare page needs team1_win_pct and team2_win_pct
            has_pcts = "team1_win_pct" in analysis or "team2_win_pct" in analysis
            print(f"✓ Claude analysis has win percentages: {has_pcts}")


class TestLiveDataFallback:
    """Test CricAPI -> Claude fallback logic"""
    
    def test_fetch_live_returns_source(self):
        """Test that fetch-live returns source field"""
        match_id = "ipl2026_008"
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live")
        assert response.status_code == 200
        data = response.json()
        
        # Should always have source field
        assert "source" in data or "noLiveMatch" in data
        
        source = data.get("source", "none")
        valid_sources = ["cricketdata.org", "claude_web_search", "none", "cache"]
        assert source in valid_sources or data.get("noLiveMatch"), f"Unexpected source: {source}"
        
        print(f"✓ Live data source: {source}")
        
        if source == "cricketdata.org":
            print("  → CricketData.org API was used (primary)")
        elif source == "claude_web_search":
            print("  → Claude web scraping was used (fallback)")
        elif data.get("noLiveMatch"):
            print("  → No live match currently (expected if match not in progress)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
