# Baatu - 11 — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant combining 50K Negative Binomial simulations, 11-factor prediction algorithms, Claude Opus deep narrative analysis, SportMonks live API, and background auto-scraping.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), Claude Opus 4.5 (Anthropic), APScheduler
- **Data Sources**: SportMonks API (primary live), CricketData.org API (fallback, 100/day), DuckDuckGo web scraping (analysis)
- **AI Engine**: Claude Opus 4.5 via emergentintegrations LlmChat
- **Background Jobs**: APScheduler (promote at 4PM/7PM IST, auto-scrape every 5 min)

## Core Features

### Two-Section Pre-Match Prediction
- **Section 1**: Algorithm-Based (11-Factor Model with 50K NB simulations)
- **Section 2**: Claude Opus Deep Narrative (web-scraped data, factors, injuries, toss scenarios, prediction)

### Claude vs Algorithm Comparison Dashboard (/compare)
- Side-by-side comparison across all IPL 2026 matches
- Agreement metrics: Matches Compared, Same Winner, Disagreements, Agreement %

### Live Match System — Claude as Single Source of Truth
- **Primary**: SportMonks API for rich live data (batting, bowling, lineup, scoreboards)
- **Fallback**: CricketData.org API when SportMonks has no data
- **Manual fetch**: "Fetch Live Scores" button only (saves API hits)
- **Claude Live Prediction**: Full context including yet-to-bat/bowl + previous form consideration for realistic win probabilities
- **Unified probabilities**: Claude's team1_win_pct and team2_win_pct are THE probabilities shown everywhere (scoreboard, prediction panel)
- **Refreshable**: Independent "Refresh" button re-runs Claude prediction using cached SportMonks data (no API refetch)
- **No duplication**: Single Claude Opus panel with chase analysis merged in — removed old algorithmic prediction panel

### SportMonks Integration
- Rich live data: full batting card, bowling card, lineup, recent balls, extras
- Yet to Bat / Yet to Bowl lineups displayed in UI
- Claude Opus receives full scorecard + remaining players for depth-aware predictions
- Fields: active_batsmen, active_bowler, batsmen_inn1/2, bowlers_inn1/2, yet_to_bat, yet_to_bowl

### Key API Endpoints
- `POST /api/matches/{id}/fetch-live` — Manual live fetch (SportMonks → Claude prediction → unified probs)
- `POST /api/matches/{id}/refresh-claude-prediction` — Refresh Claude prediction only (cached data, no API refetch)
- `GET /api/predictions/{id}/pre-match` — Cached algo prediction
- `POST /api/matches/{id}/claude-analysis` — Generate fresh Claude analysis
- `POST /api/matches/{id}/chat` — Consultation chat (Claude Opus)

## Completed
- [x] 11-Factor prediction model with 50K NB simulations
- [x] Claude Opus migration (from GPT-5.4)
- [x] Pre-match Claude narrative analysis
- [x] Algorithm vs Claude Comparison Dashboard
- [x] Component modularization (ConsultantWidgets, ChatBox)
- [x] APScheduler background tasks
- [x] SportMonks API integration for live data
- [x] Claude live win prediction with full batting/bowling lineup context
- [x] Yet-to-bat/bowl display in Live Match UI
- [x] Unified Claude probabilities (single source of truth for scoreboard + prediction)
- [x] Refreshable Claude prediction (independent refresh without re-fetching SportMonks)
- [x] Removed duplicate Live Match Prediction panel

## Backlog
- P2: Shareable prediction card
- P2: Celery migration (if APScheduler insufficient)
- P3: Prediction accuracy leaderboard
