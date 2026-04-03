# Gamble Consultant v4.2 - IPL 2026 Odds Consultant

## Problem Statement
Production-grade IPL 2026 gambling consultant with calibrated win probability, fair odds, market edge, value-bet signals, player impact, confidence bands, GPT-powered advice, and pre-match predictions using historical data. Live data from CricketData.org API.

## Architecture
- **Frontend**: React + Tailwind + Recharts + Shadcn (Dark Mode)
- **Backend**: FastAPI + MongoDB + WebSocket
- **Data Sources**: GPT-5.4 Web Search (schedule/stats/analysis/playing XI), CricketData.org API (live scores, 100/day)
- **Engines**: 6-layer Decision Engine, Pre-Match Algorithm Stack, Beta Prediction Engine

## Pre-Match Prediction System
- **Data**: GPT-5.4 web searches real H2H record (last 5 years, match-by-match detail), venue averages (1st/2nd innings, highest/lowest totals), recent form (last 5 matches with opponents), squad ratings
- **Algorithm**: 5 weighted factors → logistic combination → Platt calibration → confidence %
  - H2H Factor (25%), Venue Factor (20%), Form Factor (25%), Squad Factor (20%), Home Advantage (10%)
- **Storage**: Predictions cached in MongoDB with Playing XI + odds direction

## Playing XI System (v4.1)
- GPT-5.4 web search scrapes expected/confirmed Playing XI for IPL 2026 matches
- Returns 11 players per team with season stats
- **Luck Biasness**: Random variance factor (+-15%) applied to expected performance
- **Stored inside prediction document** alongside match prediction
- Frontend: PlayingXIPerformance component shows players with expected runs/wkts/luck icons

## Odds Direction Tracking (v4.2 - NEW)
- When re-predicting, compares new probability with previous prediction
- Stores direction: "up" / "down" / "stable" with numeric change amount
- Previous predictions archived in `prediction_history` collection
- Frontend: TrendUp/TrendDown arrows on match cards and prediction breakdown
- Shows "vs prev: X% / Y%" comparison

## Background Re-Prediction (v4.2 - NEW)
- POST /api/predictions/repredict-all — triggers async background task
- GET /api/predictions/repredict-status — poll progress (running/completed/total/current_match)
- Re-predicts ALL upcoming matches with fresh data + Playing XI + odds direction
- Each match: 2 GPT web searches (stats + playing XI) + luck biasness + direction calc
- Frontend: Purple "RE-PREDICT ALL" button with progress banner

## Odds Input System (v4.1)
- All bookmaker inputs use **0-100 probability scale** (not decimal odds)
- Backend converts 0-100 pct → decimal odds internally

## Info Tooltips (v4.1)
- Every prediction model and metric has an info tooltip

## API Endpoints
- `GET /api/` — Health
- `GET /api/schedule` — IPL 2026 schedule
- `POST /api/matches/{id}/pre-match-predict?force=true` — Predict match (force re-predict)
- `POST /api/schedule/predict-upcoming?force=true` — Batch predict all upcoming
- `GET /api/predictions/upcoming` — Get all cached predictions
- `POST /api/predictions/repredict-all` — **NEW** Background re-predict all matches
- `GET /api/predictions/repredict-status` — **NEW** Re-prediction progress
- `POST /api/matches/{id}/consult` — Full decision engine consultation
- `POST /api/matches/{id}/chat` — GPT Q&A
- `POST /api/matches/{id}/playing-xi` — Fetch Playing XI with luck biasness
- `GET /api/cricket-api/venue/{name}` — On-demand venue data
- `POST /api/cricket-api/fetch-live` — CricketData.org live
- `GET /api/cricket-api/usage` — API counter
- `WS /api/ws/{matchId}` — WebSocket

## DB Collections
- `ipl_schedule` — Match schedule
- `pre_match_predictions` — Cached predictions with playing_xi + odds_direction
- `prediction_history` — Archived superseded predictions (for odds direction tracking)
- `playing_xi` — Individual Playing XI documents
- `api_usage` — CricAPI usage tracking

## Test Results
- iteration_10.json: 94% backend (1 low-pri timeout during heavy load), 100% frontend
- Background re-prediction running (2/63 complete as of last check)

## Upcoming (P1)
- Background workers for auto-fetching (Celery)
- WebSocket real-time push

## Future (P2)
- Shareable prediction card
- Market sentiment tracking
- Prediction accuracy leaderboard
