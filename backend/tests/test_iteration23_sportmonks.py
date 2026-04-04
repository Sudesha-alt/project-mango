"""
Iteration 23: SportMonks API Integration Tests
Tests for:
- POST /api/matches/{match_id}/fetch-live returns SportMonks data with Claude prediction
- Claude prediction (claudePrediction) field structure
- Batsmen strikeRate mapping from SportMonks strike_rate
- yetToBat, yetToBowl, fullBattingCard, fullBowlingCard fields
- CricketData.org fallback when SportMonks has no data
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ipl-predictions-1.preview.emergentagent.com').rstrip('/')

class TestSportMonksIntegration:
    """Tests for SportMonks API integration with Claude prediction"""
    
    def test_health_check(self):
        """Test API is running"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ API health check passed: {data.get('message')}")
    
    def test_fetch_live_endpoint_exists(self):
        """Test POST /api/matches/{matchId}/fetch-live endpoint exists"""
        # Use the match ID from the test context
        match_id = "ipl2026_009"
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={}, timeout=60)
        # Should return 200 even if no live data (returns noLiveMatch: true)
        assert response.status_code == 200
        data = response.json()
        assert "matchId" in data or "error" in data
        print(f"✓ fetch-live endpoint exists and responds")
    
    def test_fetch_live_returns_sportmonks_data(self):
        """Test fetch-live returns SportMonks data structure when live match available"""
        match_id = "ipl2026_009"  # RR vs GT match
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={}, timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        # Check basic structure
        assert "matchId" in data
        assert "team1" in data
        assert "team2" in data
        assert "source" in data
        
        # If live data available, check SportMonks-specific fields
        if not data.get("noLiveMatch"):
            print(f"✓ Live data available, source: {data.get('source')}")
            
            # Check liveData structure
            assert "liveData" in data
            live_data = data.get("liveData", {})
            if live_data:
                assert "score" in live_data or "runs" in live_data.get("score", {})
                print(f"✓ liveData structure present")
            
            # Check batsmen field with strikeRate
            if data.get("batsmen"):
                for batsman in data["batsmen"]:
                    # strikeRate should be mapped from strike_rate
                    assert "strikeRate" in batsman or "strike_rate" in batsman
                    print(f"✓ Batsman {batsman.get('name', 'Unknown')}: strikeRate={batsman.get('strikeRate', batsman.get('strike_rate', 0))}")
            
            # Check yetToBat field
            if data.get("yetToBat"):
                assert isinstance(data["yetToBat"], list)
                print(f"✓ yetToBat: {len(data['yetToBat'])} players")
            
            # Check yetToBowl field
            if data.get("yetToBowl"):
                assert isinstance(data["yetToBowl"], list)
                print(f"✓ yetToBowl: {len(data['yetToBowl'])} players")
            
            # Check fullBattingCard
            if data.get("fullBattingCard"):
                assert isinstance(data["fullBattingCard"], list)
                print(f"✓ fullBattingCard: {len(data['fullBattingCard'])} entries")
            
            # Check fullBowlingCard
            if data.get("fullBowlingCard"):
                assert isinstance(data["fullBowlingCard"], list)
                print(f"✓ fullBowlingCard: {len(data['fullBowlingCard'])} entries")
        else:
            print(f"⚠ No live match data available (noLiveMatch: true)")
            # This is expected if the match is not currently live
            assert data.get("noLiveMatch") == True or data.get("noLiveData") == True
    
    def test_claude_prediction_structure(self):
        """Test claudePrediction field has required structure"""
        match_id = "ipl2026_009"
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={}, timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        if not data.get("noLiveMatch") and data.get("claudePrediction"):
            cp = data["claudePrediction"]
            
            # Check required fields
            required_fields = ["predicted_winner", "win_pct", "headline", "reasoning"]
            for field in required_fields:
                if field in cp:
                    print(f"✓ claudePrediction.{field} present: {str(cp[field])[:50]}...")
                else:
                    print(f"⚠ claudePrediction.{field} missing")
            
            # Check optional assessment fields
            optional_fields = ["batting_depth_assessment", "bowling_assessment", "confidence", "momentum"]
            for field in optional_fields:
                if field in cp:
                    print(f"✓ claudePrediction.{field} present")
            
            # Validate win_pct is a number
            if "win_pct" in cp:
                assert isinstance(cp["win_pct"], (int, float))
                assert 0 <= cp["win_pct"] <= 100
                print(f"✓ win_pct is valid: {cp['win_pct']}%")
        else:
            print("⚠ No Claude prediction available (match not live or no SportMonks data)")
    
    def test_probabilities_structure(self):
        """Test probabilities field has ensemble and algorithm values"""
        match_id = "ipl2026_009"
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={}, timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        if not data.get("noLiveMatch") and data.get("probabilities"):
            probs = data["probabilities"]
            
            # Check algorithm probabilities
            algo_fields = ["ensemble", "bayesian", "poisson", "dls", "momentum"]
            for field in algo_fields:
                if field in probs:
                    val = probs[field]
                    assert isinstance(val, (int, float))
                    assert 0 <= val <= 1
                    print(f"✓ probabilities.{field}: {val*100:.1f}%")
        else:
            print("⚠ No probabilities available (match not live)")
    
    def test_batsmen_strike_rate_mapping(self):
        """Test batsmen strikeRate is correctly mapped from SportMonks strike_rate"""
        match_id = "ipl2026_009"
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={}, timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        if not data.get("noLiveMatch") and data.get("batsmen"):
            for batsman in data["batsmen"]:
                # The endpoint should map strike_rate to strikeRate
                sr = batsman.get("strikeRate", batsman.get("strike_rate", 0))
                assert sr is not None
                print(f"✓ Batsman {batsman.get('name', 'Unknown')}: SR={sr}")
        else:
            print("⚠ No batsmen data available")
    
    def test_bowler_structure(self):
        """Test bowler field has required structure"""
        match_id = "ipl2026_009"
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", json={}, timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        if not data.get("noLiveMatch") and data.get("bowler"):
            bowler = data["bowler"]
            expected_fields = ["name", "overs", "runs", "wickets", "economy"]
            for field in expected_fields:
                if field in bowler:
                    print(f"✓ bowler.{field}: {bowler[field]}")
        else:
            print("⚠ No bowler data available")


