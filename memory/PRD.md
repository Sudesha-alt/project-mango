# PPL Board v3 - IPL 2026 Prediction Platform

## Problem Statement
Full-stack IPL 2026 live match prediction with exact algorithm implementations, betting odds integration, and GPT-powered analysis. All match data must be fetched via real web search (GPT-5.1 with web_search_preview tool), NOT from LLM training data.

## Architecture
- **Frontend**: React + Tailwind + Recharts + Framer Motion + Shadcn (Dark Mode)
- **Backend**: FastAPI + MongoDB + WebSocket
- **Data Source**: GPT-5.4 with `web_search_preview` tool (OpenAI SDK Responses API) — two-step approach: web search → JSON parsing
- **Algorithms**: Sigmoid/RRR Pressure Index, DLS Resource Table, Bayesian Ball-by-Ball, Monte Carlo 500 sims, Weighted Ensemble

## Implemented

### Backend (Completed 2026-04-03)
- **GPT-5.1 Web Search Integration**: Two-step approach in `ai_service.py` — Step 1: web search for raw data, Step 2: parse into structured JSON
- Exact Sigmoid/RRR Pressure Index (1st & 2nd innings formulas)
- DLS Resource Table (21x11 lookup)
- Bayesian: ball-by-ball with event likelihoods
- Monte Carlo: 500 sims with venue-calibrated probabilities
- Ensemble: 25/30/20/25 weighted + confidence band
- Betting odds input → Bayesian prior + edge calculation
- Real IPL 2026 schedule loaded via web search (70 matches: 6 completed, 1 live, 63 upcoming)
- On-demand live data via GPT-5.1 web search + WebSocket
- `noLiveMatch` graceful handling when match isn't live

### Frontend (Completed 2026-04-03)
- 5 screens: Match Selector, Pre-Match, Live Match, Post-Match, Analysis
- Multi-line Win Probability chart (5 algo lines)
- Algorithm Comparison (horizontal bars + confidence band)
- Colored Manhattan chart
- Pre-Match Radar (team comparison)
- Betting Odds Input: decimal odds + confidence slider + edge display
- Live scoreboard, ball log, batsman/bowler stats, GPT commentary
- `noLiveMatch` amber warning banner with match status

## API Endpoints
- `GET /api/` — Health + status
- `GET /api/schedule` — Full IPL 2026 schedule (from MongoDB cache)
- `GET /api/schedule/load?force=true` — Trigger web search to reload schedule
- `POST /api/matches/{id}/fetch-live` — Fetch live scores via web search
- `GET /api/matches/{id}/state` — Get cached match state
- `GET /api/squads` — All team squads
- `GET /api/data-source` — Data source info
- `WS /api/ws/{matchId}` — Real-time WebSocket

## Test Results
- Backend: 100% (21/21 tests passed)
- Frontend: 100% (all major flows working)
- Test report: `/app/test_reports/iteration_4.json`

## Upcoming Tasks (P1)
- Background workers (APScheduler) for continuous auto-fetching
- Polish WebSocket real-time push architecture

## Future Tasks (P2)
- Shareable prediction card feature
- Remove deprecated `cricket_service.py`
