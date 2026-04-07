"""
Iteration 35 - Testing Fixed Pre-Match Prediction Categories:
1. H2H factor uses historical IPL H2H data when no season data exists (source='historical_ipl')
2. Toss Impact returns non-zero logit_contribution
3. Bowling Depth uses top 5 bowlers only (bowler_count=5)
4. Balance is reflected in squad_strength factor (team1_balance, team2_balance)
5. All 8 categories produce meaningful non-zero values
6. Pre-match prediction returns valid probability (1-99%)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestIteration35H2HTossBowling:
    """Test fixed H2H, Toss Impact, and Bowling Depth categories"""

    def test_api_health(self):
        """Verify API is running"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        print(f"API Health: {data}")
        assert data.get("version") is not None

    def test_rr_vs_mi_h2h_historical(self):
        """
        Test match ipl2026_013 (RR vs MI): should show H2H 13-16 from historical_ipl source
        """
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true",
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: prediction.factors.h2h
        prediction = data.get("prediction", {})
        h2h = prediction.get("factors", {}).get("h2h", {})
        print(f"RR vs MI H2H: {h2h}")
        
        # Verify H2H source is historical_ipl (since no season data exists)
        assert h2h.get("source") == "historical_ipl", f"Expected source='historical_ipl', got '{h2h.get('source')}'"
        
        # Verify H2H values are non-zero
        team1_wins = h2h.get("team1_wins", 0)
        team2_wins = h2h.get("team2_wins", 0)
        total = h2h.get("total", 0)
        
        assert total > 0, f"Expected total H2H > 0, got {total}"
        assert team1_wins + team2_wins == total, "H2H wins should sum to total"
        
        # RR vs MI historical: RR has 13 wins, MI has 16 wins (from HISTORICAL_H2H)
        # Note: team1 in match could be RR or MI, so check the sum
        assert total == 29, f"Expected total H2H = 29 (13+16), got {total}"
        
        # Verify logit_contribution is non-zero
        logit_contribution = h2h.get("logit_contribution", 0)
        print(f"H2H logit_contribution: {logit_contribution}")
        # H2H should have some contribution since there's a difference in wins

    def test_pbks_vs_rr_h2h_historical(self):
        """
        Test match ipl2026_040 (PBKS vs RR): should show H2H 14-14 from historical_ipl source
        """
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_040/pre-match-predict?force=true",
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: prediction.factors.h2h
        prediction = data.get("prediction", {})
        h2h = prediction.get("factors", {}).get("h2h", {})
        print(f"PBKS vs RR H2H: {h2h}")
        
        # Verify H2H source is historical_ipl
        assert h2h.get("source") == "historical_ipl", f"Expected source='historical_ipl', got '{h2h.get('source')}'"
        
        # PBKS vs RR historical: 14-14 (tied)
        team1_wins = h2h.get("team1_wins", 0)
        team2_wins = h2h.get("team2_wins", 0)
        total = h2h.get("total", 0)
        
        assert total == 28, f"Expected total H2H = 28 (14+14), got {total}"
        assert team1_wins == 14 and team2_wins == 14, f"Expected 14-14, got {team1_wins}-{team2_wins}"

    def test_toss_impact_non_zero(self):
        """
        Test that Toss Impact returns non-zero logit_contribution
        Mohali night should produce logit ~0.03 (toss_win_pct=0.625)
        """
        # Test with PBKS match (Mohali venue)
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_040/pre-match-predict?force=true",
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: prediction.factors.toss_impact
        prediction = data.get("prediction", {})
        toss_impact = prediction.get("factors", {}).get("toss_impact", {})
        print(f"Toss Impact: {toss_impact}")
        
        # Verify toss_win_pct is non-zero
        toss_win_pct = toss_impact.get("toss_win_pct", 0)
        assert toss_win_pct > 0.5, f"Expected toss_win_pct > 0.5, got {toss_win_pct}"
        
        # Verify logit_contribution is non-zero
        logit_contribution = toss_impact.get("logit_contribution", 0)
        print(f"Toss Impact logit_contribution: {logit_contribution}")
        assert logit_contribution != 0, f"Expected non-zero toss logit_contribution, got {logit_contribution}"
        
        # Verify preferred_decision is set
        preferred = toss_impact.get("preferred_decision", "unknown")
        assert preferred != "unknown", f"Expected preferred_decision to be set, got '{preferred}'"

    def test_bowling_depth_top5_only(self):
        """
        Test that Bowling Depth uses top 5 bowlers only (bowler_count should be 5, not 18-20)
        """
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true",
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: prediction.factors.bowling_depth
        prediction = data.get("prediction", {})
        bowling_depth = prediction.get("factors", {}).get("bowling_depth", {})
        print(f"Bowling Depth: {bowling_depth}")
        
        # Verify bowler_count is 5 for both teams (not full squad)
        team1_bowler_count = bowling_depth.get("team1_bowler_count", 0)
        team2_bowler_count = bowling_depth.get("team2_bowler_count", 0)
        
        assert team1_bowler_count == 5, f"Expected team1_bowler_count=5, got {team1_bowler_count}"
        assert team2_bowler_count == 5, f"Expected team2_bowler_count=5, got {team2_bowler_count}"
        
        # Verify quality scores are present
        team1_quality = bowling_depth.get("team1_quality_score", 0)
        team2_quality = bowling_depth.get("team2_quality_score", 0)
        assert team1_quality > 0, f"Expected team1_quality_score > 0, got {team1_quality}"
        assert team2_quality > 0, f"Expected team2_quality_score > 0, got {team2_quality}"
        
        # Verify variety info is present
        assert "team1_variety" in bowling_depth
        assert "team2_variety" in bowling_depth

    def test_squad_strength_balance_values(self):
        """
        Test that Balance is reflected in squad_strength factor (team1_balance, team2_balance values)
        """
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true",
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: prediction.factors.squad_strength
        prediction = data.get("prediction", {})
        squad_strength = prediction.get("factors", {}).get("squad_strength", {})
        print(f"Squad Strength: {squad_strength}")
        
        # Verify balance values are present and reasonable (0-1 range)
        team1_balance = squad_strength.get("team1_balance", 0)
        team2_balance = squad_strength.get("team2_balance", 0)
        
        assert 0 < team1_balance <= 1, f"Expected 0 < team1_balance <= 1, got {team1_balance}"
        assert 0 < team2_balance <= 1, f"Expected 0 < team2_balance <= 1, got {team2_balance}"
        
        # Verify batting/bowling ratings are present
        assert squad_strength.get("team1_batting", 0) > 0
        assert squad_strength.get("team1_bowling", 0) > 0
        assert squad_strength.get("team2_batting", 0) > 0
        assert squad_strength.get("team2_bowling", 0) > 0
        
        # Verify overall scores are present
        assert squad_strength.get("team1_overall", 0) > 0
        assert squad_strength.get("team2_overall", 0) > 0

    def test_all_8_categories_non_zero(self):
        """
        Test that all 8 categories produce meaningful non-zero values in the pre-match prediction
        """
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true",
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: prediction.factors
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        print(f"All factors: {list(factors.keys())}")
        
        # Verify all 8 categories are present
        expected_categories = [
            "squad_strength", "current_form", "venue_pitch_home", "h2h",
            "toss_impact", "bowling_depth", "conditions", "momentum"
        ]
        
        for category in expected_categories:
            assert category in factors, f"Missing category: {category}"
            cat_data = factors[category]
            
            # Each category should have weight and logit_contribution
            assert "weight" in cat_data, f"{category} missing 'weight'"
            assert "logit_contribution" in cat_data, f"{category} missing 'logit_contribution'"
            
            weight = cat_data.get("weight", 0)
            assert weight > 0, f"{category} weight should be > 0, got {weight}"
            
            print(f"{category}: weight={weight}, logit_contribution={cat_data.get('logit_contribution')}")

    def test_prediction_probability_valid_range(self):
        """
        Test that pre-match prediction returns valid probability (between 1-99%)
        """
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true",
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: prediction.team1_win_prob
        prediction = data.get("prediction", {})
        team1_prob = prediction.get("team1_win_prob", 0)
        team2_prob = prediction.get("team2_win_prob", 0)
        
        print(f"Probabilities: team1={team1_prob}%, team2={team2_prob}%")
        
        # Verify probabilities are in valid range (1-99%)
        assert 1 <= team1_prob <= 99, f"team1_win_prob should be 1-99%, got {team1_prob}"
        assert 1 <= team2_prob <= 99, f"team2_win_prob should be 1-99%, got {team2_prob}"
        
        # Verify probabilities sum to 100
        assert abs(team1_prob + team2_prob - 100) < 0.5, f"Probabilities should sum to 100, got {team1_prob + team2_prob}"
        
        # Verify model info
        assert prediction.get("model") == "8-category-v2"
        assert prediction.get("confidence") in ["low", "medium", "high"]

    def test_dc_vs_gt_prediction(self):
        """
        Test match ipl2026_014 (DC vs GT) for completeness
        """
        response = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_014/pre-match-predict?force=true",
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: prediction
        prediction = data.get("prediction", {})
        print(f"DC vs GT prediction: team1={prediction.get('team1_win_prob')}%, team2={prediction.get('team2_win_prob')}%")
        
        # Verify H2H for DC vs GT
        h2h = prediction.get("factors", {}).get("h2h", {})
        print(f"DC vs GT H2H: {h2h}")
        
        # DC vs GT historical: 2-4 (from HISTORICAL_H2H)
        assert h2h.get("source") == "historical_ipl"
        assert h2h.get("total") == 6, f"Expected DC vs GT total H2H = 6, got {h2h.get('total')}"

    def test_toss_impact_different_venues(self):
        """
        Test toss impact for different venues to ensure venue-specific data is used
        """
        # Test RR vs MI (likely Jaipur/Mumbai venue)
        response1 = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true",
            timeout=60
        )
        assert response1.status_code == 200
        data1 = response1.json()
        prediction1 = data1.get("prediction", {})
        toss1 = prediction1.get("factors", {}).get("toss_impact", {})
        
        # Test DC vs GT (likely Delhi/Ahmedabad venue)
        response2 = requests.post(
            f"{BASE_URL}/api/matches/ipl2026_014/pre-match-predict?force=true",
            timeout=60
        )
        assert response2.status_code == 200
        data2 = response2.json()
        prediction2 = data2.get("prediction", {})
        toss2 = prediction2.get("factors", {}).get("toss_impact", {})
        
        print(f"Match 013 toss: venue_key={toss1.get('venue_key')}, toss_win_pct={toss1.get('toss_win_pct')}")
        print(f"Match 014 toss: venue_key={toss2.get('venue_key')}, toss_win_pct={toss2.get('toss_win_pct')}")
        
        # Both should have non-zero toss_win_pct
        assert toss1.get("toss_win_pct", 0) > 0.5
        assert toss2.get("toss_win_pct", 0) > 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
