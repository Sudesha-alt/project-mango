# The Lucky 11 / Predictability — IPL 2026 Cricket Prediction Platform

## Original Problem Statement
Build a full-stack cricket prediction app for IPL 2026 with an 8-category math model, Claude Opus contextual analysis, live scoring, and advanced prediction weighting.

## Core Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor)
- **Integrations**: Claude Opus (Anthropic via LiteLLM), SportMonks Cricket v2 API, NewsData.io, Open-Meteo Weather

## What's Been Implemented

### Pre-Match Prediction (8-Category Model)
1. Squad Strength & Balance (25%)
2. Current Season Form (21%)
3. Venue + Pitch + Home (18%)
4. Head-to-Head (11%)
5. Toss Impact (9%) — 3-tier day/afternoon/evening classification
6. Bowling Depth (8%)
7. Conditions (5%)
8. Team Momentum (3%)

### Claude Opus Pre-Match: 7-Layer Analysis
### Claude Opus Live Match: 11-Section Structured Prediction

### Performance Optimizations (asyncio.to_thread, cancel endpoints, timeouts)

### Playing XI Extraction Fix (Apr 11, 2026)
- Multi-layer validation — robust pivot parsing, scorecard-based team resolution, hard cap of 12 per team

### SportMonks Schedule Loading (Apr 11, 2026)
- Schedule loads directly from SportMonks API (74 matches)
- Merge strategy preserves existing predictions when refreshing

### Data Enrichment for Claude Live Analysis (Apr 11, 2026)
- **Player Season Stats**: Per-player batting avg/SR, bowling economy/wickets from last 5 IPL 2026 matches
- **Venue Stats**: Avg 1st innings score, bat-first win%, sample size from IPL 2024-2026 (venue_id-based matching)
- **H2H Record**: Matches played, wins per team, last meeting result across 3 seasons
- **Team Standings**: Points table with W/L/Points/NRR/Recent Form for all 10 teams
- All data fetched in parallel via asyncio.gather and fed into Claude prompt
- Enrichment applies to both `/fetch-live` and `/refresh-claude-prediction` endpoints

### Key Endpoints
- `GET /api/schedule/load` — Fetches full season from SportMonks API
- `GET /api/predictions/upcoming` — Pre-match cache for **active** schedule fixtures by default (`schedule_upcoming_only=true`); use `=false` for all stored predictions
- `GET /api/matches/{id}/playing-xi/bench` — Full franchise squad minus Expected XI (seed + DB merge)
- `GET /api/matches/{id}/playing-xi/impact-search?q=&team=` — Type-ahead for manual Impact player; `PUT …/manual-impact` saves; Claude + pre-match consume `playing_xi`
- `POST /api/matches/{id}/fetch-live` — Live scores + enriched 11-section Claude analysis
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run live Claude with enrichment
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/claude-analysis` — 7-layer pre-match Claude

## Backlog
- [ ] P1: Celery migration for background jobs
- [ ] P2: Shareable prediction card
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor server.py (>3200 lines) into modular routers
