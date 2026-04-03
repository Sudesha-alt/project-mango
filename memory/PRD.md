# Gamble Consultant v4.3 - IPL 2026 Odds Consultant

## Problem Statement
Production-grade IPL 2026 gambling consultant with calibrated win probability, fair odds, market edge, value-bet signals, player impact, confidence bands, GPT-powered advice, and pre-match predictions using historical data. Live data from CricketData.org API.

## Architecture
- **Frontend**: React + Tailwind + Recharts + Shadcn (Dark Mode)
- **Backend**: FastAPI + MongoDB + WebSocket
- **Data Sources**: GPT-5.4 Web Search (schedule/stats/analysis/playing XI), CricketData.org API (live scores, 100/day)
- **Engines**: 6-layer Decision Engine, Pre-Match Algorithm Stack, Beta Prediction Engine

## Pre-Match Prediction System
- 5 weighted factors → logistic combination → Platt calibration
- H2H (25%), Venue (20%), Form (25%), Squad (20%), Home (10%)
- Predictions cached in MongoDB with Playing XI + odds direction

## Playing XI + Expected Performance (v4.3)
- GPT-5.4 web search fetches expected/confirmed Playing XI
- **Venue-specific stats**: Last 5 matches at that specific ground (runs, avg, SR, wickets, economy at venue)
- **Buzz confidence**: 0-100 score from social media sentiment, expert picks, fantasy cricket buzz
- **Luck biasness**: +-15% random variance on expected performance
- Old PlayingXI squad section removed from PreMatch — only Expected Performance shown
- Headers: Runs | Wkts | Buzz | Luck

## Live Data Panel (v4.3)
- CricApiLivePanel only shows on **Live tab** — removed from Upcoming/Completed tabs

## Venue Resolution (v4.3)
- POST /api/schedule/resolve-venues resolves TBD venues using GPT web search
- All 70 matches now have real venue names (0 TBD)
- Auto-resolves during schedule load

## Odds Direction Tracking (v4.2)
- Compares new prediction to previous, shows up/down/stable arrows with % change

## Background Re-Prediction (v4.2)
- POST /api/predictions/repredict-all — async background task
- GET /api/predictions/repredict-status — poll progress

## Odds Input System (v4.1)
- All bookmaker inputs use 0-100 probability scale

## Info Tooltips (v4.1)
- Every prediction model has an info tooltip

## API Endpoints
- `GET /api/` — Health
- `GET /api/schedule` — IPL 2026 schedule (all venues resolved)
- `GET /api/schedule/load` — Load schedule via GPT
- `POST /api/schedule/resolve-venues` — Resolve TBD venues
- `POST /api/matches/{id}/pre-match-predict?force=true` — Predict match
- `POST /api/schedule/predict-upcoming?force=true` — Batch predict
- `GET /api/predictions/upcoming` — Cached predictions
- `POST /api/predictions/repredict-all` — Background re-predict
- `GET /api/predictions/repredict-status` — Progress
- `POST /api/matches/{id}/consult` — Decision engine
- `POST /api/matches/{id}/chat` — GPT Q&A
- `POST /api/matches/{id}/playing-xi` — Playing XI with venue stats + buzz
- `GET /api/cricket-api/venue/{name}` — Venue data
- `POST /api/cricket-api/fetch-live` — CricAPI live (Live tab only)

## Test Results
- iteration_11.json: 90% backend, 100% frontend — all features working

## Upcoming (P1)
- Background workers (Celery) for auto-fetching
- WebSocket real-time push

## Future (P2)
- Shareable prediction card
- Prediction accuracy leaderboard
- Market sentiment tracking
