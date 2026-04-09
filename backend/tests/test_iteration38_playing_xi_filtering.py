"""
Iteration 38 - Testing Playing XI Filtering Feature

Tests:
1. Health check - scheduleLoaded, squadsLoaded should be true
2. Pre-match predict with force=true - playing_xi should have 8-11 players per team (not 25-man squad)
3. Pre-match predict without force - should return cached prediction
4. Fetch-live endpoint - should return liveData with isLive or noLiveMatch
5. Refresh-claude-prediction endpoint - should return claudePrediction with win percentages
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthCheck:
    """Test API health and data loading status"""
    
    def test_health_check_returns_valid_response(self):
        """GET /api/ should return scheduleLoaded and squadsLoaded as true"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        
        data = response.json()
        assert "scheduleLoaded" in data, "Missing scheduleLoaded field"
        assert "squadsLoaded" in data, "Missing squadsLoaded field"
        assert data["scheduleLoaded"] == True, f"Schedule not loaded: {data.get('matchesInDB', 0)} matches"
        assert data["squadsLoaded"] == True, f"Squads not loaded: {data.get('squadsInDB', 0)} squads"
        
        print(f"✓ Health check passed: {data.get('matchesInDB', 0)} matches, {data.get('squadsInDB', 0)} squads loaded")
        print(f"  Version: {data.get('version', 'unknown')}")


class TestPreMatchPredictWithForce:
    """Test pre-match prediction with force=true to verify Playing XI filtering"""
    
    def test_pre_match_predict_with_force_returns_playing_xi(self):
        """POST /api/matches/ipl2026_015/pre-match-predict?force=true should return filtered Playing XI"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200, f"Pre-match predict failed: {response.status_code}"
        
        data = response.json()
        assert "playing_xi" in data, "Missing playing_xi field in response"
        
        playing_xi = data["playing_xi"]
        assert "team1_xi" in playing_xi, "Missing team1_xi in playing_xi"
        assert "team2_xi" in playing_xi, "Missing team2_xi in playing_xi"
        
        team1_xi = playing_xi.get("team1_xi", [])
        team2_xi = playing_xi.get("team2_xi", [])
        
        # Verify team1_xi has 8-11 players (not full 25-man squad)
        assert len(team1_xi) >= 8, f"team1_xi has too few players: {len(team1_xi)}"
        assert len(team1_xi) <= 15, f"team1_xi has too many players (should be ~11, not full squad): {len(team1_xi)}"
        
        # Verify team2_xi has 8-11 players (not full 25-man squad)
        assert len(team2_xi) >= 8, f"team2_xi has too few players: {len(team2_xi)}"
        assert len(team2_xi) <= 15, f"team2_xi has too many players (should be ~11, not full squad): {len(team2_xi)}"
        
        # Check source field
        source = playing_xi.get("source", "")
        assert source in ["live", "last_match", "squad_estimate", "api"], f"Unexpected source: {source}"
        
        # Check confidence field
        confidence = playing_xi.get("confidence", "")
        assert confidence in ["api-verified", "squad-based"], f"Unexpected confidence: {confidence}"
        
        print(f"✓ Pre-match predict with force=true passed")
        print(f"  Team1 XI: {len(team1_xi)} players")
        print(f"  Team2 XI: {len(team2_xi)} players")
        print(f"  Source: {source}")
        print(f"  Confidence: {confidence}")
        
        # Print player names for verification
        if team1_xi:
            t1_names = [p.get("name", "?") for p in team1_xi[:5]]
            print(f"  Team1 sample: {', '.join(t1_names)}...")
        if team2_xi:
            t2_names = [p.get("name", "?") for p in team2_xi[:5]]
            print(f"  Team2 sample: {', '.join(t2_names)}...")
    
    def test_pre_match_predict_returns_valid_prediction(self):
        """Verify prediction has valid probability values"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        assert "prediction" in data, "Missing prediction field"
        
        prediction = data["prediction"]
        assert "team1_win_prob" in prediction, "Missing team1_win_prob"
        assert "team2_win_prob" in prediction, "Missing team2_win_prob"
        
        t1_prob = prediction["team1_win_prob"]
        t2_prob = prediction["team2_win_prob"]
        
        assert 1 <= t1_prob <= 99, f"team1_win_prob out of range: {t1_prob}"
        assert 1 <= t2_prob <= 99, f"team2_win_prob out of range: {t2_prob}"
        assert abs(t1_prob + t2_prob - 100) < 1, f"Probabilities don't sum to 100: {t1_prob} + {t2_prob}"
        
        print(f"✓ Prediction valid: {data.get('team1Short', 'T1')} {t1_prob}% vs {data.get('team2Short', 'T2')} {t2_prob}%")


