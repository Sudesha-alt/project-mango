# Gamble Consultant — Product Requirements Document

## Overview
AI-powered IPL 2026 betting consultant that combines 50K Negative Binomial match simulations, 5-factor prediction algorithms, GPT-5.4 web search, and CricketData.org live data to deliver clear betting verdicts with edge analysis.

## Architecture
- **Frontend**: React (Vite), Shadcn/UI, Phosphor Icons, Recharts
- **Backend**: FastAPI, MongoDB, Scipy (NB/Poisson), OpenAI GPT-5.4
- **Data**: CricketData.org API (100/day), GPT web scraping for Playing XI and venue data

## Core Features (All Implemented)

### Match Management
- 70-match IPL 2026 schedule (AI-parsed from GPT web search)
- Upcoming/Live/Completed tabs with prediction cards
- Venue resolution for all 70 matches (no TBD)

### Playing XI + Performance System (v5.2)
- GPT-5.4 web search scrapes expected/confirmed lineups from Cricbuzz, ESPNcricinfo, Twitter/X, fantasy sites
- Injury news, fitness concerns, controversies, dropped players detected and excluded
- **Buzz Score (-100 to +100)**: Positive/negative sentiment from news + social media
  - +70 to +100: Star form, MOTM, experts' top pick
  - +30 to +69: Good form, positive sentiment
  - -10 to +29: Neutral/mixed
  - -50 to -10: Poor form, niggle concerns
  - -100 to -50: Injury doubt, controversy, terrible streak
- **buzz_reason**: 1-sentence explanation (e.g., "Scored century last match" or "Recovering from hamstring injury")
- **Performance Formula**: `expected = base_stats * (1 + buzz_modifier) * luck_factor`
  - base_stats: 60% venue-specific + 40% season form (from web search)
  - buzz_modifier: buzz_score/500 (maps -100→-20%, +100→+20%)
  - luck_factor: random ±15% variance
- Clickable buzz badges with color-coded sentiment and expandable reasons

### 5-Factor Prediction Algorithm
- Head-to-Head 5yr (25%), Venue Performance (20%), Recent Form (25%), Squad Strength (20%), Home Advantage (10%)
- Logit-based model → sigmoid calibration for final probability
- Player-level data integration (venue-specific batting/bowling stats)
- Odds direction tracking (increasing/decreasing arrows)
- Two-sided Green/Red Factor Breakdown (Team 1 left vs Team 2 right)

### 50K Negative Binomial Simulation Engine
- 50,000 match simulations per consultation using Negative Binomial distribution
- Predicted scores (mean, median, P10-P90 ranges) for both teams
- Batting-first win percentage
- Chase pressure adjustment for 2nd innings

### Consultation & Verdict System
- Market odds input (0-100 scale)
- Risk tolerance levels: Play Safe / Balanced / Risk Taker
- Market momentum (odds rising/falling)
- Bold verdict: DOMINANT/STRONG/SLIGHT/TOSS-UP
- Value signals: STRONG_VALUE / VALUE / SMALL_EDGE / NO_BET / AVOID
- Edge explanation pointers ("WHY THIS SIGNAL?" with reasoning bullets)
- AI-generated betting scenarios
- Match State hidden for upcoming matches

### User Guide (In-App)
- Floating ? button → 10-section FAQ modal
- Covers all features including decimal odds conversion, buzz scores, and performance formulas

### Live Match Features
- CricketData.org real-time fetching (100/day)
- Match State display (CRR, RRR, Pressure, Depth, Collapse Risk)

### Background Operations
- Batch re-prediction for all upcoming matches
- Progress tracking with polling

## Key Bug Fixes
- **v5.1**: scipy `nbinom.rvs` parameterization fix (1-p_param → p_param)
- **v5.2**: Buzz sentiment from 0-100 → -100 to +100 with reasons; Performance = base * buzz * luck

## Completed Milestones
- v1.0: Basic match fetching and GPT prediction
- v2.0: 5-factor algorithm, H2H, venue stats
- v3.0: Playing XI scraping, squad management, venue resolution
- v4.0: 10K→50K simulations, market momentum, batch re-prediction
- v5.0: Bold verdict UI, visual odds, consultant dashboard rewrite
- v5.1: Simulation bug fix, two-sided factor breakdown, edge reasons, user guide
- v5.2: Buzz sentiment (-100 to +100), performance formula (buzz + luck + base stats)

## Backlog
- P2: Split ConsultantDashboard.js into sub-components
- P2: Background workers (Celery) for continuous auto-scraping
- P2: Shareable prediction card functionality
- P3: Prediction accuracy leaderboard
