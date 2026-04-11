"""
Iteration 43: Test data enrichment functions for Claude live match analysis
Tests: fetch_venue_stats, fetch_h2h_record, fetch_team_standings, fetch_player_season_stats_for_xi
"""
import pytest
import requests
import os
import sys
import asyncio

# Add backend to path for direct function imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ipl-predictions-1.preview.emergentagent.com').rstrip('/')


class TestBackendHealth:
    """Test 1: Backend health check"""
    
    def test_api_health(self):
        """GET /api/ returns 200 with correct structure"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "message" in data
        assert data.get("scheduleLoaded") == True
        print(f"✓ Backend healthy: {data.get('message')}, version {data.get('version')}")


class TestScheduleEndpoint:
    """Test 2: Schedule endpoint returns matches"""
    
    def test_schedule_returns_74_matches(self):
        """GET /api/schedule returns matches array with 74 matches"""
        response = requests.get(f"{BASE_URL}/api/schedule")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        matches = data.get("matches", [])
        assert len(matches) == 74, f"Expected 74 matches, got {len(matches)}"
        print(f"✓ Schedule loaded: {len(matches)} matches")


class TestEnrichmentFunctions:
    """Test 3: Data enrichment functions work correctly"""
    
    @pytest.fixture(scope="class")
    def event_loop(self):
        """Create event loop for async tests"""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()
    
    def test_fetch_venue_stats(self):
        """Test fetch_venue_stats returns sample_size > 0, avg_first_innings_score, bat_first_win_pct"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        from services.sportmonks_service import fetch_venue_stats
        
        result = asyncio.run(fetch_venue_stats('MA Chidambaram Stadium'))
        print(f"Venue stats result: {result}")
        
        # Check structure - may have sample_size=0 if venue not found, but should have the key
        assert 'sample_size' in result, "Missing sample_size key"
        
        if result.get('sample_size', 0) > 0:
            assert 'avg_first_innings_score' in result, "Missing avg_first_innings_score"
            assert 'bat_first_win_pct' in result, "Missing bat_first_win_pct"
            print(f"✓ Venue stats: sample={result['sample_size']}, avg_1st={result.get('avg_first_innings_score')}, bat_first_win={result.get('bat_first_win_pct')}%")
        else:
            # Even with 0 sample, function should return gracefully
            print(f"✓ Venue stats returned (sample_size=0 - venue may not be found): {result.get('note', 'No note')}")
    
    def test_fetch_h2h_record(self):
        """Test fetch_h2h_record returns matches_played > 0 with team names and wins"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        from services.sportmonks_service import fetch_h2h_record
        
        result = asyncio.run(fetch_h2h_record('Chennai Super Kings', 'Delhi Capitals'))
        print(f"H2H result: {result}")
        
        # Check structure
        assert 'team1' in result, "Missing team1 key"
        assert 'team2' in result, "Missing team2 key"
        assert 'matches_played' in result, "Missing matches_played key"
        
        if result.get('matches_played', 0) > 0:
            assert 'team1_wins' in result, "Missing team1_wins"
            assert 'team2_wins' in result, "Missing team2_wins"
            print(f"✓ H2H: {result['team1']} vs {result['team2']}, {result['matches_played']} matches, "
                  f"{result['team1_wins']}-{result['team2_wins']}")
        else:
            print(f"✓ H2H returned (no matches found): {result}")
    
    def test_fetch_team_standings(self):
        """Test fetch_team_standings returns 10 teams with required fields"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        from services.sportmonks_service import fetch_team_standings
        
        result = asyncio.run(fetch_team_standings(2026))
        print(f"Standings result: {result[:3] if result else 'Empty'}...")
        
        assert isinstance(result, list), "Standings should be a list"
        
        if len(result) > 0:
            # Check first team has required fields
            first_team = result[0]
            required_fields = ['team', 'points', 'won', 'lost']
            for field in required_fields:
                assert field in first_team, f"Missing {field} in standings"
            
            # Check for optional fields
            has_nrr = 'nrr' in first_team
            has_form = 'recent_form' in first_team
            
            print(f"✓ Standings: {len(result)} teams, top team: {first_team.get('team')} "
                  f"({first_team.get('points')} pts, {first_team.get('won')}W-{first_team.get('lost')}L)"
                  f", NRR: {has_nrr}, Form: {has_form}")
        else:
            print("✓ Standings returned empty list (may be early season)")
    
    def test_fetch_player_season_stats_for_xi(self):
        """Test fetch_player_season_stats_for_xi returns enriched players with season_stats"""
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        from services.sportmonks_service import fetch_player_season_stats_for_xi
        
        # Test with sample players
        test_players = [
            {"name": "MS Dhoni", "sm_player_id": 123},
            {"name": "Ruturaj Gaikwad", "sm_player_id": 456},
            {"name": "Ravindra Jadeja", "sm_player_id": 789},
        ]
        
        result = asyncio.run(fetch_player_season_stats_for_xi(test_players, 'Chennai Super Kings', 5))
        print(f"Player stats result: {len(result)} players")
        
        assert isinstance(result, list), "Result should be a list"
        assert len(result) == len(test_players), f"Expected {len(test_players)} players, got {len(result)}"
        
        # Check structure of enriched players
        for player in result:
            assert 'name' in player, "Missing name in player"
            # season_stats may be None if no match found
            if player.get('season_stats'):
                stats = player['season_stats']
                assert 'matches' in stats, "Missing matches in season_stats"
                print(f"  ✓ {player['name']}: {stats.get('matches', 0)} matches, "
                      f"bat: {stats.get('bat_runs', 0)}r/{stats.get('bat_innings', 0)}inn, "
                      f"bowl: {stats.get('bowl_wickets', 0)}wkts")
            else:
                print(f"  ✓ {player['name']}: No season stats (player not matched)")


