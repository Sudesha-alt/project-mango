"""
PPL Board Beta Prediction API Tests - IPL 2026 Prediction Platform
Tests for Beta Prediction Engine: Poisson, Monte Carlo 10K, Player Engine, Odds, Value Bets
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ipl-predictions-1.preview.emergentagent.com')

# Test match IDs
UPCOMING_MATCH_ID = "ipl2026_008"  # DC vs MI upcoming
LIVE_MATCH_ID = "ipl2026_007"  # CSK vs PBKS live


class TestHealthEndpoint:
    """Health endpoint tests - verify version 3.0.0"""
    
    def test_health_returns_version_3(self):
        """Health endpoint returns version 3.0.0"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("version") == "3.0.0"
        print(f"✓ Health endpoint returns version {data.get('version')}")


class TestScheduleEndpoint:
    """Schedule endpoint tests - verify matches still work"""
    
    def test_schedule_returns_matches(self):
        """Schedule endpoint returns matches correctly"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        assert len(data["matches"]) > 0
        print(f"✓ Schedule returns {len(data['matches'])} matches")


class TestBetaPredictEndpoint:
    """Beta Prediction endpoint tests - POST /api/matches/{matchId}/beta-predict"""
    
    def test_beta_predict_returns_200(self):
        """Beta predict endpoint returns 200"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/beta-predict",
            json={},
            timeout=120
        )
        assert response.status_code == 200
        print("✓ Beta predict endpoint returns 200")
    
    def test_beta_predict_has_monte_carlo(self):
        """Beta predict returns monte_carlo with 10000 simulations"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/beta-predict",
            json={"market_team1_odds": 1.85, "market_team2_odds": 2.10},
            timeout=120
        )
        data = response.json()
        
        assert "monte_carlo" in data
        mc = data["monte_carlo"]
        assert mc.get("simulations") == 10000
        assert "team1_win_prob" in mc
        assert "team2_win_prob" in mc
        assert 0 <= mc["team1_win_prob"] <= 1
        assert 0 <= mc["team2_win_prob"] <= 1
        
        # Score ranges
        assert "team1_score_range" in mc
        assert "team2_score_range" in mc
        assert "p10" in mc["team1_score_range"]
        assert "p50" in mc["team1_score_range"]
        assert "p90" in mc["team1_score_range"]
        
        print(f"✓ Monte Carlo: {mc['simulations']} sims, T1 win: {mc['team1_win_prob']:.2%}, T2 win: {mc['team2_win_prob']:.2%}")
    
    def test_beta_predict_has_player_predictions(self):
        """Beta predict returns player_predictions array"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/beta-predict",
            json={},
            timeout=120
        )
        data = response.json()
        
        assert "player_predictions" in data
        players = data["player_predictions"]
        assert len(players) > 0
        
        # Check player structure
        player = players[0]
        assert "name" in player
        assert "predicted_runs" in player
        assert "predicted_wickets" in player
        assert "confidence" in player
        
        print(f"✓ Player predictions: {len(players)} players, first: {player['name']} - {player['predicted_runs']} runs, {player['predicted_wickets']} wkts, {player['confidence']}% conf")
    
    def test_beta_predict_has_poisson_distribution(self):
        """Beta predict returns poisson.runs_distribution and wickets_distribution"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/beta-predict",
            json={},
            timeout=120
        )
        data = response.json()
        
        assert "poisson" in data
        poisson = data["poisson"]
        
        # Runs distribution (may be empty for pre-match)
        assert "runs_distribution" in poisson
        
        # Wickets distribution
        assert "wickets_distribution" in poisson
        assert len(poisson["wickets_distribution"]) > 0
        
        # Check wickets distribution structure
        wkt_dist = poisson["wickets_distribution"][0]
        assert "wickets" in wkt_dist
        assert "probability" in wkt_dist
        
        print(f"✓ Poisson: runs_dist={len(poisson['runs_distribution'])} items, wickets_dist={len(poisson['wickets_distribution'])} items")
    
    def test_beta_predict_has_odds(self):
        """Beta predict returns odds.team1 and odds.team2 with true_odds, house_odds, implied_probability"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/beta-predict",
            json={},
            timeout=120
        )
        data = response.json()
        
        assert "odds" in data
        odds = data["odds"]
        
        # Team 1 odds
        assert "team1" in odds
        t1_odds = odds["team1"]
        assert "true_odds" in t1_odds
        assert "house_odds" in t1_odds
        assert "implied_probability" in t1_odds
        assert "true_probability" in t1_odds
        
        # Team 2 odds
        assert "team2" in odds
        t2_odds = odds["team2"]
        assert "true_odds" in t2_odds
        assert "house_odds" in t2_odds
        assert "implied_probability" in t2_odds
        
        # House edge
        assert "house_edge_pct" in odds
        assert odds["house_edge_pct"] == 10  # 10% house edge
        
        print(f"✓ Odds: T1 true={t1_odds['true_odds']}, house={t1_odds['house_odds']} | T2 true={t2_odds['true_odds']}, house={t2_odds['house_odds']} | Edge={odds['house_edge_pct']}%")
    
    def test_beta_predict_has_match_context(self):
        """Beta predict returns match_context with phase, pressure, powerplay/middle/death flags"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/beta-predict",
            json={},
            timeout=120
        )
        data = response.json()
        
        assert "match_context" in data
        ctx = data["match_context"]
        
        assert "phase" in ctx
        assert ctx["phase"] in ["powerplay", "middle", "death"]
        assert "pressure" in ctx
        assert "powerplay" in ctx
        assert "middle_overs" in ctx
        assert "death_overs" in ctx
        
        print(f"✓ Match context: phase={ctx['phase']}, pressure={ctx['pressure']}, powerplay={ctx['powerplay']}")
    
    def test_beta_predict_has_gpt_analysis(self):
        """Beta predict returns gpt_analysis with tactical_insight"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/beta-predict",
            json={},
            timeout=120
        )
        data = response.json()
        
        assert "gpt_analysis" in data
        gpt = data["gpt_analysis"]
        
        assert "tactical_insight" in gpt
        assert len(gpt["tactical_insight"]) > 0
        
        print(f"✓ GPT Analysis: {gpt['tactical_insight'][:100]}...")
    
    def test_beta_predict_with_market_odds_returns_value_bets(self):
        """Beta predict with market_team1_odds and market_team2_odds returns value_bets array"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/beta-predict",
            json={
                "market_team1_odds": 1.85,
                "market_team2_odds": 2.10
            },
            timeout=120
        )
        data = response.json()
        
        # value_bets should be present (may be empty if no value detected)
        assert "value_bets" in data
        assert isinstance(data["value_bets"], list)
        
        # alerts should also be present
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        
        print(f"✓ Value bets: {len(data['value_bets'])} detected, Alerts: {len(data['alerts'])}")
    
    def test_beta_predict_invalid_match(self):
        """Beta predict for invalid match returns error"""
        response = requests.post(
            f"{BASE_URL}/api/matches/invalid_match_id/beta-predict",
            json={},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        print(f"✓ Invalid match returns error: {data.get('error')}")
    
    def test_beta_predict_has_team_info(self):
        """Beta predict returns team1, team2, team1Short, team2Short, venue"""
        response = requests.post(
            f"{BASE_URL}/api/matches/{UPCOMING_MATCH_ID}/beta-predict",
            json={},
            timeout=120
        )
        data = response.json()
        
        assert "team1" in data
        assert "team2" in data
        assert "team1Short" in data
        assert "team2Short" in data
        assert "venue" in data
        assert "matchId" in data
        assert data["matchId"] == UPCOMING_MATCH_ID
        
        print(f"✓ Team info: {data['team1Short']} vs {data['team2Short']} at {data['venue']}")


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still work after beta prediction addition"""
    
    def test_fetch_live_still_works(self):
        """POST /api/matches/{matchId}/fetch-live still works"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_001/fetch-live",
            json={},
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        assert "matchId" in data or "error" in data
        print("✓ Fetch live endpoint still works")
    
    def test_match_state_still_works(self):
        """GET /api/matches/{matchId}/state still works"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_001/state")
        assert response.status_code == 200
        data = response.json()
        assert "matchId" in data
        print("✓ Match state endpoint still works")
    
    def test_squads_still_works(self):
        """GET /api/squads still works"""
        response = requests.get(f"{BASE_URL}/api/squads")
        assert response.status_code == 200
        data = response.json()
        assert "squads" in data
        print("✓ Squads endpoint still works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
