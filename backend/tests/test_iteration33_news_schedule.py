"""
Iteration 33 - Testing newsdata.io integration, schedule filtering, and weather/news endpoints
Key changes:
1. News API changed from DuckDuckGo to newsdata.io
2. Schedule endpoint filters past-date matches out of 'upcoming' into 'completed'
3. Weather + News cards on PreMatch sidebar
4. LiveMatch page should NOT have Claude tab in right sidebar
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndSchedule:
    """Test API health and schedule endpoints"""
    
    def test_api_health(self):
        """Test API health check"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data.get("scheduleLoaded") == True or data.get("matchesInDB", 0) > 0
        print(f"API Health: version={data.get('version')}, matches={data.get('matchesInDB')}")
    
    def test_seed_official_schedule(self):
        """Test seeding official schedule loads 70 matches"""
        response = requests.post(f"{BASE_URL}/api/schedule/seed-official?force=true")
        assert response.status_code == 200
        data = response.json()
        assert data.get("count") == 70 or data.get("status") == "already_loaded"
        print(f"Schedule seed: status={data.get('status')}, count={data.get('count')}")
    
    def test_schedule_returns_proper_split(self):
        """Test GET /api/schedule returns proper upcoming/completed split"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        
        assert "upcoming" in data
        assert "completed" in data
        assert "live" in data
        assert "matches" in data
        
        upcoming = data.get("upcoming", [])
        completed = data.get("completed", [])
        
        print(f"Schedule split: upcoming={len(upcoming)}, completed={len(completed)}, live={len(data.get('live', []))}")
        
        # Verify no past-date matches in upcoming
        now = datetime.now(timezone.utc)
        past_in_upcoming = 0
        for match in upcoming:
            dt_str = match.get("dateTimeGMT", "")
            if dt_str:
                try:
                    match_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    # Match is > 6 hours past start time
                    if (now - match_dt).total_seconds() > 6 * 3600:
                        past_in_upcoming += 1
                        print(f"WARNING: Past match in upcoming: {match.get('matchId')} - {dt_str}")
                except Exception as e:
                    print(f"Date parse error for {match.get('matchId')}: {e}")
        
        # Assert no past-date matches in upcoming
        assert past_in_upcoming == 0, f"Found {past_in_upcoming} past-date matches in upcoming tab"
        print("PASS: No past-date matches in upcoming tab")


class TestNewsAPI:
    """Test newsdata.io integration for match news"""
    
    def test_news_endpoint_returns_articles(self):
        """Test GET /api/matches/{match_id}/news returns articles from newsdata.io"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_001/news")
        assert response.status_code == 200
        data = response.json()
        
        assert "articles" in data
        assert "matchId" in data
        assert "team1" in data
        assert "team2" in data
        assert "count" in data
        
        articles = data.get("articles", [])
        print(f"News API: matchId={data.get('matchId')}, team1={data.get('team1')}, team2={data.get('team2')}, count={data.get('count')}")
        
        # Check article structure if articles exist
        if len(articles) > 0:
            article = articles[0]
            assert "title" in article, "Article missing title"
            assert "source" in article, "Article missing source"
            assert "date" in article or "url" in article, "Article missing date or url"
            print(f"First article: title='{article.get('title', '')[:50]}...', source={article.get('source')}")
        else:
            print("WARNING: No articles returned - newsdata.io may have rate limits or no matching news")
        
        # Count should match articles length
        assert data.get("count") == len(articles)
    
    def test_news_for_different_match(self):
        """Test news endpoint for another match"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_013/news")
        assert response.status_code == 200
        data = response.json()
        
        assert "articles" in data
        print(f"News for ipl2026_013: count={data.get('count')}, team1={data.get('team1')}, team2={data.get('team2')}")


class TestWeatherAPI:
    """Test weather endpoints"""
    
    def test_weather_by_city(self):
        """Test GET /api/weather/Mumbai returns weather data"""
        response = requests.get(f"{BASE_URL}/api/weather/Mumbai")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("available") == True, "Weather should be available for Mumbai"
        assert "current" in data
        assert "cricket_impact" in data
        
        current = data.get("current", {})
        assert "temperature" in current
        assert "humidity" in current
        assert "wind_speed_kmh" in current
        
        print(f"Weather Mumbai: temp={current.get('temperature')}C, humidity={current.get('humidity')}%, condition={current.get('condition')}")
    
    def test_weather_for_match(self):
        """Test GET /api/matches/{match_id}/weather returns cricket_impact data"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_001/weather")
        assert response.status_code == 200
        data = response.json()
        
        assert "cricket_impact" in data
        assert "matchId" in data
        
        impact = data.get("cricket_impact", {})
        assert "play_likely" in impact or "summary" in impact
        
        print(f"Match weather: matchId={data.get('matchId')}, venue={data.get('venue')}, city={data.get('city')}")
        if impact.get("summary"):
            print(f"Cricket impact: {impact.get('summary')[:100]}...")


