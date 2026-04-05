# Baatu - 11 — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant combining Weighted Probability Formula (7 granular live factors), Claude Opus AI prediction with full squad context, 50K NB simulations, SportMonks live API, and background auto-scraping.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), Claude Opus 4.5 (Anthropic), APScheduler
- **Data Sources**: SportMonks API (primary live), CricketData.org API (fallback), DuckDuckGo web scraping
- **AI Engine**: Claude Opus 4.5 via emergentintegrations LlmChat — receives full squad data for both teams
- **Background Jobs**: APScheduler (promote at 4PM/7PM IST, auto-scrape every 5 min)

## Core Features

### Enhanced Weighted Prediction — 7 Granular Live Factors
The Live (L) component of P(win) = alpha x H + (1-alpha) x L now uses 7 real-time factors from SportMonks:
- **CRR/RRR Pressure** (0.20) — phase-aware run rate comparison (powerplay/middle/death par rates)
- **Wickets in Hand** (0.15) — remaining wickets as ratio
- **Recent Wicket Penalty** (0.15) — decay penalty for wickets in last 12 balls
- **Batter Confidence** (0.15) — active batsmen strike rate + boundary hitting
- **New Batsman Factor** (0.10) — vulnerability penalty for newly arrived batter (<5 balls)
- **Bowler Threat** (0.10) — current bowler economy + wicket-taking inverted for batting side
- **Phase Momentum** (0.15) — scoring rate in last 6 balls vs par

Live Context returned: active batsmen names, bowler name, CRR, RRR, recent wickets count.

### Squad-aware Claude Predictions
- ALL Claude live analysis functions receive both team squads from DB
- Claude references specific players by name, role, and IPL career form
- Squads passed to: `claude_sportmonks_prediction`, `claude_live_analysis`, refresh endpoint
- `_get_squads_for_match` helper fetches from `ipl_squads` collection

### Auto-discovery on Page Load
- On mount, MatchSelector silently calls `refresh-live-status` to discover live matches
- Auto-switches to Live tab if matches found

### Live Match Discovery & Management
- `POST /api/matches/refresh-live-status` — queries SportMonks livescores + CricAPI, promotes matches to "live"
- Smart team matching (priority: live > upcoming) for duplicate fixtures
- Auto-completion of finished matches

### Dual Live Prediction Models
- **Weighted Probability**: P(win) = alpha x H + (1-alpha) x L with 7-factor breakdown + live context
- **Claude Opus**: AI prediction with squad-aware batting depth, bowling assessment, key matchup
- **Model Consensus**: HIGH (<=5%) / MODERATE (5-15%) / LOW (>15%)

### Key API Endpoints
- `POST /api/matches/refresh-live-status` — Discover + promote live matches
- `POST /api/matches/{id}/fetch-live` — Real-time SportMonks + Claude (with squads) + Weighted (7 factors)
- `POST /api/matches/{id}/refresh-claude-prediction` — Refresh predictions with squads
- `POST /api/matches/{id}/claude-live` — Claude live analysis with squads
- `POST /api/matches/{id}/check-status` — Status check
- `GET /api/live/current` — Currently live matches

## Completed
- [x] 11-Factor + 50K NB simulations
- [x] Claude Opus migration from GPT-5.4
- [x] Pre-match Claude narrative
- [x] Component modularization
- [x] APScheduler background tasks
- [x] SportMonks API integration
- [x] Claude live prediction with full squad context for BOTH teams
- [x] Weighted Probability model (3 basic factors)
- [x] Dual prediction models UI
- [x] Model Consensus Indicator
- [x] Live match discovery (SportMonks livescores + CricAPI)
- [x] Auto-discovery on page load
- [x] Smart team matching
- [x] Auto-completion of finished matches
- [x] Squad-aware Claude for all live analysis functions
- [x] **Enhanced Live Factors (L) — 7 granular real-time factors** (Apr 5, 2026)
- [x] **Fixed team perspective bug in weighted prediction** — L now normalized to team1's perspective before combining with H (Apr 5, 2026)

## Backlog
- P2: Shareable prediction card
- P2: Celery migration
- P3: Prediction accuracy leaderboard

## Deployment Note
Preview and deployed versions use SEPARATE databases. After deploying, the production site auto-discovers live matches on page load via the `refresh-live-status` endpoint.
