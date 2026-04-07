# The Lucky 11 — IPL 2026 Cricket Prediction Platform

## Original Problem Statement
Build a full-stack cricket prediction app for IPL 2026 with an 8-category math model, Claude Opus narrative predictions, live scoring, and advanced prediction weighting.

## Core Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor)
- **Integrations**: Claude Opus (Anthropic), SportMonks API, NewsData.io, Open-Meteo Weather

## What's Been Implemented

### Pre-Match Prediction (8-Category Model)
1. Squad Strength & Balance (25%) — top 6 batsmen + top 5 bowlers, balance bonus
2. Current Season Form (21%) — from DB completed matches with winners
3. Venue + Pitch + Home Advantage (18%)
4. Head-to-Head (11%) — Historical IPL H2H fallback (2008-2025 aggregate for all 10 teams)
5. Toss Impact (9%) — venue-specific toss_win_pct with dew, non-zero logit
6. Bowling Attack Depth (8%) — top 5 bowlers with pace/spin variety bonus
7. Conditions/Weather (5%) — Open-Meteo real data
8. Team Momentum (3%) — last 2 match W/L (skips matches without winner)

### Live Match Prediction
- **Alpha-Blended H×L Model**: P(win) = alpha × H + (1-alpha) × L
- **Phase-Based Dynamic Weighting** (Algo vs Claude):
  - Post-Toss: Algo 70% / Claude 30%
  - Mid 1st Innings: 40% / 60%
  - End 1st Innings: 20% / 80%
  - Mid 2nd Innings: 10% / 90%
  - Late game: 0% / 100%
- **Combined Prediction**: Blends Algorithm and Claude based on phase
- **User Inputs**: Gut Feeling (3% weight) + Current Betting Odds (7% weight)
- Claude receives gut feeling text + betting odds for context

### Data Sources
- Squad data from `ipl_squads` DB collection (NO scraping)
- SportMonks API for live scores, lineups, results
- Open-Meteo for weather conditions
- NewsData.io for match context/news
- `/schedule/sync-results` endpoint syncs real match winners from SportMonks

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/fetch-live` — Live data + Claude + Combined prediction
- `POST /api/matches/{id}/refresh-claude-prediction` — Re-run Claude with cached data
- `POST /api/schedule/sync-results` — Sync match winners from SportMonks

## Completed Tasks (Apr 2026)
- [x] 8-category prediction model (no scraping)
- [x] NewsData.io integration for match context
- [x] Open-Meteo weather integration
- [x] Fixed auto-scrape bug for future dates
- [x] Renamed to "The Lucky 11"
- [x] SportMonks results sync — populates winner data for completed matches
- [x] H2H, Form, Momentum now return real values (not zeros)
- [x] Phase-based dynamic weighting (5 phases: Algo vs Claude)
- [x] Gut Feeling (3%) + Betting Odds (7%) user inputs on LiveMatch
- [x] Combined Prediction card with phase indicator
- [x] Fixed H2H: Historical IPL fallback data for all 10 team pairs
- [x] Fixed Toss Impact: Now returns non-zero logit from venue toss_win_pct
- [x] Fixed Bowling Depth: Top 5 bowlers only (not full 25-man squad)
- [x] Fixed Balance: Enhanced balance bonus in squad strength calculation

## Backlog
- [ ] P2: Shareable prediction card functionality
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] Refactor: Break server.py into modular routers
