# Baatu - 11 — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant combining a 10-Category Pre-Match Model, 6-Factor Live Model, Claude Opus AI narrative analysis, and SportMonks live API.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), Claude Opus 4.5 (Anthropic), APScheduler
- **Data Sources**: SportMonks API (primary live), CricketData.org API (fallback), DuckDuckGo web scraping
- **AI Engine**: Claude Opus 4.5 via emergentintegrations LlmChat — constrained to 2023-2026 data only

## Core Prediction Models

### Pre-Match: 10-Category Model (`/app/backend/services/pre_match_predictor.py`)
Research-validated weights (categories 1-3 = 56% dominance):

| Category | Weight | Description |
|---|---|---|
| 1. Current Squad Strength & Balance | 22% | Player Impact Score (bat×SR + bowl×econ), allrounder 1.35x multiplier, balance penalty |
| 2. Current Season Form | 18% | IPL 2026 wins/losses with exponential decay, NRR differential, buzz overlay |
| 3. Venue + Pitch + Home Advantage | 16% | Venue win%, avg scores, home boost (57.91%), pitch type interaction |
| 4. Head-to-Head (recency-weighted) | 10% | Last 3 IPL seasons with sample-size damping |
| 5. Toss Impact (venue-specific) | 8% | From user-provided Excel lookup — venue+condition→preferred decision, win% |
| 6. Key Player Matchup Index | 8% | Batter vs bowler H2H aggregated across likely XI pairs |
| 7. Bowling Attack Depth & Balance | 7% | Quality bowling overs (bowler rating × 4), variety bonus |
| 8. Injury & Availability Impact | 5% | Auto-scrape + manual override (manual priority), allrounder absence = 1.35x |
| 9. Conditions (day/night, dew, weather) | 4% | Schedule timing, venue-specific dew heuristics |
| 10. Team Momentum & Psychology | 2% | Win streak, capped at 2% max shift |

Design Principles:
- No hard-capping. Probabilities outside 35-65% are rare but possible.
- 4-year rolling window with exponential decay.
- Only IPL 2026 data for form. 2023-2026 for historical.

### Live Match: 6-Factor Model (`/app/backend/services/live_predictor.py`)
| Factor | Weight |
|---|---|
| Score vs Par Score | 30% |
| Wickets in Hand | 25% |
| Recent Over Rate | 15% |
| Bowlers Remaining | 15% |
| Pre-match Base Probability | 10% |
| Match Situation Context | 5% |

### Claude Opus Analysis
- Data Constraint: All prompts enforce 2023-2026 data only
- Uses official IPL 2026 squads from DB

## Key Features
- **Combined Prediction Block**: Algorithm + Claude + Average with consensus indicator
- **Injury Override API**: Manual + auto-scrape, manual takes priority
- **Venue-specific Toss Lookup**: 10 IPL venues with condition-specific data
- **10-category factor breakdown UI**: All categories displayed with logit bars

## Key API Endpoints
- `GET /api/` — Health check
- `GET /api/schedule` — IPL schedule
- `GET /api/predictions/upcoming` — Cached pre-match predictions
- `POST /api/matches/{id}/pre-match-predict` — Run 10-category prediction
- `POST /api/matches/{id}/injury-override` — Add manual injury override
- `GET /api/matches/{id}/injury-overrides` — List injury overrides
- `DELETE /api/matches/{id}/injury-override/{player}` — Remove override
- `POST /api/matches/{id}/fetch-live` — Live data + predictions
- `POST /api/matches/{id}/claude-analysis` — Claude deep analysis

## DB Schema
- `ipl_squads`: {teamName, teamShort, players[]}
- `pre_match_predictions`: {matchId, prediction: {team1_win_prob, factors: {10 categories}}}
- `injury_overrides`: {matchId, player, team, impact_score, reason, source}
- `claude_analysis`: {matchId, analysis: {team1_win_pct, factors[], headline}}

## Accuracy Scorecard (User-tracked)
- Pre-game accuracy: 40% (2/5 completed matches)
- Post-first-innings accuracy: 100% (5/5)
- Key insight: Pre-game probabilities at 52-57% are genuine coin-flips

## Completed
- [x] 10-category pre-match algorithm with venue toss lookup
- [x] 6-factor live algorithm
- [x] Injury override API (manual + auto-scrape)
- [x] Combined Prediction Block UI
- [x] Claude 2023-2026 data constraints
- [x] 2026 IPL squad seeding
- [x] SportMonks API integration
- [x] Dual prediction models with consensus indicator

## Backlog
- P2: Shareable prediction card
- P2: Celery migration for background jobs
- P3: Prediction accuracy leaderboard
- P3: Weather API integration for real-time conditions
