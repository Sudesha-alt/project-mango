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

### Stale Data Prevention (Apr 2026)
- **Auto-invalidation**: When match results are synced via `/schedule/sync-results`, all cached pre-match predictions for upcoming matches involving either team are deleted
- **Auto-refresh**: Pre-match predictions older than 6 hours are automatically re-computed on next request
- **Cache clearing**: SportMonks season fixtures cache is cleared after each result sync so fresh fixture data is fetched
- **Scheduled auto-sync**: Background job runs every 30 minutes to check for new results, sync them, and invalidate stale predictions
- **DB-stored predictions**: All predictions stored in `pre_match_predictions` collection with `computed_at` timestamps

### Live Match — 8-Layer Claude Contextual Analysis
Claude produces contextual adjustment (+/-30%) across 8 layers applied on algo baseline.

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction (auto-refreshes stale cache)
- `POST /api/matches/{id}/fetch-live` — Live scores + Claude + combined prediction
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run Claude with cached data
- `POST /api/schedule/sync-results` — Sync results + invalidate stale predictions
- `POST /api/sync-player-stats` — Background sync of player performance stats

## Completed Tasks (Apr 2026)
- [x] All 8 pre-match categories with non-zero values
- [x] H2H 2023-2025 historical data
- [x] 8-Layer Claude contextual analysis
- [x] Phase-based dynamic weighting + Gut Feeling + Betting Odds
- [x] Playing XI from SportMonks (live + last completed match)
- [x] Player performance stats from last 5 matches per team
- [x] Form = W/L (60%) + player performance (40%)
- [x] Dynamic STAR_PLAYERS rating override from actual stats
- [x] Auto-invalidation of stale predictions on result sync
- [x] Auto-refresh of predictions older than 6 hours
- [x] Scheduled 30-min auto-sync for results + cache clearing
- [x] Season fixtures cache clearing on result sync

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor server.py into modular routers
