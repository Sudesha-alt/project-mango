# PPL Board v3 - IPL 2026 Prediction Platform

## Problem Statement
Full-stack IPL 2026 live match prediction with exact algorithm implementations, betting odds integration, and GPT-powered analysis. All match data must be fetched via real web search (GPT-5.4 with web_search_preview tool), NOT from LLM training data.

## Architecture
- **Frontend**: React + Tailwind + Recharts + Framer Motion + Shadcn (Dark Mode)
- **Backend**: FastAPI + MongoDB + WebSocket
- **Data Source**: GPT-5.4 with `web_search_preview` tool (OpenAI SDK Responses API) — two-step approach: web search then JSON parsing
- **Algorithms**: Sigmoid/RRR Pressure Index, DLS Resource Table, Bayesian Ball-by-Ball, Monte Carlo 500 sims, Weighted Ensemble
- **Beta Engine**: Poisson Distribution, Monte Carlo 10K, Player Prediction Formula, Odds Engine + House Edge, Value Bet Alerts

## Implemented

### Core Math Algorithms (Completed)
- Exact Sigmoid/RRR Pressure Index (1st & 2nd innings formulas)
- DLS Resource Table (21x11 lookup)
- Bayesian: ball-by-ball with event likelihoods
- Monte Carlo: 500 sims with venue-calibrated probabilities
- Ensemble: 25/30/20/25 weighted + confidence band

### Beta Prediction Engine (Completed 2026-04-03)
- **Poisson Distribution**: Predict runs/wickets probability distributions per over with context weighting
- **Player Prediction Formula**: `0.4*Last5Avg + 0.3*VenueAvg + 0.2*OpponentAdj + 0.1*FormMomentum`
- **Monte Carlo 10K**: 10,000 simulations using player-level predictions with chase pressure
- **Odds Engine**: True probability -> decimal odds + 10% house edge + overround calculation
- **Value Bet Alert System**: Detects HIGH_VALUE (>10% threshold) and MARKET_INEFFICIENCY bets
- **Match Context Weighting**: Powerplay/middle/death, chase/defend, pressure index, wickets pressure
- **Momentum Alerts**: Wicket clusters, boundary surges, RRR spikes, collapse risk
- **GPT-5.4 Web Search**: Fetches real player stats (last 5 matches, venue averages) for predictions
- **GPT-5.4 mini**: Quick contextual analysis with tactical insights, pattern detection, strategy recommendations

### Frontend (Completed)
- 5 screens: Match Selector, Pre-Match, Live Match, Post-Match, Analysis
- BetaPrediction component with 4 sub-tabs: Overview, Players, Poisson, Alerts
- Player Prediction Table (Name, Pred Runs, Pred Wkts, Confidence %)
- Poisson Distribution bar charts (runs & wickets)
- Monte Carlo 10K summary (win %, avg score, score ranges p10-p90)
- Odds Engine display (true odds, house odds, implied probability, overround)
- Value Bet Alert cards (color-coded HIGH_VALUE/MARKET_INEFFICIENCY)
- Context badges (phase, pressure level, RRR)
- Multi-line Win Probability chart (5 algo lines)
- Algorithm Comparison horizontal bars + confidence band
- Colored Manhattan chart
- Pre-Match Radar (team comparison)
- Betting Odds Input: decimal odds + confidence slider + edge display
- Live scoreboard, ball log, batsman/bowler stats, GPT commentary

## API Endpoints
- `GET /api/` — Health + status
- `GET /api/schedule` — Full IPL 2026 schedule
- `GET /api/schedule/load?force=true` — Reload schedule via web search
- `POST /api/matches/{id}/fetch-live` — Fetch live scores via web search
- `POST /api/matches/{id}/beta-predict` — Full beta prediction bundle
- `GET /api/matches/{id}/state` — Cached match state
- `GET /api/squads` — All team squads
- `GET /api/data-source` — Data source info
- `WS /api/ws/{matchId}` — Real-time WebSocket

## Test Results
- Backend: 100% (all tests passed)
- Frontend: 100% (all flows working)
- Test reports: iteration_4.json, iteration_5.json

## Upcoming Tasks (P1)
- Background workers (APScheduler) for continuous auto-fetching
- Polish WebSocket real-time push architecture

## Future Tasks (P2)
- Shareable prediction card feature
- Remove deprecated `cricket_service.py`
