# The Lucky 11 / Predictability — IPL 2026 Cricket Prediction Platform

## Original Problem Statement
Build a full-stack cricket prediction app for IPL 2026 with an 8-category math model, Claude Opus contextual analysis, live scoring, and advanced prediction weighting.

## Core Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor)
- **Integrations**: Claude Opus (Anthropic), SportMonks Cricket v2 API, NewsData.io, Open-Meteo Weather

## What's Been Implemented

### Pre-Match Prediction (8-Category Model)
1. Squad Strength & Balance (25%)
2. Current Season Form (21%) — W/L form (60%) + player-level performance (40%)
3. Venue + Pitch + Home (18%)
4. Head-to-Head (11%)
5. Toss Impact (9%) — 3-tier day/afternoon/evening classification
6. Bowling Depth (8%)
7. Conditions (5%) — dew/swing/spin, afternoon-aware
8. Team Momentum (3%) — **Last 2 matches, logit 0.9*win_diff (max 2.0), 1.3x boost for 2-0 streaks**

### Match Time Classification
- `_classify_match_time`: day (<2PM IST) / afternoon (2-5PM IST) / evening (>5PM IST)
- SportMonks `starting_at` cross-reference on every prediction

### Claude Opus 7-Layer Pre-Match Analysis
- Layer 1: Squad Strength & Current Form
- Layer 2: Key Matchups (batter vs bowler)
- Layer 3: Venue & Pitch Analysis
- Layer 4: Bowling Depth & Attack Quality
- Layer 5: Death Bowling Identity (overs 16-20)
- Layer 6: Head-to-Head (recency-weighted)
- Layer 7: Impact Player Options
- Algorithm Predictions table, Analyst POTM, Divergence notes, Toss Scenarios, Deciding Factor, First 6 Overs Signal

### Re-Run Claude All (Apr 2026)
- Dedicated button on upcoming page to re-run Claude 7-layer analysis for ALL matches
- Background task with cancellation support
- Progress banner with cancel button
- Status polling every 6s with timeout protection

### Performance Optimizations (Apr 2026)
- Global axios timeout (30s default) prevents infinite hangs
- Individual timeouts on all API calls (5-15s for fast, 180s for Claude generation)
- Background tasks yield to event loop via `asyncio.sleep(0.5)` between matches
- Cancel endpoints for both Re-Predict All and Claude Rerun tasks
- AbortController on fetch() calls for match state loading

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/claude-analysis` — 7-layer Claude analysis
- `POST /api/predictions/claude-rerun-all` — Background Claude re-analysis (all matches)
- `GET /api/predictions/claude-rerun-status` — Claude rerun progress
- `POST /api/predictions/claude-rerun-cancel` — Cancel Claude rerun
- `POST /api/predictions/repredict-cancel` — Cancel Re-Predict All

## Completed Tasks
- [x] All 8 pre-match categories with non-zero values
- [x] Playing XI from SportMonks (API-verified)
- [x] Player performance stats from last 5 matches
- [x] Match time classification: day/afternoon/evening
- [x] Claude 7-layer pre-match analysis with algo data
- [x] Re-Run Claude All button with progress banner + cancel
- [x] Momentum fix: logit increased to 0.9*win_diff (was 0.25*win_diff)
- [x] Performance: axios timeouts, event loop yielding, cancel endpoints

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor server.py into modular routers
