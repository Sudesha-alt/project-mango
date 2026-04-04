# Gamble Consultant v5.0 - IPL 2026 Odds Consultant

## Problem Statement
Production-grade IPL 2026 gambling consultant with calibrated win probability, fair odds, market edge, value-bet signals, player impact, confidence bands, GPT-powered advice, and pre-match predictions.

## Architecture
- Frontend: React + Tailwind + Recharts + Shadcn (Dark Mode)
- Backend: FastAPI + MongoDB + WebSocket
- Data: GPT-5.4 Web Search + CricketData.org API (100/day limit)

## Bold Winner Verdict (v5.0 - NEW)
- Clear "CSK WINS" header in large bold text at top of results
- Strength levels: DOMINANT (80%+), STRONG (65%+), SLIGHT (55%+), TOSS-UP
- Plain English explanation of why the model picked this team
- Signal badge (STRONG VALUE, VALUE, NEUTRAL, AVOID)

## Visual Odds Comparison (v5.0 - NEW)
- Side-by-side bars: Model probability vs Market probability for BOTH teams
- Dashed line showing bookmaker position
- Edge %, Fair Odds, and Overround displayed prominently

## Betting Scenarios (v5.0 - NEW)
- AI-generated betting windows: PRE_MATCH, IN_PLAY_POWERPLAY, PLAYER_OUTBURST, CHASE_DYNAMIC
- Each scenario: title, description, confidence (HIGH/MEDIUM), timing
- Example: "Watch Virat Kohli for big innings — Predicted 37.9r at SR 142"

## 50K Simulations (v5.0 - UPGRADED)
- Upgraded from 10K → 50K Negative Binomial match simulations
- More accurate probability distributions and chase dynamics

## Prediction Calculation (v4.4)
- H2H (25%): 2021-2026 match-by-match detail
- Venue (20%): Player-level venue stats (60%) + team level (40%)
- Form (25%): Individual buzz confidence (50%) + team form (50%)
- Squad (20%): Batting + bowling quality ratings
- Home (10%): Home ground boost

## Market Momentum (v4.4)
- Toggle: which team's odds rising (0→100) vs falling (100→0)
- 3% probability adjustment applied

## Playing XI (v4.3)
- News-aware: excludes injured/unavailable players
- Venue-specific stats + buzz confidence (0-100) + luck biasness

## CricAPI Live Panel
- Shows only on Live tab (not Upcoming)

## Refresh/Re-Predict
- Button in Algorithm Prediction header
- Force re-predict with fresh data + Playing XI

## API Endpoints
- GET /api/ — Health
- GET /api/schedule — IPL 2026 schedule
- POST /api/schedule/resolve-venues — Fix TBD venues
- POST /api/matches/{id}/pre-match-predict?force=true — Predict match
- POST /api/schedule/predict-upcoming — Batch predict
- GET /api/predictions/upcoming — Cached predictions
- POST /api/predictions/repredict-all — Background re-predict
- GET /api/predictions/repredict-status — Progress
- POST /api/matches/{id}/consult — Decision engine (verdict + scenarios + odds visual)
- POST /api/matches/{id}/chat — GPT Q&A
- POST /api/matches/{id}/playing-xi — Playing XI
- GET /api/cricket-api/venue/{name} — Venue data
- POST /api/cricket-api/fetch-live — CricAPI live

## Test Results
- iteration_13.json: 100% (25/25 backend, all frontend)

## Upcoming (P1)
- Background workers for auto-fetching
- WebSocket real-time push

## Future (P2)
- Shareable prediction card
- Prediction accuracy leaderboard
