# The Lucky 11 — IPL 2026 Cricket Prediction Platform

## Original Problem Statement
Build a full-stack cricket prediction app for IPL 2026 with an 8-category math model, Claude Opus contextual analysis, live scoring, and advanced prediction weighting.

## Core Architecture
- **Frontend**: React + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor)
- **Integrations**: Claude Opus (Anthropic), SportMonks API, NewsData.io, Open-Meteo Weather

## What's Been Implemented

### Pre-Match Prediction (8-Category Model)
1. Squad Strength & Balance (25%)
2. Current Season Form (21%)
3. Venue + Pitch + Home Advantage (18%)
4. Head-to-Head (11%) — IPL 2023-2025
5. Toss Impact (9%)
6. Bowling Attack Depth (8%)
7. Conditions/Weather (5%)
8. Team Momentum (3%)

### Live Match Prediction — 8-Layer Contextual Analysis
**Claude's Role**: Produces a contextual adjustment (+/- %) across 8 analytical layers. Claude does NOT produce direct win %. The system applies Claude's adjustment on top of the algorithm baseline.

**8 Layers:**
1. Batters at Crease — set vs cold bat, partnership rate, advantage assessment
2. Bowling Resources Remaining — death overs 17-20 bowler rating, quota analysis
3. Batting Depth & Tail Risk — finisher quality, collapse risk
4. Pitch & Conditions (in-game) — actual pitch behavior vs pre-game assumptions
5. High-Leverage Matchups — specific batter vs bowler IPL records
6. Momentum & Pressure Asymmetry — pressure situations, captain tactics
7. Impact Player Status — substitution implications
8. Verdict — bold, decisive, with predicted margin

**Output**: contextual_adjustment_pct (+/-30%), adjustment_confidence, primary/secondary drivers, market_mispricing signal

**Weighting System**:
- Algorithm computes structural baseline
- Claude's contextual adjustment is applied on top
- Phase-based blending: Post-Toss (Algo 70%/Claude 30%) → Late Game (0%/100%)
- User inputs: Gut Feeling (3%), Betting Odds (7%)

### Key Endpoints
- `POST /api/matches/{id}/pre-match-predict`
- `POST /api/matches/{id}/fetch-live` (accepts gut_feeling, current_betting_odds)
- `POST /api/matches/{id}/refresh-claude-prediction`
- `POST /api/schedule/sync-results`

## Completed Tasks (Apr 2026)
- [x] 8-category pre-match model with all factors producing non-zero values
- [x] Venue + Pitch data with secondary home grounds
- [x] H2H 2023-2025 IPL data
- [x] Phase-based dynamic weighting (5 phases)
- [x] Gut Feeling + Betting Odds user inputs
- [x] 8-Layer Claude contextual analysis (replaces direct win %)
- [x] Contextual adjustment system (algo baseline + Claude delta)
- [x] Frontend: 8-layer analysis display with collapsible layers, verdict, adjustment indicator

## Backlog
- [ ] P2: Shareable prediction card
- [ ] P2: Celery migration for background jobs
- [ ] P3: Prediction accuracy leaderboard
- [ ] Refactor: Break server.py into modular routers
