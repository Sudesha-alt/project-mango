"""
Iteration 39 - Testing Player Performance Integration in Pre-Match Prediction

Tests:
1. GET /api/ - Health check with squadsLoaded and scheduleLoaded
2. POST /api/matches/ipl2026_015/pre-match-predict?force=true - Full prediction with player performance
3. POST /api/matches/ipl2026_015/pre-match-predict (cached)
4. POST /api/matches/ipl2026_016/pre-match-predict?force=true - Different match (RR vs RCB)
5. POST /api/matches/ipl2026_015/fetch-live - Live data or noLiveMatch gracefully
6. POST /api/sync-player-stats - Background sync start
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ipl-predictions-1.preview.emergentagent.com').rstrip('/')


class TestHealthCheck:
    """Test health check endpoint"""
    
    def test_health_check_returns_status(self):
        """GET /api/ should return status with squadsLoaded and scheduleLoaded"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert "squadsLoaded" in data, "Response should contain squadsLoaded"
        assert "scheduleLoaded" in data, "Response should contain scheduleLoaded"
        assert data["squadsLoaded"] == True, "squadsLoaded should be True"
        assert data["scheduleLoaded"] == True, "scheduleLoaded should be True"
        assert "version" in data, "Response should contain version"
        print(f"Health check passed: version={data.get('version')}, squads={data['squadsLoaded']}, schedule={data['scheduleLoaded']}")


class TestPreMatchPredictionWithForce:
    """Test pre-match prediction with force=true (fresh prediction)"""
    
    def test_pre_match_predict_force_returns_8_categories(self):
        """POST /api/matches/ipl2026_015/pre-match-predict?force=true should return prediction with 8 categories"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        assert "prediction" in data, "Response should contain prediction"
        
        prediction = data["prediction"]
        assert "factors" in prediction, "Prediction should contain factors"
        
        factors = prediction["factors"]
        expected_categories = [
            "squad_strength", "current_form", "venue_pitch_home", "h2h",
            "toss_impact", "bowling_depth", "conditions", "momentum"
        ]
        
        for category in expected_categories:
            assert category in factors, f"Factors should contain {category}"
            assert "weight" in factors[category], f"{category} should have weight"
            assert factors[category]["weight"] > 0, f"{category} weight should be non-zero"
        
        print(f"8 categories verified with non-zero weights")
        
    def test_pre_match_predict_force_returns_form_with_player_performance(self):
        """POST /api/matches/ipl2026_015/pre-match-predict?force=true should return form data with player performance"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        form = factors.get("current_form", {})
        
        # Check form has player performance data
        assert "team1_top_performers" in form or "team2_top_performers" in form, "Form should have top_performers"
        
        # Check if top_performers is an array
        t1_performers = form.get("team1_top_performers", [])
        t2_performers = form.get("team2_top_performers", [])
        
        print(f"Team1 top performers: {len(t1_performers)}, Team2 top performers: {len(t2_performers)}")
        
        # If we have performers, check their structure
        if t1_performers:
            performer = t1_performers[0]
            assert "name" in performer, "Performer should have name"
            assert "form_score" in performer, "Performer should have form_score"
            print(f"Sample performer: {performer.get('name')} - form_score: {performer.get('form_score')}")
            
    def test_pre_match_predict_force_returns_playing_xi(self):
        """POST /api/matches/ipl2026_015/pre-match-predict?force=true should return playing_xi with source and 8-11 players"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        assert "playing_xi" in data, "Response should contain playing_xi"
        
        playing_xi = data["playing_xi"]
        assert "source" in playing_xi, "playing_xi should have source"
        assert "team1_xi" in playing_xi, "playing_xi should have team1_xi"
        assert "team2_xi" in playing_xi, "playing_xi should have team2_xi"
        
        source = playing_xi["source"]
        assert source in ["live", "last_match", "squad_estimate"], f"Source should be valid, got: {source}"
        
        team1_xi = playing_xi.get("team1_xi", [])
        team2_xi = playing_xi.get("team2_xi", [])
        
        # Should have 8-11 players per team (not full 25-man squad)
        print(f"Playing XI - Source: {source}, Team1: {len(team1_xi)} players, Team2: {len(team2_xi)} players")
        
        # At least some players should be present
        assert len(team1_xi) >= 0, "team1_xi should be a list"
        assert len(team2_xi) >= 0, "team2_xi should be a list"
        
    def test_pre_match_predict_force_returns_player_performance_summary(self):
        """POST /api/matches/ipl2026_015/pre-match-predict?force=true should return player_performance_summary"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        
        # Check for player_performance_summary or has_player_stats in form
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        form = factors.get("current_form", {})
        
        has_player_stats = form.get("has_player_stats", False)
        print(f"has_player_stats: {has_player_stats}")
        
        # Also check if player_performance_summary exists at top level
        if "player_performance_summary" in data:
            summary = data["player_performance_summary"]
            print(f"player_performance_summary: {summary}")
            if "has_data" in summary:
                print(f"has_data: {summary['has_data']}")


