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
8. Team Momentum (3%) — Last 2 matches, logit 0.9*win_diff (max 2.0), 1.3x boost for 2-0 streaks

### Claude Opus Pre-Match: 7-Layer Analysis
Layers: Squad Strength, Key Matchups, Venue/Pitch, Bowling Depth, Death Bowling, H2H, Impact Player.
Plus: Algorithm Predictions table, Analyst POTM, Divergence notes, Toss Scenarios, Deciding Factor, First 6 Signal.

### Claude Opus Live Match: 11-Section Structured Prediction (Apr 2026)
Complete rewrite of live prediction prompt:
- **S0**: Live Data Dump — explicit statement of all fetched data
- **S1**: Match Context — teams, venue, time, toss, dew
- **S2**: Squad Strength & Availability (22%) — XI ratings 1-10, absence impact analysis
- **S3**: Current Season Form (18%) — IPL 2026 only, exponential decay
- **S4**: Venue & Pitch Profile (16%) — avg 1st innings, bat-first win%, sample size
- **S5**: Head-to-Head (10%) — 3-season filter, squad validity check
- **S6**: Key Player Matchups (8%) — 3 decisive batter vs bowler matchups with stats
- **S7**: Bowling Depth & Death (7%) — Proven/Adequate/Vulnerability ratings for overs 17-20
- **S8**: Data Integrity Checks — form vs reputation, absence verification, venue recency, H2H validity, toss consistency, invented factors removed
- **S9**: Toss Scenarios — mathematically consistent with venue data
- **S10**: Final Prediction — 4 sentences: key factor, underdog chance, first 6 signal, confidence
- **S11**: Mid-Game Revision Triggers — 3 exact measurable events with % revision
- Also retains: contextual_adjustment_pct, momentum, market_mispricing

### Performance Optimizations (Apr 2026)
- Global axios timeout (30s default)
- Individual timeouts on all API calls
- Background tasks yield to event loop via asyncio.sleep(0.5)
- Cancel endpoints for Re-Predict All and Claude Rerun
- AbortController on fetch() calls

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/claude-analysis` — 7-layer pre-match Claude
- `POST /api/matches/{id}/fetch-live` — Live scores + 11-section Claude + combined prediction
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run live Claude
- `POST /api/predictions/claude-rerun-all` — Background Claude re-analysis
- `POST /api/predictions/claude-rerun-cancel` — Cancel Claude rerun
- `POST /api/predictions/repredict-cancel` — Cancel Re-Predict All

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor server.py into modular routers
