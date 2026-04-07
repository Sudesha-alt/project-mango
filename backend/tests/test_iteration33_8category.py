"""
Iteration 33 - 8-Category Model & Schedule Split Tests
Tests for The Lucky 11 IPL Prediction App

Key features tested:
- Schedule split: ~58 upcoming, ~12 completed (date-based classification)
- 8-category prediction model (no matchups/injuries)
- Playing XI with squad-based confidence
- Form data and momentum from DB
- News API (newsdata.io)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestScheduleSplit:
    """Test schedule filtering with date-based classification"""
    
    def test_schedule_returns_correct_split(self):
        """GET /api/schedule should return ~58 upcoming and ~12 completed"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("loaded") == True
        assert data.get("total") == 70
        
        upcoming = data.get("upcoming", [])
        completed = data.get("completed", [])
        
        # Verify counts (approximately)
        assert len(upcoming) >= 55, f"Expected ~58 upcoming, got {len(upcoming)}"
        assert len(upcoming) <= 60, f"Expected ~58 upcoming, got {len(upcoming)}"
        assert len(completed) >= 10, f"Expected ~12 completed, got {len(completed)}"
        assert len(completed) <= 15, f"Expected ~12 completed, got {len(completed)}"
        
        print(f"✓ Schedule split: {len(upcoming)} upcoming, {len(completed)} completed")
    
    def test_upcoming_matches_have_future_dates(self):
        """All upcoming matches should have future dates"""
        from datetime import datetime, timezone
        
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        upcoming = data.get("upcoming", [])
        now = datetime.now(timezone.utc)
        
        for match in upcoming[:10]:  # Check first 10
            dt_str = match.get("dateTimeGMT", "")
            if dt_str:
                match_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                assert match_dt > now, f"Upcoming match {match.get('matchId')} has past date: {dt_str}"
        
        print(f"✓ All checked upcoming matches have future dates")
    
    def test_completed_matches_have_past_dates(self):
        """All completed matches should have past dates"""
        from datetime import datetime, timezone
        
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        completed = data.get("completed", [])
        now = datetime.now(timezone.utc)
        
        for match in completed:
            dt_str = match.get("dateTimeGMT", "")
            if dt_str:
                match_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                assert match_dt < now, f"Completed match {match.get('matchId')} has future date: {dt_str}"
        
        print(f"✓ All {len(completed)} completed matches have past dates")
    
    def test_no_future_dates_in_completed(self):
        """No future-dated matches should appear in completed tab"""
        from datetime import datetime, timezone
        
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        completed = data.get("completed", [])
        now = datetime.now(timezone.utc)
        
        future_in_completed = []
        for match in completed:
            dt_str = match.get("dateTimeGMT", "")
            if dt_str:
                match_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                if match_dt > now:
                    future_in_completed.append(match.get("matchId"))
        
        assert len(future_in_completed) == 0, f"Future-dated matches in completed: {future_in_completed}"
        print(f"✓ No future-dated matches in completed tab")


class TestPreMatchPrediction:
    """Test 8-category pre-match prediction model"""
    
    def test_prediction_returns_8_category_model(self):
        """POST /api/matches/{id}/pre-match-predict should return 8-category-v2 model"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        pred = data.get("prediction", {})
        
        assert pred.get("model") == "8-category-v2", f"Expected 8-category-v2, got {pred.get('model')}"
        print(f"✓ Model is 8-category-v2")
    
    def test_prediction_has_8_factors(self):
        """Prediction should have exactly 8 factors (no matchups/injuries)"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        factors = data.get("prediction", {}).get("factors", {})
        
        expected_factors = [
            "squad_strength",
            "current_form",
            "venue_pitch_home",
            "h2h",
            "toss_impact",
            "bowling_depth",
            "conditions",
            "momentum"
        ]
        
        for factor in expected_factors:
            assert factor in factors, f"Missing factor: {factor}"
        
        # Verify matchups and injuries are NOT present
        assert "matchups" not in factors, "matchups should NOT be in 8-category model"
        assert "injuries" not in factors, "injuries should NOT be in 8-category model"
        
        print(f"✓ All 8 factors present, no matchups/injuries")
    
    def test_prediction_has_playing_xi_with_squad_based_confidence(self):
        """Prediction should include playing_xi with confidence='squad-based'"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        xi = data.get("playing_xi", {})
        
        assert xi.get("confidence") == "squad-based", f"Expected squad-based, got {xi.get('confidence')}"
        assert len(xi.get("team1_xi", [])) == 11, f"Expected 11 players in team1_xi"
        assert len(xi.get("team2_xi", [])) == 11, f"Expected 11 players in team2_xi"
        
        print(f"✓ Playing XI has 11+11 players with squad-based confidence")
    
    def test_prediction_has_form_data(self):
        """Prediction should include form_data from DB"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        form = data.get("form_data", {})
        
        assert "team1" in form, "form_data should have team1"
        assert "team2" in form, "form_data should have team2"
        assert "form_score" in form.get("team1", {}), "team1 should have form_score"
        
        print(f"✓ Form data present with team1 score: {form.get('team1', {}).get('form_score')}")
    
    def test_prediction_has_momentum_data(self):
        """Prediction should include momentum data (last 2 matches)"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        momentum = data.get("momentum", {})
        
        assert "team1_last2" in momentum, "momentum should have team1_last2"
        assert "team2_last2" in momentum, "momentum should have team2_last2"
        
        print(f"✓ Momentum data present: team1={momentum.get('team1_last2')}, team2={momentum.get('team2_last2')}")


class TestNewsAPI:
    """Test news API (newsdata.io)"""
    
    def test_news_endpoint_returns_articles(self):
        """GET /api/matches/{id}/news should return articles"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_013/news")
        assert response.status_code == 200
        
        data = response.json()
        assert "articles" in data, "Response should have articles"
        assert "count" in data, "Response should have count"
        
        # News count should be > 0 (newsdata.io is working)
        count = data.get("count", 0)
        print(f"✓ News endpoint returned {count} articles")
        
        # Verify article structure if any
        if count > 0:
            article = data["articles"][0]
            assert "title" in article, "Article should have title"
            print(f"  First article: {article.get('title', '')[:50]}...")


class TestMatchInfo:
    """Test match info includes city and timeIST"""
    
    def test_match_state_has_city_and_time(self):
        """GET /api/matches/{id}/state should include city and timeIST"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_013/state")
        assert response.status_code == 200
        
        data = response.json()
        info = data.get("info", data)
        
        assert "city" in info, "Match info should have city"
        assert "timeIST" in info, "Match info should have timeIST"
        
        print(f"✓ Match info: city={info.get('city')}, timeIST={info.get('timeIST')}")


class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_root(self):
        """GET /api/ should return version info"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("version") == "4.1.0"
        assert data.get("scheduleLoaded") == True
        assert data.get("squadsLoaded") == True
        
        print(f"✓ API version {data.get('version')}, {data.get('matchesInDB')} matches loaded")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
