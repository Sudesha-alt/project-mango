# Gamble Consultant — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant combining 50K Negative Binomial simulations, 5-factor prediction algorithms, GPT-5.4 web search, and CricketData.org live data.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), OpenAI GPT-5.4
- **Data**: CricketData.org API (100/day), GPT web scraping

## Core Features (All Implemented)

### Playing XI + Performance System (v5.3)
- GPT-5.4 web search scrapes expected/confirmed lineups from news, social media, fantasy sites
- **Injury/controversy/drop detection**: Unavailable players auto-excluded and replaced
- **Buzz Score (-100 to +100)**: Sentiment from news + social media
  - +70 to +100: Star form, MOTM, experts' top pick
  - +30 to +69: Good form, positive sentiment
  - -10 to +29: Neutral/mixed
  - -50 to -10: Poor form, niggle concerns
  - -100 to -50: Injury doubt, controversy, terrible streak
- **buzz_reason**: 1-sentence explanation with real facts
- **Performance Formula**: `expected = base_stats * (1 + buzz_modifier) * luck_factor`
  - base_stats: 60% venue-specific + 40% season form
  - buzz_modifier: buzz_score/500 (maps -100→-20%, +100→+20%)
  - luck_factor: random ±15%
- **Background fetch with polling**: POST starts async task, GET /status polls until done (no more proxy timeouts)

### 5-Factor Prediction Algorithm
- H2H 5yr (25%), Venue (20%), Form (25%), Squad (20%), Home (10%)
- **Form factor damping**: Small sample sizes regressed toward 50%
  - Formula: `damping = min(1.0, min_games/5.0)`, then `form_adj = 0.5 + (form_pct - 0.5) * damping`
  - 1 game = 20% weight, 5+ games = 100% weight
- Two-sided Green/Red Factor Breakdown (Team 1 vs Team 2)
- Player-level data integration with venue stats

### 50K Negative Binomial Simulation Engine
- Predicted scores (mean, median, P10-P90) for both teams
- Batting-first win percentage, chase pressure adjustment
- scipy `nbinom.rvs` parameterization fix (v5.1)

### Consultation & Verdict System
- Bold verdict: DOMINANT/STRONG/SLIGHT/TOSS-UP
- Value signals: STRONG_VALUE / VALUE / SMALL_EDGE / NO_BET / AVOID
- Edge explanation pointers ("WHY THIS SIGNAL?" with reasoning)
- AI betting scenarios
- Match State hidden for upcoming matches

### User Guide (In-App)
- 10-section FAQ modal covering all features

## Key Bug Fixes
- **v5.1**: scipy nbinom parameterization (1-p → p)
- **v5.2**: Buzz sentiment -100 to +100 with reasons
- **v5.3**: Form factor damping for small samples, Playing XI background fetch (no proxy timeout)

## Completed Milestones
- v1.0-v4.0: Core platform, algorithm, simulations
- v5.0: Bold verdict UI rewrite
- v5.1: Simulation fix, two-sided factor breakdown, edge reasons, user guide
- v5.2: Buzz sentiment (-100 to +100), performance formula
- v5.3: Form damping, background Playing XI fetch, 23 predictions recalibrated

## Backlog
- P2: Split ConsultantDashboard.js into sub-components
- P2: Background Celery workers for auto-scraping
- P2: Shareable prediction card
- P3: Prediction accuracy leaderboard
