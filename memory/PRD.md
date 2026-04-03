# Gamble Consultant v4 - IPL 2026 Odds Consultant

## Problem Statement
Production-grade IPL 2026 gambling consultant that outputs calibrated win probability (0-100), fair odds, market edge, value-bet signals, player impact, confidence/uncertainty bands, and GPT-powered layman-language advice. Users choose risk tolerance and ask questions about whether to bet.

## Architecture
- **Frontend**: React + Tailwind + Recharts + Shadcn (Dark Mode)
- **Backend**: FastAPI + MongoDB + WebSocket
- **Data Source**: GPT-5.4 with `web_search_preview` tool
- **Decision Engine**: 6-layer stack (Features → Pre-match → Live → Simulation → Calibration → Odds/Edge)
- **Consultation**: GPT-5.4 for layman advice, GPT-5.4 mini for contextual analysis

## Core Engine Layers
1. **Feature Engine**: CRR, RRR, phase flags, batting depth, pressure index, collapse risk, momentum, chase difficulty, etc.
2. **Pre-match Model**: P(win) = σ(α + T + V + X + L + B) — logistic with team strength, venue, toss, lineup, bowling
3. **Live Win Probability**: Feature-driven logistic model (phase-aware, pressure-weighted, momentum-adjusted)
4. **Score Simulation**: Negative Binomial distribution, 10,000 simulations, chase pressure adjustment
5. **Calibration**: Platt scaling to reduce overconfidence, uncertainty bands
6. **Odds & Edge**: Fair odds, overround removal, normalized market probability, edge calculation

## Value Signal Labels
- STRONG_VALUE, VALUE, SMALL_EDGE, NO_BET, AVOID, WAIT_FOR_MORE_DATA, NO_MARKET

## API Endpoints
- `GET /api/` — Health + version (4.0.0)
- `GET /api/schedule` — IPL 2026 schedule
- `GET /api/schedule/load?force=true` — Reload via web search
- `POST /api/matches/{id}/consult` — Full layered consultation
- `POST /api/matches/{id}/chat` — GPT-powered Q&A
- `POST /api/matches/{id}/fetch-live` — Live scores via web search
- `POST /api/matches/{id}/beta-predict` — Beta prediction bundle
- `GET /api/squads` — Team squads
- `WS /api/ws/{matchId}` — WebSocket

## Frontend Screens
- **Match Selector**: Live/Upcoming/Completed tabs with real IPL 2026 data
- **Consultant Dashboard** (main view): Win Gauge, Signal Badge, Edge Meter, Odds Comparison, Simulation Summary, Top Drivers, Player Impact, Match State, Chat Box
- **Pre-Match**: Consultant Dashboard + Radar charts + Playing XI
- **Live Match**: Scoreboard + Charts + Consultant (CONSULT tab default)
- **Post-Match / Analysis**: Historical data views

## Test Results
- Backend: 100% (all tests passed — iteration_6.json)
- Frontend: 100% (all UI components verified)

## Upcoming Tasks (P1)
- Background workers (APScheduler) for continuous auto-fetching
- Polish WebSocket real-time push architecture

## Future Tasks (P2)
- Shareable prediction card
- Market sentiment tracking (user betting patterns)
- Dynamic per-ball recalculation mode
