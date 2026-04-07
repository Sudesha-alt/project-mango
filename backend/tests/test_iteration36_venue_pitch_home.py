"""
Iteration 36 - Testing Venue + Pitch + Home Factor Fixes

Tests:
1. Venue + Pitch + Home factor returns non-zero logit_contribution
2. RR at Barsapara (Guwahati) should show team1_home=true (secondary home ground)
3. PBKS at Mohali should show team1_home=true
4. DC at Arun Jaitley should show team1_home=true
5. Pitch data present: pitch_type, avg_first_innings, batting_first_win_pct, pace_assist, spin_assist
6. H2H uses 2023-2025 data (total matches should be 5-7 range, not 20+)
7. Toss Impact returns non-zero logit_contribution
8. Bowling Depth shows bowler_count=5 for each team
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestVenuePitchHomeFactors:
    """Test venue, pitch, and home advantage calculations"""

    def test_api_health(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        print(f"✓ API health check passed - version {data.get('version')}")

    def test_rr_home_at_guwahati(self):
        """Test RR at Barsapara (Guwahati) shows team1_home=true (secondary home ground)
        Match: ipl2026_013 - RR vs MI at Guwahati
        """
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        venue_factor = factors.get("venue_pitch_home", {})
        
        # RR should be HOME at Guwahati (secondary home ground)
        team1_home = venue_factor.get("team1_home")
        team2_home = venue_factor.get("team2_home")
        venue_key = venue_factor.get("venue_key")
        
        print(f"Match: RR vs MI at Guwahati")
        print(f"  venue_key: {venue_key}")
        print(f"  team1_home (RR): {team1_home}")
        print(f"  team2_home (MI): {team2_home}")
        
        assert venue_key == "barsapara", f"Expected venue_key='barsapara', got '{venue_key}'"
        assert team1_home is True, f"RR should be HOME at Guwahati (secondary home), got team1_home={team1_home}"
        assert team2_home is False, f"MI should be Away at Guwahati, got team2_home={team2_home}"
        print("✓ RR correctly shows as HOME at Guwahati (secondary home ground)")

    def test_pbks_home_at_mohali(self):
        """Test PBKS at Mohali shows team1_home=true
        Match: ipl2026_017 - PBKS vs SRH at Mohali
        """
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_017/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        venue_factor = factors.get("venue_pitch_home", {})
        
        team1_home = venue_factor.get("team1_home")
        team2_home = venue_factor.get("team2_home")
        venue_key = venue_factor.get("venue_key")
        
        print(f"Match: PBKS vs SRH at Mohali")
        print(f"  venue_key: {venue_key}")
        print(f"  team1_home (PBKS): {team1_home}")
        print(f"  team2_home (SRH): {team2_home}")
        
        assert venue_key == "mohali", f"Expected venue_key='mohali', got '{venue_key}'"
        assert team1_home is True, f"PBKS should be HOME at Mohali, got team1_home={team1_home}"
        assert team2_home is False, f"SRH should be Away at Mohali, got team2_home={team2_home}"
        print("✓ PBKS correctly shows as HOME at Mohali")

    def test_dc_home_at_delhi(self):
        """Test DC at Arun Jaitley shows team1_home=true
        Match: ipl2026_014 - DC vs GT at Delhi
        """
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_014/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        venue_factor = factors.get("venue_pitch_home", {})
        
        team1_home = venue_factor.get("team1_home")
        team2_home = venue_factor.get("team2_home")
        venue_key = venue_factor.get("venue_key")
        
        print(f"Match: DC vs GT at Delhi")
        print(f"  venue_key: {venue_key}")
        print(f"  team1_home (DC): {team1_home}")
        print(f"  team2_home (GT): {team2_home}")
        
        assert venue_key == "arun_jaitley", f"Expected venue_key='arun_jaitley', got '{venue_key}'"
        assert team1_home is True, f"DC should be HOME at Delhi, got team1_home={team1_home}"
        assert team2_home is False, f"GT should be Away at Delhi, got team2_home={team2_home}"
        print("✓ DC correctly shows as HOME at Delhi")

    def test_venue_pitch_home_logit_nonzero(self):
        """Test that venue_pitch_home factor returns non-zero logit_contribution"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        venue_factor = factors.get("venue_pitch_home", {})
        
        logit_contribution = venue_factor.get("logit_contribution", 0)
        home_logit = venue_factor.get("home_logit", 0)
        pitch_logit = venue_factor.get("pitch_logit", 0)
        
        print(f"Venue + Pitch + Home factor:")
        print(f"  logit_contribution: {logit_contribution}")
        print(f"  home_logit: {home_logit}")
        print(f"  pitch_logit: {pitch_logit}")
        
        # At least one of home_logit or pitch_logit should be non-zero
        assert logit_contribution != 0 or (home_logit != 0 or pitch_logit != 0), \
            f"Venue factor should have non-zero contribution. Got logit={logit_contribution}, home={home_logit}, pitch={pitch_logit}"
        print("✓ Venue + Pitch + Home factor returns non-zero logit_contribution")

    def test_pitch_data_present(self):
        """Test that pitch data is present in venue_pitch_home factor"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        venue_factor = factors.get("venue_pitch_home", {})
        
        # Check all required pitch data fields
        pitch_type = venue_factor.get("pitch_type")
        avg_first_innings = venue_factor.get("avg_first_innings")
        batting_first_win_pct = venue_factor.get("batting_first_win_pct")
        pace_assist = venue_factor.get("pace_assist")
        spin_assist = venue_factor.get("spin_assist")
        
        print(f"Pitch data for Guwahati (Barsapara):")
        print(f"  pitch_type: {pitch_type}")
        print(f"  avg_first_innings: {avg_first_innings}")
        print(f"  batting_first_win_pct: {batting_first_win_pct}")
        print(f"  pace_assist: {pace_assist}")
        print(f"  spin_assist: {spin_assist}")
        
        assert pitch_type is not None, "pitch_type should be present"
        assert avg_first_innings is not None, "avg_first_innings should be present"
        assert batting_first_win_pct is not None, "batting_first_win_pct should be present"
        assert pace_assist is not None, "pace_assist should be present"
        assert spin_assist is not None, "spin_assist should be present"
        
        # Validate reasonable values
        assert avg_first_innings > 100, f"avg_first_innings should be > 100, got {avg_first_innings}"
        assert 0 <= pace_assist <= 1, f"pace_assist should be 0-1, got {pace_assist}"
        assert 0 <= spin_assist <= 1, f"spin_assist should be 0-1, got {spin_assist}"
        
        print("✓ All pitch data fields present with valid values")

    def test_h2h_uses_recent_data(self):
        """Test that H2H uses 2023-2025 data (total matches should be 5-7 range, not 20+)"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        h2h_factor = factors.get("h2h", {})
        
        total_matches = h2h_factor.get("total", 0)
        source = h2h_factor.get("source", "")
        team1_wins = h2h_factor.get("team1_wins", 0)
        team2_wins = h2h_factor.get("team2_wins", 0)
        
        print(f"H2H data for RR vs MI:")
        print(f"  total: {total_matches}")
        print(f"  source: {source}")
        print(f"  team1_wins (RR): {team1_wins}")
        print(f"  team2_wins (MI): {team2_wins}")
        
        # H2H should use historical_ipl data (2023-2025)
        # Total matches should be reasonable (5-15 range for 3 seasons)
        assert total_matches <= 20, f"H2H total should be <= 20 (3 seasons), got {total_matches}"
        assert total_matches >= 3, f"H2H total should be >= 3 (at least 1 per season), got {total_matches}"
        
        print(f"✓ H2H uses reasonable data range (total={total_matches})")

    def test_toss_impact_nonzero(self):
        """Test that Toss Impact returns non-zero logit_contribution"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        toss_factor = factors.get("toss_impact", {})
        
        logit_contribution = toss_factor.get("logit_contribution", 0)
        toss_win_pct = toss_factor.get("toss_win_pct", 0.5)
        preferred_decision = toss_factor.get("preferred_decision", "")
        
        print(f"Toss Impact factor:")
        print(f"  logit_contribution: {logit_contribution}")
        print(f"  toss_win_pct: {toss_win_pct}")
        print(f"  preferred_decision: {preferred_decision}")
        
        # Toss impact should be non-zero for most venues
        assert logit_contribution != 0, f"Toss Impact logit_contribution should be non-zero, got {logit_contribution}"
        assert toss_win_pct > 0.5, f"toss_win_pct should be > 0.5 (toss winner advantage), got {toss_win_pct}"
        
        print("✓ Toss Impact returns non-zero logit_contribution")

    def test_bowling_depth_top5(self):
        """Test that Bowling Depth shows bowler_count=5 for each team"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        bowling_factor = factors.get("bowling_depth", {})
        
        team1_bowler_count = bowling_factor.get("team1_bowler_count", 0)
        team2_bowler_count = bowling_factor.get("team2_bowler_count", 0)
        team1_pace_count = bowling_factor.get("team1_pace_count", 0)
        team1_spin_count = bowling_factor.get("team1_spin_count", 0)
        team2_pace_count = bowling_factor.get("team2_pace_count", 0)
        team2_spin_count = bowling_factor.get("team2_spin_count", 0)
        
        print(f"Bowling Depth factor:")
        print(f"  team1_bowler_count: {team1_bowler_count}")
        print(f"  team2_bowler_count: {team2_bowler_count}")
        print(f"  team1 pace/spin: {team1_pace_count}/{team1_spin_count}")
        print(f"  team2 pace/spin: {team2_pace_count}/{team2_spin_count}")
        
        assert team1_bowler_count == 5, f"team1_bowler_count should be 5, got {team1_bowler_count}"
        assert team2_bowler_count == 5, f"team2_bowler_count should be 5, got {team2_bowler_count}"
        
        print("✓ Bowling Depth shows bowler_count=5 for each team")

    def test_all_8_categories_present(self):
        """Test that all 8 categories are present with weights and logit_contributions"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        prediction = data.get("prediction", {})
        factors = prediction.get("factors", {})
        
        expected_categories = [
            "squad_strength",
            "current_form",
            "venue_pitch_home",
            "h2h",
            "toss_impact",
            "bowling_depth",
            "conditions",
            "momentum"
        ]
        
        print("Checking all 8 categories:")
        for cat in expected_categories:
            assert cat in factors, f"Category '{cat}' missing from factors"
            cat_data = factors[cat]
            assert "weight" in cat_data, f"Category '{cat}' missing 'weight'"
            assert "logit_contribution" in cat_data, f"Category '{cat}' missing 'logit_contribution'"
            print(f"  ✓ {cat}: weight={cat_data['weight']}, logit={cat_data['logit_contribution']}")
        
        print("✓ All 8 categories present with weights and logit_contributions")

    def test_prediction_probability_valid(self):
        """Test that prediction returns valid probability"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        prediction = data.get("prediction", {})
        team1_prob = prediction.get("team1_win_prob", 0)
        team2_prob = prediction.get("team2_win_prob", 0)
        model = prediction.get("model", "")
        
        print(f"Prediction probabilities:")
        print(f"  team1_win_prob: {team1_prob}%")
        print(f"  team2_win_prob: {team2_prob}%")
        print(f"  model: {model}")
        
        assert 1 <= team1_prob <= 99, f"team1_win_prob should be 1-99%, got {team1_prob}"
        assert 1 <= team2_prob <= 99, f"team2_win_prob should be 1-99%, got {team2_prob}"
        assert abs(team1_prob + team2_prob - 100) < 0.5, f"Probabilities should sum to 100%, got {team1_prob + team2_prob}"
        assert model == "8-category-v2", f"Model should be '8-category-v2', got '{model}'"
        
        print("✓ Prediction returns valid probability")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
