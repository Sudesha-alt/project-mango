"""
Pre-Match Prediction API Tests
==============================
Tests for the pre-match prediction feature:
- POST /api/matches/{matchId}/pre-match-predict
- GET /api/predictions/upcoming
- POST /api/schedule/predict-upcoming (batch)
- Prediction factors: H2H, Venue, Form, Squad, Home Advantage
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndBasics:
    """Basic health check and API status"""
    
    def test_health_check_returns_version_4(self):
        """GET /api/ returns version 4.0.0"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "4.0.0"
        assert data["message"] == "Gamble Consultant API"
        assert data["dataSource"] == "GPT-5.4 Web Search"
        print(f"✓ Health check passed: version {data['version']}, {data['matchesInDB']} matches in DB")

    def test_schedule_loaded(self):
        """Verify schedule is loaded with matches"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        assert data["loaded"] == True
        assert len(data["matches"]) > 0
        print(f"✓ Schedule loaded: {len(data['matches'])} matches, {len(data.get('upcoming', []))} upcoming")


class TestCachedPrediction:
    """Test cached prediction retrieval (should be instant)"""
    
    def test_cached_prediction_returns_instantly(self):
        """POST /api/matches/ipl2026_008/pre-match-predict returns cached result instantly"""
        start = time.time()
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/pre-match-predict")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return in < 2 seconds (cached)
        assert elapsed < 2.0, f"Cached prediction took {elapsed:.2f}s, expected < 2s"
        
        # Verify structure
        assert data["matchId"] == "ipl2026_008"
        assert "prediction" in data
        assert "team1_win_prob" in data["prediction"]
        assert "team2_win_prob" in data["prediction"]
        assert "confidence" in data["prediction"]
        assert "factors" in data["prediction"]
        
        print(f"✓ Cached prediction returned in {elapsed:.3f}s")
        print(f"  MI {data['prediction']['team1_win_prob']}% vs DC {data['prediction']['team2_win_prob']}%")

    def test_prediction_has_all_factors(self):
        """Prediction includes all 5 weighted factors"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/pre-match-predict")
        assert response.status_code == 200
        data = response.json()
        
        factors = data["prediction"]["factors"]
        
        # Check all 5 factors exist
        assert "h2h" in factors, "Missing h2h factor"
        assert "venue" in factors, "Missing venue factor"
        assert "form" in factors, "Missing form factor"
        assert "squad" in factors, "Missing squad factor"
        assert "home_advantage" in factors, "Missing home_advantage factor"
        
        # Verify weights sum to 1.0
        total_weight = (
            factors["h2h"]["weight"] +
            factors["venue"]["weight"] +
            factors["form"]["weight"] +
            factors["squad"]["weight"] +
            factors["home_advantage"]["weight"]
        )
        assert abs(total_weight - 1.0) < 0.01, f"Weights sum to {total_weight}, expected 1.0"
        
        print(f"✓ All 5 factors present with correct weights:")
        print(f"  H2H: {factors['h2h']['weight']*100}%, Venue: {factors['venue']['weight']*100}%")
        print(f"  Form: {factors['form']['weight']*100}%, Squad: {factors['squad']['weight']*100}%")
        print(f"  Home: {factors['home_advantage']['weight']*100}%")

    def test_h2h_factor_structure(self):
        """H2H factor includes team1_wins, team2_wins, total_matches"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/pre-match-predict")
        assert response.status_code == 200
        data = response.json()
        
        h2h = data["prediction"]["factors"]["h2h"]
        assert "team1_wins" in h2h
        assert "team2_wins" in h2h
        assert "total_matches" in h2h
        assert h2h["weight"] == 0.25
        
        print(f"✓ H2H factor: {h2h['team1_wins']}-{h2h['team2_wins']} ({h2h['total_matches']} matches)")

    def test_venue_factor_structure(self):
        """Venue factor includes avg_score, win_pct"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/pre-match-predict")
        assert response.status_code == 200
        data = response.json()
        
        venue = data["prediction"]["factors"]["venue"]
        assert "team1_avg_score" in venue
        assert "team2_avg_score" in venue
        assert "team1_win_pct" in venue
        assert "team2_win_pct" in venue
        assert venue["weight"] == 0.20
        
        print(f"✓ Venue factor: T1 avg {venue['team1_avg_score']}, T2 avg {venue['team2_avg_score']}")

    def test_form_factor_structure(self):
        """Form factor includes last5_wins, last5_win_pct"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/pre-match-predict")
        assert response.status_code == 200
        data = response.json()
        
        form = data["prediction"]["factors"]["form"]
        assert "team1_last5_wins" in form
        assert "team1_last5_win_pct" in form
        assert "team2_last5_wins" in form
        assert "team2_last5_win_pct" in form
        assert form["weight"] == 0.25
        
        print(f"✓ Form factor: T1 {form['team1_last5_wins']}W ({form['team1_last5_win_pct']}%), T2 {form['team2_last5_wins']}W ({form['team2_last5_win_pct']}%)")

    def test_squad_factor_structure(self):
        """Squad factor includes batting_rating, bowling_rating"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/pre-match-predict")
        assert response.status_code == 200
        data = response.json()
        
        squad = data["prediction"]["factors"]["squad"]
        assert "team1_batting_rating" in squad
        assert "team1_bowling_rating" in squad
        assert "team2_batting_rating" in squad
        assert "team2_bowling_rating" in squad
        assert squad["weight"] == 0.20
        
        print(f"✓ Squad factor: T1 Bat {squad['team1_batting_rating']}/Bowl {squad['team1_bowling_rating']}")


