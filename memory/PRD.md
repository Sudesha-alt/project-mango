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

### Dual Live Prediction Models (NEW - v6)
Two side-by-side prediction models during live matches:

**Model 1 — Weighted Probability Prediction (Formula-based)**
- P(win) = alpha x H + (1 - alpha) x L
- Alpha = balls_remaining / total_match_balls (dynamic weight)
- H (Historical) = 0.40 x H2H + 0.25 x Venue + 0.20 x Recent_Form + 0.15 x Toss_Advantage
- L (Live) = 0.40 x Run_Rate_Ratio + 0.35 x Wickets_in_Hand + 0.25 x Phase_Momentum
- Historical factors fetched from Claude (H2H win%, venue win%, recent form, toss advantage)
- Info (i) button shows full methodology breakdown

**Model 2 — Claude Opus Prediction (AI-based)**
- Full scorecard + remaining batting/bowling lineups passed to Claude
- Considers player form, career stats, finishing ability, death overs record
- Returns headline, reasoning, batting depth assessment, bowling assessment, key matchup
- Momentum and confidence indicators

Both models refreshable via single "Refresh Both" button.

### Live Match System
- **Primary**: SportMonks API for rich live data
- **Manual fetch**: "Fetch Live Scores" button only
- **Claude probabilities**: Single source of truth for scoreboard
- **Yet to Bat/Bowl**: Full lineups displayed
- **Refreshable**: Independent refresh without re-fetching SportMonks data

### Pre-Match System
- **Algorithm-Based**: 11-Factor Model with 50K NB simulations
- **Claude Opus Deep Narrative**: web-scraped analysis with factors, injuries, toss scenarios

### Compare Dashboard (/compare)
- Algorithm vs Claude side-by-side across all matches
- Agreement metrics and color-coded levels

### Key API Endpoints
- `POST /api/matches/{id}/fetch-live` — Manual live fetch (SportMonks + Claude + Weighted)
- `POST /api/matches/{id}/refresh-claude-prediction` — Refresh both predictions (cached data)
- `GET /api/predictions/{id}/pre-match` — Cached algo prediction
- `POST /api/matches/{id}/claude-analysis` — Fresh Claude analysis
- `POST /api/matches/{id}/chat` — Consultation chat

## Completed
- [x] 11-Factor prediction model with 50K NB simulations
- [x] Claude Opus migration (from GPT-5.4)
- [x] Pre-match Claude narrative analysis
- [x] Algorithm vs Claude Comparison Dashboard
- [x] Component modularization (ConsultantWidgets, ChatBox)
- [x] APScheduler background tasks
- [x] SportMonks API integration for live data
- [x] Claude live win prediction with full lineup context
- [x] Unified Claude probabilities (scoreboard + panels)
- [x] Weighted Probability Prediction (formula-based model)
- [x] Dual prediction models UI (side-by-side display)
- [x] Formula methodology info (i) button
- [x] Shared refresh button for both models

## Backlog
- P2: Shareable prediction card
- P2: Celery migration (if APScheduler insufficient)
- P3: Prediction accuracy leaderboard
