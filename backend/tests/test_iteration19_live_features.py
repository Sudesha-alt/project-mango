"""
Iteration 19 Tests: Live Match Features
- No auto-fetch on page load (frontend behavior - tested via Playwright)
- Manual fetch button works
- Scheduler endpoint promotes matches to 'live'
- Schedule shows live matches
- Health endpoint shows scheduler active with 4PM/7PM IST
- Chat endpoint returns enriched answers with live context
- Consult tab is default (frontend behavior - tested via Playwright)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSchedulerAndLiveFeatures:
    """Test scheduler and live match promotion features"""
    
    def test_health_endpoint_scheduler_info(self):
        """GET /api/ should show scheduler active with 4PM/7PM IST next_runs"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        
        data = response.json()
        assert "scheduler" in data, "Response should contain scheduler info"
        
        scheduler = data["scheduler"]
        assert scheduler.get("active") == True, "Scheduler should be active"
        assert "next_runs" in scheduler, "Scheduler should have next_runs"
        
        next_runs = scheduler["next_runs"]
        assert "4:00 PM IST" in next_runs, "Should have 4PM IST scheduled"
        assert "7:00 PM IST" in next_runs, "Should have 7PM IST scheduled"
        print(f"✅ Scheduler active with next_runs: {next_runs}")
    
    def test_scheduler_promote_now_endpoint(self):
        """POST /api/scheduler/promote-now should promote today's matches to 'live'"""
        response = requests.post(f"{BASE_URL}/api/scheduler/promote-now")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "done", "Promote should return status=done"
        assert "live_matches" in data, "Should return live_matches count"
        print(f"✅ Scheduler promote-now: {data['live_matches']} live matches")
    
    def test_schedule_shows_live_matches(self):
        """GET /api/schedule should show matches with status 'live'"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        assert "live" in data, "Response should contain 'live' array"
        
        live_matches = data["live"]
        assert len(live_matches) >= 1, "Should have at least 1 live match"
        
        # Verify live match structure
        for match in live_matches:
            assert match.get("status") == "live", f"Match {match.get('matchId')} should have status='live'"
            assert "matchId" in match
            assert "team1" in match
            assert "team2" in match
        
        print(f"✅ Schedule shows {len(live_matches)} live matches")
        for m in live_matches:
            print(f"   - {m.get('matchId')}: {m.get('team1Short')} vs {m.get('team2Short')}")


class TestChatWithLiveContext:
    """Test chat endpoint returns enriched answers with live match data"""
    
    def test_chat_returns_enriched_answer(self):
        """POST /api/matches/{matchId}/chat should return answer referencing live data"""
        match_id = "ipl2026_008"  # MI vs DC with live data
        
        response = requests.post(
            f"{BASE_URL}/api/matches/{match_id}/chat",
            json={
                "question": "Who is winning right now?",
                "risk_tolerance": "balanced"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "answer" in data, "Response should contain 'answer'"
        assert "question" in data, "Response should contain 'question'"
        assert "consultation_summary" in data, "Response should contain 'consultation_summary'"
        
        answer = data["answer"]
        
        # Verify answer references live match context
        # Should mention score, batsmen, projected score, or algorithm probabilities
        live_context_indicators = [
            "18/2", "18-2",  # Current score
            "Rohit", "Tilak", "Rickelton",  # Batsmen names
            "Mukesh",  # Bowler name
            "144", "projected",  # Projected score
            "powerplay", "POWERPLAY",  # Phase
            "46", "47", "53", "54",  # Algorithm probabilities (around 46% MI)
            "wicket", "wkts",  # Wickets context
        ]
        
        has_live_context = any(indicator.lower() in answer.lower() for indicator in live_context_indicators)
        assert has_live_context, f"Answer should reference live match data. Got: {answer[:200]}..."
        
        print(f"✅ Chat returns enriched answer with live context")
        print(f"   Answer preview: {answer[:150]}...")
    
    def test_chat_consultation_summary_structure(self):
        """Chat response should include consultation_summary with key fields"""
        match_id = "ipl2026_008"
        
        response = requests.post(
            f"{BASE_URL}/api/matches/{match_id}/chat",
            json={
                "question": "Should I bet on MI?",
                "risk_tolerance": "aggressive"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get("consultation_summary", {})
        
        assert "win_probability" in summary, "Should have win_probability"
        assert "value_signal" in summary, "Should have value_signal"
        assert "confidence" in summary, "Should have confidence"
        assert "fair_odds" in summary, "Should have fair_odds"
        
        print(f"✅ Consultation summary: win_prob={summary['win_probability']}%, signal={summary['value_signal']}")


class TestMatchStateWithLiveData:
    """Test match state endpoint returns cached live data"""
    
    def test_match_state_has_live_data(self):
        """GET /api/matches/{matchId}/state should return cached live data"""
        match_id = "ipl2026_008"
        
        response = requests.get(f"{BASE_URL}/api/matches/{match_id}/state")
        assert response.status_code == 200
        
        data = response.json()
        
        # Should have live data from cache
        assert "liveData" in data, "Should have liveData"
        assert "probabilities" in data, "Should have probabilities"
        
        live_data = data.get("liveData", {})
        score = live_data.get("score", {})
        
        assert score.get("runs") is not None, "Should have runs in score"
        assert score.get("wickets") is not None, "Should have wickets in score"
        assert score.get("overs") is not None, "Should have overs in score"
        
        print(f"✅ Match state has live data: {score.get('runs')}/{score.get('wickets')} in {score.get('overs')} overs")
    
    def test_match_state_has_batsmen_and_bowler(self):
        """Match state should include current batsmen and bowler"""
        match_id = "ipl2026_008"
        
        response = requests.get(f"{BASE_URL}/api/matches/{match_id}/state")
        assert response.status_code == 200
        
        data = response.json()
        
        batsmen = data.get("batsmen", [])
        bowler = data.get("bowler", {})
        
        assert len(batsmen) >= 1, "Should have at least 1 batsman"
        assert bowler.get("name"), "Should have bowler name"
        
        print(f"✅ Batsmen: {[b.get('name') for b in batsmen]}")
        print(f"✅ Bowler: {bowler.get('name')}")
    
    def test_match_state_has_projected_score(self):
        """Match state should include projected_score in probabilities"""
        match_id = "ipl2026_008"
        
        response = requests.get(f"{BASE_URL}/api/matches/{match_id}/state")
        assert response.status_code == 200
        
        data = response.json()
        
        probs = data.get("probabilities", {})
        
        # live_prediction is computed on-the-fly in fetch-live, not stored in DB
        # But projected_score should be in probabilities
        assert "projected_score" in probs, "Should have projected_score in probabilities"
        assert probs["projected_score"] > 0, "Projected score should be positive"
        
        print(f"✅ Projected score: {probs.get('projected_score')}")
    
    def test_match_state_has_algorithm_probabilities(self):
        """Match state should include algorithm probabilities"""
        match_id = "ipl2026_008"
        
        response = requests.get(f"{BASE_URL}/api/matches/{match_id}/state")
        assert response.status_code == 200
        
        data = response.json()
        
        probs = data.get("probabilities", {})
        
        # Actual keys: ensemble, bayesian, monte_carlo, dls_resource, confidence_band, pressure_index, projected_score
        assert "ensemble" in probs, "Should have ensemble probability"
        assert "bayesian" in probs, "Should have bayesian probability"
        assert "monte_carlo" in probs, "Should have monte_carlo probability"
        assert "dls_resource" in probs, "Should have dls_resource probability"
        
        print(f"✅ Algorithm probabilities: ensemble={probs.get('ensemble'):.3f}, bayesian={probs.get('bayesian'):.3f}, monte_carlo={probs.get('monte_carlo'):.3f}")


class TestLiveMatchPromotion:
    """Test that promoted matches have correct status"""
    
    def test_promoted_match_has_live_status(self):
        """Promoted matches should have status='live'"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200
        
        data = response.json()
        matches = data.get("matches", [])
        
        # Find ipl2026_008 and ipl2026_009
        test_match_ids = ["ipl2026_008", "ipl2026_009"]
        
        for match_id in test_match_ids:
            match = next((m for m in matches if m.get("matchId") == match_id), None)
            assert match is not None, f"Match {match_id} should exist"
            assert match.get("status") == "live", f"Match {match_id} should have status='live'"
            assert "promotedAt" in match, f"Match {match_id} should have promotedAt timestamp"
        
        print(f"✅ Both test matches (ipl2026_008, ipl2026_009) have status='live' with promotedAt")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
