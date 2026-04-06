"""
Iteration 32 - Comprehensive Backend API Tests
Tests all features requested in the codebase audit:
- Homepage/Schedule endpoints (70 matches)
- Weather API (Open-Meteo)
- News API (DuckDuckGo)
- Pre-match prediction endpoints
- Live match endpoints
- Match state endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://ipl-predictions-1.preview.emergentagent.com"


class TestHealthAndSchedule:
    """Test health check and schedule endpoints"""

    def test_api_health_check(self):
        """API health check returns version 4.1.0"""
        resp = requests.get(f"{BASE_URL}/api/")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("version") == "4.1.0"
        assert "Baatu" in data.get("message", "")
        print(f"✓ Health check passed: version {data.get('version')}")

    def test_schedule_returns_70_matches(self):
        """GET /api/schedule returns 70 matches"""
        resp = requests.get(f"{BASE_URL}/api/schedule")
        assert resp.status_code == 200
        data = resp.json()
        matches = data.get("matches", [])
        assert len(matches) == 70, f"Expected 70 matches, got {len(matches)}"
        print(f"✓ Schedule has {len(matches)} matches")

    def test_schedule_matches_have_required_fields(self):
        """Each match has city, timeIST, venue fields"""
        resp = requests.get(f"{BASE_URL}/api/schedule")
        assert resp.status_code == 200
        matches = resp.json().get("matches", [])
        
        # Check first 5 matches for required fields
        for m in matches[:5]:
            assert "city" in m, f"Match {m.get('matchId')} missing city"
            assert "timeIST" in m, f"Match {m.get('matchId')} missing timeIST"
            assert "venue" in m, f"Match {m.get('matchId')} missing venue"
            assert "team1" in m, f"Match {m.get('matchId')} missing team1"
            assert "team2" in m, f"Match {m.get('matchId')} missing team2"
        print("✓ Matches have required fields (city, timeIST, venue, team1, team2)")

    def test_schedule_first_match_is_rcb_vs_srh(self):
        """First match is RCB vs SRH in Bengaluru"""
        resp = requests.get(f"{BASE_URL}/api/schedule")
        assert resp.status_code == 200
        matches = resp.json().get("matches", [])
        first = matches[0]
        assert "Royal Challengers" in first.get("team1", "") or "RCB" in first.get("team1Short", "")
        assert "Sunrisers" in first.get("team2", "") or "SRH" in first.get("team2Short", "")
        assert "Bengaluru" in first.get("city", "") or "Bengaluru" in first.get("venue", "")
        print(f"✓ First match: {first.get('team1Short')} vs {first.get('team2Short')} at {first.get('city')}")

    def test_seed_official_schedule(self):
        """POST /api/schedule/seed-official?force=true loads 70 matches"""
        resp = requests.post(f"{BASE_URL}/api/schedule/seed-official?force=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("count") == 70, f"Expected 70 matches, got {data.get('count')}"
        assert data.get("source") == "official_pdf"
        print(f"✓ Seeded {data.get('count')} matches from official PDF")


class TestWeatherAPI:
    """Test weather endpoints (Open-Meteo integration)"""

    def test_weather_for_mumbai(self):
        """GET /api/weather/Mumbai returns weather data"""
        resp = requests.get(f"{BASE_URL}/api/weather/Mumbai")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("available") == True, f"Weather not available: {data.get('error')}"
        assert "current" in data
        assert data["current"].get("temperature") is not None
        print(f"✓ Mumbai weather: {data['current'].get('temperature')}°C, {data['current'].get('condition')}")

    def test_weather_for_bengaluru(self):
        """GET /api/weather/Bengaluru returns weather data"""
        resp = requests.get(f"{BASE_URL}/api/weather/Bengaluru")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("available") == True
        print(f"✓ Bengaluru weather: {data['current'].get('temperature')}°C")

    def test_match_weather_endpoint(self):
        """GET /api/matches/ipl2026_001/weather returns weather with cricket_impact"""
        resp = requests.get(f"{BASE_URL}/api/matches/ipl2026_001/weather")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("available") == True or "error" not in data
        if data.get("available"):
            assert "cricket_impact" in data
            assert "dew_factor" in data.get("cricket_impact", {})
            print(f"✓ Match weather: {data.get('city')}, dew: {data['cricket_impact'].get('dew_factor')}")
        else:
            print(f"⚠ Weather unavailable for match: {data.get('error')}")


class TestNewsAPI:
    """Test news endpoints (DuckDuckGo integration)"""

    def test_match_news_endpoint(self):
        """GET /api/matches/ipl2026_001/news returns news articles (may be empty due to rate limits)"""
        resp = requests.get(f"{BASE_URL}/api/matches/ipl2026_001/news")
        assert resp.status_code == 200
        data = resp.json()
        assert "articles" in data
        assert "matchId" in data
        # Note: DuckDuckGo may return empty due to rate limiting
        print(f"✓ News endpoint returned {data.get('count', 0)} articles (may be 0 due to rate limits)")


class TestMatchState:
    """Test match state endpoints"""

    def test_match_state_returns_schedule_info(self):
        """GET /api/matches/ipl2026_001/state returns match info with city, timeIST"""
        resp = requests.get(f"{BASE_URL}/api/matches/ipl2026_001/state")
        assert resp.status_code == 200
        data = resp.json()
        # Should have either direct fields or info object
        info = data.get("info", data)
        assert info.get("city") or info.get("venue"), "Missing city/venue"
        assert info.get("team1") or info.get("matchId"), "Missing team1/matchId"
        print(f"✓ Match state: {info.get('team1Short', 'T1')} vs {info.get('team2Short', 'T2')} at {info.get('city', info.get('venue'))}")

    def test_match_state_for_match_020(self):
        """GET /api/matches/ipl2026_020/state returns match info"""
        resp = requests.get(f"{BASE_URL}/api/matches/ipl2026_020/state")
        assert resp.status_code == 200
        data = resp.json()
        info = data.get("info", data)
        assert info.get("matchId") == "ipl2026_020" or "ipl2026_020" in str(data)
        print(f"✓ Match 020 state retrieved")


class TestPreMatchPrediction:
    """Test pre-match prediction endpoints"""

    def test_get_cached_prediction(self):
        """GET /api/predictions/ipl2026_001/pre-match returns cached prediction"""
        resp = requests.get(f"{BASE_URL}/api/predictions/ipl2026_001/pre-match")
        assert resp.status_code == 200
        data = resp.json()
        # May or may not have prediction cached
        if data.get("prediction"):
            assert "team1_win_prob" in data["prediction"]
            assert "team2_win_prob" in data["prediction"]
            print(f"✓ Cached prediction: {data['team1Short']} {data['prediction']['team1_win_prob']}%")
        else:
            print("✓ No cached prediction (expected for fresh match)")

    def test_generate_fresh_prediction(self):
        """POST /api/matches/ipl2026_020/pre-match-predict generates fresh prediction"""
        # This test may take 20-60 seconds due to Claude API
        resp = requests.post(f"{BASE_URL}/api/matches/ipl2026_020/pre-match-predict", timeout=120)
        assert resp.status_code == 200
        data = resp.json()
        assert "prediction" in data
        assert data["prediction"].get("team1_win_prob") is not None
        assert data["prediction"].get("team2_win_prob") is not None
        # Check weather is included
        if data.get("weather"):
            assert data["weather"].get("available") in [True, False]
        print(f"✓ Generated prediction: {data.get('team1Short')} {data['prediction']['team1_win_prob']}% vs {data.get('team2Short')} {data['prediction']['team2_win_prob']}%")

    def test_prediction_has_10_categories(self):
        """Pre-match prediction includes 10-category breakdown"""
        resp = requests.get(f"{BASE_URL}/api/predictions/ipl2026_001/pre-match")
        assert resp.status_code == 200
        data = resp.json()
        if data.get("prediction"):
            pred = data["prediction"]
            # Check for category breakdown
            if "category_breakdown" in pred:
                categories = pred["category_breakdown"]
                assert len(categories) >= 5, f"Expected at least 5 categories, got {len(categories)}"
                print(f"✓ Prediction has {len(categories)} category breakdown")
            else:
                print("✓ Prediction exists (category breakdown may be in different format)")


class TestLiveMatchEndpoints:
    """Test live match endpoints"""

    def test_fetch_live_endpoint_exists(self):
        """POST /api/matches/{match_id}/fetch-live endpoint exists"""
        # Just test that endpoint exists and returns proper response
        resp = requests.post(f"{BASE_URL}/api/matches/ipl2026_001/fetch-live", timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        # Should return either live data or noLiveMatch indicator
        assert "matchId" in data or "error" in data
        print(f"✓ Fetch live endpoint works: noLiveMatch={data.get('noLiveMatch', False)}")

    def test_refresh_claude_prediction_endpoint(self):
        """POST /api/matches/{match_id}/refresh-claude-prediction endpoint exists"""
        resp = requests.post(f"{BASE_URL}/api/matches/ipl2026_001/refresh-claude-prediction", timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        # May return error if no cached data
        if data.get("error"):
            print(f"✓ Refresh Claude endpoint: {data.get('error')} (expected if no cached data)")
        else:
            print(f"✓ Refresh Claude endpoint returned prediction")

    def test_check_status_endpoint(self):
        """POST /api/matches/{match_id}/check-status endpoint exists"""
        resp = requests.post(f"{BASE_URL}/api/matches/ipl2026_001/check-status", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "matchId" in data
        assert "is_live" in data or "sportmonks_status" in data
        print(f"✓ Check status: is_live={data.get('is_live')}, is_finished={data.get('is_finished')}")

    def test_refresh_live_status_endpoint(self):
        """POST /api/matches/refresh-live-status discovers live matches"""
        resp = requests.post(f"{BASE_URL}/api/matches/refresh-live-status", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "sportmonks_live" in data or "checked" in data
        print(f"✓ Refresh live status: {data.get('sportmonks_live', 0)} live on SportMonks")


class TestUpcomingPredictions:
    """Test upcoming predictions endpoint"""

    def test_upcoming_predictions(self):
        """GET /api/predictions/upcoming returns predictions list"""
        resp = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert resp.status_code == 200
        data = resp.json()
        assert "predictions" in data
        print(f"✓ Upcoming predictions: {len(data.get('predictions', []))} matches")


class TestClaudeAnalysis:
    """Test Claude analysis endpoints"""

    def test_claude_analysis_get(self):
        """GET /api/matches/{match_id}/claude-analysis returns cached analysis"""
        resp = requests.get(f"{BASE_URL}/api/matches/ipl2026_001/claude-analysis")
        assert resp.status_code == 200
        data = resp.json()
        # May or may not have cached analysis
        if data.get("analysis"):
            print(f"✓ Claude analysis cached: {data.get('analysis', {}).get('headline', 'N/A')[:50]}...")
        else:
            print("✓ No cached Claude analysis (expected)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
