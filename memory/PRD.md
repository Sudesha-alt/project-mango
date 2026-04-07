# The Lucky 11 — IPL 2026 Cricket Prediction Engine

## Overview
Real-time IPL 2026 prediction platform using dual models (8-Category Algorithm + Claude Opus AI), official squad rosters, SportMonks live scoring, Open-Meteo weather, and newsdata.io news.

## Tech Stack
- **Frontend**: React + Shadcn/UI + Phosphor Icons
- **Backend**: FastAPI + MongoDB
- **AI**: Claude Opus (Anthropic) via Emergent Integrations
- **Data**: SportMonks (live scores), Open-Meteo (weather, free), newsdata.io (news)

## Core Design Principles
- **NO web scraping** — all data from DB squads, APIs, or official sources
- **Squad data ONLY from ipl_squads collection** (user-provided IPL 2026 rosters)
- **Expected XI from squad roster only** (not scraped)
- **Weather from Open-Meteo** (free, no API key)
- **News from newsdata.io** (API key required)

## 8-Category Pre-Match Model (v2)
| Category | Weight |
|---|---|
| Squad Strength & Balance | 25% |
| Current Season Form (DB) | 21% |
| Venue + Pitch + Home Adv | 18% |
| Head-to-Head | 11% |
| Toss Impact (venue-specific) | 9% |
| Bowling Depth & Balance | 8% |
| Conditions (weather/dew) | 5% |
| Momentum (last 2 matches) | 3% |

**Removed**: Key Player Matchups, Injuries & Availability

## Architecture
```
/app/backend/
├── server.py                          # FastAPI routes + DB
├── services/
│   ├── pre_match_predictor.py         # 8-category model (no scraping)
│   ├── live_predictor.py              # Alpha-blended live model
│   ├── form_service.py                # Form + Momentum + Expected XI
│   ├── ai_service.py                  # Claude Opus (no scraped data)
│   ├── sportmonks_service.py          # Live scoring
│   ├── weather_service.py             # Open-Meteo weather
│   ├── schedule_data.py               # Official IPL 2026 schedule
│   ├── web_scraper.py                 # newsdata.io news
│   ├── probability_engine.py          # Ensemble probability
│   └── consultant_engine.py           # Betting consultant

/app/frontend/src/
├── pages/
│   ├── PreMatch.js                    # 8-factor breakdown + weather + news
│   ├── LiveMatch.js                   # Live match (no duplicate Claude tab)
│   ├── MatchSelector.js               # Homepage with 58/12 split
├── components/
│   ├── WeatherCard.js                 # Weather display
│   ├── NewsCard.js                    # News articles
│   ├── PreMatchPredictionBreakdown.js # 8-factor bars
```

## Key Fixes (This Session)
- Fixed schedule filter: future-dated matches ALWAYS go to upcoming (regardless of DB status)
- Auto-scrape date guard: prevents marking future matches as completed
- Re-seeded official schedule (70 matches from PDF)

## Backlog
- P2: Shareable prediction card
- P2: Celery migration for background jobs
- P3: Prediction accuracy leaderboard
- Refactoring: server.py split into route modules