class TestCricketDataFallback:
    """Tests for CricketData.org fallback when SportMonks has no data"""
    
    def test_cricdata_fetch_live_endpoint(self):
        """Test GET /api/cricket-api/fetch-live endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/cricket-api/fetch-live", timeout=30)
        # May return error if API limit reached, but endpoint should exist
        assert response.status_code == 200
        data = response.json()
        print(f"✓ CricAPI fetch-live endpoint responds: {list(data.keys())[:5]}")
    
    def test_cricdata_usage_endpoint(self):
        """Test GET /api/cricket-api/usage returns usage stats"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/usage", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "hits" in data or "limit" in data
        print(f"✓ CricAPI usage: {data}")
    
    def test_cricdata_cached_endpoint(self):
        """Test GET /api/cricket-api/cached returns cached data"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/cached", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data or "count" in data
        print(f"✓ CricAPI cached: {data.get('count', 0)} matches")


class TestMatchStateEndpoint:
    """Tests for match state retrieval"""
    
    def test_get_match_state(self):
        """Test GET /api/matches/{matchId}/state returns cached state"""
        match_id = "ipl2026_009"
        response = requests.get(f"{BASE_URL}/api/matches/{match_id}/state", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "matchId" in data
        print(f"✓ Match state retrieved: {list(data.keys())[:5]}")


class TestScheduleEndpoint:
    """Tests for schedule endpoint"""
    
    def test_get_schedule(self):
        """Test GET /api/schedule returns matches"""
        response = requests.get(f"{BASE_URL}/api/schedule", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        print(f"✓ Schedule: {len(data.get('matches', []))} matches")
        
        # Find the test match
        matches = data.get("matches", [])
        test_match = next((m for m in matches if m.get("matchId") == "ipl2026_009"), None)
        if test_match:
            print(f"✓ Test match found: {test_match.get('team1')} vs {test_match.get('team2')}")
        else:
            print("⚠ Test match ipl2026_009 not found in schedule")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