class TestPreMatchPredictCached:
    """Test pre-match prediction without force returns cached data"""
    
    def test_pre_match_predict_without_force_returns_cached(self):
        """POST /api/matches/ipl2026_015/pre-match-predict (no force) should return cached prediction"""
        # First call with force to ensure cache exists
        requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        
        # Second call without force should return cached
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict")
        assert response.status_code == 200, f"Cached pre-match predict failed: {response.status_code}"
        
        data = response.json()
        assert "matchId" in data, "Missing matchId in cached response"
        assert data["matchId"] == "ipl2026_015", f"Wrong matchId: {data['matchId']}"
        assert "prediction" in data, "Missing prediction in cached response"
        assert "playing_xi" in data, "Missing playing_xi in cached response"
        
        print(f"✓ Cached pre-match predict returned successfully")
        print(f"  Computed at: {data.get('computed_at', 'unknown')}")


class TestFetchLiveEndpoint:
    """Test fetch-live endpoint for live match data"""
    
    def test_fetch_live_returns_valid_response(self):
        """POST /api/matches/ipl2026_015/fetch-live should return liveData or noLiveMatch"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_015/fetch-live",
            json={},
            timeout=120  # Claude Opus can take 30-90 seconds
        )
        assert response.status_code == 200, f"Fetch live failed: {response.status_code}"
        
        data = response.json()
        
        # Should have either liveData with isLive=true OR noLiveMatch=true
        if data.get("noLiveMatch"):
            # Match is not live - this is valid behavior
            assert data["noLiveMatch"] == True
            print(f"✓ Fetch live returned noLiveMatch=true (match not currently live)")
            print(f"  Status: {data.get('status', 'unknown')}")
        else:
            # Match is live - verify liveData structure
            assert "liveData" in data, "Missing liveData when noLiveMatch is false"
            live_data = data["liveData"]
            
            # Check for isLive field
            is_live = live_data.get("isLive", False) or data.get("liveData", {}).get("isLive", False)
            
            print(f"✓ Fetch live returned live data")
            print(f"  isLive: {is_live}")
            print(f"  Source: {data.get('source', 'unknown')}")
            
            # If live, check for claudePrediction
            if data.get("claudePrediction"):
                claude = data["claudePrediction"]
                print(f"  Claude team1_win_pct: {claude.get('team1_win_pct', 'N/A')}")
                print(f"  Claude team2_win_pct: {claude.get('team2_win_pct', 'N/A')}")
            
            # Check for combinedPrediction
            if data.get("combinedPrediction"):
                combined = data["combinedPrediction"]
                print(f"  Combined team1_pct: {combined.get('team1_pct', 'N/A')}")
                print(f"  Combined phase: {combined.get('phase_label', 'N/A')}")


class TestRefreshClaudePrediction:
    """Test refresh-claude-prediction endpoint"""
    
    def test_refresh_claude_prediction_returns_valid_response(self):
        """POST /api/matches/ipl2026_015/refresh-claude-prediction should return claudePrediction"""
        # First ensure we have cached live data by calling fetch-live
        fetch_response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_015/fetch-live",
            json={},
            timeout=120
        )
        
        if fetch_response.status_code != 200:
            pytest.skip("fetch-live failed, cannot test refresh-claude-prediction")
        
        fetch_data = fetch_response.json()
        if fetch_data.get("noLiveMatch"):
            # No live match - refresh-claude will fail
            response = requests.post(
                f"{BASE_URL}/api/matches/ipl2026_015/refresh-claude-prediction",
                timeout=120
            )
            assert response.status_code == 200
            data = response.json()
            # Should return error about no cached data
            if data.get("error"):
                print(f"✓ Refresh claude prediction correctly returned error for non-live match")
                print(f"  Error: {data['error']}")
                return
        
        # If we have live data, test refresh
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_015/refresh-claude-prediction",
            timeout=120
        )
        assert response.status_code == 200, f"Refresh claude prediction failed: {response.status_code}"
        
        data = response.json()
        
        # Check for claudePrediction
        if data.get("claudePrediction"):
            claude = data["claudePrediction"]
            assert "team1_win_pct" in claude or "error" in claude, "Missing team1_win_pct in claudePrediction"
            
            if not claude.get("error"):
                t1_pct = claude.get("team1_win_pct")
                t2_pct = claude.get("team2_win_pct")
                print(f"✓ Refresh claude prediction returned valid data")
                print(f"  team1_win_pct: {t1_pct}")
                print(f"  team2_win_pct: {t2_pct}")
        
        # Check for weightedPrediction
        if data.get("weightedPrediction"):
            weighted = data["weightedPrediction"]
            print(f"  Weighted team1_pct: {weighted.get('team1_pct', 'N/A')}")
        
        # Check for combinedPrediction
        if data.get("combinedPrediction"):
            combined = data["combinedPrediction"]
            print(f"  Combined team1_pct: {combined.get('team1_pct', 'N/A')}")
            print(f"  Phase: {combined.get('phase_label', 'N/A')}")


class TestPlayingXIFilteringLogic:
    """Test the Playing XI filtering logic in detail"""
    
    def test_playing_xi_not_full_squad(self):
        """Verify playing_xi contains filtered players, not full 25-man squad"""
        # Get full squad count first
        schedule_response = requests.get(f"{BASE_URL}/api/schedule")
        assert schedule_response.status_code == 200
        
        schedule_data = schedule_response.json()
        matches = schedule_data.get("matches", [])
        
        # Find match ipl2026_015
        match_015 = None
        for m in matches:
            if m.get("matchId") == "ipl2026_015":
                match_015 = m
                break
        
        if not match_015:
            pytest.skip("Match ipl2026_015 not found in schedule")
        
        t1_short = match_015.get("team1Short", "")
        t2_short = match_015.get("team2Short", "")
        
        # Get full squad sizes
        t1_squad_response = requests.get(f"{BASE_URL}/api/squads/{t1_short}")
        t2_squad_response = requests.get(f"{BASE_URL}/api/squads/{t2_short}")
        
        t1_full_squad_size = 0
        t2_full_squad_size = 0
        
        if t1_squad_response.status_code == 200:
            t1_squad = t1_squad_response.json().get("squad", {})
            t1_full_squad_size = len(t1_squad.get("players", []))
        
        if t2_squad_response.status_code == 200:
            t2_squad = t2_squad_response.json().get("squad", {})
            t2_full_squad_size = len(t2_squad.get("players", []))
        
        print(f"  Full squad sizes: {t1_short}={t1_full_squad_size}, {t2_short}={t2_full_squad_size}")
        
        # Now get pre-match prediction with force
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        
        data = response.json()
        playing_xi = data.get("playing_xi", {})
        
        t1_xi_size = len(playing_xi.get("team1_xi", []))
        t2_xi_size = len(playing_xi.get("team2_xi", []))
        
        print(f"  Playing XI sizes: team1={t1_xi_size}, team2={t2_xi_size}")
        
        # Playing XI should be significantly smaller than full squad (if full squad > 15)
        if t1_full_squad_size > 15:
            assert t1_xi_size < t1_full_squad_size, f"team1_xi ({t1_xi_size}) should be smaller than full squad ({t1_full_squad_size})"
        
        if t2_full_squad_size > 15:
            assert t2_xi_size < t2_full_squad_size, f"team2_xi ({t2_xi_size}) should be smaller than full squad ({t2_full_squad_size})"
        
        print(f"✓ Playing XI filtering verified - not using full squad")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
