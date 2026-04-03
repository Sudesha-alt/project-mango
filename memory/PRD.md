# PPL Board - IPL 2026 Prediction Platform v2

## Problem Statement
Full-stack IPL 2026 live match prediction, odds tracking, and probability modeling with GPT-powered analysis.

## Architecture
- **Frontend**: React SPA + Tailwind + Shadcn + Recharts + Framer Motion
- **Backend**: FastAPI + MongoDB + WebSocket
- **Data Sources**: CricAPI (live), GPT-4.1 (schedule, squads, predictions, live fallback)
- **Algorithms**: Pressure Index, DLS Resource, Bayesian, Monte Carlo, Ensemble

## What's Been Implemented (2026-04-03)
### Backend
- GPT-powered IPL 2026 schedule loader (74 matches in MongoDB)
- GPT-powered team squads loader (all 10 IPL teams)
- On-demand live data fetching (CricAPI first, GPT fallback) via button
- 5 probability algorithms running on live data
- Odds engine calculating from probabilities
- Claude/GPT AI predictions for matches and players
- WebSocket for real-time updates
- MongoDB caching for all data

### Frontend  
- 5 screens: Match Selector, Pre-Match, Live Match, Post-Match, Analysis
- Proper tabs: Live/Upcoming/Completed with match counts
- Completed matches show scores, winners, venues
- "Fetch Live Scores" button for on-demand data
- Full live dashboard: scoreboard, batsmen, bowler, ball log, commentary
- 4 algorithm models + ensemble display
- Algorithm radar chart
- Odds panel, Player predictions panel
- Dark command-center theme
- WebSocket connectivity

## P0 Remaining
- [x] Full IPL 2026 schedule (74 matches)
- [x] Proper Live/Upcoming/Completed categorization
- [x] On-demand live fetching via button
- [x] 4 algorithm models + ensemble on live data

## P1 Next
- Upgrade to CricAPI paid tier for real live data
- Historical player stats database
- Venue-based win probability analysis
- Score prediction accuracy tracking
