# Baatu - 11 — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant combining 50K Negative Binomial simulations, 11-factor prediction algorithms, Claude Opus deep narrative analysis, CricketData.org live API, and background auto-scraping.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), Claude Opus 4.5 (Anthropic), APScheduler
- **Data Sources**: CricketData.org API (primary, 100/day), DuckDuckGo web scraping (fallback)
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
- **Primary**: CricketData.org API for live scores
- **Fallback**: Claude web scraping when CricAPI has no data
- **Manual fetch**: "Fetch Live Scores" button (saves API hits)
- **Auto-scrape**: Background job every 5 minutes for score updates
- **Claude Live Analysis**: Real-time expert analysis tab

### Component Architecture (Split in v5.0)
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
- Full live context: batsmen, bowler, probabilities, projected score, chase analysis

## Key API Endpoints
- `GET /api/` — Health check (Claude Opus + Web Scraping, scheduler status)
- `GET /api/predictions/{id}/pre-match` — Cached algo prediction
- `GET /api/matches/{id}/claude-analysis` — Cached Claude analysis
- `POST /api/matches/{id}/claude-analysis` — Generate fresh Claude analysis
- `POST /api/matches/{id}/claude-live` — Real-time Claude live analysis
- `POST /api/matches/{id}/fetch-live` — Manual live score fetch (CricAPI → Claude fallback)
- `POST /api/matches/{id}/chat` — Consultation chat (Claude Opus)
- `POST /api/scheduler/promote-now` — Manual match promotion

## Backlog
- P3: Shareable prediction card
- P3: Prediction accuracy leaderboard