class TestGetUpcomingPredictions:
    """Test GET /api/predictions/upcoming endpoint"""
    
    def test_get_upcoming_predictions(self):
        """GET /api/predictions/upcoming returns all stored predictions"""
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert response.status_code == 200
        data = response.json()
        
        assert "predictions" in data
        assert "count" in data
        assert data["count"] >= 1  # At least ipl2026_008 should be cached
        
        print(f"✓ GET /api/predictions/upcoming: {data['count']} predictions stored")
        
        # Verify structure of each prediction
        for pred in data["predictions"]:
            assert "matchId" in pred
            assert "team1" in pred
            assert "team2" in pred
            assert "prediction" in pred
            assert "team1_win_prob" in pred["prediction"]
            assert "team2_win_prob" in pred["prediction"]
            print(f"  - {pred['matchId']}: {pred.get('team1Short', '?')} {pred['prediction']['team1_win_prob']}% vs {pred.get('team2Short', '?')} {pred['prediction']['team2_win_prob']}%")

    def test_predictions_include_stats(self):
        """Predictions include raw stats data"""
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            pred = data["predictions"][0]
            assert "stats" in pred
            stats = pred["stats"]
            assert "h2h" in stats
            assert "venue_stats" in stats
            assert "form" in stats
            assert "squad_strength" in stats
            print(f"✓ Predictions include raw stats data")


class TestExistingEndpoints:
    """Verify existing endpoints still work"""
    
    def test_schedule_endpoint(self):
        """GET /api/schedule still works"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        print(f"✓ GET /api/schedule: {len(data['matches'])} matches")

    def test_squads_endpoint(self):
        """GET /api/squads still works"""
        response = requests.get(f"{BASE_URL}/api/squads")
        assert response.status_code == 200
        data = response.json()
        assert "squads" in data
        print(f"✓ GET /api/squads: {len(data['squads'])} squads")

    def test_match_state_endpoint(self):
        """GET /api/matches/{id}/state still works"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_008/state")
        assert response.status_code == 200
        data = response.json()
        assert "matchId" in data or "info" in data
        print(f"✓ GET /api/matches/ipl2026_008/state works")

    def test_cricket_api_usage(self):
        """GET /api/cricket-api/usage still works"""
        response = requests.get(f"{BASE_URL}/api/cricket-api/usage")
        assert response.status_code == 200
        data = response.json()
        assert "hits" in data or "limit" in data
        print(f"✓ GET /api/cricket-api/usage works")

    def test_data_source_endpoint(self):
        """GET /api/data-source still works"""
        response = requests.get(f"{BASE_URL}/api/data-source")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "GPT-5.4 Web Search"
        print(f"✓ GET /api/data-source: {data['source']}")


class TestPredictionNotFound:
    """Test error handling for non-existent matches"""
    
    def test_prediction_for_invalid_match(self):
        """POST /api/matches/invalid_id/pre-match-predict returns error"""
        response = requests.post(f"{BASE_URL}/api/matches/invalid_match_id/pre-match-predict")
        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()
        assert "error" in data
        print(f"✓ Invalid match returns error: {data['error']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
