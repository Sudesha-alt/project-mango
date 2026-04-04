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
- Color-coded agreement levels (HIGH/MODERATE/LOW)

### Live Match System
- **Primary**: SportMonks API for rich live data (batting, bowling, lineup, scoreboards)
- **Fallback**: CricketData.org API when SportMonks has no data
- **Manual fetch**: "Fetch Live Scores" button only (saves API hits)
- **Claude Live Prediction**: Full context including yet-to-bat/bowl passed to Claude Opus for real-time win prediction with batting depth and bowling assessment
- **Auto-scrape**: Background job every 5 minutes for score updates via CricAPI

### SportMonks Integration (NEW - v5.1)
- Rich live data: full batting card, bowling card, lineup, recent balls, extras
- Yet to Bat / Yet to Bowl lineups displayed in UI
- Claude Opus receives full scorecard + remaining players for depth-aware predictions
- Data fields: active_batsmen, active_bowler, batsmen_inn1/2, bowlers_inn1/2, yet_to_bat, yet_to_bowl

### Component Architecture
- `ConsultantWidgets.js` — WinGauge, SignalBadge, EdgeMeter, EdgeReasons, DriversPanel, PlayerImpact, UncertaintyBand, SimulationSummary
- `ChatBox.js` — Standalone chat component
- `ConsultantDashboard.js` — Orchestrator importing sub-components
- `ClaudeAnalysis.js` — Rich narrative display
- `ClaudeLiveAnalysis.js` — Live match analysis display
- `ComparisonDashboard.js` — Algorithm vs Claude comparison page

### Match Scheduler
- APScheduler at 4PM & 7PM IST: promote today's matches to "live"
- Auto-scrape every 5 minutes: update live match scores from CricAPI
- Manual trigger: `POST /api/scheduler/promote-now`

### Enriched Chat Context
- Claude Opus powered (was GPT-5.4)
- Full live context: batsmen, bowler, yet-to-bat/bowl, probabilities, projected score, chase analysis, Claude prediction

## Key API Endpoints
- `GET /api/` — Health check (Claude Opus + Web Scraping, scheduler status)
- `GET /api/predictions/{id}/pre-match` — Cached algo prediction
- `GET /api/matches/{id}/claude-analysis` — Cached Claude analysis
- `POST /api/matches/{id}/claude-analysis` — Generate fresh Claude analysis
- `POST /api/matches/{id}/claude-live` — Real-time Claude live analysis
- `POST /api/matches/{id}/fetch-live` — Manual live score fetch (SportMonks primary, CricAPI fallback, Claude prediction)
- `POST /api/matches/{id}/chat` — Consultation chat (Claude Opus)
- `POST /api/scheduler/promote-now` — Manual match promotion

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
- [x] RRR calculation fix in LiveScoreboard

## Backlog
- P2: Shareable prediction card
- P2: Celery migration (if APScheduler insufficient)
- P3: Prediction accuracy leaderboard
