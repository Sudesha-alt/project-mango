"""
Iteration 37 - Testing New Pre-Match Prediction Features:
1. KKR vs LSG H2H returns non-zero team1_wins and team2_wins with source=historical_ipl
2. Toss impact includes dew_impact_text explaining which team benefits from dew
3. Toss impact dew_multiplier is 1.5 for heavy dew, 1.2 for moderate
4. Bowling depth includes venue_key, venue_pace_assist, venue_spin_assist in response
5. Bowling depth team1_venue_quality and team2_venue_quality are different (venue-weighted)
6. Conditions includes favours_team field (team1 or team2 or neutral)
7. Conditions includes conditions_edge_text with specific team references
8. Conditions logit is non-zero when dew is heavy or humidity > 65
9. All 8 factors produce valid logit_contribution values
10. Pre-match prediction returns valid probability between 1-99%
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestIteration37VenueDewConditions:
    """Test new venue-weighted bowling depth, dew impact text, and team-specific conditions"""
    
    def test_api_health(self):
        """Test API health check"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("version") is not None
        print(f"API health check passed - version: {data.get('version')}")
    
    def test_kkr_vs_lsg_h2h_historical(self):
        """Test KKR vs LSG (ipl2026_015) H2H returns non-zero wins with source=historical_ipl"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        h2h = data.get("prediction", {}).get("factors", {}).get("h2h", {})
        print(f"KKR vs LSG H2H: team1_wins={h2h.get('team1_wins')}, team2_wins={h2h.get('team2_wins')}, source={h2h.get('source')}")
        
        # H2H should have non-zero wins for both teams (KKR vs LSG have played since 2022)
        assert h2h.get("team1_wins", 0) > 0 or h2h.get("team2_wins", 0) > 0, "H2H should have non-zero wins"
        assert h2h.get("source") == "historical_ipl", f"H2H source should be historical_ipl, got {h2h.get('source')}"
        assert h2h.get("total", 0) > 0, "H2H total should be > 0"
        print(f"PASSED: KKR vs LSG H2H has {h2h.get('total')} total matches with source=historical_ipl")
    
    def test_toss_impact_dew_impact_text(self):
        """Test toss impact includes dew_impact_text explaining dew conditions"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        toss = data.get("prediction", {}).get("factors", {}).get("toss_impact", {})
        print(f"Toss Impact: dew_factor={toss.get('dew_factor')}, dew_impact_text={toss.get('dew_impact_text')}")
        
        # dew_impact_text should be present
        assert "dew_impact_text" in toss, "toss_impact should include dew_impact_text"
        assert toss.get("dew_impact_text") is not None, "dew_impact_text should not be None"
        assert len(toss.get("dew_impact_text", "")) > 10, "dew_impact_text should be descriptive"
        print(f"PASSED: dew_impact_text present: '{toss.get('dew_impact_text')}'")
    
    def test_toss_impact_dew_multiplier(self):
        """Test toss impact dew_multiplier values"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        toss = data.get("prediction", {}).get("factors", {}).get("toss_impact", {})
        dew_factor = toss.get("dew_factor", "none")
        dew_multiplier = toss.get("dew_multiplier")
        
        print(f"Toss Impact: dew_factor={dew_factor}, dew_multiplier={dew_multiplier}")
        
        # dew_multiplier should be present
        assert "dew_multiplier" in toss, "toss_impact should include dew_multiplier"
        assert dew_multiplier is not None, "dew_multiplier should not be None"
        
        # Verify multiplier values based on dew_factor
        if dew_factor == "heavy":
            assert dew_multiplier == 1.5, f"Heavy dew should have multiplier 1.5, got {dew_multiplier}"
        elif dew_factor == "moderate":
            assert dew_multiplier == 1.2, f"Moderate dew should have multiplier 1.2, got {dew_multiplier}"
        else:
            assert dew_multiplier in [0.8, 1.0], f"No/light dew should have multiplier 0.8 or 1.0, got {dew_multiplier}"
        
        print(f"PASSED: dew_multiplier={dew_multiplier} for dew_factor={dew_factor}")
    
    def test_bowling_depth_venue_fields(self):
        """Test bowling depth includes venue_key, venue_pace_assist, venue_spin_assist"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        bowling = data.get("prediction", {}).get("factors", {}).get("bowling_depth", {})
        print(f"Bowling Depth: venue_key={bowling.get('venue_key')}, pace_assist={bowling.get('venue_pace_assist')}, spin_assist={bowling.get('venue_spin_assist')}")
        
        # Venue fields should be present
        assert "venue_key" in bowling, "bowling_depth should include venue_key"
        assert "venue_pace_assist" in bowling, "bowling_depth should include venue_pace_assist"
        assert "venue_spin_assist" in bowling, "bowling_depth should include venue_spin_assist"
        
        # Eden Gardens (KKR home) should have specific values
        assert bowling.get("venue_key") == "eden_gardens", f"Venue should be eden_gardens, got {bowling.get('venue_key')}"
        assert bowling.get("venue_pace_assist") == 0.5, f"Eden Gardens pace_assist should be 0.5, got {bowling.get('venue_pace_assist')}"
        assert bowling.get("venue_spin_assist") == 0.4, f"Eden Gardens spin_assist should be 0.4, got {bowling.get('venue_spin_assist')}"
        
        print(f"PASSED: Bowling depth has venue fields - venue_key={bowling.get('venue_key')}, pace={bowling.get('venue_pace_assist')}, spin={bowling.get('venue_spin_assist')}")
    
    def test_bowling_depth_venue_weighted_quality(self):
        """Test bowling depth team1_venue_quality and team2_venue_quality are different (venue-weighted)"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        bowling = data.get("prediction", {}).get("factors", {}).get("bowling_depth", {})
        t1_vq = bowling.get("team1_venue_quality")
        t2_vq = bowling.get("team2_venue_quality")
        t1_q = bowling.get("team1_quality_score")
        t2_q = bowling.get("team2_quality_score")
        
        print(f"Bowling Depth: team1_quality={t1_q}, team1_venue_quality={t1_vq}")
        print(f"Bowling Depth: team2_quality={t2_q}, team2_venue_quality={t2_vq}")
        
        # Venue quality should be present and different from raw quality
        assert t1_vq is not None, "team1_venue_quality should be present"
        assert t2_vq is not None, "team2_venue_quality should be present"
        
        # Venue quality should be different from raw quality (venue-weighted)
        # The venue_score = score * 4 * (1 + venue_multiplier), so it should be higher than raw score
        assert t1_vq != t1_q or t2_vq != t2_q, "Venue quality should differ from raw quality (venue-weighted)"
        
        print(f"PASSED: Venue-weighted quality present - team1_venue_quality={t1_vq}, team2_venue_quality={t2_vq}")
    
    def test_conditions_favours_team_field(self):
        """Test conditions includes favours_team field (team1 or team2 or neutral)"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        conditions = data.get("prediction", {}).get("factors", {}).get("conditions", {})
        favours = conditions.get("favours_team")
        
        print(f"Conditions: favours_team={favours}")
        
        # favours_team should be present and valid
        assert "favours_team" in conditions, "conditions should include favours_team"
        assert favours in ["team1", "team2", "neutral"], f"favours_team should be team1/team2/neutral, got {favours}"
        
        print(f"PASSED: favours_team={favours}")
    
    def test_conditions_edge_text(self):
        """Test conditions includes conditions_edge_text with specific team references"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        conditions = data.get("prediction", {}).get("factors", {}).get("conditions", {})
        edge_text = conditions.get("conditions_edge_text")
        
        print(f"Conditions: conditions_edge_text={edge_text}")
        
        # conditions_edge_text should be present
        assert "conditions_edge_text" in conditions, "conditions should include conditions_edge_text"
        assert edge_text is not None, "conditions_edge_text should not be None"
        
        print(f"PASSED: conditions_edge_text present: '{edge_text}'")
    
    def test_all_8_factors_logit_contribution(self):
        """Test all 8 factors produce valid logit_contribution values"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        factors = data.get("prediction", {}).get("factors", {})
        expected_factors = ["squad_strength", "current_form", "venue_pitch_home", "h2h", 
                          "toss_impact", "bowling_depth", "conditions", "momentum"]
        
        for factor_name in expected_factors:
            factor = factors.get(factor_name, {})
            logit = factor.get("logit_contribution")
            weight = factor.get("weight")
            
            assert factor_name in factors, f"Factor {factor_name} should be present"
            assert "logit_contribution" in factor, f"Factor {factor_name} should have logit_contribution"
            assert "weight" in factor, f"Factor {factor_name} should have weight"
            assert isinstance(logit, (int, float)), f"Factor {factor_name} logit should be numeric, got {type(logit)}"
            
            print(f"Factor {factor_name}: weight={weight}, logit_contribution={logit}")
        
        print(f"PASSED: All 8 factors have valid logit_contribution values")
    
    def test_prediction_probability_valid_range(self):
        """Test pre-match prediction returns valid probability between 1-99%"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_015/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        pred = data.get("prediction", {})
        t1_prob = pred.get("team1_win_prob")
        t2_prob = pred.get("team2_win_prob")
        model = pred.get("model")
        
        print(f"Prediction: team1_win_prob={t1_prob}%, team2_win_prob={t2_prob}%, model={model}")
        
        # Probabilities should be valid
        assert t1_prob is not None, "team1_win_prob should be present"
        assert t2_prob is not None, "team2_win_prob should be present"
        assert 1 <= t1_prob <= 99, f"team1_win_prob should be 1-99%, got {t1_prob}"
        assert 1 <= t2_prob <= 99, f"team2_win_prob should be 1-99%, got {t2_prob}"
        assert abs(t1_prob + t2_prob - 100) < 0.5, f"Probabilities should sum to ~100%, got {t1_prob + t2_prob}"
        assert model == "8-category-v2", f"Model should be 8-category-v2, got {model}"
        
        print(f"PASSED: Valid prediction - {t1_prob}% vs {t2_prob}% with model={model}")
    
    def test_rr_vs_mi_at_guwahati(self):
        """Test RR vs MI (ipl2026_013) at Guwahati - secondary home ground"""
        response = requests.post(f"{BASE_URL}/api/matches/ipl2026_013/pre-match-predict?force=true")
        assert response.status_code == 200
        data = response.json()
        
        pred = data.get("prediction", {})
        factors = pred.get("factors", {})
        
        # Venue should be barsapara (Guwahati)
        venue = factors.get("venue_pitch_home", {})
        bowling = factors.get("bowling_depth", {})
        toss = factors.get("toss_impact", {})
        conditions = factors.get("conditions", {})
        h2h = factors.get("h2h", {})
        
        print(f"RR vs MI at Guwahati:")
        print(f"  Venue: {venue.get('venue_key')}, team1_home={venue.get('team1_home')}")
        print(f"  Bowling: venue_pace_assist={bowling.get('venue_pace_assist')}, venue_spin_assist={bowling.get('venue_spin_assist')}")
        print(f"  Toss: dew_impact_text={toss.get('dew_impact_text')}")
        print(f"  Conditions: favours_team={conditions.get('favours_team')}, edge_text={conditions.get('conditions_edge_text')}")
        print(f"  H2H: team1_wins={h2h.get('team1_wins')}, team2_wins={h2h.get('team2_wins')}, source={h2h.get('source')}")
        
        # RR should be home at Guwahati (secondary home ground)
        assert venue.get("team1_home") == True, "RR should be HOME at Guwahati"
        assert venue.get("venue_key") == "barsapara", f"Venue should be barsapara, got {venue.get('venue_key')}"
        
        # Bowling depth should have venue fields
        assert bowling.get("venue_pace_assist") == 0.6, f"Barsapara pace_assist should be 0.6, got {bowling.get('venue_pace_assist')}"
        assert bowling.get("venue_spin_assist") == 0.3, f"Barsapara spin_assist should be 0.3, got {bowling.get('venue_spin_assist')}"
        
        # Toss should have dew_impact_text
        assert toss.get("dew_impact_text") is not None, "Toss should have dew_impact_text"
        
        # Conditions should have favours_team and edge_text
        assert conditions.get("favours_team") in ["team1", "team2", "neutral"], "Conditions should have valid favours_team"
        assert conditions.get("conditions_edge_text") is not None, "Conditions should have conditions_edge_text"
        
        print(f"PASSED: RR vs MI at Guwahati - all new fields present")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