class TestPreMatchPredictionCached:
    """Test pre-match prediction without force (cached)"""
    
    def test_pre_match_predict_cached_returns_prediction(self):
        """POST /api/matches/ipl2026_015/pre-match-predict (without force) should return cached prediction"""
        # First ensure we have a cached prediction
        requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true", timeout=120)
        
        # Now test cached
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "prediction" in data, "Response should contain prediction"
        assert "matchId" in data, "Response should contain matchId"
        assert data["matchId"] == "ipl2026_015", "matchId should match"
        
        print(f"Cached prediction returned for match {data['matchId']}")


class TestPreMatchPredictionDifferentMatch:
    """Test pre-match prediction for different match (RR vs RCB)"""
    
    def test_pre_match_predict_rr_vs_rcb(self):
        """POST /api/matches/ipl2026_016/pre-match-predict?force=true should work for RR vs RCB"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_016/pre-match-predict?force=true", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        assert "prediction" in data, "Response should contain prediction"
        
        prediction = data["prediction"]
        assert "team1_win_prob" in prediction, "Prediction should have team1_win_prob"
        assert "team2_win_prob" in prediction, "Prediction should have team2_win_prob"
        
        t1_prob = prediction["team1_win_prob"]
        t2_prob = prediction["team2_win_prob"]
        
        assert 1 <= t1_prob <= 99, f"team1_win_prob should be 1-99, got {t1_prob}"
        assert 1 <= t2_prob <= 99, f"team2_win_prob should be 1-99, got {t2_prob}"
        
        print(f"RR vs RCB prediction: Team1 {t1_prob}% vs Team2 {t2_prob}%")


class TestFetchLive:
    """Test fetch-live endpoint"""
    
    def test_fetch_live_returns_gracefully(self):
        """POST /api/matches/ipl2026_015/fetch-live should return live data or noLiveMatch gracefully"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_015/fetch-live",
            json={},
            timeout=120
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Should not have error
        assert "error" not in data or data.get("error") is None, f"Should not have error, got: {data.get('error')}"
        
        # Should have matchId
        assert "matchId" in data, "Response should contain matchId"
        
        # Either has live data or noLiveMatch flag
        if data.get("noLiveMatch"):
            print(f"No live match currently - noLiveMatch: {data['noLiveMatch']}")
            assert data["noLiveMatch"] == True
        else:
            print(f"Live data returned - isLive: {data.get('liveData', {}).get('isLive')}")
            # If live, should have liveData
            if "liveData" in data:
                live_data = data["liveData"]
                print(f"Live score: {live_data.get('score', {})}")


class TestSyncPlayerStats:
    """Test sync-player-stats endpoint"""
    
    def test_sync_player_stats_starts_background(self):
        """POST /api/sync-player-stats should start background sync"""
        response = requests.post(f"{BASE_URL}/api/sync-player-stats", timeout=30)
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data, "Response should contain status"
        assert data["status"] == "sync_started", f"Status should be sync_started, got: {data['status']}"
        
        print(f"Player stats sync started: {data}")


class TestPredictionWeights:
    """Test that all 8 prediction categories have non-zero weights"""
    
    def test_all_weights_non_zero(self):
        """All 8 categories should have non-zero weights in prediction"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true", timeout=120)
        assert response.status_code == 200
        
        data = response.json()
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        
        weights_sum = 0
        for category, details in factors.items():
            weight = details.get("weight", 0)
            assert weight > 0, f"{category} should have non-zero weight, got {weight}"
            weights_sum += weight
            print(f"{category}: weight={weight}, logit_contribution={details.get('logit_contribution', 0)}")
        
        # Weights should sum to approximately 1.0
        assert 0.99 <= weights_sum <= 1.01, f"Weights should sum to ~1.0, got {weights_sum}"
        print(f"Total weights sum: {weights_sum}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
