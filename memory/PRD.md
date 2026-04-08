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
- **Weighted Model**: Claude's win % fed directly as base anchor (Factor 5)
- **Phase-Based Dynamic Weighting** (5 phases: Algo vs Claude blend)
- **Combined Prediction** with Gut Feeling (3%) + Betting Odds (7%)
- **Claude Opus**: Natural flowing narrative analysis style:
  - "Bottom line: [TEAM] should win this [how]. Here's the real reasoning:"
  - References specific scorecard numbers, player figures, run rates
  - Identifies the key wildcard player
  - "Verdict: [TEAM] wins by [margin]. There's roughly [X]% chance [OTHER] pulls off [scenario]."

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict`
- `POST /api/matches/{id}/fetch-live` (accepts gut_feeling, current_betting_odds)
- `POST /api/matches/{id}/refresh-claude-prediction`
- `POST /api/schedule/sync-results`

## Completed Tasks (Apr 2026)
- [x] 8-category pre-match model
- [x] Venue + Pitch data with secondary home grounds
- [x] H2H 2023-2025 IPL data
- [x] Phase-based dynamic weighting (5 phases)
- [x] Gut Feeling (3%) + Betting Odds (7%) inputs
- [x] Claude win % fed directly into weighted model
- [x] Claude narrative-style analysis (conversational, data-driven, decisive)
- [x] Frontend: flowing analysis display with key player card

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] Refactor: Break server.py into modular routers
