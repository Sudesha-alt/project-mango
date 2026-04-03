# PPL Board - IPL 2026 Prediction Platform

## Problem Statement
Build a production-grade full-stack web application for IPL 2026 live match prediction, real-time odds tracking, and continuous probability modeling.

## Architecture
- **Frontend**: React SPA with Tailwind CSS, Shadcn UI, Recharts, Phosphor Icons, Framer Motion
- **Backend**: FastAPI (Python) with MongoDB, WebSocket gateway
- **Data Sources**: CricAPI (primary), Cricbuzz API (fallback), Claude AI (predictions)
- **Algorithms**: Pressure Index, DLS Resource, Bayesian, Monte Carlo, Ensemble

## User Personas
- Cricket enthusiasts wanting live predictions
- Data analysts interested in probability models
- Fantasy cricket players looking for player performance insights

## Core Requirements
- Real-time match data from CricAPI
- 5 probability algorithms running continuously
- WebSocket push updates
- AI-powered predictions via Claude
- Player-level predictions (runs, wickets, economy)
- Dark mode UI with command-center aesthetic

## What's Been Implemented (2026-04-03)
### Backend
- FastAPI server with /api prefix routing
- CricAPI integration with rate-limit handling + 16-min backoff
- Cricbuzz unofficial API fallback
- 5 probability algorithms (Pressure Index, DLS, Bayesian, Monte Carlo, Ensemble)
- Odds engine (calculates from probability)
- Claude AI integration for match/player predictions
- WebSocket gateway for real-time updates
- Background worker for live match updates
- MongoDB caching for match data persistence

### Frontend
- 5 pages: Match Selector, Pre-Match, Live Match, Post-Match, Analysis
- Dark theme with Barlow Condensed / DM Sans / JetBrains Mono fonts
- Live Scoreboard component with animated score updates
- Ball Log visualization
- Algorithm Panel with 5 model displays
- Win Probability Chart (AreaChart)
- Manhattan Chart (BarChart)
- Algorithm Radar Chart
- Odds Engine panel with trend indicators
- Playing XI panel
- Player Predictions with filtering
- WebSocket hook for real-time updates
- API status display with cooldown timer
- Navigation between all screens

## Known Issues
- CricAPI free tier has strict rate limits (100 calls/day, 15-min blocks)
- Cricbuzz unofficial API may return 402 (payment required)
- No ball-by-ball data available in current API tier

## P0 - Critical
- [x] CricAPI integration
- [x] Probability algorithms
- [x] WebSocket real-time updates
- [x] 4 main screens
- [x] Dark mode UI

## P1 - Important
- [ ] Upgrade to CricAPI paid tier for reliable data
- [ ] Historical match data seeding
- [ ] Player stats database
- [ ] Venue-based analysis

## P2 - Nice to Have
- [ ] Push notifications for key events
- [ ] Social sharing of predictions
- [ ] User accounts for prediction tracking
- [ ] Leaderboard for prediction accuracy
