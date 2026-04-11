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
- Refresh button always returns API-verified Playing XI (not squad-based)
- Status endpoint falls back to DB cache when task is complete

### Schedule Management (Apr 2026)
- **Winner-based categorization**: Match is completed ONLY if it has a winner (not date-based)
- **Date guard on sync**: sync-results only updates matches whose date has already passed (prevents future contamination)
- **Sync Results button**: Frontend button to manually trigger result sync from SportMonks
- **Fixed DB**: Reset 23 wrongly-completed future matches back to Upcoming

### DLS / Overs Reduced (Apr 2026)
- User can input DLS context (e.g., "Match reduced to 15 overs, revised target 142") in live match page
- Passed through to Claude via `dls_info` parameter in both `fetch-live` and `refresh-claude-prediction` endpoints
- Claude prompt includes DLS section marked as CRITICAL with instructions to adjust probabilities accordingly

### Re-Predict All
- Deletes old pre-match prediction + Claude analysis from DB for each match
- Re-runs algo with fresh Playing XI + player performance + Claude for ALL upcoming matches
- Status polling with phase info (algo/claude per match)

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/fetch-live` — Live scores + Claude + combined prediction (accepts dls_info)
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run Claude (accepts dls_info)
- `POST /api/matches/{id}/playing-xi` — Refresh Playing XI (API-verified)
- `POST /api/schedule/sync-results` — Sync results with date guard
- `POST /api/predictions/repredict-all` — Background full re-prediction

## Completed Tasks (Apr 2026)
- [x] All 8 pre-match categories with non-zero values
- [x] Playing XI from SportMonks (API-verified, not squad-based)
- [x] Player performance stats from last 5 matches per team
- [x] Form = W/L (60%) + player performance (40%)
- [x] Re-Predict All: deletes old, runs algo + Claude for ALL matches
- [x] All Claude endpoints use filtered Playing XI
- [x] Schedule fix: winner-based categorization (15 completed, 55 upcoming)
- [x] Date guard on sync-results to prevent future match contamination
- [x] Sync Results button in frontend
- [x] DLS/Overs Reduced input in live match page, passed to Claude
- [x] Playing XI refresh returns API-verified (fixed _bg_fetch_playing_xi)
- [x] Playing XI status endpoint falls back to DB cache

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor server.py into modular routers
