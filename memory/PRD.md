# Baatu - 11 — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant combining a 6-Factor Live Prediction Model, 5-Factor Pre-Match Model, Claude Opus AI narrative analysis, and SportMonks live API.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), Claude Opus 4.5 (Anthropic), APScheduler
- **Data Sources**: SportMonks API (primary live), CricketData.org API (fallback), DuckDuckGo web scraping
- **AI Engine**: Claude Opus 4.5 via emergentintegrations LlmChat — constrained to 2023-2026 data only
- **Background Jobs**: APScheduler (promote at 4PM/7PM IST, auto-scrape every 5 min)

## Core Prediction Models

### Pre-Match: 5-Factor Model (`/app/backend/services/pre_match_predictor.py`)
Weights:
1. **Form** (35%) — IPL 2026 season results + player buzz sentiment
2. **Squad Strength / Availability** (25%) — 2026 roster quality from STAR_PLAYERS DB
3. **Team Combination / Strategy** (20%) — XI settled-ness, role clarity, overseas balance
4. **Home Advantage** (15%) — Venue familiarity, crowd, conditions
5. **H2H / Pitch Conditions** (5%) — Historical head-to-head, pitch type

### Live Match: 6-Factor Model (`/app/backend/services/live_predictor.py`)
Weights:
1. **Score vs Par Score** (30%) — Phase-adjusted par comparison with sigmoid mapping
2. **Wickets in Hand** (25%) — Non-linear wicket ratio with phase context
3. **Recent Over Rate** (15%) — Last 12 balls scoring rate vs required
4. **Bowlers Remaining** (15%) — Bowling team's remaining quality options
5. **Pre-match Base Probability** (10%) — Anchor from pre-match algorithm
6. **Match Situation Context** (5%) — New batsman, death over pressure, momentum

### Claude Opus Analysis
- **Data Constraint**: All Claude prompts enforce 2023-2026 data only. No pre-2023 references.
- Uses official IPL 2026 squads from DB for all analysis
- Provides narrative predictions, key matchups, injury impacts

## UI Features

### Combined Prediction Block (PreMatch Page)
- Shows Algorithm %, Claude %, and Average % side-by-side
- Model consensus indicator: HIGH (≤5% diff), MODERATE (5-15%), LOW (>15%)
- Individual model boxes with distinct styling

### PreMatch Page
- Combined Prediction Block (top)
- 5-Factor Algorithm Breakdown with logit bars
- Claude Opus Deep Analysis (narrative)
- Expected Playing XI with buzz scores
- Consultant Dashboard

### LiveMatch Page
- 6-Factor Algorithm Breakdown with color-coded bars
- Claude Opus Live Prediction
- Model Consensus Indicator
- Betting Edge Calculator
- Live score with SportMonks data

## Key API Endpoints
- `GET /api/` — Health check
- `GET /api/schedule` — IPL schedule
- `GET /api/predictions/upcoming` — Cached pre-match predictions
- `POST /api/matches/{id}/pre-match-predict` — Run/refresh pre-match prediction
- `POST /api/matches/{id}/fetch-live` — Fetch live data + predictions
- `POST /api/matches/{id}/claude-analysis` — Claude deep analysis
- `POST /api/matches/{id}/refresh-claude-prediction` — Refresh Claude live prediction
- `POST /api/matches/refresh-live-status` — Discover live matches

## DB Schema
- `ipl_squads`: {teamName, teamShort, players: [{name, role, isCaptain, isOverseas}]}
- `pre_match_predictions`: {matchId, prediction: {team1_win_prob, team2_win_prob, factors: {form, squad_strength, team_combination, home_advantage, h2h_pitch}}}
- `claude_analysis`: {matchId, analysis: {team1_win_pct, team2_win_pct, factors[], headline}}
- `live_snapshots`: {matchId, weightedPrediction: {team1_pct, team2_pct, breakdown: {score_vs_par, wickets_in_hand, recent_over_rate, bowlers_remaining, pre_match_base, match_situation_context}}}

## Completed (Apr 2026)
- [x] 2026 IPL squad seeding
- [x] Claude Opus integration with 2023-2026 data constraint
- [x] 5-factor pre-match algorithm (Form 35%, Squad 25%, Combo 20%, Home 15%, H2H 5%)
- [x] 6-factor live algorithm (ScoreVsPar 30%, Wickets 25%, RecentRate 15%, Bowlers 15%, PreMatch 10%, Context 5%)
- [x] Combined Prediction Block UI (Algo + Claude + Average)
- [x] PreMatch 5-factor breakdown display
- [x] LiveMatch 6-factor breakdown display
- [x] Claude prompt 2023-2026 constraints
- [x] Squad-aware Claude for all analysis functions
- [x] SportMonks API integration
- [x] Live match discovery + auto-completion
- [x] Dual prediction models with consensus indicator
- [x] Consultant Dashboard
- [x] APScheduler background tasks

## Backlog
- P2: Shareable prediction card
- P2: Celery migration for background jobs
- P3: Prediction accuracy leaderboard

## Deployment Note
Preview and deployed versions use SEPARATE databases. After deploying, the production site auto-discovers live matches on page load.
