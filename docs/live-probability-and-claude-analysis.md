# Live win probability, historical score, phase weighting, and Claude analysis

This document describes how **live match probabilities** are produced in Project Mango, how the **historical structural model (H)** works, how **phase-based weighting** blends algorithmic and Claude outputs, and what each **Claude** path does. It is aligned with the current backend implementation (`probability_engine.py`, `live_predictor.py`, `ai_service.py`, `server.py`).

---

## 1. Overview: three layers you will see in the API

| Layer | Where it lives | Typical field in response | Role |
|--------|----------------|----------------------------|------|
| **A. Four-algorithm ensemble** | `services/probability_engine.py` → `ensemble_probability` | `probabilities.ensemble` (0–1), plus `pressure_index`, `dls_resource`, `bayesian`, `monte_carlo` | Scorecard-only statistical blend (no LLM). |
| **B. Historical structural H** | `services/live_predictor.py` → `compute_live_prediction` | `weightedPrediction` | Uses the **pre-match structural score** (H) only; no alpha decay and no live six-factor blend in this layer. |
| **C. Phase-weighted Claude blend** | `live_predictor.py` → `compute_combined_prediction` | `combinedPrediction` | After refresh, blends **B** with Claude’s **team1 win %**, with weights that depend on **match phase**; optional gut feeling and market odds slots. |

**Fetch live scores** (`POST /matches/{match_id}/fetch-live`) runs **A** and **B** (B without Claude: `claude_prediction=None`). It does **not** call Claude Opus.

**Refresh predictions** (`POST /matches/{match_id}/refresh-claude-prediction`) runs **`claude_sportmonks_prediction`**, then recomputes **B** with Claude’s JSON, then **C**. It also **overwrites** `probabilities.ensemble` with the **stabilized Claude team1 win probability** (see §6).

---

## 2. Layer A — Four-algorithm ensemble (`ensemble_probability`)

**Entry:** `ensemble_probability(runs, wickets, overs, target, innings, odds_team_a, ball_history, venue_avg, total_overs)` in `probability_engine.py`.

### 2.1 Inputs

- **Scorecard:** `runs`, `wickets`, `overs` for the **current innings**, `innings` (1 or 2), `target` (chase target in2nd innings).
- **Optional betting prior:** `odds_team_a` — normalized implied probability for “team A” when the user supplies book odds on the fetch-live request.
- **Optional ball history:** Recent balls converted to structured events (`runs`, `isWicket`, `isWide`, `isNoBall`) for the Bayesian updater.
- **Venue:** `venue_avg` (default **165** in `fetch-live`; the Monte Carlo / pressure pieces scale with this).

### 2.2 Four components

1. **Pressure index (`pressure_index`)**  
   - **1st innings:** Projects run rate to 20 overs vs `venue_avg`, mixes in wickets lost, clamps to a bounded probability.  
   - **2nd innings:** Uses **CRR vs RRR** ratio in a sigmoid, blended with an overs/wickets “resource” style term.

2. **DLS-inspired resource model (`dls_probability`)**  
   Uses a precomputed **resource table** `DLS_TABLE` (overs remaining × wickets in hand).  
   - **1st innings:** “Resources used” vs runs → projected intensity vs a typical total.  
   - **2nd innings:** Compares **runs vs par for resources used** to target to get a win probability.

3. **Bayesian belief (`bayesian_probability`)**  
   - Prior from **betting odds** if provided, else 0.5.  
   - Sequential updates from **ball_history** using fixed likelihoods per event type (boundary, dot, wicket, etc.).  
   - Blended with **pressure_index** (75% posterior / 25% pressure) when pressure is available.

4. **Monte Carlo (`monte_carlo_simulation`, 500 sims)**  
   - **2nd innings:** Simulates remaining balls with a simple categorical outcome model (scaled by `venue_avg`); fraction of sims reaching the target → probability.  
   - **1st innings:** Simulates rest of innings, takes **median** projected score vs `venue_avg` for a probability (also returns projected score in the tuple).

### 2.3 Ensemble blend and output

```text
ensemble = 0.25 × pressure_index
 + 0.30 × dls_resource
         + 0.20 × bayesian
         + 0.25 × monte_carlo
```

- **Clamped:** `ensemble ∈ [0.02, 0.98]`.
- **`confidence_band`:** half the range between max and min of the four components (dispersion of models).

**Interpretation:** All four pieces are defined relative to the **current innings scorecard** (chase logic in the 2nd innings). The API exposes decimal **team1** odds derived from `ensemble` in `fetch-live`; consumers should treat the numeric **batting context** consistently with how `runs`/`target` are defined for that innings.

