"""
Iteration 18 Tests: Baatu - 11 Major Update
============================================
Tests for:
1. App renamed to 'Baatu - 11' (API root message)
2. 11-factor prediction model (expanded from 5 factors)
3. Consultation uses cached 11-factor prediction
4. New factors: toss_impact, pitch_conditions, key_matchups, death_overs, powerplay, momentum
5. Simulation returns realistic probabilities with mean scores
6. edge_reasons array populated
7. Player impact includes buzz_score and buzz_reason
8. RR vs GT (ipl2026_009) shows GT winning
9. Playing XI background task pattern
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBaatu11Rename:
    """Test app renamed to Baatu - 11"""
    
    def test_api_root_returns_baatu_11(self):
        """API root should return 'Baatu - 11 API' message"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Baatu - 11" in data["message"], f"Expected 'Baatu - 11' in message, got: {data['message']}"
        print(f"PASS: API root returns '{data['message']}'")


class TestElevenFactorModel:
    """Test 11-factor prediction model"""
    
    def test_consult_returns_11_factor_model_source(self):
        """POST /api/matches/ipl2026_008/consult should return model_source='11_factor_algorithm'"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check model_source
        model_source = data.get("model_source")
        assert model_source == "11_factor_algorithm", f"Expected '11_factor_algorithm', got: {model_source}"
        print(f"PASS: model_source = '{model_source}'")
    
    def test_consult_returns_11_factors_in_pre_match_factors(self):
        """Consultation pre_match_factors should include all 11 factors"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        factors = data.get("pre_match_factors", {})
        
        # Original 5 factors
        original_factors = ["h2h", "venue", "form", "squad", "home_advantage"]
        # New 6 factors
        new_factors = ["toss_impact", "pitch_conditions", "key_matchups", "death_overs", "powerplay", "momentum"]
        
        all_11_factors = original_factors + new_factors
        
        missing_factors = []
        for factor in all_11_factors:
            if factor not in factors:
                missing_factors.append(factor)
        
        assert len(missing_factors) == 0, f"Missing factors: {missing_factors}. Got factors: {list(factors.keys())}"
        print(f"PASS: All 11 factors present: {list(factors.keys())}")
        
        # Verify each factor has weight and logit_contribution
        for factor in all_11_factors:
            factor_data = factors.get(factor, {})
            assert "weight" in factor_data, f"Factor '{factor}' missing 'weight'"
            assert "logit_contribution" in factor_data, f"Factor '{factor}' missing 'logit_contribution'"
        print("PASS: All factors have weight and logit_contribution")
    
    def test_new_factors_have_correct_weights(self):
        """New factors should have correct weights summing to ~1.0"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        factors = data.get("pre_match_factors", {})
        
        # Expected weights from pre_match_predictor.py
        expected_weights = {
            "h2h": 0.12,
            "venue": 0.10,
            "form": 0.12,
            "squad": 0.10,
            "home_advantage": 0.06,
            "toss_impact": 0.08,
            "pitch_conditions": 0.10,
            "key_matchups": 0.10,
            "death_overs": 0.08,
            "powerplay": 0.08,
            "momentum": 0.06,
        }
        
        total_weight = 0
        for factor, expected_weight in expected_weights.items():
            actual_weight = factors.get(factor, {}).get("weight", 0)
            total_weight += actual_weight
            # Allow small tolerance for floating point
            assert abs(actual_weight - expected_weight) < 0.01, f"Factor '{factor}' weight mismatch: expected {expected_weight}, got {actual_weight}"
        
        # Total should be ~1.0
        assert abs(total_weight - 1.0) < 0.01, f"Total weight should be ~1.0, got {total_weight}"
        print(f"PASS: All factor weights correct, total = {total_weight}")


class TestNewFactorDetails:
    """Test new factor details are populated"""
    
    def test_toss_impact_factor_details(self):
        """toss_impact factor should have toss_winner_win_pct, bat_first_win_pct, chase_friendly"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        toss = data.get("pre_match_factors", {}).get("toss_impact", {})
        assert "toss_winner_win_pct" in toss or "bat_first_win_pct" in toss, f"toss_impact missing expected fields: {toss}"
        print(f"PASS: toss_impact has details: {list(toss.keys())}")
    
    def test_pitch_conditions_factor_details(self):
        """pitch_conditions factor should have pitch_type, pace_assistance, spin_assistance, dew_factor"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        pitch = data.get("pre_match_factors", {}).get("pitch_conditions", {})
        expected_fields = ["pitch_type", "dew_factor"]
        for field in expected_fields:
            assert field in pitch, f"pitch_conditions missing '{field}': {pitch}"
        print(f"PASS: pitch_conditions has details: {list(pitch.keys())}")
    
    def test_key_matchups_factor_details(self):
        """key_matchups factor should have team1_matchup_score, team2_matchup_score"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        matchups = data.get("pre_match_factors", {}).get("key_matchups", {})
        assert "team1_matchup_score" in matchups, f"key_matchups missing team1_matchup_score: {matchups}"
        assert "team2_matchup_score" in matchups, f"key_matchups missing team2_matchup_score: {matchups}"
        print(f"PASS: key_matchups has scores: t1={matchups.get('team1_matchup_score')}, t2={matchups.get('team2_matchup_score')}")
    
    def test_death_overs_factor_details(self):
        """death_overs factor should have team1_avg_score, team1_avg_conceded, etc."""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        death = data.get("pre_match_factors", {}).get("death_overs", {})
        expected_fields = ["team1_avg_score", "team1_avg_conceded", "team2_avg_score", "team2_avg_conceded"]
        for field in expected_fields:
            assert field in death, f"death_overs missing '{field}': {death}"
        print(f"PASS: death_overs has details: {list(death.keys())}")
    
    def test_powerplay_factor_details(self):
        """powerplay factor should have team1_avg_score, team1_avg_wkts_lost, etc."""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        pp = data.get("pre_match_factors", {}).get("powerplay", {})
        expected_fields = ["team1_avg_score", "team2_avg_score"]
        for field in expected_fields:
            assert field in pp, f"powerplay missing '{field}': {pp}"
        print(f"PASS: powerplay has details: {list(pp.keys())}")
    
    def test_momentum_factor_details(self):
        """momentum factor should have team1_streak, team2_streak, team1_last10_wins, team2_last10_wins"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        momentum = data.get("pre_match_factors", {}).get("momentum", {})
        expected_fields = ["team1_streak", "team2_streak", "team1_last10_wins", "team2_last10_wins"]
        for field in expected_fields:
            assert field in momentum, f"momentum missing '{field}': {momentum}"
        print(f"PASS: momentum has details: {list(momentum.keys())}")


class TestSimulationAndEdge:
    """Test simulation returns realistic probabilities and edge_reasons"""
    
    def test_simulation_returns_realistic_probabilities(self):
        """Simulation should return probabilities between 5-95%, not 100/0"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        sim = data.get("simulation", {})
        t1_prob = sim.get("team1_win_prob", 0)
        t2_prob = sim.get("team2_win_prob", 0)
        
        # Should not be 100/0 or 0/100
        assert t1_prob > 0.05, f"team1_win_prob too low: {t1_prob}"
        assert t1_prob < 0.95, f"team1_win_prob too high: {t1_prob}"
        assert t2_prob > 0.05, f"team2_win_prob too low: {t2_prob}"
        assert t2_prob < 0.95, f"team2_win_prob too high: {t2_prob}"
        
        print(f"PASS: Realistic simulation probs: t1={t1_prob:.2%}, t2={t2_prob:.2%}")
    
    def test_simulation_returns_mean_scores(self):
        """Simulation should return mean_team1_score and mean_team2_score"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        sim = data.get("simulation", {})
        t1_mean = sim.get("mean_team1_score")
        t2_mean = sim.get("mean_team2_score")
        
        assert t1_mean is not None, "mean_team1_score missing"
        assert t2_mean is not None, "mean_team2_score missing"
        assert 100 < t1_mean < 250, f"mean_team1_score unrealistic: {t1_mean}"
        assert 100 < t2_mean < 250, f"mean_team2_score unrealistic: {t2_mean}"
        
        print(f"PASS: Mean scores: t1={t1_mean}, t2={t2_mean}")
    
    def test_edge_reasons_populated(self):
        """edge_reasons array should be populated when market odds provided"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        edge_reasons = data.get("edge_reasons", [])
        assert isinstance(edge_reasons, list), f"edge_reasons should be list, got: {type(edge_reasons)}"
        assert len(edge_reasons) > 0, "edge_reasons should not be empty when market odds provided"
        
        print(f"PASS: edge_reasons has {len(edge_reasons)} items: {edge_reasons[:2]}...")


