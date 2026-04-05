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

### Live Match Discovery & Management
- **Refresh Matches**: Queries SportMonks `/livescores` + CricAPI to discover live IPL matches, promotes them to "live" in schedule
- **Auto-completion**: Finished matches automatically pushed to "completed" with winner/result
- **Team matching**: Smart fuzzy matching with priority (live > upcoming > future) to handle multiple fixtures between same teams
- **Check Status**: Individual match status check against SportMonks

### Dual Live Prediction Models
**Model 1 — Weighted Probability**: P(win) = alpha x H + (1-alpha) x L with full breakdown + info button
**Model 2 — Claude Opus**: AI prediction considering player form, batting depth, bowling options
**Model Consensus Indicator**: HIGH (≤5%) / MODERATE (5-15%) / LOW (>15%)

### Real-time Score Fetching
- SportMonks primary: full batting card, bowling card, lineup, recent balls
- CricAPI fallback when SportMonks unavailable
- Manual "Fetch Live Scores" triggers SportMonks → Claude prediction pipeline
- Yet to Bat/Bowl lineups displayed and passed to Claude

### Key API Endpoints
- `POST /api/matches/refresh-live-status` — Discover + promote live matches
- `POST /api/matches/{id}/fetch-live` — Real-time SportMonks data + Claude + Weighted predictions
- `POST /api/matches/{id}/refresh-claude-prediction` — Refresh predictions only
- `POST /api/matches/{id}/check-status` — Individual status check
- `GET /api/live/current` — Currently live matches

## Completed
- [x] 11-Factor + 50K NB simulations
- [x] Claude Opus migration from GPT-5.4
- [x] Pre-match Claude narrative
- [x] Component modularization
- [x] APScheduler background tasks
- [x] SportMonks API integration (livescores + fixture details)
- [x] Claude live prediction with full lineup context + historical factors
- [x] Weighted Probability model (formula-based)
- [x] Dual prediction models UI (side-by-side)
- [x] Model Consensus Indicator (HIGH/MODERATE/LOW)
- [x] Live match discovery from SportMonks livescores API
- [x] Refresh Matches button (Live tab)
- [x] Smart team matching (priority: live > upcoming)
- [x] Auto-completion of finished matches
- [x] Check Status + match completed banner

## Backlog
- P2: Shareable prediction card
- P2: Celery migration
- P3: Prediction accuracy leaderboard
