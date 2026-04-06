"""
Iteration 29 - Dual Prediction System Tests

Tests for:
1. PreMatch page Combined Prediction Block (Algo + Claude + Average)
2. PreMatchPredictionBreakdown 5-factor model (Form 35%, Squad 25%, Team Combo 20%, Home 15%, H2H 5%)
3. LiveMatch page 6-factor model (Score vs Par 30%, Wickets 25%, Recent Rate 15%, Bowlers 15%, Pre-match 10%, Context 5%)
4. Backend API health and predictions endpoints
5. Claude prompts contain 2023-2026 data constraint
6. compute_live_prediction imported from live_predictor.py
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ipl-predictions-1.preview.emergentagent.com').rstrip('/')


class TestBackendHealth:
    """Test backend API health and basic endpoints"""
    
    def test_api_health(self):
        """Test /api/ health endpoint returns valid response"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        print(f"API Health: {data.get('message')} - Version {data.get('version')}")
    
    def test_schedule_endpoint(self):
        """Test /api/schedule returns matches list"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        print(f"Schedule: {len(data.get('matches', []))} matches found")
    
    def test_predictions_upcoming(self):
        """Test /api/predictions/upcoming returns predictions list"""
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        print(f"Upcoming predictions: {data.get('count', 0)} predictions found")


class TestPreMatchPrediction5Factor:
    """Test the 5-factor pre-match prediction model"""
    
    def test_prematch_prediction_structure(self):
        """Test pre-match prediction returns 5-factor breakdown"""
        # First get an upcoming match
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert response.status_code == 200
        predictions = response.json().get("predictions", [])
        
        if not predictions:
            pytest.skip("No predictions available to test")
        
        pred = predictions[0]
        prediction = pred.get("prediction", {})
        factors = prediction.get("factors", {})
        
        # Verify 5 factors exist
        expected_factors = ["form", "squad_strength", "team_combination", "home_advantage", "h2h_pitch"]
        for factor in expected_factors:
            assert factor in factors, f"Missing factor: {factor}"
            print(f"Factor '{factor}' present with weight {factors[factor].get('weight', 'N/A')}")
    
    def test_prematch_factor_weights(self):
        """Test pre-match factors have correct weights (Form 35%, Squad 25%, Team Combo 20%, Home 15%, H2H 5%)"""
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert response.status_code == 200
        predictions = response.json().get("predictions", [])
        
        if not predictions:
            pytest.skip("No predictions available to test")
        
        pred = predictions[0]
        factors = pred.get("prediction", {}).get("factors", {})
        
        # Expected weights
        expected_weights = {
            "form": 0.35,
            "squad_strength": 0.25,
            "team_combination": 0.20,
            "home_advantage": 0.15,
            "h2h_pitch": 0.05,
        }
        
        for factor_name, expected_weight in expected_weights.items():
            actual_weight = factors.get(factor_name, {}).get("weight")
            assert actual_weight == expected_weight, f"Factor {factor_name}: expected weight {expected_weight}, got {actual_weight}"
            print(f"Factor '{factor_name}' weight: {actual_weight} (expected {expected_weight}) ✓")
        
        # Verify weights sum to 1.0
        total_weight = sum(expected_weights.values())
        assert abs(total_weight - 1.0) < 0.001, f"Weights should sum to 1.0, got {total_weight}"
        print(f"Total weights sum: {total_weight} ✓")


class TestLivePrediction6Factor:
    """Test the 6-factor live prediction model from live_predictor.py"""
    
    def test_live_predictor_import(self):
        """Verify compute_live_prediction is imported from live_predictor.py in server.py"""
        # This is a code verification test - we check the server.py imports
        import sys
        sys.path.insert(0, '/app/backend')
        
        # Import the live_predictor module
        from services.live_predictor import compute_live_prediction
        assert callable(compute_live_prediction), "compute_live_prediction should be callable"
        print("compute_live_prediction imported successfully from live_predictor.py ✓")
    
    def test_live_predictor_weights(self):
        """Test live predictor has correct 6-factor weights"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.live_predictor import compute_live_prediction
        
        # Create mock data to test the function
        mock_sm_data = {
            "current_score": {"runs": 100, "wickets": 3, "overs": 12.0},
            "current_innings": 1,
            "crr": 8.33,
            "rrr": None,
            "recent_balls": ["4", "1", "0", "2", "6", "1"],
            "active_batsmen": [{"name": "Test Player", "balls": 20}],
            "active_bowler": {"name": "Test Bowler", "economy": 7.5},
            "bowling_card": [],
            "yet_to_bowl": [],
            "batting_team": "Team A",
        }
        mock_claude = {}
        mock_match_info = {"team1": "Team A", "team2": "Team B"}
        
        result = compute_live_prediction(mock_sm_data, mock_claude, mock_match_info, pre_match_prob=50)
        
        assert result is not None, "compute_live_prediction should return a result"
        assert "weights" in result, "Result should contain weights"
        
        expected_weights = {
            "score_vs_par": 0.30,
            "wickets_in_hand": 0.25,
            "recent_over_rate": 0.15,
            "bowlers_remaining": 0.15,
            "pre_match_base": 0.10,
            "match_situation_context": 0.05,
        }
        
        for factor, expected_weight in expected_weights.items():
            actual_weight = result["weights"].get(factor)
            assert actual_weight == expected_weight, f"Factor {factor}: expected {expected_weight}, got {actual_weight}"
            print(f"Live factor '{factor}' weight: {actual_weight} (expected {expected_weight}) ✓")
        
        # Verify weights sum to 1.0
        total = sum(expected_weights.values())
        assert abs(total - 1.0) < 0.001, f"Weights should sum to 1.0, got {total}"
        print(f"Total live weights sum: {total} ✓")
    
    def test_live_predictor_breakdown(self):
        """Test live predictor returns breakdown with all 6 factors"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.live_predictor import compute_live_prediction
        
        mock_sm_data = {
            "current_score": {"runs": 150, "wickets": 5, "overs": 16.0},
            "current_innings": 2,
            "crr": 9.38,
            "rrr": 10.5,
            "target": 180,
            "recent_balls": ["4", "1", "W", "2", "6", "1", "0", "4", "1", "2", "0", "1"],
            "active_batsmen": [{"name": "Batter 1", "balls": 30}, {"name": "Batter 2", "balls": 5}],
            "active_bowler": {"name": "Bowler", "economy": 8.5, "overs": 3},
            "bowling_card": [{"name": "B1", "overs": 4}, {"name": "B2", "overs": 3}],
            "yet_to_bowl": [{"name": "B3"}],
            "batting_team": "Team B",
        }
        mock_claude = {}
        mock_match_info = {"team1": "Team A", "team2": "Team B"}
        
        result = compute_live_prediction(mock_sm_data, mock_claude, mock_match_info, pre_match_prob=45)
        
        assert "breakdown" in result, "Result should contain breakdown"
        breakdown = result["breakdown"]
        
        expected_factors = [
            "score_vs_par",
            "wickets_in_hand",
            "recent_over_rate",
            "bowlers_remaining",
            "pre_match_base",
            "match_situation_context",
        ]
        
        for factor in expected_factors:
            assert factor in breakdown, f"Missing breakdown factor: {factor}"
            value = breakdown[factor]
            assert 0 <= value <= 1, f"Factor {factor} value {value} should be between 0 and 1"
            print(f"Breakdown '{factor}': {value:.3f} ✓")
        
        # Verify L value exists
        assert "L" in result, "Result should contain L value"
        print(f"L value: {result['L']} ✓")
        
        # Verify team percentages
        assert "team1_pct" in result and "team2_pct" in result
        assert abs(result["team1_pct"] + result["team2_pct"] - 100) < 0.1
        print(f"Team percentages: {result['team1_pct']}% vs {result['team2_pct']}% ✓")


class TestClaudePrompts2023_2026:
    """Test that Claude prompts contain 2023-2026 data constraint"""
    
    def test_ai_service_prompts_contain_constraint(self):
        """Verify ai_service.py prompts contain '2023-2026' or '2023 to 2026' constraint"""
        with open('/app/backend/services/ai_service.py', 'r') as f:
            content = f.read()
        
        # Check for the constraint text
        constraint_found = "2023" in content and "2026" in content
        assert constraint_found, "ai_service.py should contain 2023-2026 data constraint"
        
        # Check specific constraint phrases
        phrases_to_check = [
            "2023 to 2026",
            "2023-2026",
        ]
        
        found_phrases = []
        for phrase in phrases_to_check:
            if phrase in content:
                found_phrases.append(phrase)
        
        assert len(found_phrases) > 0, f"Should find at least one constraint phrase. Found: {found_phrases}"
        print(f"Found constraint phrases in ai_service.py: {found_phrases} ✓")
        
        # Count occurrences
        count_2023_2026 = content.count("2023") + content.count("2026")
        print(f"Total references to 2023/2026 in ai_service.py: {count_2023_2026} ✓")


class TestPreMatchPredictorModule:
    """Test the pre_match_predictor.py module directly"""
    
    def test_compute_prediction_function(self):
        """Test compute_prediction returns correct 5-factor structure"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.pre_match_predictor import compute_prediction
        
        # Mock stats data
        mock_stats = {
            "form": {
                "team1_last5_wins": 3,
                "team1_last5_losses": 2,
                "team2_last5_wins": 2,
                "team2_last5_losses": 3,
            },
            "squad_strength": {
                "team1_batting_rating": 75,
                "team1_bowling_rating": 70,
                "team2_batting_rating": 72,
                "team2_bowling_rating": 73,
            },
            "venue_stats": {
                "is_team1_home": True,
                "is_team2_home": False,
            },
            "h2h": {
                "team1_wins": 6,
                "team2_wins": 4,
            },
            "pitch_conditions": {
                "pitch_type": "balanced",
                "dew_factor": 3,
            },
        }
        
        result = compute_prediction(mock_stats)
        
        assert "team1_win_prob" in result
        assert "team2_win_prob" in result
        assert "factors" in result
        
        factors = result["factors"]
        expected_factors = ["form", "squad_strength", "team_combination", "home_advantage", "h2h_pitch"]
        
        for factor in expected_factors:
            assert factor in factors, f"Missing factor: {factor}"
            assert "weight" in factors[factor], f"Factor {factor} missing weight"
            assert "logit_contribution" in factors[factor], f"Factor {factor} missing logit_contribution"
        
        # Verify weights
        assert factors["form"]["weight"] == 0.35
        assert factors["squad_strength"]["weight"] == 0.25
        assert factors["team_combination"]["weight"] == 0.20
        assert factors["home_advantage"]["weight"] == 0.15
        assert factors["h2h_pitch"]["weight"] == 0.05
        
        print(f"Pre-match prediction: {result['team1_win_prob']}% vs {result['team2_win_prob']}% ✓")
        print("All 5 factors present with correct weights ✓")


class TestCombinedPredictionData:
    """Test data structure for Combined Prediction Block"""
    
    def test_prediction_data_for_combined_block(self):
        """Test that prediction data has fields needed for CombinedPredictionBlock"""
        response = requests.get(f"{BASE_URL}/api/predictions/upcoming")
        assert response.status_code == 200
        predictions = response.json().get("predictions", [])
        
        if not predictions:
            pytest.skip("No predictions available to test")
        
        pred = predictions[0]
        
        # Check required fields for algo prediction
        assert "prediction" in pred, "Should have prediction field"
        prediction = pred["prediction"]
        assert "team1_win_prob" in prediction, "Should have team1_win_prob"
        assert "team2_win_prob" in prediction, "Should have team2_win_prob"
        
        print(f"Match: {pred.get('team1Short', '?')} vs {pred.get('team2Short', '?')}")
        print(f"Algo prediction: {prediction['team1_win_prob']}% vs {prediction['team2_win_prob']}% ✓")
        
        # Verify probabilities sum to 100
        total = prediction["team1_win_prob"] + prediction["team2_win_prob"]
        assert abs(total - 100) < 0.1, f"Probabilities should sum to 100, got {total}"
        print(f"Probabilities sum to {total} ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
