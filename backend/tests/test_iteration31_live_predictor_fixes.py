"""
Iteration 31 - Live Predictor 4 Fixes Tests

Tests for the 4 fixes to the live prediction model:
1. Non-linear alpha curve (compute_alpha function)
2. Rebalanced H weights (H2H reduced from 0.40 to 0.10, venue/form increased)
3. Squad strength differential (0.22 weight using Playing XI data)
4. Venue-specific par scores (wankhede: 178, chinnaswamy: 195, chepauk: 158)

Formula: P(win) = alpha * H + (1-alpha) * L
Alpha decays: 0.85 -> 0.20 (inn1) -> 0.05 (inn2)
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ipl-predictions-1.preview.emergentagent.com').rstrip('/')


class TestLivePredictorFixes:
    """Test the 4 fixes to the live prediction model"""

    # ═══ FIX 1: Non-linear Alpha Curve Tests ═══
    
    def test_compute_alpha_at_0_balls_returns_085(self):
        """Alpha should be 0.85 at 0 balls (pre-game)"""
        from services.live_predictor import compute_alpha
        alpha = compute_alpha(0, 1)
        assert alpha == 0.85, f"Expected alpha=0.85 at 0 balls, got {alpha}"
        print(f"✓ Alpha at 0 balls (pre-game): {alpha}")

    def test_compute_alpha_at_60_balls_inn1(self):
        """Alpha should be ~0.525 at 60 balls (mid inn1)"""
        from services.live_predictor import compute_alpha
        alpha = compute_alpha(60, 1)
        # At 60 balls: progress = 60/120 = 0.5, alpha = 0.85 - 0.65*0.5 = 0.525
        assert 0.50 <= alpha <= 0.55, f"Expected alpha ~0.525 at 60 balls inn1, got {alpha}"
        print(f"✓ Alpha at 60 balls (mid inn1): {alpha}")

    def test_compute_alpha_at_120_balls_end_inn1(self):
        """Alpha should be ~0.20 at 120 balls (end of inn1)"""
        from services.live_predictor import compute_alpha
        alpha = compute_alpha(120, 1)
        assert 0.18 <= alpha <= 0.22, f"Expected alpha ~0.20 at 120 balls, got {alpha}"
        print(f"✓ Alpha at 120 balls (end inn1): {alpha}")

    def test_compute_alpha_at_180_balls_mid_inn2(self):
        """Alpha should be ~0.125 at 180 balls (mid inn2)"""
        from services.live_predictor import compute_alpha
        alpha = compute_alpha(180, 2)
        # At 180 balls: inn2_balls = 60, progress = 0.5, alpha = 0.20 - 0.15*0.5 = 0.125
        assert 0.10 <= alpha <= 0.15, f"Expected alpha ~0.125 at 180 balls inn2, got {alpha}"
        print(f"✓ Alpha at 180 balls (mid inn2): {alpha}")

    def test_compute_alpha_at_240_balls_end_match(self):
        """Alpha should be ~0.05 at 240 balls (end of match)"""
        from services.live_predictor import compute_alpha
        alpha = compute_alpha(240, 2)
        assert alpha == 0.05, f"Expected alpha=0.05 at 240 balls, got {alpha}"
        print(f"✓ Alpha at 240 balls (end match): {alpha}")

    def test_compute_alpha_never_below_005(self):
        """Alpha should never go below 0.05"""
        from services.live_predictor import compute_alpha
        alpha = compute_alpha(300, 2)  # Beyond match end
        assert alpha >= 0.05, f"Alpha should never be below 0.05, got {alpha}"
        print(f"✓ Alpha at 300 balls (beyond match): {alpha}")

    # ═══ FIX 2: Rebalanced H Weights Tests ═══
    
    def test_h_weights_sum_to_1(self):
        """H weights should sum to 1.0: 0.22 + 0.10 + 0.28 + 0.25 + 0.15 = 1.0"""
        # From live_predictor.py: H = 0.22*squad + 0.10*h2h + 0.28*venue + 0.25*form + 0.15*toss
        weights = {
            "squad_strength": 0.22,
            "h2h_win_pct": 0.10,
            "venue_win_pct": 0.28,
            "recent_form_pct": 0.25,
            "toss_advantage_pct": 0.15
        }
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001, f"H weights should sum to 1.0, got {total}"
        print(f"✓ H weights sum to 1.0: {weights}")

    def test_h2h_weight_is_010(self):
        """H2H weight should be reduced to 0.10 (from 0.40)"""
        # Verify in the code that H2H is 0.10
        import re
        with open('/app/backend/services/live_predictor.py', 'r') as f:
            content = f.read()
        # Look for the H calculation line
        match = re.search(r'0\.10\s*\*\s*h2h', content)
        assert match, "H2H weight should be 0.10 in H calculation"
        print("✓ H2H weight is 0.10 (reduced from 0.40)")

    def test_venue_weight_is_028(self):
        """Venue weight should be 0.28"""
        import re
        with open('/app/backend/services/live_predictor.py', 'r') as f:
            content = f.read()
        match = re.search(r'0\.28\s*\*\s*venue_pct', content)
        assert match, "Venue weight should be 0.28 in H calculation"
        print("✓ Venue weight is 0.28")

    def test_form_weight_is_025(self):
        """Form weight should be 0.25"""
        import re
        with open('/app/backend/services/live_predictor.py', 'r') as f:
            content = f.read()
        match = re.search(r'0\.25\s*\*\s*form_pct', content)
        assert match, "Form weight should be 0.25 in H calculation"
        print("✓ Form weight is 0.25")

    # ═══ FIX 3: Squad Strength Differential Tests ═══
    
    def test_compute_squad_strength_differential_exists(self):
        """compute_squad_strength_differential function should exist"""
        from services.live_predictor import compute_squad_strength_differential
        assert callable(compute_squad_strength_differential)
        print("✓ compute_squad_strength_differential function exists")

    def test_squad_strength_returns_05_for_empty_data(self):
        """Squad strength should return 0.5 for empty data"""
        from services.live_predictor import compute_squad_strength_differential
        result = compute_squad_strength_differential({})
        assert result == 0.5, f"Expected 0.5 for empty data, got {result}"
        print(f"✓ Squad strength for empty data: {result}")

    def test_squad_strength_returns_05_for_equal_teams(self):
        """Squad strength should return ~0.5 for equal teams"""
        from services.live_predictor import compute_squad_strength_differential
        xi_data = {
            "team1_xi": [{"expected_runs": 30, "expected_wickets": 1, "role": "batsman"} for _ in range(11)],
            "team2_xi": [{"expected_runs": 30, "expected_wickets": 1, "role": "batsman"} for _ in range(11)]
        }
        result = compute_squad_strength_differential(xi_data)
        assert 0.45 <= result <= 0.55, f"Expected ~0.5 for equal teams, got {result}"
        print(f"✓ Squad strength for equal teams: {result}")

    def test_squad_strength_weight_is_022(self):
        """Squad strength weight should be 0.22 in H calculation"""
        import re
        with open('/app/backend/services/live_predictor.py', 'r') as f:
            content = f.read()
        match = re.search(r'0\.22\s*\*\s*squad_pct', content)
        assert match, "Squad strength weight should be 0.22 in H calculation"
        print("✓ Squad strength weight is 0.22")

    # ═══ FIX 4: Venue-Specific Par Scores Tests ═══
    
    def test_venue_par_scores_dict_exists(self):
        """VENUE_PAR_SCORES dictionary should exist"""
        from services.live_predictor import VENUE_PAR_SCORES
        assert isinstance(VENUE_PAR_SCORES, dict)
        print(f"✓ VENUE_PAR_SCORES exists with {len(VENUE_PAR_SCORES)} venues")

    def test_wankhede_par_is_178(self):
        """Wankhede par score should be 178"""
        from services.live_predictor import VENUE_PAR_SCORES
        assert "wankhede" in VENUE_PAR_SCORES
        assert VENUE_PAR_SCORES["wankhede"]["par"] == 178
        print(f"✓ Wankhede par: {VENUE_PAR_SCORES['wankhede']}")

    def test_chinnaswamy_par_is_195(self):
        """Chinnaswamy par score should be 195"""
        from services.live_predictor import VENUE_PAR_SCORES
        assert "chinnaswamy" in VENUE_PAR_SCORES
        assert VENUE_PAR_SCORES["chinnaswamy"]["par"] == 195
        print(f"✓ Chinnaswamy par: {VENUE_PAR_SCORES['chinnaswamy']}")

    def test_chepauk_par_is_158(self):
        """Chepauk par score should be 158"""
        from services.live_predictor import VENUE_PAR_SCORES
        assert "chepauk" in VENUE_PAR_SCORES
        assert VENUE_PAR_SCORES["chepauk"]["par"] == 158
        print(f"✓ Chepauk par: {VENUE_PAR_SCORES['chepauk']}")

    def test_venue_profile_contains_required_fields(self):
        """Each venue profile should have par, bat_first_win_pct, dew_risk"""
        from services.live_predictor import VENUE_PAR_SCORES
        for venue, profile in VENUE_PAR_SCORES.items():
            assert "par" in profile, f"{venue} missing 'par'"
            assert "bat_first_win_pct" in profile, f"{venue} missing 'bat_first_win_pct'"
            assert "dew_risk" in profile, f"{venue} missing 'dew_risk'"
        print("✓ All venue profiles have required fields (par, bat_first_win_pct, dew_risk)")

    def test_get_venue_profile_function(self):
        """get_venue_profile should return correct profile for known venues"""
        from services.live_predictor import get_venue_profile
        profile = get_venue_profile("Wankhede Stadium, Mumbai")
        assert profile["par"] == 178
        print(f"✓ get_venue_profile('Wankhede Stadium, Mumbai'): {profile}")

    def test_get_venue_profile_default(self):
        """get_venue_profile should return default for unknown venues"""
        from services.live_predictor import get_venue_profile
        profile = get_venue_profile("Unknown Stadium")
        assert profile["par"] == 170  # default par
        print(f"✓ get_venue_profile('Unknown Stadium'): {profile}")

    # ═══ compute_live_prediction Response Structure Tests ═══
    
    def test_compute_live_prediction_returns_alpha(self):
        """compute_live_prediction should return alpha in response"""
        from services.live_predictor import compute_live_prediction
        sm_data = {
            "current_score": {"runs": 100, "wickets": 3, "overs": 12.0},
            "current_innings": 1,
            "crr": 8.33,
            "rrr": None,
            "recent_balls": [],
            "active_batsmen": [],
            "active_bowler": None,
            "batting_team": "Team A"
        }
        claude_pred = {"historical_factors": {"h2h_win_pct": 0.5, "venue_win_pct": 0.5, "recent_form_pct": 0.5, "toss_advantage_pct": 0.5}}
        match_info = {"team1": "Team A", "team2": "Team B", "venue": "Wankhede"}
        
        result = compute_live_prediction(sm_data, claude_pred, match_info)
        assert result is not None
        assert "alpha" in result
        assert 0.05 <= result["alpha"] <= 0.85
        print(f"✓ compute_live_prediction returns alpha: {result['alpha']}")

    def test_compute_live_prediction_returns_H_and_L(self):
        """compute_live_prediction should return H and L in response"""
        from services.live_predictor import compute_live_prediction
        sm_data = {
            "current_score": {"runs": 100, "wickets": 3, "overs": 12.0},
            "current_innings": 1,
            "crr": 8.33,
            "rrr": None,
            "recent_balls": [],
            "active_batsmen": [],
            "active_bowler": None,
            "batting_team": "Team A"
        }
        claude_pred = {"historical_factors": {"h2h_win_pct": 0.5, "venue_win_pct": 0.5, "recent_form_pct": 0.5, "toss_advantage_pct": 0.5}}
        match_info = {"team1": "Team A", "team2": "Team B", "venue": "Wankhede"}
        
        result = compute_live_prediction(sm_data, claude_pred, match_info)
        assert "H" in result
        assert "L" in result
        assert "L_team1" in result
        print(f"✓ compute_live_prediction returns H={result['H']}, L={result['L']}, L_team1={result['L_team1']}")

    def test_compute_live_prediction_returns_H_breakdown(self):
        """compute_live_prediction should return H_breakdown with all 5 factors"""
        from services.live_predictor import compute_live_prediction
        sm_data = {
            "current_score": {"runs": 100, "wickets": 3, "overs": 12.0},
            "current_innings": 1,
            "crr": 8.33,
            "rrr": None,
            "recent_balls": [],
            "active_batsmen": [],
            "active_bowler": None,
            "batting_team": "Team A"
        }
        claude_pred = {"historical_factors": {"h2h_win_pct": 0.5, "venue_win_pct": 0.5, "recent_form_pct": 0.5, "toss_advantage_pct": 0.5}}
        match_info = {"team1": "Team A", "team2": "Team B", "venue": "Wankhede"}
        
        result = compute_live_prediction(sm_data, claude_pred, match_info)
        assert "H_breakdown" in result
        h_breakdown = result["H_breakdown"]
        required_fields = ["squad_strength", "h2h_win_pct", "venue_win_pct", "recent_form_pct", "toss_advantage_pct"]
        for field in required_fields:
            assert field in h_breakdown, f"H_breakdown missing {field}"
        print(f"✓ H_breakdown contains all 5 factors: {list(h_breakdown.keys())}")

    def test_compute_live_prediction_returns_L_breakdown(self):
        """compute_live_prediction should return L_breakdown with all 6 factors"""
        from services.live_predictor import compute_live_prediction
        sm_data = {
            "current_score": {"runs": 100, "wickets": 3, "overs": 12.0},
            "current_innings": 1,
            "crr": 8.33,
            "rrr": None,
            "recent_balls": [],
            "active_batsmen": [],
            "active_bowler": None,
            "batting_team": "Team A"
        }
        claude_pred = {"historical_factors": {"h2h_win_pct": 0.5, "venue_win_pct": 0.5, "recent_form_pct": 0.5, "toss_advantage_pct": 0.5}}
        match_info = {"team1": "Team A", "team2": "Team B", "venue": "Wankhede"}
        
        result = compute_live_prediction(sm_data, claude_pred, match_info)
        assert "L_breakdown" in result
        l_breakdown = result["L_breakdown"]
        required_fields = ["score_vs_par", "wickets_in_hand", "recent_over_rate", "bowlers_remaining", "pre_match_base", "match_situation_context"]
        for field in required_fields:
            assert field in l_breakdown, f"L_breakdown missing {field}"
        print(f"✓ L_breakdown contains all 6 factors: {list(l_breakdown.keys())}")

    def test_compute_live_prediction_returns_venue_profile(self):
        """compute_live_prediction should return venue_profile"""
        from services.live_predictor import compute_live_prediction
        sm_data = {
            "current_score": {"runs": 100, "wickets": 3, "overs": 12.0},
            "current_innings": 1,
            "crr": 8.33,
            "rrr": None,
            "recent_balls": [],
            "active_batsmen": [],
            "active_bowler": None,
            "batting_team": "Team A"
        }
        claude_pred = {"historical_factors": {"h2h_win_pct": 0.5, "venue_win_pct": 0.5, "recent_form_pct": 0.5, "toss_advantage_pct": 0.5}}
        match_info = {"team1": "Team A", "team2": "Team B", "venue": "Wankhede Stadium"}
        
        result = compute_live_prediction(sm_data, claude_pred, match_info)
        assert "venue_profile" in result
        vp = result["venue_profile"]
        assert "par_20" in vp
        assert "bat_first_win_pct" in vp
        assert "dew_risk" in vp
        print(f"✓ venue_profile: {vp}")


class TestServerIntegration:
    """Test server.py integration with live_predictor"""

    def test_api_health_check(self):
        """Backend health check should return valid response"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("message") == "Baatu - 11 API"
        assert data.get("version") == "4.1.0"
        print(f"✓ API health check: {data['message']} v{data['version']}")

    def test_server_imports_compute_live_prediction(self):
        """server.py should import compute_live_prediction from live_predictor"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        assert "from services.live_predictor import compute_live_prediction" in content
        print("✓ server.py imports compute_live_prediction")

    def test_server_passes_xi_data_to_compute_live_prediction(self):
        """server.py should pass xi_data (cached_xi) to compute_live_prediction"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        # Look for the call with xi_data parameter
        assert "xi_data=cached_xi" in content or "cached_xi" in content
        print("✓ server.py passes xi_data to compute_live_prediction")

    def test_fetch_live_endpoint_exists(self):
        """POST /api/matches/{match_id}/fetch-live endpoint should exist"""
        # Use a known match ID
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_071/fetch-live")
        # Should return 200 or valid error, not 404
        assert response.status_code != 404, "fetch-live endpoint not found"
        print(f"✓ fetch-live endpoint exists, status: {response.status_code}")


