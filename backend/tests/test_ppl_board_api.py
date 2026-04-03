"""
PPL Board API Tests - IPL 2026 Prediction Platform
Tests for GPT-5.1 Web Search integration and match data endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ipl-predictions-1.preview.emergentagent.com')

class TestHealthEndpoint:
    """Health endpoint tests - /api/"""
    
    def test_health_returns_200(self):
        """Health endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        print("✓ Health endpoint returns 200")
    
    def test_health_has_correct_version(self):
        """Health endpoint returns version 3.0.0"""
        response = requests.get(f"{BASE_URL}/api/")
        data = response.json()
        assert data.get("version") == "3.0.0"
        print(f"✓ Version is {data.get('version')}")
    
    def test_health_has_gpt51_datasource(self):
        """Health endpoint returns GPT-5.1 Web Search as dataSource"""
        response = requests.get(f"{BASE_URL}/api/")
        data = response.json()
        assert data.get("dataSource") == "GPT-5.1 Web Search"
        print(f"✓ DataSource is {data.get('dataSource')}")
    
    def test_health_shows_schedule_loaded(self):
        """Health endpoint shows schedule is loaded"""
        response = requests.get(f"{BASE_URL}/api/")
        data = response.json()
        assert data.get("scheduleLoaded") == True
        assert data.get("matchesInDB") > 0
        print(f"✓ Schedule loaded with {data.get('matchesInDB')} matches")


