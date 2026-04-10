# The Lucky 11 / Predictability — IPL 2026 Cricket Prediction Platform

## Original Problem Statement
Build a full-stack cricket prediction app for IPL 2026 with an 8-category math model, Claude Opus contextual analysis, live scoring, and advanced prediction weighting.

## Core Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor)
- **Integrations**: Claude Opus (Anthropic), SportMonks Cricket v2 API, NewsData.io, Open-Meteo Weather

## What's Been Implemented

### Pre-Match Prediction (8-Category Model)
1. Squad Strength & Balance (25%) — batting/bowling balance bonus, dynamically adjusted by player performance stats
2. Current Season Form (21%) — combines W/L form (60%) + player-level performance form (40%) from SportMonks batting/bowling data
3. Venue + Pitch + Home (18%) — pitch type, pace/spin assist, secondary home venues, pitch-fit advantage
4. Head-to-Head (11%) — IPL 2023-2025 H2H (all 45 team pairs)
5. Toss Impact (9%) — dew_multiplier (1.5 heavy/1.2 moderate), dew_impact_text explaining chasing advantage
6. Bowling Depth (8%) — venue-weighted quality (pacers score more at pace venues, spinners at spin venues)
7. Conditions (5%) — team-specific: heavy dew favours better batting team, swing favours more pacers, dry favours more spinners
8. Team Momentum (3%)

### Playing XI Integration (Apr 2026)
- **Pipeline**: Live fixtures -> Last completed match from IPL season fixtures -> Squad estimate fallback
- **SportMonks v2 Team ID mapping**: Correct IDs for all 10 IPL teams
- **Season-based fixture lookup**: Uses IPL 2026 season fixtures (id=1795) to find last completed match per team
- **Substitute filtering**: Excludes impact player subs using lineup.substitution field
- **Graceful fallback**: Falls back to full squad if API data unavailable or name matching below 8-player threshold

### Player Performance Stats (Apr 2026)
- **fetch_team_recent_performance()**: Fetches batting/bowling scorecard data from last 5 completed matches per team
- **Team-filtered**: Only aggregates stats for the specified team's players (filters by team_id)
- **3-Year coverage**: IPL seasons 2024 (id=1484), 2025 (id=1689), 2026 (id=1795)
- **Form enhancement**: Player batting avg/SR and bowling economy/wickets per innings compute a player-level form score
- **Dynamic STAR_PLAYERS override**: In compute_prediction(), actual player stats dynamically adjust the static STAR_PLAYERS ratings (+/-12 points based on current form)
- **sync-player-stats endpoint**: Background sync of all player stats from 3 seasons into MongoDB

### Live Match — 8-Layer Claude Contextual Analysis
Claude produces contextual adjustment (+/-30%) across 8 layers, not direct win %. System applies adjustment on algo baseline.

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction with Playing XI + player performance
- `POST /api/matches/{id}/fetch-live` — Live scores + Claude + combined prediction (accepts gut_feeling, current_betting_odds)
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run Claude with cached data
- `POST /api/schedule/sync-results` — Sync match results from SportMonks
- `POST /api/sync-player-stats` — Background sync of player performance stats

## Completed Tasks (Apr 2026)
- [x] All 8 pre-match categories producing team-specific non-zero values
- [x] H2H 2023-2025 historical data for all team pairs
- [x] Toss: dew_multiplier + dew_impact_text (heavy/moderate/none)
- [x] Bowling: venue-weighted quality scores (pace/spin assist)
- [x] Conditions: team-specific advantage (dew->batting, swing->pace, dry->spin)
- [x] 8-Layer Claude contextual analysis with contextual adjustment
- [x] Phase-based dynamic weighting + Gut Feeling + Betting Odds
- [x] Playing XI filtering for Pre-Match predictions (via SportMonks API)
- [x] Playing XI filtering for Live Match predictions (fetch-live + refresh-claude)
- [x] Substitute player exclusion from Playing XI (SportMonks lineup.substitution field)
- [x] Correct SportMonks v2 Team ID mapping for all 10 IPL teams
- [x] Season-based Playing XI fetching (last completed match per team)
- [x] Player performance stats from last 5 matches per team
- [x] Team-filtered player stats (only team's players, not opponents)
- [x] Form calculation combining W/L (60%) + player performance (40%)
- [x] Dynamic STAR_PLAYERS rating override from actual performance
- [x] Player sync endpoint (background task)

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor: Break server.py into modular routers
