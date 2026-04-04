# Baatu - 11 — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant (renamed from "Gamble Consultant") combining 50K Negative Binomial simulations, 11-factor prediction algorithms, GPT-5.4 web search, and CricketData.org live data.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), OpenAI GPT-5.4
- **Data**: CricketData.org API (100/day), GPT web scraping

## Core Features (All Implemented)

### 11-Factor Prediction Model (v5.4)
| # | Factor | Weight | Source |
|---|--------|--------|--------|
| 1 | Head-to-Head (5yr) | 12% | GPT web search: IPL 2021-2026 results |
| 2 | Venue Performance | 10% | GPT: team avg scores + win % at ground |
| 3 | Recent Form | 12% | GPT: last 5 IPL 2026 matches, sample-size damped |
| 4 | Squad Strength | 10% | GPT: batting depth + bowling attack ratings |
| 5 | Home Advantage | 6% | Ground ownership (+0.3 logit) |
| 6 | Toss Impact | 8% | GPT: bat-first win %, toss-winner match-win % |
| 7 | Pitch & Conditions | 10% | GPT: pitch type, pace/spin assist, dew factor |
| 8 | Key Matchups | 10% | GPT: batter vs bowler T20 records |
| 9 | Death Overs (16-20) | 8% | GPT: avg runs scored/conceded in death |
| 10 | Powerplay (1-6) | 8% | GPT: avg PP score, wickets lost |
| 11 | Momentum | 6% | GPT: win/loss streaks, last 10 matches |

### Playing XI + Performance System
- GPT-5.4 web search for expected lineups from news, social media, fantasy sites
- Injury/controversy/drop detection: unavailable players excluded and replaced
- **Buzz Score (-100 to +100)**: Sentiment from news + social media with reasons
- **Performance Formula**: `expected = base_stats * (1 + buzz_modifier) * luck_factor`
- Background fetch with polling (no proxy timeout)
- DB updated so all users see same data

### 50K Negative Binomial Simulation Engine
- Predicted scores (mean, median, P10-P90) for both teams
- Batting-first win %, chase pressure adjustment

### Consultation & Verdict System
- Uses cached 11-factor prediction (model_source: "11_factor_algorithm")
- Bold verdict: DOMINANT/STRONG/SLIGHT/TOSS-UP
- Value signals with edge explanation pointers

### Live Match Prediction (v5.4)
- Real-time prediction during live matches based on:
  - Current batsmen on field (set indicator, impact rating)
  - Current bowler analysis (economy, wickets, impact)
  - Projected score (1st innings)
  - Chase analysis (2nd innings: difficulty, RRR vs CRR)
  - Phase (Powerplay/Middle/Death)
  - Wickets in hand

### User Guide (In-App)
- 10-section FAQ modal covering all features

## Key Bug Fixes
- **v5.1**: scipy nbinom parameterization (1-p → p)
- **v5.3**: Form factor damping for small samples, Playing XI background fetch
- **v5.4**: Consultation uses 11-factor cached prediction instead of 5-factor fallback, skip double Platt calibration

## Completed Milestones
- v1.0-v4.0: Core platform, algorithm, simulations
- v5.0: Bold verdict UI rewrite
- v5.1: Simulation fix, two-sided factor breakdown, edge reasons, user guide
- v5.2: Buzz sentiment (-100 to +100), performance formula
- v5.3: Form damping, background Playing XI fetch
- v5.4: 11-factor model, renamed Baatu-11, live match prediction, extensive GPT data fetch

## Backlog
- P2: Split ConsultantDashboard.js into sub-components
- P2: Background Celery workers for auto-scraping
- P2: Shareable prediction card
- P3: Prediction accuracy leaderboard
