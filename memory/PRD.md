# Baatu - 11 — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant combining a 10-Category Pre-Match Model, Alpha-Blended H×L Live Model, Claude Opus AI narrative analysis, and SportMonks live API.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Claude Opus 4.5 (Anthropic), APScheduler
- **Data Sources**: SportMonks API (primary live), CricketData.org API (fallback), DuckDuckGo web scraping
- **AI Engine**: Claude Opus 4.5 via emergentintegrations — constrained to 2023-2026 data only

## Core Prediction Models

### Pre-Match: 10-Category Model (`/app/backend/services/pre_match_predictor.py`)
| Category | Weight |
|---|---|
| 1. Current Squad Strength & Balance | 22% |
| 2. Current Season Form | 18% |
| 3. Venue + Pitch + Home Advantage | 16% |
| 4. Head-to-Head (recency-weighted) | 10% |
| 5. Toss Impact (venue-specific) | 8% |
| 6. Key Player Matchup Index | 8% |
| 7. Bowling Attack Depth & Balance | 7% |
| 8. Injury & Availability Impact | 5% |
| 9. Conditions (day/night, dew, weather) | 4% |
| 10. Team Momentum & Psychology | 2% |

### Live Match: Alpha-Blended H×L Model (`/app/backend/services/live_predictor.py`)
**Formula**: P(win) = alpha × H + (1 - alpha) × L

**Alpha** (stage-aware non-linear decay):
- Pre-game: 0.85 | End 1st innings: 0.20 | End match: 0.05

**H (Historical/Structural)**:
| Factor | Weight |
|---|---|
| Squad Strength (from Playing XI) | 0.22 |
| Venue Win % | 0.28 |
| Recent Form | 0.25 |
| Toss Advantage | 0.15 |
| H2H (reduced from 0.40) | 0.10 |

**L (Live 6-Factor)**:
| Factor | Weight |
|---|---|
| Score vs Par (venue-specific) | 0.30 |
| Wickets in Hand | 0.25 |
| Recent Over Rate | 0.15 |
| Bowlers Remaining | 0.15 |
| Pre-match Base | 0.10 |
| Match Situation Context | 0.05 |

**Venue Par Scores**: Wankhede 178, Chinnaswamy 195, Chepauk 158, Eden Gardens 175, Motera 172, Uppal 182, Kotla 168, Default 170

### Claude Opus Analysis
- Data Constraint: All prompts enforce 2023-2026 data only
- Uses official IPL 2026 squads from DB

## Key Features
- **Combined Prediction Block**: Algorithm + Claude + Average with consensus indicator
- **Injury Override API**: Manual + auto-scrape, manual takes priority
- **Venue-specific Toss Lookup**: 10 IPL venues with condition-specific data
- **Live Match Auto-Discovery**: Auto-creates schedule entries for rematches
- **Stricter Team Matching**: 2-word + city-name matching prevents false positives

## Key API Endpoints
- `GET /api/` — Health check
- `GET /api/schedule` — IPL schedule
- `POST /api/matches/refresh-live-status` — Discover live matches
- `GET /api/predictions/upcoming` — Cached pre-match predictions
- `POST /api/matches/{id}/pre-match-predict` — Run 10-category prediction
- `POST /api/matches/{id}/fetch-live` — Live data + alpha×H+L prediction
- `POST /api/matches/{id}/injury-override` — Manual injury override
- `GET /api/matches/{id}/injury-overrides` — List overrides
- `DELETE /api/matches/{id}/injury-override/{player}` — Remove override
- `POST /api/matches/{id}/claude-analysis` — Claude deep analysis

## Accuracy Scorecard (User-tracked)
- Pre-game accuracy: 40% (2/5 completed matches)
- Post-first-innings accuracy: 100% (5/5)

## Completed
- [x] 10-category pre-match algorithm
- [x] Alpha-blended H×L live model with 4 research fixes
- [x] Non-linear alpha curve (0.85→0.20→0.05)
- [x] Squad strength differential in H (0.22 weight)
- [x] Venue-specific par scores (14 venues)
- [x] H2H reduced to 0.10 (from 0.40)
- [x] Injury override API
- [x] Combined Prediction Block UI
- [x] Live match auto-discovery for rematches
- [x] Stricter team name matching

## Backlog
- P2: Shareable prediction card
- P2: Celery migration for background jobs
- P3: Prediction accuracy leaderboard
- P3: Weather API integration
