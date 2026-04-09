# The Lucky 11 — IPL 2026 Cricket Prediction Platform

## Original Problem Statement
Build a full-stack cricket prediction app for IPL 2026 with an 8-category math model, Claude Opus contextual analysis, live scoring, and advanced prediction weighting.

## Core Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor)
- **Integrations**: Claude Opus (Anthropic), SportMonks API, NewsData.io, Open-Meteo Weather

## What's Been Implemented

### Pre-Match Prediction (8-Category Model)
1. Squad Strength & Balance (25%) — batting/bowling balance bonus
2. Current Season Form (21%) — from DB completed matches
3. Venue + Pitch + Home (18%) — pitch type, pace/spin assist, secondary home venues, pitch-fit advantage
4. Head-to-Head (11%) — IPL 2023-2025 H2H (all 45 team pairs)
5. Toss Impact (9%) — dew_multiplier (1.5 heavy/1.2 moderate), dew_impact_text explaining chasing advantage
6. Bowling Depth (8%) — venue-weighted quality (pacers score more at pace venues, spinners at spin venues)
7. Conditions (5%) — team-specific: heavy dew favours better batting team, swing favours more pacers, dry favours more spinners
8. Team Momentum (3%)

### Live Match — 8-Layer Claude Contextual Analysis
Claude produces contextual adjustment (+/-30%) across 8 layers, not direct win %. System applies adjustment on algo baseline.

### Playing XI Integration (Apr 2026)
- Pre-match: Fetches actual Playing XI from SportMonks (live or last completed match), cross-references with DB squad, and filters down to ~11 active players for predictions.
- Live match: Filters squads to Playing XI using SportMonks lineup data (excluding substitutes) before passing to Claude and combined prediction models.
- Graceful fallback to full squad if API data unavailable or name matching falls below 8-player threshold.

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict`
- `POST /api/matches/{id}/fetch-live` (accepts gut_feeling, current_betting_odds)
- `POST /api/matches/{id}/refresh-claude-prediction`
- `POST /api/schedule/sync-results`

## Completed Tasks (Apr 2026)
- [x] All 8 pre-match categories producing team-specific non-zero values
- [x] H2H 2023-2025 historical data for all team pairs
- [x] Toss: dew_multiplier + dew_impact_text (heavy/moderate/none)
- [x] Bowling: venue-weighted quality scores (pace/spin assist)
- [x] Conditions: team-specific advantage (dew→batting, swing→pace, dry→spin)
- [x] 8-Layer Claude contextual analysis with contextual adjustment
- [x] Phase-based dynamic weighting + Gut Feeling + Betting Odds
- [x] Playing XI filtering for Pre-Match predictions (via SportMonks API)
- [x] Playing XI filtering for Live Match predictions (fetch-live + refresh-claude)
- [x] Substitute player exclusion from Playing XI (SportMonks lineup.substitution field)

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor: Break server.py into modular routers