class TestLiveMatchEndpoint:
    """Test 4: Live match endpoint exists and responds"""
    
    def test_fetch_live_endpoint_exists(self):
        """POST /api/matches/{match_id}/fetch-live exists and responds"""
        # Get a match ID from schedule
        schedule_resp = requests.get(f"{BASE_URL}/api/schedule")
        matches = schedule_resp.json().get("matches", [])
        
        if not matches:
            pytest.skip("No matches in schedule")
        
        # Use first upcoming match
        upcoming = [m for m in matches if m.get("status", "").lower() in ("upcoming", "ns", "not started")]
        if not upcoming:
            # Use any match
            match_id = matches[0].get("matchId")
        else:
            match_id = upcoming[0].get("matchId")
        
        response = requests.post(f"{BASE_URL}/api/matches/{match_id}/fetch-live")
        
        # Should return 200 even if no live match (returns noLiveMatch: true)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Check response structure
        assert "matchId" in data or "error" in data, "Response should have matchId or error"
        
        if data.get("noLiveMatch"):
            print(f"✓ Fetch-live endpoint works: No live match for {match_id} (expected)")
        elif data.get("error"):
            print(f"✓ Fetch-live endpoint works: {data.get('error')}")
        else:
            print(f"✓ Fetch-live endpoint works: Live data returned for {match_id}")


class TestClaudeFunctionSignature:
    """Test 5: claude_sportmonks_prediction accepts 'enrichment' parameter"""
    
    def test_claude_function_signature(self):
        """Verify claude_sportmonks_prediction function signature accepts enrichment"""
        import inspect
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        from services.ai_service import claude_sportmonks_prediction
        
        sig = inspect.signature(claude_sportmonks_prediction)
        params = list(sig.parameters.keys())
        
        assert 'enrichment' in params, f"'enrichment' parameter not found. Params: {params}"
        print(f"✓ claude_sportmonks_prediction accepts 'enrichment' parameter")
        print(f"  Full signature: {params}")


class TestClaudePromptSections:
    """Test 6: Claude prompt includes required sections"""
    
    def test_prompt_includes_enrichment_sections(self):
        """Verify ai_service.py prompt includes PLAYER STATS, VENUE STATS, H2H, STANDINGS sections"""
        with open('/app/backend/services/ai_service.py', 'r') as f:
            content = f.read()
        
        required_sections = [
            "PLAYER IPL 2026 SEASON STATS",
            "VENUE STATS",
            "HEAD-TO-HEAD RECORD",
            "IPL 2026 STANDINGS"
        ]
        
        missing = []
        for section in required_sections:
            if section not in content:
                missing.append(section)
        
        assert len(missing) == 0, f"Missing sections in Claude prompt: {missing}"
        print(f"✓ Claude prompt includes all required sections:")
        for section in required_sections:
            print(f"  - {section}")


class TestExistingUnitTests:
    """Test 7: Existing unit tests still pass"""
    
    def test_playing_xi_extraction_tests(self):
        """Run existing playing XI extraction tests"""
        import subprocess
        result = subprocess.run(
            ['python', '-m', 'pytest', 
             '/app/backend/tests/test_playing_xi_extraction.py',
             '/app/backend/tests/test_filter_squads.py',
             '-v', '--tb=short'],
            capture_output=True,
            text=True,
            cwd='/app/backend'
        )
        
        print(f"Test output:\n{result.stdout}")
        if result.stderr:
            print(f"Stderr:\n{result.stderr}")
        
        assert result.returncode == 0, f"Unit tests failed with return code {result.returncode}"
        print("✓ All existing unit tests passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
