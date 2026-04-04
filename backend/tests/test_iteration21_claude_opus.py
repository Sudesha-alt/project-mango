"""
Iteration 21 Tests: Claude Opus Integration
Tests for the major refactor switching from GPT-5.4 to Claude Opus for predictions and scraping.

Features tested:
1. GET /api/ shows dataSource as 'Claude Opus + Web Scraping'
2. POST /api/matches/{matchId}/claude-analysis returns rich narrative analysis
3. POST /api/matches/{matchId}/claude-live returns real-time analysis
4. POST /api/matches/{matchId}/chat works (now powered by Claude Opus)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MATCH_ID = "ipl2026_008"  # MI vs DC - has cached Claude analysis and live data


class TestClaudeOpusIntegration:
    """Tests for Claude Opus integration replacing GPT-5.4"""

    def test_api_root_shows_claude_opus_data_source(self):
        """GET /api/ should show dataSource as 'Claude Opus + Web Scraping'"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert "dataSource" in data
        assert data["dataSource"] == "Claude Opus + Web Scraping"
        print(f"✓ API root shows dataSource: {data['dataSource']}")

    def test_claude_analysis_endpoint_returns_rich_data(self):
        """POST /api/matches/{matchId}/claude-analysis returns rich narrative analysis"""
        response = requests.post(f"{BASE_URL}/api/matches/{MATCH_ID}/claude-analysis")
        assert response.status_code == 200
        
        data = response.json()
        assert "matchId" in data
        assert data["matchId"] == MATCH_ID
        assert "analysis" in data
        
        analysis = data["analysis"]
        # Check for required fields in Claude analysis
        assert "team1_win_pct" in analysis
        assert "team2_win_pct" in analysis
        assert "headline" in analysis
        assert "factors" in analysis
        assert isinstance(analysis["factors"], list)
        assert len(analysis["factors"]) > 0
        
        # Check factor structure
        factor = analysis["factors"][0]
        assert "title" in factor
        assert "analysis" in factor
        assert "tag" in factor
        assert "favors" in factor
        
        # Check for injuries
        assert "key_injuries" in analysis
        
        # Check for toss scenarios
        assert "batting_first_scenario" in analysis
        
        # Check for prediction summary
        assert "prediction_summary" in analysis
        assert "confidence" in analysis
        
        # Check for deciding logic
        assert "deciding_logic" in analysis
        
        print(f"✓ Claude analysis returned with {len(analysis['factors'])} factors")
        print(f"  - Win probabilities: {analysis['team1_win_pct']}% vs {analysis['team2_win_pct']}%")
        print(f"  - Headline: {analysis['headline'][:60]}...")
        print(f"  - Confidence: {analysis['confidence']}")

    def test_claude_analysis_has_team_tags_on_factors(self):
        """Claude Analysis factors should have team tags (favors field)"""
        response = requests.post(f"{BASE_URL}/api/matches/{MATCH_ID}/claude-analysis")
        assert response.status_code == 200
        
        data = response.json()
        analysis = data["analysis"]
        factors = analysis["factors"]
        
        # Check that factors have favors field with valid values
        valid_favors = ["MI", "DC", "NEUTRAL"]
        for factor in factors:
            assert "favors" in factor
            assert factor["favors"] in valid_favors, f"Invalid favors value: {factor['favors']}"
        
        # Count factors by team
        mi_factors = sum(1 for f in factors if f["favors"] == "MI")
        dc_factors = sum(1 for f in factors if f["favors"] == "DC")
        neutral_factors = sum(1 for f in factors if f["favors"] == "NEUTRAL")
        
        print(f"✓ Factor distribution: MI={mi_factors}, DC={dc_factors}, NEUTRAL={neutral_factors}")

    def test_claude_live_endpoint_returns_realtime_analysis(self):
        """POST /api/matches/{matchId}/claude-live returns real-time analysis"""
        response = requests.post(f"{BASE_URL}/api/matches/{MATCH_ID}/claude-live")
        assert response.status_code == 200
        
        data = response.json()
        assert "matchId" in data
        assert data["matchId"] == MATCH_ID
        assert "analysis" in data
        
        analysis = data["analysis"]
        # Check for required live analysis fields
        assert "current_state_summary" in analysis
        assert "momentum" in analysis
        assert "momentum_reason" in analysis
        assert "win_probability" in analysis
        
        # Check for player assessments
        assert "key_batsman_assessment" in analysis
        assert "key_bowler_assessment" in analysis
        
        # Check for phase and betting advice
        assert "phase_analysis" in analysis
        assert "betting_advice" in analysis
        assert "projected_outcome" in analysis
        assert "confidence" in analysis
        
        print(f"✓ Claude live analysis returned")
        print(f"  - Momentum: {analysis['momentum']}")
        print(f"  - Win probability: {analysis['win_probability']}")
        print(f"  - Confidence: {analysis['confidence']}")

    def test_chat_endpoint_works_with_claude(self):
        """POST /api/matches/{matchId}/chat should work (now powered by Claude Opus)"""
        payload = {
            "question": "Should I bet on MI?",
            "risk_tolerance": "balanced"
        }
        response = requests.post(
            f"{BASE_URL}/api/matches/{MATCH_ID}/chat",
            json=payload
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "question" in data
        assert data["question"] == "Should I bet on MI?"
        assert "answer" in data
        assert len(data["answer"]) > 50  # Should have substantial response
        assert "risk_tolerance" in data
        assert "consultation_summary" in data
        
        # Check consultation summary structure
        summary = data["consultation_summary"]
        assert "win_probability" in summary
        assert "value_signal" in summary
        assert "confidence" in summary
        
        print(f"✓ Chat endpoint working with Claude Opus")
        print(f"  - Answer length: {len(data['answer'])} chars")
        print(f"  - Value signal: {summary['value_signal']}")

    def test_chat_with_different_risk_tolerances(self):
        """Chat endpoint should respect different risk tolerance levels"""
        for risk in ["conservative", "balanced", "aggressive"]:
            payload = {
                "question": "Is this a good bet?",
                "risk_tolerance": risk
            }
            response = requests.post(
                f"{BASE_URL}/api/matches/{MATCH_ID}/chat",
                json=payload
            )
            assert response.status_code == 200
            data = response.json()
            assert data["risk_tolerance"] == risk
            print(f"✓ Chat works with risk_tolerance={risk}")


class TestClaudeAnalysisCache:
    """Tests for Claude analysis caching behavior"""

    def test_claude_analysis_is_cached(self):
        """Claude analysis should be cached in DB for fast retrieval"""
        # First call - may be cached already
        response1 = requests.post(f"{BASE_URL}/api/matches/{MATCH_ID}/claude-analysis")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second call - should return cached result
        response2 = requests.post(f"{BASE_URL}/api/matches/{MATCH_ID}/claude-analysis")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Both should have same generatedAt timestamp (cached)
        assert data1.get("generatedAt") == data2.get("generatedAt")
        print(f"✓ Claude analysis is cached (generatedAt: {data1.get('generatedAt')})")

    def test_claude_analysis_has_model_info(self):
        """Claude analysis should include model information"""
        response = requests.post(f"{BASE_URL}/api/matches/{MATCH_ID}/claude-analysis")
        assert response.status_code == 200
        
        data = response.json()
        assert "model" in data
        assert "claude" in data["model"].lower()
        print(f"✓ Model info present: {data['model']}")


class TestMatchStateWithLiveData:
    """Tests for match state endpoint with live data"""

    def test_match_state_returns_live_data(self):
        """GET /api/matches/{matchId}/state should return live data for ipl2026_008"""
        response = requests.get(f"{BASE_URL}/api/matches/{MATCH_ID}/state")
        assert response.status_code == 200
        
        data = response.json()
        assert "matchId" in data
        assert data["matchId"] == MATCH_ID
        
        # Should have live data components
        assert "batsmen" in data or "liveData" in data
        assert "probabilities" in data or "aiPrediction" in data
        
        print(f"✓ Match state returned for {MATCH_ID}")
        if "batsmen" in data and data["batsmen"]:
            print(f"  - Batsmen: {[b['name'] for b in data['batsmen'][:2]]}")


class TestWebScraperIntegration:
    """Tests to verify web scraper is being used"""

    def test_api_indicates_web_scraping_source(self):
        """API should indicate web scraping is the data source"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert "Web Scraping" in data.get("dataSource", "")
        print(f"✓ Web scraping confirmed in dataSource")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
