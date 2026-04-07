# The Lucky 11 — IPL 2026 Cricket Prediction Platform

## Original Problem Statement
Build a full-stack cricket prediction app for IPL 2026 with an 8-category math model, Claude Opus narrative predictions, live scoring, and advanced prediction weighting.

## Core Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor)
- **Integrations**: Claude Opus (Anthropic), SportMonks API, NewsData.io, Open-Meteo Weather

## What's Been Implemented

### Pre-Match Prediction (8-Category Model)
1. Squad Strength & Balance (25%) — top 6 bat + top 5 bowl, balance bonus
2. Current Season Form (21%) — from DB completed matches with winners
3. Venue + Pitch + Home Advantage (18%) — pitch_type, avg_first_innings, pace/spin assist, home/away with secondary venues
4. Head-to-Head (11%) — IPL 2023-2025 H2H (all 45 team pairs, includes playoffs)
5. Toss Impact (9%) — venue-specific toss_win_pct with dew, non-zero logit
6. Bowling Attack Depth (8%) — top 5 bowlers with pace/spin variety bonus
7. Conditions/Weather (5%) — Open-Meteo real data
8. Team Momentum (3%) — last 2 match W/L

### Venue Data
- All IPL venues with pitch characteristics: pitch_type, avg_first_innings, batting_first_win_pct, pace_assist, spin_assist
- Secondary home grounds: RR (Jaipur + Guwahati), PBKS (Mohali + Dharamshala)
- Pitch-based advantage: team bowling composition vs venue surface match

### Live Match Prediction
- Phase-Based Dynamic Weighting (5 phases: Algo vs Claude blend)
- Combined Prediction with Gut Feeling (3%) + Betting Odds (7%)
- Claude receives user context for narrative

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict` — 8-category prediction
- `POST /api/matches/{id}/fetch-live` — Live data + Claude + Combined
- `POST /api/matches/{id}/refresh-claude-prediction`
- `POST /api/schedule/sync-results`

## Completed Tasks (Apr 2026)
- [x] 8-category prediction model (no scraping)
- [x] NewsData.io, Open-Meteo, SportMonks integrations
- [x] Phase-based dynamic weighting (5 phases)
- [x] Gut Feeling (3%) + Betting Odds (7%) inputs
- [x] H2H with 2023-2025 IPL data (all 45 pairs)
- [x] Toss Impact non-zero logit
- [x] Bowling Depth top 5 bowlers
- [x] Balance bonus in squad strength
- [x] Venue + Pitch data (type, avg score, pace/spin assist)
- [x] Secondary home grounds (RR at Guwahati, PBKS at Dharamshala)
- [x] Pitch-based advantage (team bowling vs surface match)

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] Refactor: Break server.py into modular routers