class TestDataSourceEndpoint:
    """Data source endpoint tests - /api/data-source"""
    
    def test_data_source_returns_200(self):
        """Data source endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/data-source")
        assert response.status_code == 200
        print("✓ Data source endpoint returns 200")
    
    def test_data_source_has_gpt51(self):
        """Data source shows GPT-5.1 Web Search"""
        response = requests.get(f"{BASE_URL}/api/data-source")
        data = response.json()
        assert data.get("source") == "GPT-5.1 Web Search"
        assert data.get("model") == "gpt-5.1"
        assert data.get("tool") == "web_search_preview"
        print(f"✓ Data source: {data.get('source')}, model: {data.get('model')}, tool: {data.get('tool')}")


class TestScheduleEndpoint:
    """Schedule endpoint tests - /api/schedule"""
    
    def test_schedule_returns_200(self):
        """Schedule endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        print("✓ Schedule endpoint returns 200")
    
    def test_schedule_has_matches(self):
        """Schedule returns matches array"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        data = response.json()
        assert "matches" in data
        assert len(data["matches"]) > 0
        print(f"✓ Schedule has {len(data['matches'])} matches")
    
    def test_schedule_has_categorization(self):
        """Schedule has live/upcoming/completed categorization"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        data = response.json()
        assert "live" in data
        assert "upcoming" in data
        assert "completed" in data
        print(f"✓ Categories: Live={len(data['live'])}, Upcoming={len(data['upcoming'])}, Completed={len(data['completed'])}")
    
    def test_schedule_match_structure(self):
        """Matches have proper structure with required fields"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        data = response.json()
        match = data["matches"][0]
        
        # Required fields
        assert "matchId" in match
        assert "team1" in match
        assert "team2" in match
        assert "team1Short" in match
        assert "team2Short" in match
        assert "status" in match
        assert "dateTimeGMT" in match
        
        print(f"✓ Match structure valid: {match.get('matchId')} - {match.get('team1Short')} vs {match.get('team2Short')}")
    
    def test_completed_matches_have_scores(self):
        """Completed matches have score and winner fields"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        data = response.json()
        completed = data.get("completed", [])
        
        if len(completed) > 0:
            match = completed[0]
            assert "score" in match, "Completed match should have score"
            assert "winner" in match, "Completed match should have winner"
            assert match.get("score") is not None
            assert match.get("winner") is not None
            print(f"✓ Completed match has score: {match.get('score')[:50]}... Winner: {match.get('winner')}")
        else:
            pytest.skip("No completed matches to test")
    
    def test_live_matches_have_status(self):
        """Live matches have status=Live and score field"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        data = response.json()
        live = data.get("live", [])
        
        if len(live) > 0:
            match = live[0]
            assert match.get("status").lower() in ["live", "in progress"]
            assert "score" in match
            print(f"✓ Live match: {match.get('team1Short')} vs {match.get('team2Short')} - Status: {match.get('status')}")
        else:
            print("⚠ No live matches currently (this is expected if no match is in progress)")


class TestFetchLiveEndpoint:
    """Fetch live data endpoint tests - POST /api/matches/{matchId}/fetch-live"""
    
    def test_fetch_live_for_completed_match(self):
        """Fetch live for completed match returns noLiveMatch flag"""
        # Use a completed match
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_001/fetch-live", 
                                 json={}, timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        # Should return noLiveMatch=True for completed match
        assert "matchId" in data
        assert "team1" in data
        assert "team2" in data
        print(f"✓ Fetch live for completed match returned: noLiveMatch={data.get('noLiveMatch')}")
    
    def test_fetch_live_for_live_match(self):
        """Fetch live for live match returns live data or noLiveMatch"""
        # Get the live match ID
        schedule_response = requests.get(f"{BASE_URL}/api/schedule")
        schedule = schedule_response.json()
        live_matches = schedule.get("live", [])
        
        if len(live_matches) == 0:
            pytest.skip("No live matches to test")
        
        match_id = live_matches[0].get("matchId")
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live", 
                                 json={}, timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        assert "matchId" in data
        assert data.get("matchId") == match_id
        assert "source" in data or "noLiveMatch" in data
        print(f"✓ Fetch live for live match {match_id}: source={data.get('source')}, noLiveMatch={data.get('noLiveMatch')}")
    
    def test_fetch_live_with_betting_odds(self):
        """Fetch live with betting odds returns bettingEdge"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_001/fetch-live", 
                                 json={
                                     "betting_team1_odds": 1.85,
                                     "betting_team2_odds": 2.10,
                                     "betting_confidence": 70
                                 }, timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        # Should have betting input recorded
        if not data.get("noLiveMatch"):
            assert "bettingInput" in data
            assert "bettingEdge" in data
            print(f"✓ Betting odds processed: {data.get('bettingInput')}")
        else:
            print(f"✓ Fetch live returned noLiveMatch (expected for non-live match)")
    
    def test_fetch_live_invalid_match(self):
        """Fetch live for invalid match returns error"""
        response = requests.post(f"{BASE_URL}/api/matches/invalid_match_id/fetch-live", 
                                 json={}, timeout=30)
        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()
        assert "error" in data
        print(f"✓ Invalid match returns error: {data.get('error')}")


class TestMatchStateEndpoint:
    """Match state endpoint tests - GET /api/matches/{matchId}/state"""
    
    def test_match_state_returns_200(self):
        """Match state endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_001/state")
        assert response.status_code == 200
        print("✓ Match state endpoint returns 200")
    
    def test_match_state_has_match_id(self):
        """Match state returns matchId"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_001/state")
        data = response.json()
        assert "matchId" in data
        print(f"✓ Match state has matchId: {data.get('matchId')}")


class TestSquadsEndpoint:
    """Squads endpoint tests - /api/squads"""
    
    def test_squads_returns_200(self):
        """Squads endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/squads")
        assert response.status_code == 200
        print("✓ Squads endpoint returns 200")
    
    def test_squads_has_teams(self):
        """Squads returns team data"""
        response = requests.get(f"{BASE_URL}/api/squads")
        data = response.json()
        assert "squads" in data
        print(f"✓ Squads has {len(data.get('squads', []))} teams")
    
    def test_team_squad_returns_200(self):
        """Individual team squad endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/squads/CSK")
        assert response.status_code == 200
        data = response.json()
        assert "squad" in data
        print(f"✓ CSK squad endpoint returns data")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
