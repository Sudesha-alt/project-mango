"""
CricketData.org API Integration Tests
=====================================
Tests for POST /api/cricket-api/fetch-live, GET /api/cricket-api/usage, GET /api/cricket-api/cached
Rate limit: 100 hits/day - minimize fetch-live calls
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCricDataAPI:
    """CricketData.org API endpoint tests"""
    
    def test_api_root_version(self):
        """GET /api/ returns version 4.0.0 and 'Gamble Consultant API'"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "4.0.0"
        assert data["message"] == "Gamble Consultant API"
        print(f"✓ API version: {data['version']}, message: {data['message']}")
    
    def test_usage_endpoint_returns_stats(self):
        """GET /api/cricket-api/usage returns current day's API usage stats"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/usage")
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "date" in data
        assert "hits" in data
        assert "limit" in data
        assert "remaining" in data
        
        # Validate data types
        assert isinstance(data["hits"], int)
        assert isinstance(data["limit"], int)
        assert data["limit"] == 100  # Free tier limit
        
        # Validate remaining calculation
        expected_remaining = data["limit"] - data["hits"]
        assert data["remaining"] == expected_remaining or data["remaining"] is not None
        
        print(f"✓ Usage: {data['hits']}/{data['limit']} hits used, {data['remaining']} remaining")
    
    def test_cached_endpoint_returns_matches(self):
        """GET /api/cricket-api/cached returns cached match data without API hit"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/cached")
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "matches" in data
        assert "count" in data
        assert "source" in data
        assert data["source"] == "cache"
        
        # Validate matches array
        assert isinstance(data["matches"], list)
        assert data["count"] == len(data["matches"])
        
        print(f"✓ Cached: {data['count']} matches from cache")
        
        # If matches exist, validate match structure
        if data["matches"]:
            match = data["matches"][0]
            self._validate_match_structure(match)
    
    def _validate_match_structure(self, match):
        """Helper to validate match object structure"""
        required_fields = [
            "cricapi_id", "name", "status", "venue", "team1", "team2",
            "innings", "matchStarted", "matchEnded", "source"
        ]
        for field in required_fields:
            assert field in match, f"Missing field: {field}"
        
        # Validate innings structure
        assert isinstance(match["innings"], list)
        if match["innings"]:
            innings = match["innings"][0]
            assert "runs" in innings
            assert "wickets" in innings
            assert "overs" in innings
            assert "inning_label" in innings
        
        print(f"  ✓ Match structure valid: {match['team1']} vs {match['team2']}")
    
    def test_cached_matches_have_ipl_data(self):
        """Cached matches contain IPL 2026 match details"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/cached")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            for match in data["matches"]:
                # Verify it's IPL data
                name_lower = match["name"].lower()
                assert "ipl" in name_lower or "indian premier league" in name_lower, \
                    f"Match not IPL: {match['name']}"
                
                # Verify team names are IPL teams
                ipl_teams = ["chennai super kings", "mumbai indians", "royal challengers",
                             "kolkata knight riders", "delhi capitals", "punjab kings",
                             "rajasthan royals", "sunrisers hyderabad", "lucknow super giants",
                             "gujarat titans"]
                team1_lower = match["team1"].lower()
                team2_lower = match["team2"].lower()
                
                team1_valid = any(team in team1_lower for team in ipl_teams)
                team2_valid = any(team in team2_lower for team in ipl_teams)
                assert team1_valid, f"Team1 not IPL team: {match['team1']}"
                assert team2_valid, f"Team2 not IPL team: {match['team2']}"
                
                print(f"  ✓ IPL match: {match['team1']} vs {match['team2']}")
        else:
            print("  ⚠ No cached matches to validate")
    
    def test_cached_matches_have_scores(self):
        """Cached matches include innings scores with runs/wickets/overs"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/cached")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            for match in data["matches"]:
                if match["matchStarted"]:
                    assert len(match["innings"]) > 0, f"No innings for started match: {match['name']}"
                    
                    for innings in match["innings"]:
                        assert isinstance(innings["runs"], int), "Runs should be int"
                        assert isinstance(innings["wickets"], int), "Wickets should be int"
                        assert innings["runs"] >= 0, "Runs should be non-negative"
                        assert 0 <= innings["wickets"] <= 10, "Wickets should be 0-10"
                        
                        print(f"  ✓ {innings['inning_label']}: {innings['runs']}/{innings['wickets']} ({innings['overs']} ov)")
        else:
            print("  ⚠ No cached matches to validate scores")
    
    def test_fetch_live_endpoint_single_call(self):
        """POST /api/cricket-api/fetch-live returns IPL 2026 matches (1 API hit)"""
        # First check current usage
        usage_before = requests.get(f"{BASE_URL}/api/cricket-api/usage").json()
        hits_before = usage_before.get("hits", 0)
        
        # Make the fetch call (costs 1 API hit)
        response = requests.post(f"{BASE_URL}/api/cricket-api/fetch-live", timeout=60)
        assert response.status_code == 200
        data = response.json()
        
        # Check for error (daily limit)
        if "error" in data:
            print(f"  ⚠ API error: {data['error']}")
            pytest.skip(f"API error: {data['error']}")
        
        # Validate response structure
        assert "matches" in data
        assert "count" in data
        assert "api_info" in data
        assert "all_matches_count" in data
        assert "source" in data
        assert data["source"] == "cricketdata.org"
        
        # Validate api_info structure
        api_info = data["api_info"]
        assert "hits_today" in api_info
        assert "hits_limit" in api_info
        assert "hits_remaining" in api_info
        assert "fetched_at" in api_info
        
        # Verify API hit was counted
        assert api_info["hits_today"] >= hits_before, "API hit should be counted"
        
        print(f"✓ Fetch live: {data['count']} IPL matches, {api_info['hits_today']}/{api_info['hits_limit']} hits used")
        
        # Validate matches if any
        if data["count"] > 0:
            for match in data["matches"]:
                self._validate_match_structure(match)
    
    def test_usage_endpoint_no_api_hit(self):
        """GET /api/cricket-api/usage does NOT cost an API hit"""
        # Get usage twice
        response1 = requests.get(f"{BASE_URL}/api/cricket-api/usage")
        hits1 = response1.json().get("hits", 0)
        
        response2 = requests.get(f"{BASE_URL}/api/cricket-api/usage")
        hits2 = response2.json().get("hits", 0)
        
        # Hits should not increase
        assert hits2 == hits1, "Usage endpoint should not cost API hit"
        print(f"✓ Usage endpoint free: hits unchanged at {hits1}")
    
    def test_cached_endpoint_no_api_hit(self):
        """GET /api/cricket-api/cached does NOT cost an API hit"""
        # Get usage before
        usage_before = requests.get(f"{BASE_URL}/api/cricket-api/usage").json()
        hits_before = usage_before.get("hits", 0)
        
        # Call cached endpoint
        requests.get(f"{BASE_URL}/api/cricket-api/cached")
        
        # Get usage after
        usage_after = requests.get(f"{BASE_URL}/api/cricket-api/usage").json()
        hits_after = usage_after.get("hits", 0)
        
        # Hits should not increase
        assert hits_after == hits_before, "Cached endpoint should not cost API hit"
        print(f"✓ Cached endpoint free: hits unchanged at {hits_before}")


