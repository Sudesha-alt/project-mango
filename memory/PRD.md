# The Lucky 11 — IPL 2026 Cricket Prediction Platform

## Original Problem Statement
Build a full-stack cricket prediction app for IPL 2026 with an 8-category math model, Claude Opus narrative predictions, live scoring, and advanced prediction weighting.

## Core Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor)
- **Integrations**: Claude Opus (Anthropic), SportMonks API, NewsData.io, Open-Meteo Weather

## What's Been Implemented

### Pre-Match Prediction (8-Category Model)
1. Squad Strength & Balance (25%)
2. Current Season Form (21%)
3. Venue + Pitch + Home Advantage (18%) — pitch type, pace/spin assist, secondary home venues
4. Head-to-Head (11%) — IPL 2023-2025 H2H data
5. Toss Impact (9%) — venue-specific toss_win_pct with dew
6. Bowling Attack Depth (8%) — top 5 bowlers with variety bonus
7. Conditions/Weather (5%) — Open-Meteo
8. Team Momentum (3%)

### Live Match Prediction
- **Weighted Model**: Claude's win % passed directly as base anchor (Factor 5) into the 6-factor live model
- **Phase-Based Dynamic Weighting** (Algo vs Claude blend)
- **Combined Prediction** with Gut Feeling (3%) + Betting Odds (7%)
- **Claude Opus**: Must state clear winner verdict — no hedging

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict`
- `POST /api/matches/{id}/fetch-live` (accepts gut_feeling, current_betting_odds)
- `POST /api/matches/{id}/refresh-claude-prediction`
- `POST /api/schedule/sync-results`

## Completed Tasks (Apr 2026)
- [x] 8-category pre-match model
- [x] Phase-based dynamic weighting (5 phases)
- [x] Gut Feeling (3%) + Betting Odds (7%) inputs
- [x] H2H with 2023-2025 IPL data
- [x] Venue + Pitch data (type, avg score, pace/spin)
- [x] Secondary home grounds
- [x] Claude win % fed directly into weighted model as base anchor
- [x] Claude forced to give clear winner_verdict (no hedging)
- [x] Winner verdict displayed prominently on frontend

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] Refactor: Break server.py into modular routers
