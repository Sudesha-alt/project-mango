# Gamble Consultant v4.4 - IPL 2026 Odds Consultant

## Problem Statement
Production-grade IPL 2026 gambling consultant with calibrated win probability, fair odds, market edge, value-bet signals, player impact, confidence bands, GPT-powered advice, and pre-match predictions using historical data. Live data from CricketData.org API.

## Architecture
- **Frontend**: React + Tailwind + Recharts + Shadcn (Dark Mode)
- **Backend**: FastAPI + MongoDB + WebSocket
- **Data Sources**: GPT-5.4 Web Search (schedule/stats/analysis/playing XI), CricketData.org API (live scores, 100/day)
- **Engines**: 6-layer Decision Engine, Pre-Match Algorithm Stack, Beta Prediction Engine

## Prediction Calculation (v4.4 - Updated)
Uses 5 weighted factors with **player-level data** from Playing XI:
- **H2H (25%)**: Win ratio from 2021-2026, match-by-match detail
- **Venue (20%)**: Player-level venue stats (60%) blended with team-level venue win% (40%). Each player's runs/avg/SR/wkts at that specific ground used.
- **Form (25%)**: Individual player form via buzz confidence (50%) blended with team last-5 win% (50%)
- **Squad (20%)**: Batting depth (55%) + bowling attack (45%) rating
- **Home (10%)**: Home ground boost (+0.25 logit)
- Returns `uses_player_data: true` flag when Playing XI data was used

## Market Momentum (v4.4 - NEW)
- User selects which team has **increasing odds (0→100)** and which has **decreasing (100→0)**
- Applies ~3% probability adjustment to the blended win probability
- Response includes `market_momentum` object with direction and adjustment %
- Auto-toggle: selecting one team for "rising" auto-sets the other for "falling"

## Playing XI System (v4.3)
- GPT-5.4 web search with **news-aware filtering**: excludes injured/rested/dropped/banned players
- Replaces unavailable players with likely squad alternatives
- Returns: venue_stats (last 5 matches at that ground), buzz_confidence (0-100 social sentiment), luck_factor
- Stored inside prediction document

## Refresh/Re-Predict (v4.4 - NEW)
- "RE-PREDICT" button in PreMatchPredictionBreakdown header
- Calls `?force=true` to get fresh data with latest Playing XI and stats
- "PLAYER-LEVEL DATA" purple badge shows when player data was used in calculation

## Odds Direction Tracking (v4.2)
- Shows TrendUp/TrendDown arrows with % change vs previous prediction
- Previous predictions archived in `prediction_history` collection

## Background Re-Prediction (v4.2)
- POST /api/predictions/repredict-all — async background task
- GET /api/predictions/repredict-status — poll progress

## Odds Input System (v4.1)
- 0-100 probability scale for all bookmaker inputs

## Info Tooltips (v4.1)
- Every prediction model has an info tooltip

## API Endpoints
- `GET /api/` — Health
- `GET /api/schedule` — IPL 2026 schedule
- `POST /api/schedule/resolve-venues` — Fix TBD venues
- `POST /api/matches/{id}/pre-match-predict?force=true` — Predict/re-predict match
- `POST /api/schedule/predict-upcoming?force=true` — Batch predict all
- `GET /api/predictions/upcoming` — Cached predictions
- `POST /api/predictions/repredict-all` — Background re-predict
- `GET /api/predictions/repredict-status` — Progress
- `POST /api/matches/{id}/consult` — Decision engine (accepts odds_trend_increasing/decreasing)
- `POST /api/matches/{id}/chat` — GPT Q&A
- `POST /api/matches/{id}/playing-xi` — Playing XI with venue stats + buzz
- `GET /api/cricket-api/venue/{name}` — Venue data
- `POST /api/cricket-api/fetch-live` — CricAPI live (Live tab only)

## Test Results
- iteration_12.json: 100% backend (11/11), 100% frontend — all features working

## Upcoming (P1)
- Background workers (Celery) for auto-fetching
- WebSocket real-time push

## Future (P2)
- Shareable prediction card
- Prediction accuracy leaderboard
- Market sentiment tracking