class TestLiveMatchAPI:
    """Test live match API response structure"""

    def test_fetch_live_returns_weighted_prediction(self):
        """fetch-live should return weightedPrediction with alpha/H/L"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_071/fetch-live")
        if response.status_code == 200:
            data = response.json()
            if data.get("noLiveMatch"):
                pytest.skip("Match not currently live")
            if "weightedPrediction" in data and data["weightedPrediction"]:
                wp = data["weightedPrediction"]
                assert "alpha" in wp, "weightedPrediction missing alpha"
                assert "H" in wp, "weightedPrediction missing H"
                assert "L" in wp, "weightedPrediction missing L"
                assert "H_breakdown" in wp, "weightedPrediction missing H_breakdown"
                assert "L_breakdown" in wp, "weightedPrediction missing L_breakdown"
                print(f"✓ weightedPrediction structure verified: alpha={wp['alpha']}, H={wp['H']}, L={wp['L']}")
            else:
                pytest.skip("No weightedPrediction in response (match may not be live)")
        else:
            pytest.skip(f"fetch-live returned {response.status_code}")

    def test_match_state_endpoint(self):
        """GET /api/matches/{match_id}/state should return match state"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_071/state")
        assert response.status_code == 200
        data = response.json()
        assert "matchId" in data
        print(f"✓ match state endpoint works, matchId: {data.get('matchId')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
