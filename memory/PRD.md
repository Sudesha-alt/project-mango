# Baatu - 11 — Pro Cricket Prediction Engine

## Overview
Real-time IPL prediction platform using dual models (Algorithm + Claude Opus), SportMonks live scoring, Open-Meteo weather, and DuckDuckGo news integration.

## Tech Stack
- **Frontend**: React + Shadcn/UI + Phosphor Icons
- **Backend**: FastAPI + MongoDB
- **AI**: Claude Opus (Anthropic) via Emergent Integrations
- **Data**: SportMonks API (live scores), Open-Meteo (weather, free), DuckDuckGo (news, free)

## Core Features
1. **10-Category Pre-Match Model**: Squad(22%) + Form(18%) + Venue(16%) + H2H(12%) + Toss(8%) + Matchups(6%) + Bowling(7%) + Injuries(5%) + Conditions(4%) + Momentum(2%)
2. **Live Alpha-Blended Model**: P(win) = alpha × H + (1-alpha) × L with piecewise decay
3. **Claude Opus Analysis**: Deep narrative prediction with full scorecard + squad + weather context
4. **Official IPL 2026 Schedule**: 70 matches seeded from official TATA IPL 2026 PDF
5. **Real-time Weather**: Open-Meteo API (free, no key) with cricket impact assessment
6. **Match News**: DuckDuckGo text search for latest match/team news
7. **SportMonks Integration**: Live ball-by-ball data, batsmen, bowlers, partnerships
8. **Consultant Engine**: Risk-adjusted betting recommendations

## Architecture
```
/app/backend/
├── server.py                          # FastAPI routes + DB interactions
├── services/
│   ├── live_predictor.py              # Alpha-blended live math model
│   ├── pre_match_predictor.py         # 10-category pre-match model
│   ├── ai_service.py                  # Claude Opus integrations
│   ├── sportmonks_service.py          # Live scoring data fetcher
│   ├── weather_service.py             # Open-Meteo weather (free, no key)
│   ├── schedule_data.py               # Official IPL 2026 schedule from PDF
│   ├── web_scraper.py                 # DuckDuckGo search + news
│   ├── probability_engine.py          # Ensemble probability calculations
│   ├── consultant_engine.py           # Betting consultant logic
│   └── cricdata_service.py            # CricketData.org fallback

/app/frontend/src/
├── pages/
│   ├── PreMatch.js                    # Pre-match analysis with weather + news
│   ├── LiveMatch.js                   # Live match with weather overlay
│   ├── PostMatch.js                   # Post-match review
│   └── Analysis.js                    # Analysis dashboard
├── components/
│   ├── WeatherCard.js                 # Real-time weather display
│   ├── NewsCard.js                    # Match news articles
│   ├── CombinedPredictionBlock.js     # Algo + Claude combined view
│   ├── PreMatchPredictionBreakdown.js # 10-factor breakdown
│   └── ...                            # Other components
```

## Key API Endpoints
- `GET /api/schedule` — Full schedule (70 matches)
- `POST /api/schedule/seed-official` — Seed official PDF schedule
- `POST /api/matches/{id}/pre-match-predict` — Generate prediction
- `POST /api/matches/{id}/fetch-live` — Fetch live scores
- `POST /api/matches/{id}/refresh-claude-prediction` — Refresh Claude analysis
- `GET /api/weather/{city}` — Weather by city (Open-Meteo)
- `GET /api/matches/{id}/weather` — Match-specific weather
- `GET /api/matches/{id}/news` — Match news articles

## DB Collections
- `ipl_schedule` — 70 official matches with city, timeIST, venue
- `ipl_squads` — Team rosters with player roles
- `pre_match_predictions` — Cached algorithm predictions
- `live_snapshots` — Live match state snapshots

## Backlog
- P2: Shareable prediction card
- P2: Celery migration for background jobs
- P3: Weather API integration for real-time conditions ✅ DONE
- P3: Prediction accuracy leaderboard
- Refactoring: server.py is 2400+ lines, could be split into route modules