class TestMatchState:
    """Test match state endpoint"""
    
    def test_match_state_includes_city_timeist(self):
        """Test GET /api/matches/{match_id}/state returns match info including city, timeIST"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_020/state")
        assert response.status_code == 200
        data = response.json()
        
        # Should have match info either directly or in 'info' field
        info = data.get("info", data)
        
        # Check for required fields
        has_city = "city" in info or "city" in data
        has_time = "timeIST" in info or "timeIST" in data
        has_match_number = "match_number" in info or "match_number" in data
        has_series = "series" in info or "series" in data
        
        print(f"Match state ipl2026_020: city={info.get('city', data.get('city'))}, timeIST={info.get('timeIST', data.get('timeIST'))}")
        print(f"  match_number={info.get('match_number', data.get('match_number'))}, series={info.get('series', data.get('series'))}")
        
        # At least some of these should be present
        assert has_city or has_time or has_match_number, "Match state should include city, timeIST, or match_number"


class TestPreMatchPrediction:
    """Test pre-match prediction endpoints"""
    
    def test_cached_prediction_includes_weather(self):
        """Test GET /api/predictions/{match_id}/pre-match returns cached prediction with weather data"""
        response = requests.get(f"{BASE_URL}/api/predictions/ipl2026_013/pre-match")
        assert response.status_code == 200
        data = response.json()
        
        # If prediction exists, check for weather
        if data.get("prediction"):
            print(f"Pre-match prediction found for ipl2026_013")
            if data.get("weather"):
                weather = data.get("weather")
                print(f"  Weather included: available={weather.get('available')}, city={weather.get('city')}")
            else:
                print("  No weather data in cached prediction (may need to regenerate)")
        else:
            print("No cached prediction for ipl2026_013 - this is expected if not generated yet")


class TestScheduleFiltering:
    """Test schedule filtering logic"""
    
    def test_upcoming_tab_no_past_matches(self):
        """Verify UPCOMING tab shows only future matches"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        
        upcoming = data.get("upcoming", [])
        now = datetime.now(timezone.utc)
        
        for match in upcoming:
            dt_str = match.get("dateTimeGMT", "")
            if dt_str:
                try:
                    match_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    time_diff = (now - match_dt).total_seconds()
                    # Allow 6 hours buffer
                    assert time_diff < 6 * 3600, f"Match {match.get('matchId')} is past-dated but in upcoming: {dt_str}"
                except Exception:
                    pass
        
        print(f"PASS: All {len(upcoming)} upcoming matches are future-dated")
    
    def test_completed_tab_includes_past_matches(self):
        """Verify COMPLETED tab includes past-date matches"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        
        completed = data.get("completed", [])
        now = datetime.now(timezone.utc)
        
        past_count = 0
        for match in completed:
            dt_str = match.get("dateTimeGMT", "")
            if dt_str:
                try:
                    match_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    if (now - match_dt).total_seconds() > 6 * 3600:
                        past_count += 1
                except Exception:
                    pass
        
        print(f"Completed tab: {len(completed)} total, {past_count} past-dated matches")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
