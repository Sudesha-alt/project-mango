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
5. Toss Impact (9%) — **3-tier match time classification**: day/afternoon/evening with time-aware dew multipliers
6. Bowling Depth (8%) — venue-weighted quality
7. Conditions (5%) — dew/swing/spin team-specific, afternoon-aware
8. Team Momentum (3%)

### Match Time Classification (Apr 2026)
- `_classify_match_time`: 3-tier day/afternoon/evening
  - `day` (before 2 PM IST) — no dew
  - `afternoon` (2-5 PM IST, 3:30 PM slot) — minimal dew, dew_multiplier=0.55
  - `evening` (after 5 PM IST, 7:30 PM slot) — significant dew, dew_multiplier=1.0
- SportMonks cross-reference: `starting_at` from API verified on every prediction

### Claude Opus 7-Layer Pre-Match Analysis (Apr 2026)
Completely rewritten to produce structured, data-driven, layered match previews:
- **Layer 1**: Squad Strength & Current Form (with SportMonks form data)
- **Layer 2**: Key Matchups (batter vs bowler, decisive duel)
- **Layer 3**: Venue & Pitch Analysis (time-of-day aware)
- **Layer 4**: Bowling Depth & Attack Quality (by phase)
- **Layer 5**: Death Bowling Identity (overs 16-20)
- **Layer 6**: Head-to-Head (recency-weighted)
- **Layer 7**: Impact Player Options
- **Algorithm Predictions table**: Shows POTM, Top Batters/Bowlers from algo
- **Analyst POTM**: Claude's own pick with 3 stat-backed reasons
- **Algorithm vs Analyst Divergence**: Explicitly notes when predictions differ by >10%
- **Deciding Factor & First 6 Overs Signal**: Tactical guidance
- **Data inputs**: Expected XI, algo output, player performance, weather, form/H2H, news

### Playing XI Integration
- Pipeline: Live fixtures -> Last completed match -> Squad estimate fallback
- Refresh button always returns API-verified Playing XI
- Status endpoint falls back to DB cache

### Schedule Management
- Winner-based categorization (match completed ONLY if winner present)
- Sync Results button with date guard

### DLS / Overs Reduced
- User input in live match page, passed to Claude via `dls_info`

### Re-Predict All
- Deletes old predictions + Claude analysis
- Recalculates with fresh Playing XI + player performance + Claude for ALL upcoming matches
- Now passes algo data, player perf, weather, form to Claude 7-layer prompt

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/claude-analysis` — 7-layer Claude analysis (enriched with algo data)
- `GET /api/matches/{id}/claude-analysis` — cached Claude analysis
- `DELETE /api/matches/{id}/claude-analysis` — clear cached analysis
- `POST /api/matches/{id}/fetch-live` — Live scores + Claude + combined prediction
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run Claude live
- `POST /api/matches/{id}/playing-xi` — Refresh Playing XI (API-verified)
- `POST /api/schedule/sync-results` — Sync results with date guard
- `POST /api/predictions/repredict-all` — Background full re-prediction

## Completed Tasks
- [x] All 8 pre-match categories with non-zero values
- [x] Playing XI from SportMonks (API-verified, not squad-based)
- [x] Player performance stats from last 5 matches per team
- [x] Form = W/L (60%) + player performance (40%)
- [x] Re-Predict All: deletes old, runs algo + Claude for ALL matches
- [x] All Claude endpoints use filtered Playing XI
- [x] Schedule fix: winner-based categorization
- [x] DLS/Overs Reduced input in live match page
- [x] Playing XI refresh returns API-verified
- [x] Match time classification: 3-tier day/afternoon/evening
- [x] SportMonks start time cross-reference
- [x] Afternoon match dew reduction
- [x] **Claude 7-layer pre-match analysis** with algo data, player perf, weather, form, news
- [x] **Frontend: New ClaudeAnalysis component** with collapsible layers, dual probability bars, algo vs analyst divergence, POTM, deciding factor, first 6 signal

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor server.py into modular routers
