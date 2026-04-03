# Gamble Consultant v4 - IPL 2026 Odds Consultant

## Problem Statement
Production-grade IPL 2026 gambling consultant that outputs calibrated win probability (0-100), fair odds, market edge, value-bet signals, player impact, confidence/uncertainty bands, and GPT-powered layman-language advice. Users choose risk tolerance and ask questions about whether to bet. Live match data from CricketData.org API (100 hits/day).

## Architecture
- **Frontend**: React + Tailwind + Recharts + Shadcn (Dark Mode)
- **Backend**: FastAPI + MongoDB + WebSocket
- **Data Sources**: 
  - GPT-5.4 with `web_search_preview` for schedule/squads/analysis
  - CricketData.org API for live match scores (100 hits/day, manual trigger only)
- **Decision Engine**: 6-layer stack (Features → Pre-match → Live → Simulation → Calibration → Odds/Edge)
- **Consultation**: GPT-5.4 for layman advice, GPT-5.4 mini for contextual analysis

## Core Engine Layers
1. **Feature Engine**: CRR, RRR, phase flags, batting depth, pressure, collapse risk, momentum, chase difficulty
2. **Pre-match Model**: P(win) = σ(α + T + V + X + L + B)
3. **Live Win Probability**: Feature-driven logistic (phase-aware, pressure-weighted)
4. **Score Simulation**: Negative Binomial, 10K sims, chase pressure adjustment
5. **Calibration**: Platt scaling, uncertainty bands
6. **Odds & Edge**: Fair odds, overround removal, normalized market probability, edge

## CricketData.org Integration
- API Key: stored in backend .env as CRICAPI_KEY
- Endpoints: currentMatches filtered for IPL 2026
- Rate limit: 100 hits/day, tracked in MongoDB, displayed in UI
- Manual trigger only — user clicks "Fetch Live IPL Details"
- Returns: team names, innings scores, venues, match status

## Value Signal Labels
STRONG_VALUE, VALUE, SMALL_EDGE, NO_BET, AVOID, WAIT_FOR_MORE_DATA, NO_MARKET

## API Endpoints
- `GET /api/` — Health (v4.0.0)
- `GET /api/schedule` — IPL 2026 schedule
- `POST /api/matches/{id}/consult` — Full layered consultation
- `POST /api/matches/{id}/chat` — GPT Q&A
- `POST /api/matches/{id}/fetch-live` — Live scores via web search
- `POST /api/matches/{id}/beta-predict` — Beta prediction bundle
- `POST /api/cricket-api/fetch-live` — CricketData.org live data (1 hit)
- `GET /api/cricket-api/usage` — API hit counter
- `GET /api/cricket-api/cached` — Cached CricAPI data (free)
- `GET /api/squads` — Team squads
- `WS /api/ws/{matchId}` — WebSocket

## Test Results
- Backend: 100% — iteration_7.json
- Frontend: 100% — all verified
- API usage: 8/100 hits used today

## Upcoming (P1)
- Background workers for auto-fetching
- WebSocket real-time push

## Future (P2)
- Shareable prediction card
- Market sentiment tracking
