# Baatu - 11 — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant combining 50K Negative Binomial simulations, 11-factor prediction algorithms, Claude Opus deep narrative analysis, web scraping, and CricketData.org live data.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), Claude Opus 4.5 (Anthropic), APScheduler
- **Data Sources**: DuckDuckGo web scraping (real-time), CricketData.org API (100/day)
- **AI Engine**: Claude Opus 4.5 via emergentintegrations LlmChat

## Core Features (All Implemented)

### Two-Section Pre-Match Prediction

#### Section 1: Algorithm-Based (11-Factor Model)
| # | Factor | Weight |
|---|--------|--------|
| 1 | Head-to-Head (5yr) | 12% |
| 2 | Venue Performance | 10% |
| 3 | Recent Form | 12% |
| 4 | Squad Strength | 10% |
| 5 | Home Advantage | 6% |
| 6 | Toss Impact | 8% |
| 7 | Pitch & Conditions | 10% |
| 8 | Key Matchups | 10% |
| 9 | Death Overs (16-20) | 8% |
| 10 | Powerplay (1-6) | 8% |
| 11 | Momentum | 6% |

#### Section 2: Claude Opus Deep Narrative Analysis (NEW v5.0)
- Web scrapes real-time data (H2H, form, injuries, conditions, player stats) via DuckDuckGo
- Claude Opus generates rich pundit-style narrative with:
  - Win probability (e.g., MI 47% vs DC 53%)
  - Key headline factor
  - 6-10 analysis factors with team tags (favors T1/T2/NEUTRAL)
  - Injury & availability updates
  - Toss scenarios (bat-first / bowl-first probabilities)
  - Deciding logic paragraph
  - Bold prediction summary with confidence level
- Cached in DB for instant retrieval, refresh button for re-scrape

### Claude Opus Live Match Analysis (NEW v5.0)
- Real-time analysis during live matches
- Combines scraped live data + algorithm outputs
- Shows: state summary, momentum, batsman/bowler assessments (threat levels), phase analysis, projected outcome, betting advice, win probability, confidence

### Match Scheduler (v4.1)
- APScheduler at 4PM & 7PM IST daily promotes today's matches to "live" status
- Manual trigger: `POST /api/scheduler/promote-now`
- Syncs live snapshot scores to schedule on startup

### Manual Live Fetch (v4.1)
- On-demand "Fetch Live Scores" button (saves API hits)
- After fetch: runs 4 probability algorithms + live prediction
- Score saved to schedule for match card display

### Enriched Chat Context (v4.1 → v5.0)
- Now powered by Claude Opus (was GPT-5.4)
- Full live context: batsmen, bowler, probabilities, projected score, chase analysis, phase
- Claude answers referencing specific player performances and algorithm outputs

### ConsultantDashboard (v4.2)
- Single-column stacked layout (fixed overflow)
- Verdict → Win Gauge + Edge → Simulations → Drivers → Scenarios → Chat

### Playing XI + Buzz Scores
- Web search for expected lineups, buzz sentiment (-100 to +100)
- Background fetch with polling

### 50K Negative Binomial Simulation Engine
- Predicted scores, batting-first win %, chase pressure

## Tech Stack Change Log
- v5.0: GPT-5.4 → Claude Opus 4.5 (all AI calls)
- v5.0: Added DuckDuckGo web scraping (web_scraper.py)
- v5.0: New components: ClaudeAnalysis.js, ClaudeLiveAnalysis.js
- v4.1: Added APScheduler, manual live fetch, enriched chat
- v4.2: Fixed ConsultantDashboard layout overflow

## Key API Endpoints
- `GET /api/` - Health check (shows Claude Opus + Web Scraping)
- `POST /api/matches/{id}/claude-analysis` - Deep narrative prediction (cached)
- `DELETE /api/matches/{id}/claude-analysis` - Clear cached analysis
- `POST /api/matches/{id}/claude-live` - Real-time live analysis
- `POST /api/matches/{id}/chat` - Consultation chat (Claude Opus)
- `POST /api/matches/{id}/fetch-live` - Manual live score fetch
- `POST /api/scheduler/promote-now` - Manual match promotion

## Backlog
- P2: Split ConsultantDashboard.js into sub-components
- P2: Background Celery workers for auto-scraping
- P2: Shareable prediction card
- P3: Prediction accuracy leaderboard
