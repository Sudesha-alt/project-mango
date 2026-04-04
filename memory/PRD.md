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
- Playing XI scraping with venue-specific player stats + social buzz confidence

### 5-Factor Prediction Algorithm
- Head-to-Head 5yr (25%), Venue Performance (20%), Recent Form (25%), Squad Strength (20%), Home Advantage (10%)
- Logit-based model → sigmoid calibration for final probability
- Player-level data integration (venue-specific batting/bowling stats)
- Odds direction tracking (increasing/decreasing arrows)

### 50K Negative Binomial Simulation Engine
- 50,000 match simulations per consultation using Negative Binomial distribution
- Predicted scores (mean, median, P10-P90 ranges) for both teams
- Batting-first win percentage
- Chase pressure adjustment for 2nd innings
- Realistic score distributions (right-skewed like actual cricket)

### Consultation & Verdict System
- Market odds input (0-100 scale) with decimal odds conversion guide
- Risk tolerance levels: Play Safe / Balanced / Risk Taker
- Market momentum (odds rising/falling) manual toggle
- Bold verdict: DOMINANT/STRONG/SLIGHT/TOSS-UP
- Value signals: STRONG_VALUE / VALUE / SMALL_EDGE / NO_BET / AVOID
- Edge explanation pointers ("WHY THIS SIGNAL?" with 3 reasoning bullets)
- AI-generated betting scenarios (PRE_MATCH, IN_PLAY, PLAYER_OUTBURST, etc.)

### Two-Sided Factor Breakdown (v5.1)
- Each factor displayed as Team 1 (left) vs Team 2 (right) bar
- Green bars = advantage, Red bars = disadvantage
- Rounded stats (no long decimals)
- Team-specific detail text under each factor

### User Guide (In-App)
- Floating ? button (bottom-left) opens full guide modal
- 10 sections: Getting Started, Match Selector, Algorithm Prediction, Consultation Engine, Understanding the Verdict, 50K Simulations, Betting Scenarios, Playing XI & Players, Consultant Chat, Live Matches
- Expandable sections and Q&A items
- Covers decimal odds conversion, signal explanations, P10-P90 interpretation

### Live Match Features
- CricketData.org real-time fetching (100/day API limit)
- Match State display (CRR, RRR, Pressure Index, Batting Depth, Collapse Risk)
- Match State hidden for upcoming matches (overs=0, score=0)
- GPT-powered live analysis

### Background Operations
- Batch re-prediction for all upcoming matches
- Progress tracking with polling
- News-based player availability filtering
- Luck biasness (±15%) for match-day variance

## Key Bug Fixes (v5.1)
- **50K Simulation Fix**: scipy `nbinom.rvs` was called with `1-p_param` instead of `p_param`, causing mean scores of ~1030 instead of ~165, clamped to 300, making every simulation 100%/0%. Fixed to use correct parameter.
- **Edge Recommendation Text**: Improved signal reasoning with explicit pointers explaining WHY the signal was given
- **Player Impact Restriction**: Now pulls only from cached Expected Playing XI, not random squad

## Completed Milestones
- v1.0: Basic match fetching and GPT prediction
- v2.0: 5-factor algorithm, H2H, venue stats
- v3.0: Playing XI scraping, squad management, venue resolution
- v4.0: 10K→50K simulations, market momentum, batch re-prediction
- v5.0: Bold verdict UI, visual odds, consultant dashboard rewrite
- v5.1: Simulation bug fix, two-sided factor breakdown, edge reasons, user guide

## Backlog
- P2: Split ConsultantDashboard.js into sub-components (OddsComparison, SimulationSummary, DriversPanel)
- P2: Background workers (Celery) for continuous auto-scraping
- P2: Shareable prediction card functionality
- P3: Prediction accuracy leaderboard