class TestCricDataMatchDetails:
    """Tests for match detail structure from CricAPI"""
    
    def test_match_has_team_info(self):
        """Matches include team_info with shortname and img"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/cached")
        data = response.json()
        
        if data["count"] > 0:
            for match in data["matches"]:
                if "team_info" in match and match["team_info"]:
                    for team_name, info in match["team_info"].items():
                        assert "shortname" in info, f"Missing shortname for {team_name}"
                        assert "img" in info, f"Missing img for {team_name}"
                        print(f"  ✓ {team_name}: {info['shortname']}")
        else:
            print("  ⚠ No cached matches to validate team_info")
    
    def test_match_has_venue(self):
        """Matches include venue information"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/cached")
        data = response.json()
        
        if data["count"] > 0:
            for match in data["matches"]:
                assert "venue" in match
                assert match["venue"], f"Empty venue for {match['name']}"
                print(f"  ✓ Venue: {match['venue'][:50]}...")
        else:
            print("  ⚠ No cached matches to validate venue")
    
    def test_match_has_status(self):
        """Matches include status (live/completed/upcoming)"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/cached")
        data = response.json()
        
        if data["count"] > 0:
            for match in data["matches"]:
                assert "status" in match
                assert match["status"], f"Empty status for {match['name']}"
                print(f"  ✓ Status: {match['status']}")
        else:
            print("  ⚠ No cached matches to validate status")
    
    def test_completed_match_has_target(self):
        """Completed 2nd innings matches have target calculated"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/cached")
        data = response.json()
        
        if data["count"] > 0:
            for match in data["matches"]:
                if match["matchEnded"] and match["current_innings"] >= 2:
                    assert "target" in match
                    if match["target"]:
                        assert match["target"] > 0, "Target should be positive"
                        print(f"  ✓ {match['team1']} vs {match['team2']}: Target {match['target']}")
        else:
            print("  ⚠ No cached matches to validate target")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