class TestPlayerImpact:
    """Test player impact includes buzz_score and buzz_reason"""
    
    def test_player_impact_has_buzz_fields(self):
        """Player impact should include buzz_score and buzz_reason"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_008/consult",
            json={"market_pct_team1": 55, "market_pct_team2": 45}
        )
        assert response.status_code == 200
        data = response.json()
        
        player_impact = data.get("player_impact", [])
        
        if len(player_impact) > 0:
            player = player_impact[0]
            assert "buzz_score" in player, f"Player missing buzz_score: {player}"
            assert "buzz_reason" in player, f"Player missing buzz_reason: {player}"
            print(f"PASS: Player impact has buzz fields: buzz_score={player.get('buzz_score')}, buzz_reason='{player.get('buzz_reason', '')[:50]}...'")
        else:
            print("WARN: No player_impact data returned (may need Playing XI fetch first)")


class TestRRvsGTPrediction:
    """Test RR vs GT (ipl2026_009) shows GT winning"""
    
    def test_rr_vs_gt_shows_gt_winning(self):
        """RR vs GT prediction should show GT winning (not RR)"""
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_009/consult",
            json={"market_pct_team1": 50, "market_pct_team2": 50}
        )
        assert response.status_code == 200
        data = response.json()
        
        win_prob = data.get("win_probability", 50)
        team = data.get("team", "")
        opponent = data.get("opponent", "")
        
        # win_probability is for team1 (RR)
        # If GT is winning, RR's win_prob should be < 50
        # Based on previous iteration, GT should be winning at ~68-71%
        
        verdict = data.get("verdict", {})
        winner = verdict.get("winner", "")
        winner_prob = verdict.get("winner_probability", 50)
        
        print(f"Match: {team} vs {opponent}")
        print(f"Verdict: {winner} winning at {winner_prob}%")
        
        # GT should be the winner
        assert "Gujarat" in winner or "GT" in winner or winner_prob > 50 and "Rajasthan" not in winner, \
            f"Expected GT to be winning, but verdict shows: {winner} at {winner_prob}%"
        
        print(f"PASS: GT is winning as expected")


class TestPlayingXIBackgroundTask:
    """Test Playing XI uses background task pattern"""
    
    def test_playing_xi_post_returns_started(self):
        """POST /api/matches/{id}/playing-xi should return status=started"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/playing-xi")
        assert response.status_code == 200
        data = response.json()
        
        status = data.get("status")
        assert status in ["started", "running", "already_running"], f"Expected status=started/running, got: {status}"
        print(f"PASS: Playing XI POST returns status='{status}'")
    
    def test_playing_xi_status_returns_running_or_done(self):
        """GET /api/matches/{id}/playing-xi/status should return running/done"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_008/playing-xi/status")
        assert response.status_code == 200
        data = response.json()
        
        status = data.get("status")
        # Could be idle, running, done, or error
        assert status in ["idle", "running", "done", "error"] or "team1_xi" in data, \
            f"Unexpected status response: {data}"
        print(f"PASS: Playing XI status returns: {status if status else 'data with team1_xi'}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