---

## 3. Layer B — Historical structural score H (`compute_live_prediction`)

**Entry:** `compute_live_prediction(sm_data, claude_prediction, match_info, pre_match_prob, xi_data, enrichment)` in `live_predictor.py`.

### 3.1 Core formula

```text
P(team1) = H
```

- **H** — **Historical / structural** team1-centric score in **[0, 1]** (see §3.2).

Final display: `team1_pct` and `team2_pct` in **[1, 99]** (integer-ish tenths).

### 3.2 H — Historical / structural factors (team1-centric)

```text
H = 0.22 × squad_strength
  + 0.10 × h2h_win_pct
  + 0.28 × venue_win_pct
  + 0.25 × recent_form_pct
  + 0.15 × toss_advantage_pct
```

| Factor | Source |
|--------|--------|
| **squad_strength** | `compute_squad_strength_differential(xi_data)` from expected runs/wickets per XI player (all-rounder bump), or **0.5** if no XI. |
| **h2h, venue, form, toss** | `build_historical_factors_from_enrichment` using SportMonks **H2H**, **venue bat-first win %**, **standings win rates**, and **toss winner** heuristic (team1 gets ~0.58 if they won toss, ~0.42 if team2 won, else 0.5). |
| **Overrides** | If Claude’s JSON includes `historical_factors`, `merge_historical_factors` **overrides** those keys with Claude’s normalized values. |

The model intentionally excludes the live six-factor blend from this layer; live adaptation happens in the Claude layer and the phase-weighted combiner.

---

## 4. Layer C — Phase-weighted blend (`compute_combined_prediction`)

**When:** After **Refresh predictions**, when both `weighted_pred` and `claude_prediction` exist.

**Idea:** The **algorithmic** side supplies `algo_pred["team1_pct"]` (from **§3**). Claude supplies **`claude_pred["team1_win_pct"]`** (after refresh stabilization). They are blended with weights that **favor Claude later in the game**.

### 4.1 Phase detection (`detect_match_phase`)

| Phase key | Condition | Label (human-readable) |
|-----------|-----------|-------------------------|
| `pre_game` | Innings 1, overs ≤ 0.1 | Early1st / post-toss |
| `mid_1st_inn` | Innings 1, overs < 12 | Mid 1st innings |
| `end_1st_inn` | Innings 1, overs ≥ 12 | End 1st innings |
| `mid_2nd_inn` | Innings 2, overs < 12 | Mid 2nd innings |
| `late_game` | Innings 2, overs ≥ 12 | Late game |

### 4.2 Default algo / Claude weights (`PHASE_WEIGHTS`)

| Phase | Algorithm (weightedPrediction) | Claude |
|-------|---------------------------------|--------|
| `pre_game` | **70%** | **30%** |
| `mid_1st_inn` | **40%** | **60%** |
| `end_1st_inn` | **20%** | **80%** |
| `mid_2nd_inn` | **10%** | **90%** |
| `late_game` | **0%** | **100%** |

### 4.3 Optional user inputs (carved from the same100%)

- **Gut feeling** (non-empty string): adds **3%** weight to a small nudge around50% using keyword sentiment (±5 points to the gut channel).  
- **Betting odds** (`current_betting_odds` as team1 implied %): adds **7%** weight to that market number.

If either is present, **algo and Claude weights are scaled by `(1 − gut_weight − odds_weight)`** so the total remains a convex combination.

**Output:** `combinedPrediction` with `team1_pct`, `team2_pct`, `phase`, `phase_label`, `algo_weight`, `claude_weight`, diagnostics, and `model: "phase-weighted-v2"`.

---

## 5. Claude analysis paths (what each call does)

### 5.1 Live win prediction — `claude_sportmonks_prediction` (Opus)

**Used by:** `refresh_claude_prediction` (and the same enrichment pattern as fetch-live, plus impact-sub history when configured).

**Role:** Produces a **large structured JSON** with **11 sections** (match context, squads, form, venue, H2H, matchups, death bowling, data integrity, …) ending in **`section_10_final_prediction`** (committed team1/team2 win **integers** summing to 100) and **`section_11_revision_triggers`**.

**Prompt constraints (high level):**

