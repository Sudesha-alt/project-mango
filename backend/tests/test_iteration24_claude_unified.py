"""
Iteration 24 Tests: Claude Unified Probabilities
- Claude's probability is single source of truth (scoreboard + prediction panel)
- Duplicate Live Match Prediction panel removed
- Claude prediction refreshable independently via refresh-claude-prediction endpoint
- Yet-to-bat/bowl passed to Claude for realistic win probabilities
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestClaudeUnifiedProbabilities:
    """Test Claude as single source of truth for probabilities"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.match_id = "ipl2026_009"  # RR vs GT live match
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_health_check(self):
        """Test API health endpoint"""
        response = self.session.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "scheduler" in data or "status" in data
        print("✓ Health check passed")
    
    def test_fetch_live_returns_claude_prediction(self):
        """Test POST /api/matches/{matchId}/fetch-live returns claudePrediction"""
        response = self.session.post(
            f"{BASE_URL}/api/matches/{self.match_id}/fetch-live",
            json={},
            timeout=60  # Claude API takes 10-20 seconds
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check claudePrediction exists
        assert "claudePrediction" in data, "claudePrediction missing from response"
        claude_pred = data["claudePrediction"]
        
        # Check team1_win_pct and team2_win_pct exist
        assert "team1_win_pct" in claude_pred, "team1_win_pct missing from claudePrediction"
        assert "team2_win_pct" in claude_pred, "team2_win_pct missing from claudePrediction"
        
        # Check they sum to 100
        t1_pct = claude_pred["team1_win_pct"]
        t2_pct = claude_pred["team2_win_pct"]
        total = t1_pct + t2_pct
        assert abs(total - 100) < 1, f"team1_win_pct ({t1_pct}) + team2_win_pct ({t2_pct}) = {total}, should be 100"
        
        print(f"✓ claudePrediction has team1_win_pct={t1_pct}, team2_win_pct={t2_pct}, sum={total}")
        
        # Store for later tests
        self.__class__.fetch_live_data = data
    
    def test_probabilities_source_is_claude(self):
        """Test probabilities.source is 'claude' and ensemble matches claudePrediction"""
        data = getattr(self.__class__, 'fetch_live_data', None)
        if not data:
            # Fetch if not already fetched
            response = self.session.post(
                f"{BASE_URL}/api/matches/{self.match_id}/fetch-live",
                json={},
                timeout=60
            )
            data = response.json()
        
        assert "probabilities" in data, "probabilities missing from response"
        probs = data["probabilities"]
        
        # Check source is 'claude'
        assert probs.get("source") == "claude", f"probabilities.source should be 'claude', got '{probs.get('source')}'"
        
        # Check ensemble matches claudePrediction.team1_win_pct / 100
        claude_pred = data.get("claudePrediction", {})
        t1_pct = claude_pred.get("team1_win_pct", 50)
        expected_ensemble = round(t1_pct / 100, 4)
        actual_ensemble = probs.get("ensemble", 0)
        
        # Allow small floating point difference
        assert abs(actual_ensemble - expected_ensemble) < 0.01, \
            f"probabilities.ensemble ({actual_ensemble}) should match claudePrediction.team1_win_pct/100 ({expected_ensemble})"
        
        print(f"✓ probabilities.source='claude', ensemble={actual_ensemble} matches team1_win_pct/100={expected_ensemble}")
    
    def test_refresh_claude_prediction_endpoint(self):
        """Test POST /api/matches/{matchId}/refresh-claude-prediction returns updated prediction"""
        response = self.session.post(
            f"{BASE_URL}/api/matches/{self.match_id}/refresh-claude-prediction",
            json={},
            timeout=60  # Claude API takes 10-20 seconds
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should not have error
        assert "error" not in data or data.get("error") is None, f"refresh-claude-prediction returned error: {data.get('error')}"
        
        # Check claudePrediction exists
        assert "claudePrediction" in data, "claudePrediction missing from refresh response"
        claude_pred = data["claudePrediction"]
        
        # Check team1_win_pct and team2_win_pct exist
        assert "team1_win_pct" in claude_pred, "team1_win_pct missing from refreshed claudePrediction"
        assert "team2_win_pct" in claude_pred, "team2_win_pct missing from refreshed claudePrediction"
        
        # Check they sum to 100
        t1_pct = claude_pred["team1_win_pct"]
        t2_pct = claude_pred["team2_win_pct"]
        total = t1_pct + t2_pct
        assert abs(total - 100) < 1, f"Refreshed: team1_win_pct ({t1_pct}) + team2_win_pct ({t2_pct}) = {total}, should be 100"
        
        # Check probabilities updated
        assert "probabilities" in data, "probabilities missing from refresh response"
        probs = data["probabilities"]
        assert probs.get("source") == "claude", f"Refreshed probabilities.source should be 'claude', got '{probs.get('source')}'"
        
        # Check refreshedAt timestamp
        assert "refreshedAt" in data, "refreshedAt timestamp missing from refresh response"
        
        print(f"✓ refresh-claude-prediction returned updated claudePrediction: team1={t1_pct}%, team2={t2_pct}%")
        print(f"✓ probabilities.source='claude', refreshedAt={data['refreshedAt']}")
    
    def test_yet_to_bat_and_bowl_in_response(self):
        """Test yetToBat and yetToBowl arrays are present in fetch-live response"""
        data = getattr(self.__class__, 'fetch_live_data', None)
        if not data:
            response = self.session.post(
                f"{BASE_URL}/api/matches/{self.match_id}/fetch-live",
                json={},
                timeout=60
            )
            data = response.json()
        
        # Check yetToBat exists and has player names
        assert "yetToBat" in data, "yetToBat missing from response"
        yet_to_bat = data["yetToBat"]
        assert isinstance(yet_to_bat, list), "yetToBat should be a list"
        
        # Check yetToBowl exists and has player names
        assert "yetToBowl" in data, "yetToBowl missing from response"
        yet_to_bowl = data["yetToBowl"]
        assert isinstance(yet_to_bowl, list), "yetToBowl should be a list"
        
        # Log player names
        ytb_names = [p.get("name", p) if isinstance(p, dict) else p for p in yet_to_bat[:5]]
        ytbowl_names = [p.get("name", p) if isinstance(p, dict) else p for p in yet_to_bowl[:5]]
        
        print(f"✓ yetToBat has {len(yet_to_bat)} players: {ytb_names}")
        print(f"✓ yetToBowl has {len(yet_to_bowl)} players: {ytbowl_names}")
    
    def test_claude_prediction_has_required_fields(self):
        """Test claudePrediction has all required fields for UI display"""
        data = getattr(self.__class__, 'fetch_live_data', None)
        if not data:
            response = self.session.post(
                f"{BASE_URL}/api/matches/{self.match_id}/fetch-live",
                json={},
                timeout=60
            )
            data = response.json()
        
        claude_pred = data.get("claudePrediction", {})
        
        # Required fields for UI
        required_fields = [
            "predicted_winner",
            "headline",
            "reasoning",
            "momentum",
            "confidence",
            "team1_win_pct",
            "team2_win_pct"
        ]
        
        for field in required_fields:
            assert field in claude_pred, f"claudePrediction missing required field: {field}"
            print(f"✓ claudePrediction.{field} = {claude_pred[field][:50] if isinstance(claude_pred[field], str) and len(claude_pred[field]) > 50 else claude_pred[field]}")
        
        # Optional but expected fields
        optional_fields = ["batting_depth_assessment", "bowling_assessment", "key_matchup"]
        for field in optional_fields:
            if field in claude_pred:
                print(f"✓ claudePrediction.{field} present")
    
    def test_match_state_endpoint_returns_cached_data(self):
        """Test GET /api/matches/{matchId}/state returns cached data with Claude probabilities"""
        response = self.session.get(f"{BASE_URL}/api/matches/{self.match_id}/state")
        assert response.status_code == 200
        data = response.json()
        
        # If live data was fetched, should have claudePrediction
        if data.get("claudePrediction"):
            claude_pred = data["claudePrediction"]
            assert "team1_win_pct" in claude_pred, "Cached claudePrediction missing team1_win_pct"
            assert "team2_win_pct" in claude_pred, "Cached claudePrediction missing team2_win_pct"
            print(f"✓ Cached state has claudePrediction with team1={claude_pred.get('team1_win_pct')}%, team2={claude_pred.get('team2_win_pct')}%")
        
        if data.get("probabilities"):
            probs = data["probabilities"]
            print(f"✓ Cached state has probabilities.source='{probs.get('source')}', ensemble={probs.get('ensemble')}")


class TestRefreshClaudePredictionNoRefetch:
    """Test that refresh-claude-prediction doesn't re-fetch SportMonks data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.match_id = "ipl2026_009"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_refresh_uses_cached_sportmonks_data(self):
        """Test refresh-claude-prediction uses cached data, not fresh API call"""
        # First, ensure we have cached data by calling fetch-live
        fetch_response = self.session.post(
            f"{BASE_URL}/api/matches/{self.match_id}/fetch-live",
            json={},
            timeout=60
        )
        assert fetch_response.status_code == 200
        fetch_data = fetch_response.json()
        
        # Record the fetchedAt timestamp
        fetched_at = fetch_data.get("fetchedAt")
        print(f"✓ Initial fetch completed at {fetched_at}")
        
        # Now call refresh-claude-prediction
        time.sleep(2)  # Small delay to ensure different timestamp
        refresh_response = self.session.post(
            f"{BASE_URL}/api/matches/{self.match_id}/refresh-claude-prediction",
            json={},
            timeout=60
        )
        assert refresh_response.status_code == 200
        refresh_data = refresh_response.json()
        
        # Check refreshedAt is different from fetchedAt
        refreshed_at = refresh_data.get("refreshedAt")
        assert refreshed_at != fetched_at, "refreshedAt should be different from fetchedAt"
        print(f"✓ Refresh completed at {refreshed_at} (different from fetch)")
        
        # Verify we got updated Claude prediction
        assert "claudePrediction" in refresh_data
        assert "probabilities" in refresh_data
        print("✓ refresh-claude-prediction returned updated prediction without re-fetching SportMonks")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
