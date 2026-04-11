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
Plus: Algorithm Predictions table, Analyst POTM, Divergence notes, Toss Scenarios, Deciding Factor, First 6 Signal.

### Claude Opus Live Match: 11-Section Structured Prediction (Apr 2026)
- **S0**: Live Data Dump
- **S1**: Match Context
- **S2**: Squad Strength & Availability (22%)
- **S3**: Current Season Form (18%)
- **S4**: Venue & Pitch Profile (16%)
- **S5**: Head-to-Head (10%)
- **S6**: Key Player Matchups (8%)
- **S7**: Bowling Depth & Death (7%)
- **S8**: Data Integrity Checks
- **S9**: Toss Scenarios
- **S10**: Final Prediction
- **S11**: Mid-Game Revision Triggers

### Performance Optimizations (Apr 2026)
- Global axios timeout (30s default)
- Individual timeouts on all API calls
- Background tasks yield to event loop via asyncio.sleep(0.5)
- Cancel endpoints for Re-Predict All and Claude Rerun

### Playing XI Extraction Fix (Apr 2026)
- **Bug**: Claude was evaluating full squad (16+ players) instead of Playing XI (11)
- **Root cause**: `parse_fixture()` lineup pivot parsing failed silently → fell back to full squad
- **Fix**: Multi-layer validation:
  - Layer 1: Robust pivot parsing with type normalization
  - Layer 2: Scorecard-based team resolution for unassigned players
  - Layer 3: Pruning oversized XI using batting/bowling evidence
  - Layer 4: Hard cap of 12 players (11 + 1 impact sub) in both parse_fixture() and _filter_squads_to_playing_xi()
- **Tests**: 10 unit tests covering all edge cases (all passing)

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/claude-analysis` — 7-layer pre-match Claude
- `POST /api/matches/{id}/fetch-live` — Live scores + 11-section Claude + combined prediction
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run live Claude
- `POST /api/predictions/claude-rerun-all` — Background Claude re-analysis
- `POST /api/predictions/claude-rerun-cancel` — Cancel Claude rerun
- `POST /api/predictions/repredict-cancel` — Cancel Re-Predict All

## Backlog
- [ ] P1: Celery migration for background jobs
- [ ] P2: Shareable prediction card
- [ ] P3: Prediction accuracy leaderboard
- [ ] P3: Refactor server.py (>3200 lines) into modular routers
