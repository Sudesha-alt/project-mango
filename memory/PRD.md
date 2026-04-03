# Gamble Consultant v4.1 - IPL 2026 Odds Consultant

## Problem Statement
Production-grade IPL 2026 gambling consultant with calibrated win probability, fair odds, market edge, value-bet signals, player impact, confidence bands, GPT-powered advice, and pre-match predictions using historical data (H2H 5yr, venue stats, recent form, squad strength). Live data from CricketData.org API.

## Architecture
- **Frontend**: React + Tailwind + Recharts + Shadcn (Dark Mode)
- **Backend**: FastAPI + MongoDB + WebSocket
- **Data Sources**: GPT-5.4 Web Search (schedule/stats/analysis), CricketData.org API (live scores, 100/day)
- **Engines**: 6-layer Decision Engine, Pre-Match Algorithm Stack, Beta Prediction Engine

## Pre-Match Prediction System
- **Data**: GPT-5.4 web searches real H2H record (last 5 years, match-by-match detail), venue averages (1st/2nd innings, highest/lowest totals), recent form (last 5 matches with opponents), squad ratings
- **Algorithm**: 5 weighted factors → logistic combination → Platt calibration → confidence %
  - H2H Factor (25%): Win ratio from last 5 years of head-to-head IPL matches
  - Venue Factor (20%): Average scores + win % at specific ground + home advantage
  - Form Factor (25%): Last 5 match win percentage for both teams
  - Squad Factor (20%): Batting depth rating + bowling attack rating
  - Home Advantage (10%): Home ground boost
- **Storage**: Predictions computed once and stored in MongoDB for instant retrieval
- **Frontend**: Confidence bar on match cards, full factor breakdown with info tooltips

## Playing XI System (NEW v4.1)
- GPT-5.4 web search scrapes expected/confirmed Playing XI for IPL 2026 matches
- Returns 11 players per team with season stats (runs, avg, SR, wickets, economy)
- **Luck Biasness**: Random variance factor (+-15%) applied to expected performance representing unpredictable match-day conditions
- Cached in MongoDB `playing_xi` collection

## Odds Input System (Updated v4.1)
- All bookmaker inputs use **0-100 probability scale** (not decimal odds)
- Backend converts 0-100 pct → decimal odds internally where needed
- Fields: `market_pct_team1`, `market_pct_team2` (0-100)

## Info Tooltips (NEW v4.1)
- Every prediction model and metric has an info tooltip explaining its function in plain English
- Sections covered: Algorithm Prediction, Factor Breakdown (H2H, Venue, Form, Squad, Home), Risk Tolerance, Bookmaker Win %, Win Probability Gauge, Edge Meter, Simulation Summary, Top Drivers, Player Impact, Match State

## API Endpoints
- `GET /api/` — Health (v4.0.0)
- `GET /api/schedule` — IPL 2026 schedule
- `POST /api/matches/{id}/pre-match-predict` — Predict match (cached in DB)
- `POST /api/schedule/predict-upcoming` — Batch predict all upcoming
- `GET /api/predictions/upcoming` — Get all cached predictions
- `POST /api/matches/{id}/consult` — Full decision engine consultation (0-100 pct inputs)
- `POST /api/matches/{id}/chat` — GPT Q&A (0-100 pct inputs)
- `POST /api/matches/{id}/fetch-live` — Live scores via web search (0-100 pct inputs)
- `POST /api/matches/{id}/beta-predict` — Beta prediction (0-100 pct inputs)
- `POST /api/matches/{id}/playing-xi` — **NEW** Fetch Playing XI with luck biasness
- `GET /api/cricket-api/venue/{venue_name}` — **NEW** On-demand venue data from CricketData.org
- `POST /api/cricket-api/fetch-live` — CricketData.org live (1 hit)
- `GET /api/cricket-api/usage` — API counter
- `GET /api/squads` — Squads
- `WS /api/ws/{matchId}` — WebSocket

## Test Results
- iteration_9.json: 100% (all backend endpoints + all frontend elements)
- 64 predictions cached for upcoming matches

## Upcoming (P1)
- Background workers for auto-fetching
- WebSocket real-time push

## Future (P2)
- Shareable prediction card
- Market sentiment tracking
