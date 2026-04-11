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
- 10 unit tests all passing

### SportMonks Schedule Loading (Apr 11, 2026)
- **Changed**: Schedule now loads directly from SportMonks API (`fetch_ipl_season_schedule()`)
- **Removed**: GPT web scraping for schedule loading
- **Fallback**: Uses seed data from `schedule_data.py` only if SportMonks API fails
- **74 matches loaded** with real teams, venues, scores, winners, toss data
- Merge strategy preserves existing predictions/analysis when refreshing
- `fixture_id` stored per match for direct SportMonks lookups

### Key Endpoints
- `GET /api/schedule/load` — Fetches full season from SportMonks API (use `?force=true` to refresh)
- `POST /api/schedule/seed-official` — Fallback: seed from hardcoded PDF data
- `POST /api/schedule/sync-results` — Sync completed match results from SportMonks
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/claude-analysis` — 7-layer pre-match Claude
- `POST /api/matches/{id}/fetch-live` — Live scores + 11-section Claude
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run live Claude

## Backlog
- [ ] P1: Celery migration for background jobs
- [ ] P2: Shareable prediction card
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor server.py (>3200 lines) into modular routers
