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
2. Current Season Form (21%) — W/L form (60%) + player-level performance (40%)
3. Venue + Pitch + Home (18%)
4. Head-to-Head (11%)
5. Toss Impact (9%) — 3-tier day/afternoon/evening classification
6. Bowling Depth (8%)
7. Conditions (5%) — dew/swing/spin, afternoon-aware
8. Team Momentum (3%) — Last 2 matches, logit 0.9*win_diff (max 2.0), 1.3x boost for 2-0 streaks

### Claude Opus Pre-Match: 7-Layer Analysis
Layers: Squad Strength, Key Matchups, Venue/Pitch, Bowling Depth, Death Bowling, H2H, Impact Player.

### Claude Opus Live Match: 11-Section Structured Prediction
S0-S11: Live Data Dump through Mid-Game Revision Triggers.

### Performance Optimizations (Apr 2026)
- asyncio.to_thread wrapping for LiteLLM, cancel endpoints, axios timeouts

### Playing XI Extraction Fix (Apr 11, 2026)
- **Bug**: Claude evaluated full squad (16+ players) instead of Playing XI (11)
- **Fix**: Multi-layer validation — robust pivot parsing, scorecard-based team resolution, hard cap of 12 per team
- **Tests**: 10 unit tests all passing

### Full Schedule Loading Fix (Apr 11, 2026)
- **Bug**: DB only had 10 matches (GPT-generated), IPL 2026 has 70 matches
- **Fix**: Loaded all 70 matches from official PDF seed data, merged with existing results
- **Schedule/load endpoint**: Now uses merge strategy — preserves existing results, inserts missing matches

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/claude-analysis` — 7-layer pre-match Claude
- `POST /api/matches/{id}/fetch-live` — Live scores + 11-section Claude
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run live Claude
- `GET /api/schedule/load` — Loads full 70-match schedule (merge strategy)
- `POST /api/schedule/seed-official` — Force-seed from official PDF data

## Backlog
- [ ] P1: Celery migration for background jobs
- [ ] P2: Shareable prediction card
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor server.py (>3200 lines) into modular routers
