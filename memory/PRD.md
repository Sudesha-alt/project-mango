# The Lucky 11 — IPL 2026 Cricket Prediction Platform

## Original Problem Statement
Build a full-stack cricket prediction app for IPL 2026 with an 8-category math model, Claude Opus contextual analysis, live scoring, and advanced prediction weighting.

## Core Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor)
- **Integrations**: Claude Opus (Anthropic), SportMonks API, NewsData.io, Open-Meteo Weather

## What's Been Implemented

### Pre-Match Prediction (8-Category Model)
1. Squad Strength & Balance (25%) — batting/bowling balance bonus
2. Current Season Form (21%) — from DB completed matches
3. Venue + Pitch + Home (18%) — pitch type, pace/spin assist, secondary home venues, pitch-fit advantage
4. Head-to-Head (11%) — IPL 2023-2025 H2H (all 45 team pairs)
5. Toss Impact (9%) — dew_multiplier (1.5 heavy/1.2 moderate), dew_impact_text explaining chasing advantage
6. Bowling Depth (8%) — venue-weighted quality (pacers score more at pace venues, spinners at spin venues)
7. Conditions (5%) — team-specific: heavy dew favours better batting team, swing favours more pacers, dry favours more spinners
8. Team Momentum (3%)

### Live Match — 8-Layer Claude Contextual Analysis
Claude produces contextual adjustment (+/-30%) across 8 layers, not direct win %. System applies adjustment on algo baseline.

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict`
- `POST /api/matches/{id}/fetch-live` (accepts gut_feeling, current_betting_odds)
- `POST /api/matches/{id}/refresh-claude-prediction`
- `POST /api/schedule/sync-results`

## Completed Tasks (Apr 2026)
- [x] All 8 pre-match categories producing team-specific non-zero values
- [x] H2H 2023-2025 historical data for all team pairs
- [x] Toss: dew_multiplier + dew_impact_text (heavy/moderate/none)
- [x] Bowling: venue-weighted quality scores (pace/spin assist)
- [x] Conditions: team-specific advantage (dew→batting, swing→pace, dry→spin)
- [x] 8-Layer Claude contextual analysis with contextual adjustment
- [x] Phase-based dynamic weighting + Gut Feeling + Betting Odds

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] Refactor: Break server.py into modular routers
