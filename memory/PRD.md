# Baatu - 11 — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant combining 50K Negative Binomial simulations, 11-factor prediction algorithms, GPT-5.4 web search, and CricketData.org live data.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), OpenAI GPT-5.4, APScheduler
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

### Match Scheduler (v4.1)
- APScheduler runs at **4:00 PM IST** and **7:00 PM IST** daily
- Promotes today's upcoming matches to "live" status on the Live tab
- Manual trigger: `POST /api/scheduler/promote-now`
- Syncs live snapshot scores to schedule on startup + promote

### Manual Live Fetch (v4.1)
- Live scores fetched **on-demand only** (manual "Fetch Live Scores" button)
- After fetch: runs 4 probability algorithms + live prediction
- **Score saved to schedule** so match cards show live score (e.g., "MI 41/2 (6 ov)")

### Enriched Chat Context (v4.1)
- Chat passes full live context to GPT: batsmen, bowler, probabilities, projected score, chase analysis, phase
- GPT answers referencing specific player performances and algorithm outputs

### ConsultantDashboard (v4.2 — Fixed Layout)
- Single-column stacked layout (no more 3-column grid overflow)
- Sections: Verdict → Win Gauge + Edge → Simulations → Drivers → Betting Scenarios → Player Impact → Chat
- Removed OddsComparison visual (redundant with Edge meter)

### Playing XI + Performance System
- GPT-5.4 web search for expected lineups
- Buzz Score (-100 to +100) with reasons
- Performance Formula: `expected = base_stats * (1 + buzz_modifier) * luck_factor`
- Background fetch with polling (no proxy timeout)

### 50K Negative Binomial Simulation Engine
- Predicted scores (mean, median, P10-P90) for both teams
- Batting-first win %, chase pressure adjustment

### Live Match Prediction (v5.4)
- Real-time prediction: batsmen on field, bowler analysis, projected score, chase analysis, phase

### User Guide (In-App)
- 10-section FAQ modal covering all features

## Key Bug Fixes
- v5.1: scipy nbinom parameterization
- v5.3: Form factor damping, Playing XI background fetch
- v5.4: 11-factor consultation, skip double Platt calibration
- v4.2: ConsultantDashboard layout overflow fix, match card score update

## Completed Milestones
- v1.0-v4.0: Core platform, algorithm, simulations
- v5.0: Bold verdict UI rewrite
- v5.1: Simulation fix, two-sided factor breakdown, edge reasons, user guide
- v5.2: Buzz sentiment, performance formula
- v5.3: Form damping, background Playing XI fetch
- v5.4: 11-factor model, renamed Baatu-11, live match prediction
- v4.1: Scheduler (4PM/7PM IST), manual-only live fetch, enriched chat context
- v4.2: ConsultantDashboard layout fix, match card live score display, removed OddsComparison

## Backlog
- P2: Split ConsultantDashboard.js into sub-components
- P2: Background Celery workers for auto-scraping
- P2: Shareable prediction card
- P3: Prediction accuracy leaderboard
