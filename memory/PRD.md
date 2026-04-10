# The Lucky 11 / Predictability — IPL 2026 Cricket Prediction Platform

## Original Problem Statement
Build a full-stack cricket prediction app for IPL 2026 with an 8-category math model, Claude Opus contextual analysis, live scoring, and advanced prediction weighting.

## Core Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor)
- **Integrations**: Claude Opus (Anthropic), SportMonks Cricket v2 API, NewsData.io, Open-Meteo Weather

## What's Been Implemented

### Pre-Match Prediction (8-Category Model)
1. Squad Strength & Balance (25%) — dynamically adjusted by actual player performance stats
2. Current Season Form (21%) — W/L form (60%) + player-level performance form (40%) from SportMonks
3. Venue + Pitch + Home (18%) — pitch type, pace/spin assist, secondary home venues
4. Head-to-Head (11%) — IPL 2023-2025 H2H (all 45 team pairs)
5. Toss Impact (9%) — dew_multiplier, dew_impact_text
6. Bowling Depth (8%) — venue-weighted quality
7. Conditions (5%) — dew/swing/spin team-specific
8. Team Momentum (3%)

### Playing XI Integration
- Pipeline: Live fixtures -> Last completed match from season fixtures -> Squad estimate fallback
- SportMonks v2 correct team IDs for all 10 IPL teams
- Season-based fixture lookup (2024-2026)
- Substitute filtering via lineup.substitution field

### Player Performance Stats
- Per-player batting/bowling stats from last 5 completed matches (team-filtered)
- Dynamic STAR_PLAYERS rating override (+/-12 pts based on actual form)
- 3-year coverage: IPL 2024, 2025, 2026

### Stale Data Prevention
- Auto-invalidation: sync-results deletes cached predictions for affected teams
- Auto-refresh: predictions >6 hours old are auto-recomputed
- Scheduled auto-sync: 30-min background job
- Cache clearing: SportMonks fixtures cache cleared on sync

### Re-Predict All (Apr 2026)
- **Endpoint**: `POST /api/predictions/repredict-all` — triggers background re-prediction of ALL upcoming matches
- **For each match**: 1) Delete old pre-match prediction from DB, 2) Delete old Claude analysis from DB, 3) Clear caches, 4) Re-run algo with fresh Playing XI + player performance, 5) Re-run Claude with filtered Playing XI, 6) Store fresh results
- **Status polling**: `GET /api/predictions/repredict-status` — returns running/completed/failed/phase
- **Claude analysis**: Now runs for ALL upcoming matches (previously only next 3)
- **All Claude endpoints use Playing XI**: Pre-match analysis, live analysis, 8-layer sportmonks prediction — all filter squads to expected 11

### Live Match — 8-Layer Claude Contextual Analysis
Claude produces contextual adjustment (+/-30%) across 8 layers applied on algo baseline.

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/fetch-live` — Live scores + Claude + combined prediction
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run Claude
- `POST /api/matches/{id}/claude-analysis` — Claude deep pre-match analysis (uses Playing XI)
- `POST /api/matches/{id}/claude-live` — Claude live analysis (uses Playing XI)
- `POST /api/schedule/sync-results` — Sync results + invalidate stale predictions
- `POST /api/predictions/repredict-all` — Background full re-prediction
- `GET /api/predictions/repredict-status` — Poll re-prediction progress

## Completed Tasks (Apr 2026)
- [x] All 8 pre-match categories with non-zero values
- [x] H2H 2023-2025 historical data
- [x] 8-Layer Claude contextual analysis
- [x] Phase-based dynamic weighting + Gut Feeling + Betting Odds
- [x] Playing XI from SportMonks (live + last completed match)
- [x] Player performance stats from last 5 matches per team
- [x] Form = W/L (60%) + player performance (40%)
- [x] Dynamic STAR_PLAYERS rating override
- [x] Auto-invalidation + auto-refresh + scheduled sync
- [x] Re-Predict All: deletes old data, runs algo + Claude for all upcoming matches
- [x] All Claude endpoints use filtered Playing XI (not full squad)
- [x] Claude prompts updated to say "Expected Playing XI"

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor server.py into modular routers
