"""
Iteration 17 Tests: Playing XI Background Fetch + Form Factor Damping + Bug Fixes
==================================================================================
Tests for:
1. Playing XI background fetch with polling pattern (POST returns immediately, GET /status for results)
2. Form factor damping (sample-size based regression to 50%)
3. RR vs GT (ipl2026_009) prediction now shows GT winning
4. Consultation returns realistic simulation probs and edge_reasons
5. Player impact includes buzz_score and buzz_reason fields
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPlayingXIBackgroundFetch:
    """Test the new background fetch + polling pattern for Playing XI"""
    
    def test_playing_xi_post_returns_immediately(self):
        """POST /api/matches/{id}/playing-xi should return immediately with status=started"""
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/playing-xi", timeout=10)
        elapsed = time.time() - start_time
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should return quickly (not blocking for 60-90s GPT call)
        assert elapsed < 5, f"POST took {elapsed}s - should return immediately, not block"
        
        # Should have status field
        assert "status" in data, f"Response missing 'status' field: {data}"
        assert data["status"] in ["started", "running"], f"Expected status 'started' or 'running', got {data['status']}"
        print(f"✓ POST /playing-xi returned in {elapsed:.2f}s with status={data['status']}")
    
    def test_playing_xi_status_endpoint_exists(self):
        """GET /api/matches/{id}/playing-xi/status should return status info"""
        response = requests.get(f"{BASE_URL}/api/matches/ipl2026_008/playing-xi/status", timeout=10)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should have status field (idle, running, done, or error)
        # If previous test triggered a fetch, it might be running or done
        # If no fetch was triggered, it should be idle or have cached data
        if "status" in data:
            assert data["status"] in ["idle", "running", "done", "error"], f"Unexpected status: {data['status']}"
            print(f"✓ GET /playing-xi/status returned status={data['status']}")
        elif "team1_xi" in data:
            # Already completed - has data
            assert len(data.get("team1_xi", [])) > 0, "Expected team1_xi data"
            print(f"✓ GET /playing-xi/status returned completed data with {len(data['team1_xi'])} players")
        else:
            print(f"✓ GET /playing-xi/status returned: {list(data.keys())}")


class TestFormFactorDamping:
    """Test the sample-size damping for form factor"""
    
    def test_form_damping_formula(self):
        """
        Form factor damping: with small sample (1W-0L vs 0W-1L), logit should be much smaller
        than with large sample (5W-0L vs 0W-5L).
        
        Formula: damping = min(1.0, min_games/5.0)
        Then: form_adj = 0.5 + (form_pct - 0.5) * damping
        """
        # Import the compute_prediction function to test directly
        import sys
        sys.path.insert(0, '/app/backend')
        from services.pre_match_predictor import compute_prediction
        
        # Test case 1: Small sample (1W-0L vs 0W-1L) - should have damped logit
        small_sample_stats = {
            "h2h": {"team1_wins": 5, "team2_wins": 5, "no_result": 0},
            "venue_stats": {"team1_avg_score": 165, "team2_avg_score": 165, "team1_win_pct": 50, "team2_win_pct": 50},
            "form": {
                "team1_last5_wins": 1, "team1_last5_losses": 0, "team1_last5_win_pct": 100,
                "team2_last5_wins": 0, "team2_last5_losses": 1, "team2_last5_win_pct": 0
            },
            "squad_strength": {"team1_batting_rating": 70, "team1_bowling_rating": 70, "team2_batting_rating": 70, "team2_bowling_rating": 70}
        }
        
        # Test case 2: Large sample (5W-0L vs 0W-5L) - should have full logit
        large_sample_stats = {
            "h2h": {"team1_wins": 5, "team2_wins": 5, "no_result": 0},
            "venue_stats": {"team1_avg_score": 165, "team2_avg_score": 165, "team1_win_pct": 50, "team2_win_pct": 50},
            "form": {
                "team1_last5_wins": 5, "team1_last5_losses": 0, "team1_last5_win_pct": 100,
                "team2_last5_wins": 0, "team2_last5_losses": 5, "team2_last5_win_pct": 0
            },
            "squad_strength": {"team1_batting_rating": 70, "team1_bowling_rating": 70, "team2_batting_rating": 70, "team2_bowling_rating": 70}
        }
        
        small_pred = compute_prediction(small_sample_stats)
        large_pred = compute_prediction(large_sample_stats)
        
        small_form_logit = abs(small_pred["factors"]["form"]["logit_contribution"])
        large_form_logit = abs(large_pred["factors"]["form"]["logit_contribution"])
        
        # With damping, small sample should have much smaller form logit
        # 1 game: damping = 1/5 = 0.2
        # 5 games: damping = 5/5 = 1.0
        # So small_form_logit should be ~20% of large_form_logit
        
        assert small_form_logit < large_form_logit, \
            f"Small sample form logit ({small_form_logit}) should be < large sample ({large_form_logit})"
        
        ratio = small_form_logit / large_form_logit if large_form_logit > 0 else 0
        assert ratio < 0.5, f"Small sample logit should be <50% of large sample, got {ratio*100:.1f}%"
        
        print(f"✓ Form damping working: small sample logit={small_form_logit:.4f}, large sample logit={large_form_logit:.4f}, ratio={ratio:.2f}")
        
        # Also check that the win probabilities are different
        small_t1_prob = small_pred["team1_win_prob"]
        large_t1_prob = large_pred["team1_win_prob"]
        
        # Large sample should show more extreme probability (team1 should win more convincingly)
        assert large_t1_prob > small_t1_prob, \
            f"Large sample should show higher team1 win prob ({large_t1_prob}) than small sample ({small_t1_prob})"
        
        print(f"✓ Win probs: small sample={small_t1_prob}%, large sample={large_t1_prob}%")


class TestRRvsGTPrediction:
    """Test that RR vs GT (ipl2026_009) now shows GT winning"""
    
    def test_rr_vs_gt_prediction_favors_gt(self):
        """RR vs GT prediction should now show GT winning (not RR) after form damping fix"""
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming", timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        predictions = data.get("predictions", [])
        rr_gt_match = None
        for pred in predictions:
            if pred.get("matchId") == "ipl2026_009":
                rr_gt_match = pred
                break
        
        if not rr_gt_match:
            pytest.skip("Match ipl2026_009 (RR vs GT) not found in predictions")
        
        prediction = rr_gt_match.get("prediction", {})
        team1 = rr_gt_match.get("team1", "")
        team2 = rr_gt_match.get("team2", "")
        t1_prob = prediction.get("team1_win_prob", 50)
        t2_prob = prediction.get("team2_win_prob", 50)
        
        print(f"Match: {team1} vs {team2}")
        print(f"Probabilities: {team1}={t1_prob}%, {team2}={t2_prob}%")
        
        # GT should be winning (either as team1 or team2)
        if "Gujarat" in team1 or "GT" in rr_gt_match.get("team1Short", ""):
            # GT is team1
            assert t1_prob > t2_prob, f"GT (team1) should be winning but {team1}={t1_prob}% vs {team2}={t2_prob}%"
            print(f"✓ GT (team1) is winning with {t1_prob}%")
        elif "Gujarat" in team2 or "GT" in rr_gt_match.get("team2Short", ""):
            # GT is team2
            assert t2_prob > t1_prob, f"GT (team2) should be winning but {team1}={t1_prob}% vs {team2}={t2_prob}%"
            print(f"✓ GT (team2) is winning with {t2_prob}%")
        else:
            # Check by team short names
            t1_short = rr_gt_match.get("team1Short", "")
            t2_short = rr_gt_match.get("team2Short", "")
            if t2_short == "GT":
                assert t2_prob > t1_prob, f"GT should be winning but {t1_short}={t1_prob}% vs {t2_short}={t2_prob}%"
                print(f"✓ GT is winning with {t2_prob}%")
            elif t1_short == "GT":
                assert t1_prob > t2_prob, f"GT should be winning but {t1_short}={t1_prob}% vs {t2_short}={t2_prob}%"
                print(f"✓ GT is winning with {t1_prob}%")


class TestConsultationEndpoint:
    """Test the consultation endpoint returns realistic data"""
    
    def test_consult_returns_realistic_simulation_probs(self):
        """POST /api/matches/{id}/consult should return realistic simulation probabilities"""
        payload = {
            "market_pct_team1": 55,
            "market_pct_team2": 45,
            "risk_tolerance": "balanced"
        }
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/consult", json=payload, timeout=60)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Check simulation data
        sim = data.get("simulation", {})
        assert sim, "Response missing 'simulation' field"
        
        t1_win_prob = sim.get("team1_win_prob", 0)
        t2_win_prob = sim.get("team2_win_prob", 0)
        
        # Probabilities should be realistic (not 100/0 or 0/100)
        assert 0.05 < t1_win_prob < 0.95, f"team1_win_prob={t1_win_prob} is not realistic"
        assert 0.05 < t2_win_prob < 0.95, f"team2_win_prob={t2_win_prob} is not realistic"
        
        # Should sum to ~1.0
        total = t1_win_prob + t2_win_prob
        assert 0.98 < total < 1.02, f"Probabilities should sum to ~1.0, got {total}"
        
        print(f"✓ Simulation probs: team1={t1_win_prob*100:.1f}%, team2={t2_win_prob*100:.1f}%")
        
        # Check predicted scores
        mean_t1 = sim.get("mean_team1_score", 0)
        mean_t2 = sim.get("mean_team2_score", 0)
        
        assert 100 < mean_t1 < 250, f"mean_team1_score={mean_t1} is not realistic for T20"
        assert 100 < mean_t2 < 250, f"mean_team2_score={mean_t2} is not realistic for T20"
        
        print(f"✓ Predicted scores: team1={mean_t1}, team2={mean_t2}")
    
    def test_consult_returns_edge_reasons(self):
        """POST /api/matches/{id}/consult should return edge_reasons when market odds provided"""
        payload = {
            "market_pct_team1": 55,
            "market_pct_team2": 45,
            "risk_tolerance": "balanced"
        }
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/consult", json=payload, timeout=60)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        edge_reasons = data.get("edge_reasons", [])
        assert isinstance(edge_reasons, list), f"edge_reasons should be a list, got {type(edge_reasons)}"
        assert len(edge_reasons) > 0, "edge_reasons should not be empty when market odds provided"
        
        print(f"✓ edge_reasons has {len(edge_reasons)} items: {edge_reasons[:2]}...")
    
    def test_consult_player_impact_has_buzz_fields(self):
        """POST /api/matches/{id}/consult should return player_impact with buzz_score and buzz_reason"""
        payload = {
            "market_pct_team1": 55,
            "market_pct_team2": 45,
            "risk_tolerance": "balanced"
        }
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_008/consult", json=payload, timeout=60)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        player_impact = data.get("player_impact", [])
        assert isinstance(player_impact, list), f"player_impact should be a list"
        
        if len(player_impact) > 0:
            player = player_impact[0]
            
            # Should have buzz_score field (can be 0 for legacy data)
            assert "buzz_score" in player, f"Player missing buzz_score field: {player.keys()}"
            
            # buzz_score should be in range -100 to +100 (or 0 for legacy)
            bs = player.get("buzz_score", 0)
            assert -100 <= bs <= 100, f"buzz_score={bs} out of range [-100, +100]"
            
            # Should have buzz_reason field (can be empty string for legacy)
            assert "buzz_reason" in player, f"Player missing buzz_reason field: {player.keys()}"
            
            # Should have predicted_runs and predicted_wickets
            assert "predicted_runs" in player, f"Player missing predicted_runs"
            assert "predicted_wickets" in player, f"Player missing predicted_wickets"
            
            print(f"✓ Player impact has buzz fields: buzz_score={bs}, buzz_reason='{player.get('buzz_reason', '')[:30]}...'")
            print(f"✓ Player: {player.get('name')} - {player.get('predicted_runs')}r, {player.get('predicted_wickets')}w")
        else:
            print("⚠ No player_impact data returned (may need Playing XI fetch)")


class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_root(self):
        """GET /api/ should return health info"""
        response = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ API root: {data.get('message')}")
    
    def test_schedule_endpoint(self):
        """GET /api/schedule should return matches"""
        response = requests.get(f"{BASE_URL}/api/schedule", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        print(f"✓ Schedule has {len(data.get('matches', []))} matches")
    
    def test_predictions_upcoming(self):
        """GET /api/predictions/upcoming should return predictions"""
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        print(f"✓ Predictions has {len(data.get('predictions', []))} items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
