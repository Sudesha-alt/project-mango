# PPL Board v3 - IPL 2026 Prediction Platform

## Problem Statement
Full-stack IPL 2026 live match prediction with exact algorithm implementations, betting odds integration, and GPT-powered analysis.

## Architecture
- **Frontend**: React + Tailwind + Recharts + Framer Motion + Shadcn
- **Backend**: FastAPI + MongoDB + WebSocket
- **Data**: CricAPI (live), GPT-4.1 (schedule, squads, predictions, live fallback)
- **Algorithms**: Sigmoid/RRR, DLS Resource Table, Bayesian Ball-by-Ball, Monte Carlo 500 sims, Weighted Ensemble

## Implemented (2026-04-03)
### Backend
- Exact Sigmoid/RRR Pressure Index (1st & 2nd innings formulas)
- DLS Resource Table (21x11 lookup: Z[o][w] = 100*(1-exp(-L*o)), L=0.04+0.015*(w/10))
- Bayesian: ball-by-ball with event likelihoods (boundary=0.72, dot=0.35, wicket=0.18, etc.)
- Monte Carlo: 500 sims with venue-calibrated probabilities + wicket penalty
- Ensemble: 25/30/20/25 weighted + confidence band
- Betting odds input → Bayesian prior + edge calculation (Market vs Model)
- IPL 2026 schedule (74 matches, RCB vs SRH opener, 25 completed, 49 upcoming)
- On-demand live data via CricAPI/GPT + WebSocket

### Frontend
- 5 screens: Match Selector, Pre-Match, Live Match, Post-Match, Analysis
- Multi-line Win Probability chart (5 algo lines: blue/red/purple/amber/white + legend)
- Algorithm Comparison (horizontal bars + confidence band)
- Colored Manhattan chart (gray/amber/green by RPO, red border for wickets)
- Pre-Match Radar (team comparison: Form, H2H, Venue, Batting, Bowling, NRR)
- Betting Odds Input: decimal odds + confidence slider + edge display
- Live scoreboard, ball log, batsman/bowler stats, GPT commentary

## Test Results: 100% backend, 98% frontend (minor console warnings only)