- **Rule 8 / anchor:** Section 10 should not move more than **~12 points** vs the **pre-game ensemble** (`probabilities.ensemble` from the four-algorithm block) unless the **live scorecard** or **confirmed XI** justifies it.  
- **Rule 9:** **Impact / named substitute history** (when present in enrichment) is **sheet-level** SportMonks data, not proof a sub played.  
- Full scorecard JSON and inning-wise tables are **authoritative** over scraped text.

**Post-processing (server):**

1. Prefer **`section_10_final_prediction.team1_win_pct`** as the committed Claude probability.  
2. Else fall back to short-code keys, `predicted_winner`, or **ensemble + `contextual_adjustment_pct`** (clamped to ±30).  
3. **`stabilize_team1_win_pct`:** EMA-style blend with previous refresh (`ema_alpha=0.42`) and a **flip guard** so small noisy changes don’t flip the favorite unless **|new−50| ≥ 3.25** vs the previous side.  
4. Writes **`claudePrediction`** and sets **`probabilities.ensemble = claude_t1 / 100`** with **`source: "algo+claude"`**.

### 5.2 Live narrative — `claude_live_analysis`

**Used by:** `POST /matches/{match_id}/claude-live`.

**Role:** Shorter **real-time** JSON (momentum, key batsmen/bowlers, phase, betting-style advice, win_probability block). Uses **SportMonks snapshot** as ground truth when present; **opening-partnership** rules to avoid wrong opener inference; can include **impact sub history** in the prompt when fetched.

### 5.3 Pre-match deep analysis — `claude_deep_match_analysis`

**Used by:** `POST /matches/{match_id}/claude-analysis` (requires expected XI + cached **pre-match** 8-factor prediction).

**Role:** **7-layer** structured preview (squad, matchups, venue, bowling, death, H2H, **impact player options**). Injects **impact sub history** when available so Layer 7 can reference **recent named subs** from lineups.

---

## 6. How the pieces connect in one refresh cycle

1. **Cached** `probabilities` still hold the last **ensemble** (either pure four-model from last fetch, or last refresh’s **Claude** value).  
2. **`claude_sportmonks_prediction`** runs with **sm_data**, **squads (XI-filtered)**, **weather**, **news**, **enrichment** (venue, H2H, standings, enriched XI stats, impact sub history, …).  
3. **`compute_live_prediction`** runs with that Claude object so **H** can use Claude `historical_factors` and **L** uses **`team1_win_pct`** as **pre_match_base** where applicable.  
4. **`compute_combined_prediction`** merges **weightedPrediction** with **Claude team1 win %** using **phase weights** (+ optional gut/odds).  
5. **`probabilities.ensemble`** is updated to the **stabilized Claude** team1 probability for downstream consumers that read a single scalar.

---

## 7. Auxiliary: `live_prediction` on fetch-live

**`_compute_live_prediction`** builds a **human-facing summary** (phase, CRR, RRR, chase difficulty, batsmen/bowler tags). Its **`win_probability`** field is **`probabilities.ensemble × 100`** — i.e. it tracks the **same scalar** as the four-model ensemble at fetch time, not the historical-only `H` score or phase-weighted number, unless a refresh has already rewritten `ensemble`.

---

## 8. Bench & manual IPL Impact (pre-match UI)

| Endpoint | Role |
|----------|------|
| `GET /api/matches/{match_id}/playing-xi/bench?team=team1\|team2` | Full franchise bench list (same pool as below). |
| `GET /api/matches/{match_id}/playing-xi/impact-search?team=…&q=…` | Type-ahead over that bench (`q` min 2 chars; substring + fuzzy rank). UI uses this for manual Impact selection. |
| `PUT /api/matches/{match_id}/playing-xi/manual-impact` | Save/clear one bench pick per team; persisted on `playing_xi` (upsert) and mirrored on the prediction doc. |

`GET /api/predictions/upcoming` — **Default** `schedule_upcoming_only=true` (omit or pass explicitly) returns only predictions whose `matchId` is still **active** on **`ipl_schedule`** (upcoming, not started, live, in progress, etc.). Set `schedule_upcoming_only=false` to return every cached pre-match row (e.g. completed-match history).

---

## 9. File reference

| Concern | Primary file(s) |
|---------|------------------|
| Four algorithms + ensemble | `backend/services/probability_engine.py` |
| α, H, L, phase weights, stabilization | `backend/services/live_predictor.py` |
| Claude prompts & JSON shapes | `backend/services/ai_service.py` |
| HTTP orchestration, DB, cache | `backend/server.py` |

---

*Last reviewed against backend layout as of the documentation authoring date; if weights or phase boundaries change in code, update this file in the same commit.*
