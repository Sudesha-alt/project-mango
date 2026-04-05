# Baatu - 11 — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant combining Weighted Probability Formula, Claude Opus AI prediction, 50K NB simulations, 11-factor algorithms, SportMonks live API, and background auto-scraping.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), Claude Opus 4.5 (Anthropic), APScheduler
- **Data Sources**: SportMonks API (primary live), CricketData.org API (fallback), DuckDuckGo web scraping
- **AI Engine**: Claude Opus 4.5 via emergentintegrations LlmChat
- **Background Jobs**: APScheduler (promote at 4PM/7PM IST, auto-scrape every 5 min)

## Core Features

### Dual Live Prediction Models
**Model 1 — Weighted Probability**: P(win) = alpha x H + (1-alpha) x L with info button
**Model 2 — Claude Opus**: AI prediction with batting depth, bowling assessment, key matchup
**Model Consensus Indicator**: HIGH/MODERATE/LOW agreement between models

### Smart Live Match Management
- **Refresh Matches button** on Live tab: Checks all "live" matches against SportMonks + CricAPI fallback
- Finished matches auto-pushed to "completed" with winner/result
- Match completed banner on individual live pages with navigation options
- `POST /api/matches/refresh-live-status` — Bulk status check + auto-completion
- `POST /api/matches/{id}/check-status` — Individual match status check
- `GET /api/live/current` — Find currently live IPL matches

### Live Match Page
- SportMonks primary data source, CricAPI fallback
- Manual "Fetch Live Scores" + "Check Status" buttons
- Yet to Bat/Bowl lineups
- Claude probabilities as single source of truth for scoreboard
- Refreshable predictions without re-fetching SportMonks

### Pre-Match + Compare
- 11-Factor algorithm + 50K NB simulations
- Claude Opus deep narrative analysis
- Algorithm vs Claude comparison dashboard

### Key API Endpoints
- `POST /api/matches/{id}/fetch-live` — Manual live fetch
- `POST /api/matches/{id}/refresh-claude-prediction` — Refresh predictions
- `POST /api/matches/refresh-live-status` — Bulk live status check
- `POST /api/matches/{id}/check-status` — Individual status check
- `GET /api/live/current` — Currently live matches

## Completed
- [x] 11-Factor + 50K NB simulations
- [x] Claude Opus migration
- [x] Pre-match Claude narrative
- [x] Compare dashboard
- [x] Component modularization
- [x] APScheduler background tasks
- [x] SportMonks API integration
- [x] Claude live win prediction with lineup context
- [x] Unified Claude probabilities
- [x] Weighted Probability model (formula-based)
- [x] Dual prediction models UI
- [x] Formula info (i) button
- [x] Model Consensus Indicator
- [x] Smart live match detection + auto-completion
- [x] Refresh Matches on Live tab
- [x] Match completed banner + navigation

## Backlog
- P2: Shareable prediction card
- P2: Celery migration
- P3: Prediction accuracy leaderboard
