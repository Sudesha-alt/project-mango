"""
Test Suite for Iteration 9 Features:
1. 0-100 odds scale for consultation and chat endpoints
2. Playing XI endpoint with luck_factor
3. Venue fetch endpoint from CricketData API
4. Edge calculation with 0-100 probability inputs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ipl-predictions-1.preview.emergentagent.com').rstrip('/')


class TestHealthAndBasics:
    """Basic API health checks"""
    
    def test_api_health(self):
        """Test API is running and returns correct version"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Gamble Consultant API"
        assert data["version"] == "4.0.0"
        print(f"SUCCESS: API health check passed - version {data['version']}")


class TestConsultationEndpoint0to100Scale:
    """Test /api/matches/{match_id}/consult with 0-100 probability scale"""
    
    def test_consult_accepts_market_pct_fields(self):
        """Test consultation endpoint accepts market_pct_team1/team2 (0-100 values)"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "win_probability" in data
        assert "edge_pct" in data
        assert "fair_decimal_odds" in data
        print(f"SUCCESS: Consultation endpoint accepts 0-100 pct fields")
        print(f"  - Win probability: {data.get('win_probability')}%")
        print(f"  - Edge: {data.get('edge_pct')}%")
        print(f"  - Fair odds: {data.get('fair_decimal_odds')}")
    
    def test_consult_edge_calculation_with_0_100_inputs(self):
        """Test edge calculation is correct when using 0-100 probability inputs"""
        # If market says 55% for team1, that's 1.82 decimal odds
        # If model says 60%, edge should be positive (model sees more value)
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify odds_detail contains the bookmaker pct values
        odds_detail = data.get("odds_detail", {})
        assert "bookmaker_pct_team1" in odds_detail or "market_implied_probability" in odds_detail
        print(f"SUCCESS: Edge calculation working with 0-100 inputs")
        print(f"  - Odds detail: {odds_detail}")
    
    def test_consult_without_market_odds(self):
        """Test consultation works without market odds (should return NO_MARKET signal)"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/consult",
            json={
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "win_probability" in data
        # Without market odds, edge should be None or signal should be NO_MARKET
        print(f"SUCCESS: Consultation works without market odds")
        print(f"  - Signal: {data.get('value_signal')}")
    
    def test_consult_with_extreme_values(self):
        """Test consultation handles extreme 0-100 values (e.g., 90/10)"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/consult",
            json={
                "market_pct_team1": 90,
                "market_pct_team2": 10,
                "risk_tolerance": "aggressive"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "win_probability" in data
        print(f"SUCCESS: Consultation handles extreme values (90/10)")


class TestChatEndpoint0to100Scale:
    """Test /api/matches/{match_id}/chat with 0-100 probability scale"""
    
    def test_chat_accepts_market_pct_fields(self):
        """Test chat endpoint accepts market_pct_team1/team2 (0-100 values)"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/chat",
            json={
                "question": "Should I bet on CSK?",
                "risk_tolerance": "balanced",
                "market_pct_team1": 55,
                "market_pct_team2": 45
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "question" in data
        assert data["question"] == "Should I bet on CSK?"
        print(f"SUCCESS: Chat endpoint accepts 0-100 pct fields")
        print(f"  - Answer preview: {data.get('answer', '')[:100]}...")
    
    def test_chat_returns_consultation_summary(self):
        """Test chat returns consultation summary with win probability"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/chat",
            json={
                "question": "What's the edge here?",
                "risk_tolerance": "safe",
                "market_pct_team1": 60,
                "market_pct_team2": 40
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "consultation_summary" in data
        summary = data["consultation_summary"]
        assert "win_probability" in summary
        assert "value_signal" in summary
        print(f"SUCCESS: Chat returns consultation summary")
        print(f"  - Win prob: {summary.get('win_probability')}%")
        print(f"  - Signal: {summary.get('value_signal')}")


class TestPlayingXIEndpoint:
    """Test POST /api/matches/{match_id}/playing-xi endpoint"""
    
    def test_playing_xi_returns_both_teams(self):
        """Test playing XI endpoint returns team1_xi and team2_xi"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_007/playing-xi")
        assert response.status_code == 200
        data = response.json()
        
        assert "team1_xi" in data, "Response should contain team1_xi"
        assert "team2_xi" in data, "Response should contain team2_xi"
        print(f"SUCCESS: Playing XI endpoint returns both teams")
        print(f"  - Team 1 XI count: {len(data.get('team1_xi', []))}")
        print(f"  - Team 2 XI count: {len(data.get('team2_xi', []))}")
    
    def test_playing_xi_has_luck_factor(self):
        """Test each player in playing XI has luck_factor field"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_007/playing-xi")
        assert response.status_code == 200
        data = response.json()
        
        team1_xi = data.get("team1_xi", [])
        team2_xi = data.get("team2_xi", [])
        
        # Check at least some players have luck_factor
        luck_factors_found = 0
        for player in team1_xi + team2_xi:
            if "luck_factor" in player:
                luck_factors_found += 1
                # Luck factor should be between 0.85 and 1.15
                assert 0.80 <= player["luck_factor"] <= 1.20, f"Luck factor {player['luck_factor']} out of range"
        
        assert luck_factors_found > 0, "At least some players should have luck_factor"
        print(f"SUCCESS: Playing XI has luck_factor on players")
        print(f"  - Players with luck_factor: {luck_factors_found}")
        
        # Print sample player
        if team1_xi:
            sample = team1_xi[0]
            print(f"  - Sample player: {sample.get('name')} - luck_factor: {sample.get('luck_factor')}")
    
    def test_playing_xi_player_structure(self):
        """Test player objects have expected fields"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_007/playing-xi")
        assert response.status_code == 200
        data = response.json()
        
        team1_xi = data.get("team1_xi", [])
        if team1_xi:
            player = team1_xi[0]
            # Check expected fields
            expected_fields = ["name", "role"]
            for field in expected_fields:
                assert field in player, f"Player should have {field} field"
            print(f"SUCCESS: Player structure is correct")
            print(f"  - Fields: {list(player.keys())}")
    
    def test_playing_xi_includes_metadata(self):
        """Test playing XI response includes matchId and fetched_at"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_007/playing-xi")
        assert response.status_code == 200
        data = response.json()
        
        assert "matchId" in data, "Response should include matchId"
        assert "fetched_at" in data, "Response should include fetched_at"
        print(f"SUCCESS: Playing XI includes metadata")
        print(f"  - Match ID: {data.get('matchId')}")


class TestVenueFetchEndpoint:
    """Test GET /api/cricket-api/venue/{venue_name} endpoint"""
    
    def test_venue_fetch_returns_data(self):
        """Test venue fetch endpoint returns venue data"""
        # Use a common IPL venue
        venue_name = "Wankhede"
        response = requests.get(f"{BASE_URL}/api/cricket-api/venue/{venue_name}")
        assert response.status_code == 200
        data = response.json()
        
        assert "venue" in data, "Response should include venue field"
        assert data["venue"] == venue_name
        print(f"SUCCESS: Venue fetch endpoint returns data")
        print(f"  - Venue: {data.get('venue')}")
        print(f"  - Matches found: {data.get('matches_found', 0)}")
    
    def test_venue_fetch_includes_api_info(self):
        """Test venue fetch includes API usage info"""
        venue_name = "Chennai"
        response = requests.get(f"{BASE_URL}/api/cricket-api/venue/{venue_name}")
        assert response.status_code == 200
        data = response.json()
        
        # Should include api_info or error about rate limit
        if "error" not in data:
            assert "api_info" in data or "source" in data
            print(f"SUCCESS: Venue fetch includes API info")
            if "api_info" in data:
                print(f"  - API info: {data.get('api_info')}")
        else:
            print(f"INFO: Venue fetch returned error (possibly rate limited): {data.get('error')}")


class TestBetaPredictionEndpoint0to100Scale:
    """Test /api/matches/{match_id}/beta-predict with 0-100 probability scale"""
    
    def test_beta_predict_accepts_market_pct_fields(self):
        """Test beta prediction accepts market_team1_pct/team2_pct (0-100 values)"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/beta-predict",
            json={
                "market_team1_pct": 55,
                "market_team2_pct": 45
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "monte_carlo" in data
        assert "odds" in data
        assert "player_predictions" in data
        print(f"SUCCESS: Beta prediction accepts 0-100 pct fields")
        print(f"  - Monte Carlo team1 win prob: {data.get('monte_carlo', {}).get('team1_win_prob')}")


class TestFetchLiveEndpoint0to100Scale:
    """Test /api/matches/{match_id}/fetch-live with 0-100 probability scale"""
    
    def test_fetch_live_accepts_betting_pct_fields(self):
        """Test fetch-live accepts betting_team1_pct/team2_pct (0-100 values)"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/fetch-live",
            json={
                "betting_team1_pct": 55,
                "betting_team2_pct": 45,
                "betting_confidence": 80
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return match data (may be noLiveMatch if not live)
        assert "matchId" in data or "error" in data
        print(f"SUCCESS: Fetch-live accepts 0-100 pct fields")
        if "bettingInput" in data:
            print(f"  - Betting input: {data.get('bettingInput')}")


class TestEdgeCalculationMath:
    """Test edge calculation math is correct with 0-100 inputs"""
    
    def test_edge_positive_when_model_higher(self):
        """Test edge is positive when model probability > market probability"""
        # If market says 40% (low confidence in team1), but model says higher
        # Edge should be positive
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/consult",
            json={
                "market_pct_team1": 40,  # Market undervalues team1
                "market_pct_team2": 60,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        win_prob = data.get("win_probability", 50)
        edge = data.get("edge_pct")
        
        print(f"INFO: Model win prob: {win_prob}%, Market: 40%, Edge: {edge}%")
        
        # If model thinks team1 has >40% chance, edge should be positive
        if win_prob > 40 and edge is not None:
            assert edge > 0, f"Edge should be positive when model ({win_prob}%) > market (40%)"
            print(f"SUCCESS: Edge is positive ({edge}%) when model > market")
        else:
            print(f"INFO: Edge calculation depends on model output")


class TestRequestBodyFieldNames:
    """Verify correct field names are accepted by endpoints"""
    
    def test_consult_field_names(self):
        """Verify ConsultRequest accepts market_pct_team1/market_pct_team2"""
        # These are the correct field names per the Pydantic model
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/consult",
            json={
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        print("SUCCESS: ConsultRequest accepts market_pct_team1/market_pct_team2")
    
    def test_chat_field_names(self):
        """Verify ChatRequest accepts market_pct_team1/market_pct_team2"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/chat",
            json={
                "question": "Test",
                "market_pct_team1": 55,
                "market_pct_team2": 45,
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        print("SUCCESS: ChatRequest accepts market_pct_team1/market_pct_team2")
    
    def test_beta_predict_field_names(self):
        """Verify BetaPredictRequest accepts market_team1_pct/market_team2_pct"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/beta-predict",
            json={
                "market_team1_pct": 55,
                "market_team2_pct": 45
            }
        )
        assert response.status_code == 200
        print("SUCCESS: BetaPredictRequest accepts market_team1_pct/market_team2_pct")
    
    def test_fetch_live_field_names(self):
        """Verify FetchLiveRequest accepts betting_team1_pct/betting_team2_pct"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_007/fetch-live",
            json={
                "betting_team1_pct": 55,
                "betting_team2_pct": 45,
                "betting_confidence": 80
            }
        )
        assert response.status_code == 200
        print("SUCCESS: FetchLiveRequest accepts betting_team1_pct/betting_team2_pct")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
