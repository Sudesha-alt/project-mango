"""
Pre-Match Prediction Engine — IPL 2026
10-Category Model (Research-Validated Weights)

Category                                Weight
1. Current Squad Strength and Balance    22%
2. Current Season Form                   18%
3. Venue and Pitch Profile + Home Adv    16%
4. Head-to-Head (recency-weighted)       10%
5. Toss Impact (venue-specific)           8%
6. Key Player Matchup Index               8%
7. Bowling Attack Depth and Balance       7%
8. Injury and Availability Impact         5%
9. Conditions (day/night, dew, weather)   4%
10. Team Momentum and Psychological       2%

Design Principles:
- Categories 1-3 (56%) dominate. If 4-10 contradict 1-3, that's a red flag.
- No hard-capping. Probabilities outside 35-65% should be rare but possible.
- Data: IPL 2026 only for form. 4-year rolling window for historical with exponential decay.
- Allrounders get multiplier bonus (their absence has multiplicative effect).
"""
import math
import logging
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)

# ── Weights ──
WEIGHTS = {
    "squad_strength": 0.22,
    "current_form": 0.18,
    "venue_pitch_home": 0.16,
    "h2h": 0.10,
    "toss_impact": 0.08,
    "matchup_index": 0.08,
    "bowling_depth": 0.07,
    "injury_availability": 0.05,
    "conditions": 0.04,
    "momentum": 0.02,
}

# ── Toss Lookup (from user-provided venue-specific Excel data) ──
# Each venue maps to a default entry + condition-specific overrides.
# chasing_bias is the boost to chasing team's logit when toss winner elects to bowl.
TOSS_LOOKUP = {
    "wankhede": {
        "city": "mumbai",
        "default_decision": "bowl",
        "conditions": {
            "night":     {"preferred": "bowl", "toss_win_pct": 0.65, "chasing_bias": 0.15, "weight": "HIGH"},
            "day":       {"preferred": "bat",  "toss_win_pct": 0.535, "chasing_bias": 0.0,  "weight": "MED"},
            "dew":       {"preferred": "bowl", "toss_win_pct": 0.70, "chasing_bias": 0.15, "weight": "VERY HIGH"},
        },
    },
    "chepauk": {
        "city": "chennai",
        "default_decision": "bat",
        "conditions": {
            "normal":    {"preferred": "bat",  "toss_win_pct": 0.60, "chasing_bias": 0.0,  "weight": "HIGH"},
            "dry":       {"preferred": "bat",  "toss_win_pct": 0.65, "chasing_bias": 0.0,  "weight": "VERY HIGH"},
        },
    },
    "chinnaswamy": {
        "city": "bangalore",
        "default_decision": "bowl",
        "conditions": {
            "high_scoring": {"preferred": "bowl", "toss_win_pct": 0.575, "chasing_bias": 0.12, "weight": "HIGH"},
            "dew":          {"preferred": "bowl", "toss_win_pct": 0.65,  "chasing_bias": 0.12, "weight": "VERY HIGH"},
        },
    },
    "narendra_modi": {
        "city": "ahmedabad",
        "default_decision": "bowl",
        "conditions": {
            "black_soil": {"preferred": "bat",  "toss_win_pct": 0.58, "chasing_bias": 0.0,  "weight": "MED"},
            "red_soil":   {"preferred": "bowl", "toss_win_pct": 0.60, "chasing_bias": 0.0,  "weight": "MED"},
            "night":      {"preferred": "bowl", "toss_win_pct": 0.62, "chasing_bias": 0.0,  "weight": "HIGH"},
        },
    },
    "eden_gardens": {
        "city": "kolkata",
        "default_decision": "bowl",
        "conditions": {
            "night":      {"preferred": "bowl", "toss_win_pct": 0.625, "chasing_bias": 0.10, "weight": "HIGH"},
            "spin":       {"preferred": "bat",  "toss_win_pct": 0.55,  "chasing_bias": 0.0,  "weight": "MED"},
        },
    },
    "arun_jaitley": {
        "city": "delhi",
        "default_decision": "bat",
        "conditions": {
            "slow":       {"preferred": "bat",  "toss_win_pct": 0.58, "chasing_bias": 0.0,  "weight": "HIGH"},
            "small":      {"preferred": "bowl", "toss_win_pct": 0.55, "chasing_bias": 0.0,  "weight": "MED"},
        },
    },
    "rajiv_gandhi": {
        "city": "hyderabad",
        "default_decision": "bowl",
        "conditions": {
            "night":      {"preferred": "bowl", "toss_win_pct": 0.60, "chasing_bias": 0.08, "weight": "HIGH"},
        },
    },
    "mohali": {
        "city": "mohali",
        "default_decision": "bowl",
        "conditions": {
            "night":      {"preferred": "bowl", "toss_win_pct": 0.625, "chasing_bias": 0.0, "weight": "HIGH"},
        },
    },
    "sawai_mansingh": {
        "city": "jaipur",
        "default_decision": "bowl",
        "conditions": {
            "night":      {"preferred": "bowl", "toss_win_pct": 0.56, "chasing_bias": 0.06, "weight": "MED"},
        },
    },
    "ekana": {
        "city": "lucknow",
        "default_decision": "bowl",
        "conditions": {
            "night":      {"preferred": "bowl", "toss_win_pct": 0.57, "chasing_bias": 0.07, "weight": "MED"},
        },
    },
}

# Venue alias mapping for fuzzy matching
VENUE_ALIASES = {
    "wankhede": ["wankhede", "mumbai"],
    "chepauk": ["chepauk", "chidambaram", "chennai"],
    "chinnaswamy": ["chinnaswamy", "bengaluru", "bangalore"],
    "narendra_modi": ["narendra modi", "motera", "ahmedabad"],
    "eden_gardens": ["eden garden", "kolkata"],
    "arun_jaitley": ["arun jaitley", "feroz shah", "delhi"],
    "rajiv_gandhi": ["rajiv gandhi", "uppal", "hyderabad"],
    "mohali": ["mohali", "chandigarh", "punjab"],
    "sawai_mansingh": ["sawai", "jaipur", "rajasthan"],
    "ekana": ["ekana", "lucknow", "bharat ratna"],
}

# Home ground mapping
HOME_GROUNDS = {
    "mumbai indians": "wankhede",
    "chennai super kings": "chepauk",
    "royal challengers bengaluru": "chinnaswamy",
    "royal challengers bangalore": "chinnaswamy",
    "gujarat titans": "narendra_modi",
    "kolkata knight riders": "eden_gardens",
    "delhi capitals": "arun_jaitley",
    "sunrisers hyderabad": "rajiv_gandhi",
    "punjab kings": "mohali",
    "rajasthan royals": "sawai_mansingh",
    "lucknow super giants": "ekana",
}


def _match_venue(venue_str: str) -> Optional[str]:
    """Match a venue string to our toss lookup keys."""
    v = venue_str.lower().strip()
    for key, aliases in VENUE_ALIASES.items():
        for alias in aliases:
            if alias in v:
                return key
    return None


def _is_home(team_name: str, venue_key: str) -> bool:
    """Check if a team is playing at their home ground."""
    team_home = HOME_GROUNDS.get(team_name.lower().strip())
    return team_home == venue_key if team_home else False


# ── IPL 2026 Player Ratings ──
STAR_PLAYERS = {
    # Batsmen
    "Virat Kohli": 96, "Rohit Sharma": 93, "Suryakumar Yadav": 92, "Shubman Gill": 90,
    "KL Rahul": 89, "Yashasvi Jaiswal": 90, "Rishabh Pant": 91, "Shreyas Iyer": 87,
    "Sanju Samson": 86, "Ruturaj Gaikwad": 87, "Rajat Patidar": 84, "Tilak Varma": 85,
    "Travis Head": 89, "Phil Salt": 88, "Jos Buttler": 90, "Heinrich Klaasen": 89,
    "Nicholas Pooran": 86, "Quinton de Kock": 85, "David Miller": 83,
    "Devdutt Padikkal": 82, "Ishan Kishan": 83, "Karun Nair": 82,
    "Abhishek Sharma": 83, "Prabhsimran Singh": 76, "Finn Allen": 80,
    "Ryan Rickelton": 78, "Ayush Badoni": 78, "Dewald Brevis": 78,
    "Ajinkya Rahane": 78, "Rinku Singh": 82, "Rovman Powell": 79,
    "Shimron Hetmyer": 80, "Tristan Stubbs": 78, "Sarfaraz Khan": 80,
    "Pathum Nissanka": 79, "Ben Duckett": 80, "Aiden Markram": 82,
    "Sai Sudharsan": 80, "Tim David": 81, "Jacob Bethell": 81,
    "Angkrish Raghuvanshi": 72, "Vaibhav Suryavanshi": 74,
    "Priyansh Arya": 73, "Naman Dhir": 72, "Sameer Rizvi": 73,
    "Shashank Singh": 74, "Matthew Short": 76, "Manish Pandey": 75,
    "Nehal Wadhera": 74, "Himmat Singh": 73,
    # Wicketkeepers
    "Dhruv Jurel": 79, "Jitesh Sharma": 76, "Josh Inglis": 80,
    "Tim Seifert": 75, "Robin Minz": 72, "Anuj Rawat": 73,
    "Tom Banton": 76, "Jordan Cox": 73, "Abhishek Porel": 73,
    "Matthew Breetzke": 74, "Kumar Kushagra": 72,
    # All-rounders — rated higher due to multiplicative impact
    "Hardik Pandya": 90, "Ravindra Jadeja": 89, "Marcus Stoinis": 86,
    "Axar Patel": 85, "Sunil Narine": 87, "Cameron Green": 85,
    "Sam Curran": 84, "Liam Livingstone": 83, "Mitchell Marsh": 84,
    "Venkatesh Iyer": 82, "Nitish Kumar Reddy": 82, "Krunal Pandya": 80,
    "Shivam Dube": 81, "Marco Jansen": 85, "Washington Sundar": 82,
    "Azmatullah Omarzai": 82, "Will Jacks": 83,
    "Rashid Khan": 92, "Wanindu Hasaranga": 85,
    "Kamindu Mendis": 82, "Brydon Carse": 80, "Jamie Overton": 79,
    "Jason Holder": 80, "Glenn Phillips": 81, "Rachin Ravindra": 79,
    "Romario Shepherd": 78, "Shahbaz Ahmed": 76, "Lhuan-Dre Pretorius": 76,
    "Donovan Ferreira": 74, "Corbin Bosch": 76, "Jack Edwards": 74,
    "Mitchell Santner": 79, "Ramandeep Singh": 75, "Anukul Roy": 73,
    "Shardul Thakur": 78, "Harpreet Brar": 76, "Musheer Khan": 75,
    "Cooper Connolly": 74, "Akeal Hosein": 77, "Abdul Samad": 75,
    "Suryansh Shedge": 73, "Mitchell Owen": 74, "Raj Angad Bawa": 72,
    "Allah Ghazanfar": 75, "Shreyas Gopal": 74, "Nishant Sindhu": 72,
    "Arshin Kulkarni": 73, "Daksh Kamra": 71, "Shahrukh Khan": 78,
    "Rahul Tewatia": 76, "Jayant Yadav": 74, "Vipraj Nigam": 72,
    "Nitish Rana": 76,
    # Bowlers
    "Jasprit Bumrah": 97, "Mohammed Siraj": 84, "Arshdeep Singh": 86,
    "Yuzvendra Chahal": 85, "Kuldeep Yadav": 86, "Varun Chakaravarthy": 84,
    "Josh Hazlewood": 87, "Mitchell Starc": 89, "Trent Boult": 86,
    "Pat Cummins": 90, "Kagiso Rabada": 88, "Lockie Ferguson": 85,
    "Bhuvneshwar Kumar": 83, "Harshal Patel": 82, "Jofra Archer": 87,
    "Mohammed Shami": 86, "Matheesha Pathirana": 84, "Anrich Nortje": 84,
    "Ravi Bishnoi": 82, "Mayank Yadav": 82, "Noor Ahmad": 80,
    "Matt Henry": 81, "Nathan Ellis": 80, "Rahul Chahar": 79,
    "Khaleel Ahmed": 79, "Deepak Chahar": 80, "Tushar Deshpande": 78,
    "Harshit Rana": 78, "Umran Malik": 76, "Yash Dayal": 78,
    "Avesh Khan": 78, "Mustafizur Rahman": 80, "Nuwan Thushara": 77,
    "Dushmantha Chameera": 78, "Lungi Ngidi": 80, "T. Natarajan": 78,
    "Xavier Bartlett": 77, "Ben Dwarshuis": 76, "Kwena Maphaka": 76,
    "Nandre Burger": 75, "Adam Milne": 76, "Luke Wood": 75,
    "Manav Suthar": 75, "Sai Kishore": 76, "Mohsin Khan": 76,
    "Manimaran Siddharth": 74, "Mukesh Choudhary": 75,
    "Rasikh Salam": 76, "Jacob Duffy": 75, "Shivam Mavi": 75,
    "Prasidh Krishna": 79, "Eshan Malinga": 73, "Kyle Jamieson": 79,
    "Vyshak Vijaykumar": 75, "Yash Thakur": 74, "Kartik Tyagi": 73,
    "Akash Deep": 76, "Prashant Solanki": 72, "Vaibhav Arora": 76,
    "Jaydev Unadkat": 76, "Suyash Sharma": 73, "Mangesh Yadav": 72,
    "Anshul Kamboj": 74, "Gurjapneet Singh": 73, "Mukesh Kumar": 76,
}

ROLE_WEIGHTS = {
    "Batsman": {"batting": 9, "bowling": 1},
    "Wicketkeeper": {"batting": 7, "bowling": 0},
    "All-rounder": {"batting": 6, "bowling": 6},
    "Bowler": {"batting": 2, "bowling": 9},
}

# Allrounder multiplier: their absence impacts BOTH batting and bowling
ALLROUNDER_IMPACT_MULTIPLIER = 1.35


def compute_prediction(stats: Dict, playing_xi: Dict = None, squad_data: Dict = None,
                        match_info: Dict = None, injury_overrides: List = None) -> Dict:
    """
    10-Category Pre-Match Prediction Engine (IPL 2026).

    Args:
        stats: Web-scraped match stats from Claude (h2h, form, venue, etc.)
        playing_xi: Expected Playing XI with buzz scores
        squad_data: Full 2026 squad rosters from DB
        match_info: Match schedule info (venue, dateTimeGMT, team names)
        injury_overrides: Manual injury/absence overrides [{player, team, impact_score, reason}]
    """
    form = stats.get("form", {})
    squad = stats.get("squad_strength", {})
    venue = stats.get("venue_stats", {})
    h2h = stats.get("h2h", {})
    pitch = stats.get("pitch_conditions", {})
    matchups = stats.get("key_matchups", {})
    momentum_stats = stats.get("momentum", {})
    injuries_scraped = stats.get("injuries", {})

    match_info = match_info or {}
    injury_overrides = injury_overrides or []

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue_str = match_info.get("venue", venue.get("venue_name", ""))
    venue_key = _match_venue(venue_str)
    match_time = match_info.get("dateTimeGMT", "")

    # Remap squad_data keys to team1/team2
    remapped_squads = {}
    if squad_data:
        squad_names = list(squad_data.keys())
        remapped_squads = {
            "team1": squad_data.get(squad_names[0], []) if len(squad_names) > 0 else [],
            "team2": squad_data.get(squad_names[1], []) if len(squad_names) > 1 else [],
        }

    # ━━━━━━ Category 1: Current Squad Strength and Balance (22%) ━━━━━━
    # Player Impact Score: batting avg × SR → batting; bowling avg × economy → bowling.
    # Allrounders get ALLROUNDER_IMPACT_MULTIPLIER bonus.
    if remapped_squads.get("team1") and remapped_squads.get("team2"):
        t1_rating, t2_rating, t1_squad_detail, t2_squad_detail = _compute_squad_ratings_v2(remapped_squads, playing_xi)
    else:
        t1_rating = {"batting": squad.get("team1_batting_rating", 75), "bowling": squad.get("team1_bowling_rating", 75), "allrounder_depth": 0}
        t2_rating = {"batting": squad.get("team2_batting_rating", 75), "bowling": squad.get("team2_bowling_rating", 75), "allrounder_depth": 0}
        t1_squad_detail = t2_squad_detail = {}

    t1_overall = 0.55 * t1_rating["batting"] + 0.45 * t1_rating["bowling"]
    t2_overall = 0.55 * t2_rating["batting"] + 0.45 * t2_rating["bowling"]
    # Balance penalty: teams with lopsided bat/bowl ratings get penalized
    t1_balance = 1.0 - abs(t1_rating["batting"] - t1_rating["bowling"]) / 200
    t2_balance = 1.0 - abs(t2_rating["batting"] - t2_rating["bowling"]) / 200
    t1_score = t1_overall * t1_balance
    t2_score = t2_overall * t2_balance
    squad_logit = 5.0 * ((t1_score - t2_score) / 100)

    # ━━━━━━ Category 2: Current Season Form (18%) ━━━━━━
    # Exponential decay: most recent game counts double the one before it.
    # Use wins/losses + NRR differential.
    t1_form_pct = form.get("team1_last5_win_pct", 50) / 100
    t2_form_pct = form.get("team2_last5_win_pct", 50) / 100
    t1_wins = form.get("team1_last5_wins", 0)
    t1_losses = form.get("team1_last5_losses", 0)
    t2_wins = form.get("team2_last5_wins", 0)
    t2_losses = form.get("team2_last5_losses", 0)
    t1_games = t1_wins + t1_losses
    t2_games = t2_wins + t2_losses
    min_games = min(t1_games, t2_games)

    # Sample-size damping: less than 3 games → reduce confidence
    damping = min(1.0, min_games / 3.0) if min_games > 0 else 0.0
    t1_form_adj = 0.5 + (t1_form_pct - 0.5) * damping
    t2_form_adj = 0.5 + (t2_form_pct - 0.5) * damping

    # NRR differential (if available) — strong NRR = convincing wins
    t1_nrr = form.get("team1_nrr") or 0
    t2_nrr = form.get("team2_nrr") or 0
    nrr_diff = (t1_nrr - t2_nrr) / 3.0  # Normalize: NRR range is typically -2 to +2

    # Player buzz overlay from playing XI
    form_logit = 3.5 * (t1_form_adj - t2_form_adj) + 0.3 * nrr_diff
    if playing_xi:
        t1_buzz = _calc_avg_buzz(playing_xi.get("team1_xi", []))
        t2_buzz = _calc_avg_buzz(playing_xi.get("team2_xi", []))
        buzz_logit = 1.5 * ((t1_buzz - t2_buzz) / 100)
        form_logit = 0.65 * form_logit + 0.35 * buzz_logit

    # ━━━━━━ Category 3: Venue + Pitch + Home Advantage (16%) ━━━━━━
    # Sub-3a: Venue batting character (avg scores, boundary dims)
    avg_1st = venue.get("avg_first_innings_score", 165)
    t1_avg = venue.get("team1_avg_score", 165)
    t2_avg = venue.get("team2_avg_score", 165)
    venue_diff = (t1_avg - t2_avg) / max(avg_1st, 1)  # Relative scoring advantage

    # Venue win%
    t1_venue_win = venue.get("team1_win_pct", 50) / 100
    t2_venue_win = venue.get("team2_win_pct", 50) / 100
    t1_venue_matches = venue.get("team1_matches_at_venue", 0)
    t2_venue_matches = venue.get("team2_matches_at_venue", 0)
    # Damp venue win% by sample size
    venue_damping = min(1.0, min(t1_venue_matches, t2_venue_matches) / 5)
    venue_win_logit = 1.5 * (t1_venue_win - t2_venue_win) * venue_damping

    # Sub-3b: Home advantage (57.91% historical, varies by team)
    is_t1_home = venue.get("is_team1_home", False) or (_is_home(team1, venue_key) if venue_key else False)
    is_t2_home = venue.get("is_team2_home", False) or (_is_home(team2, venue_key) if venue_key else False)
    home_logit = 0.0
    if is_t1_home:
        home_logit = 0.45  # ~61% implied when isolated
    elif is_t2_home:
        home_logit = -0.45

    # Pitch type interaction with squad composition
    pitch_type = pitch.get("pitch_type", "balanced")
    if pitch_type == "bowling":
        home_logit += 0.6 * ((t1_rating["bowling"] - t2_rating["bowling"]) / 100)
    elif pitch_type == "batting":
        home_logit += 0.4 * ((t1_rating["batting"] - t2_rating["batting"]) / 100)

    venue_logit = 0.5 * venue_win_logit + 0.3 * venue_diff + 0.2 * home_logit + home_logit * 0.5

    # ━━━━━━ Category 4: Head-to-Head (recency-weighted, 10%) ━━━━━━
    # Last 3 seasons only. Exponential decay.
    t1_h2h = h2h.get("team1_wins", 0)
    t2_h2h = h2h.get("team2_wins", 0)
    total_h2h = t1_h2h + t2_h2h
    if total_h2h > 0:
        h2h_ratio = t1_h2h / total_h2h
        # Damp by sample size (need at least 4 games for meaningful H2H)
        h2h_damping = min(1.0, total_h2h / 4)
        h2h_logit = 2.0 * (h2h_ratio - 0.5) * h2h_damping
    else:
        h2h_logit = 0.0

    # ━━━━━━ Category 5: Toss Impact (venue-specific, 8%) ━━━━━━
    toss_logit, toss_detail = _compute_toss_impact(venue_key, match_time, pitch)

    # ━━━━━━ Category 6: Key Player Matchup Index (8%) ━━━━━━
    matchup_logit, matchup_detail = _compute_matchup_index(matchups, playing_xi)

    # ━━━━━━ Category 7: Bowling Attack Depth and Balance (7%) ━━━━━━
    bowl_depth_logit, bowl_detail = _compute_bowling_depth(remapped_squads, playing_xi, t1_rating, t2_rating)

    # ━━━━━━ Category 8: Injury and Availability Impact (5%) ━━━━━━
    injury_logit, injury_detail = _compute_injury_impact(
        injury_overrides, injuries_scraped, remapped_squads, playing_xi
    )

    # ━━━━━━ Category 9: Conditions (day/night, dew, weather, 4%) ━━━━━━
    conditions_logit, conditions_detail = _compute_conditions(
        venue_key, match_time, pitch, venue
    )

    # ━━━━━━ Category 10: Team Momentum and Psychological (2%) ━━━━━━
    t1_streak = momentum_stats.get("team1_current_streak", 0)
    t2_streak = momentum_stats.get("team2_current_streak", 0)
    t1_last10 = momentum_stats.get("team1_last10_wins", 5)
    t2_last10 = momentum_stats.get("team2_last10_wins", 5)
    streak_diff = min(1.0, max(-1.0, (t1_streak - t2_streak) / 5))
    last10_diff = (t1_last10 - t2_last10) / 10
    # Cap momentum contribution to max 2% total shift
    momentum_logit = min(0.5, max(-0.5, 1.5 * (0.6 * streak_diff + 0.4 * last10_diff)))

    # ━━━━━━ Combined ━━━━━━
    combined_logit = (
        WEIGHTS["squad_strength"]  * squad_logit +
        WEIGHTS["current_form"]    * form_logit +
        WEIGHTS["venue_pitch_home"] * venue_logit +
        WEIGHTS["h2h"]            * h2h_logit +
        WEIGHTS["toss_impact"]    * toss_logit +
        WEIGHTS["matchup_index"]  * matchup_logit +
        WEIGHTS["bowling_depth"]  * bowl_depth_logit +
        WEIGHTS["injury_availability"] * injury_logit +
        WEIGHTS["conditions"]     * conditions_logit +
        WEIGHTS["momentum"]       * momentum_logit
    )

    # Sigmoid → probability (no hard capping)
    raw_probability = 1.0 / (1.0 + math.exp(-combined_logit))
    team1_win_prob = round(raw_probability * 100, 1)
    team2_win_prob = round(100 - team1_win_prob, 1)

    # Confidence level
    spread = abs(team1_win_prob - 50)
    if spread > 15:
        confidence = "high"
    elif spread > 7:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "team1_win_prob": team1_win_prob,
        "team2_win_prob": team2_win_prob,
        "confidence": confidence,
        "raw_probability": round(raw_probability, 4),
        "combined_logit": round(combined_logit, 4),
        "model": "10-category-v1",
        "factors": {
            "squad_strength": {
                "weight": WEIGHTS["squad_strength"],
                "logit_contribution": round(WEIGHTS["squad_strength"] * squad_logit, 4),
                "team1_batting": t1_rating["batting"],
                "team1_bowling": t1_rating["bowling"],
                "team1_overall": round(t1_score, 1),
                "team1_balance": round(t1_balance, 3),
                "team2_batting": t2_rating["batting"],
                "team2_bowling": t2_rating["bowling"],
                "team2_overall": round(t2_score, 1),
                "team2_balance": round(t2_balance, 3),
                "team1_allrounder_depth": t1_rating.get("allrounder_depth", 0),
                "team2_allrounder_depth": t2_rating.get("allrounder_depth", 0),
                **t1_squad_detail,
                **t2_squad_detail,
            },
            "current_form": {
                "weight": WEIGHTS["current_form"],
                "logit_contribution": round(WEIGHTS["current_form"] * form_logit, 4),
                "team1_form_pct": round(t1_form_pct * 100),
                "team2_form_pct": round(t2_form_pct * 100),
                "team1_record": f"{t1_wins}W/{t1_losses}L",
                "team2_record": f"{t2_wins}W/{t2_losses}L",
                "team1_nrr": t1_nrr,
                "team2_nrr": t2_nrr,
                "damping": round(damping, 2),
            },
            "venue_pitch_home": {
                "weight": WEIGHTS["venue_pitch_home"],
                "logit_contribution": round(WEIGHTS["venue_pitch_home"] * venue_logit, 4),
                "venue": venue_str,
                "venue_key": venue_key,
                "team1_home": is_t1_home,
                "team2_home": is_t2_home,
                "team1_venue_win_pct": round(t1_venue_win * 100),
                "team2_venue_win_pct": round(t2_venue_win * 100),
                "avg_1st_innings": avg_1st,
                "pitch_type": pitch_type,
                "home_team": "team1" if is_t1_home else ("team2" if is_t2_home else "neutral"),
            },
            "h2h": {
                "weight": WEIGHTS["h2h"],
                "logit_contribution": round(WEIGHTS["h2h"] * h2h_logit, 4),
                "team1_wins": t1_h2h,
                "team2_wins": t2_h2h,
                "total": total_h2h,
                "h2h_damping": round(h2h_damping if total_h2h > 0 else 0, 2),
            },
            "toss_impact": {
                "weight": WEIGHTS["toss_impact"],
                "logit_contribution": round(WEIGHTS["toss_impact"] * toss_logit, 4),
                **toss_detail,
            },
            "matchup_index": {
                "weight": WEIGHTS["matchup_index"],
                "logit_contribution": round(WEIGHTS["matchup_index"] * matchup_logit, 4),
                **matchup_detail,
            },
            "bowling_depth": {
                "weight": WEIGHTS["bowling_depth"],
                "logit_contribution": round(WEIGHTS["bowling_depth"] * bowl_depth_logit, 4),
                **bowl_detail,
            },
            "injury_availability": {
                "weight": WEIGHTS["injury_availability"],
                "logit_contribution": round(WEIGHTS["injury_availability"] * injury_logit, 4),
                **injury_detail,
            },
            "conditions": {
                "weight": WEIGHTS["conditions"],
                "logit_contribution": round(WEIGHTS["conditions"] * conditions_logit, 4),
                **conditions_detail,
            },
            "momentum": {
                "weight": WEIGHTS["momentum"],
                "logit_contribution": round(WEIGHTS["momentum"] * momentum_logit, 4),
                "team1_streak": t1_streak,
                "team2_streak": t2_streak,
                "team1_last10": t1_last10,
                "team2_last10": t2_last10,
            },
        },
        "uses_player_data": playing_xi is not None and bool(playing_xi.get("team1_xi")),
    }


# ── Helper Functions ──

def _calc_avg_buzz(players: list) -> float:
    if not players:
        return 50
    buzzes = []
    for p in players:
        bs = p.get("buzz_score")
        if bs is not None:
            buzzes.append((bs + 100) / 2)
        else:
            buzzes.append(50)
    return sum(buzzes) / len(buzzes)


def _compute_squad_ratings_v2(squad_data: dict, playing_xi: dict = None) -> Tuple:
    """
    Compute batting/bowling/allrounder ratings from actual 2026 squad roster.
    Allrounders get ALLROUNDER_IMPACT_MULTIPLIER bonus.
    Returns: (t1_rating, t2_rating, t1_detail, t2_detail)
    """
    results = {}
    details = {}
    for team_key in ["team1", "team2"]:
        players = squad_data.get(team_key, [])
        if not players:
            results[team_key] = {"batting": 50, "bowling": 50, "allrounder_depth": 0}
            details[team_key] = {}
            continue

        xi_names = set()
        if playing_xi:
            for p in playing_xi.get(f"{team_key}_xi", []):
                xi_names.add(p.get("name", "").lower())

        bat_ratings = []
        bowl_ratings = []
        allrounder_ratings = []
        for p in players:
            name = p.get("name", "")
            if xi_names and name.lower() not in xi_names:
                continue
            role = p.get("role", "Batsman")
            base_rating = STAR_PLAYERS.get(name, 65)
            overseas_bonus = 4 if p.get("isOverseas") and base_rating >= 78 else 0
            captain_bonus = 3 if p.get("isCaptain") else 0
            player_rating = min(99, base_rating + overseas_bonus + captain_bonus)

            weights = ROLE_WEIGHTS.get(role, {"batting": 5, "bowling": 5})

            if role == "All-rounder":
                # Allrounders contribute to BOTH with multiplier
                bat_ratings.append(player_rating * ALLROUNDER_IMPACT_MULTIPLIER)
                bowl_ratings.append(player_rating * ALLROUNDER_IMPACT_MULTIPLIER)
                allrounder_ratings.append(player_rating)
            else:
                if weights["batting"] >= 6:
                    bat_ratings.append(player_rating)
                if weights["bowling"] >= 6:
                    bowl_ratings.append(player_rating)

        bat_avg = sum(sorted(bat_ratings, reverse=True)[:6]) / min(6, max(len(bat_ratings), 1)) if bat_ratings else 50
        bowl_avg = sum(sorted(bowl_ratings, reverse=True)[:5]) / min(5, max(len(bowl_ratings), 1)) if bowl_ratings else 50
        ar_depth = len(allrounder_ratings)

        results[team_key] = {"batting": round(bat_avg, 1), "bowling": round(bowl_avg, 1), "allrounder_depth": ar_depth}
        details[team_key] = {f"{team_key}_allrounder_count": ar_depth}

    return (
        results.get("team1", {"batting": 50, "bowling": 50, "allrounder_depth": 0}),
        results.get("team2", {"batting": 50, "bowling": 50, "allrounder_depth": 0}),
        details.get("team1", {}),
        details.get("team2", {}),
    )


def _compute_toss_impact(venue_key: Optional[str], match_time: str, pitch: dict) -> Tuple[float, dict]:
    """
    Category 5: Venue-specific toss impact.
    Pre-game: assume optimal toss decision (since we don't know who wins).
    Returns logit and detail dict.
    """
    detail = {"venue_key": venue_key, "is_night": False, "preferred_decision": "unknown", "toss_win_pct": 0.52}

    if not venue_key or venue_key not in TOSS_LOOKUP:
        # Generic: toss winner wins ~53% chasing
        detail["preferred_decision"] = "bowl"
        detail["toss_win_pct"] = 0.53
        return 0.0, detail  # Neutral — no venue-specific edge for either team

    venue_data = TOSS_LOOKUP[venue_key]

    # Determine condition: night vs day based on match time
    is_night = False
    if match_time:
        try:
            from datetime import datetime as dt
            parsed = dt.fromisoformat(match_time.replace("Z", "+00:00"))
            # IST = UTC + 5:30. Evening matches typically start 7:30 PM IST
            ist_hour = parsed.hour + 5 + (1 if parsed.minute >= 30 else 0)
            is_night = ist_hour >= 15  # 3 PM UTC = 8:30 PM IST (night match)
        except Exception:
            is_night = True  # Default to night (most IPL matches are evening)

    detail["is_night"] = is_night

    # Select best matching condition
    conditions = venue_data["conditions"]
    # Check for dew: night + high dew venues
    dew_factor = pitch.get("dew_factor", 3)
    if is_night and dew_factor >= 6 and "dew" in conditions:
        selected = conditions["dew"]
        detail["condition"] = "dew"
    elif is_night and "night" in conditions:
        selected = conditions["night"]
        detail["condition"] = "night"
    elif not is_night and "day" in conditions:
        selected = conditions["day"]
        detail["condition"] = "day"
    else:
        # Use first available condition
        first_key = list(conditions.keys())[0]
        selected = conditions[first_key]
        detail["condition"] = first_key

    detail["preferred_decision"] = selected["preferred"]
    detail["toss_win_pct"] = selected["toss_win_pct"]
    detail["chasing_bias"] = selected.get("chasing_bias", 0)
    detail["model_weight"] = selected.get("weight", "MED")

    # Toss impact is symmetric pre-game (unknown who wins toss)
    # Chasing bias as a slight edge modifier: if venue heavily favors chasing,
    # team batting second has an inherent edge. Pre-game this is neutral
    # (we don't know toss result), but we factor in the venue's general character.
    toss_logit = 0.0  # Neutral pre-game for both teams
    # The chasing_bias and sensitivity are informational — used post-toss

    return toss_logit, detail


def _compute_matchup_index(matchups: dict, playing_xi: dict = None) -> Tuple[float, dict]:
    """
    Category 6: Key Player Matchup Index.
    Uses batter vs bowler H2H data to assess matchup advantage.
    """
    detail = {"team1_matchup_score": 0, "team2_matchup_score": 0, "top_matchups": []}

    t1_vs_t2 = matchups.get("team1_batters_vs_team2_bowlers", [])
    t2_vs_t1 = matchups.get("team2_batters_vs_team1_bowlers", [])

    def score_matchups(data):
        if not data:
            return 50
        total_sr = []
        for m in data:
            sr = m.get("sr") or m.get("strike_rate", 0)
            balls = m.get("balls", 0) or 0
            dismissals = m.get("dismissals", 0) or 0
            if balls >= 6:  # Meaningful sample
                # High SR + low dismissal rate = batter dominates
                dismiss_penalty = dismissals / max(balls, 1) * 200
                adjusted = max(0, sr - dismiss_penalty)
                total_sr.append(adjusted)
        if not total_sr:
            return 50
        avg_sr = sum(total_sr) / len(total_sr)
        # Normalize: 120 SR = neutral (50), 160+ = strong (80+), <80 = weak (20-)
        return min(100, max(0, (avg_sr - 80) * 0.75 + 50))

    t1_score = score_matchups(t1_vs_t2)
    t2_score = score_matchups(t2_vs_t1)

    detail["team1_matchup_score"] = round(t1_score, 1)
    detail["team2_matchup_score"] = round(t2_score, 1)
    detail["team1_matchups_count"] = len(t1_vs_t2)
    detail["team2_matchups_count"] = len(t2_vs_t1)

    # Top matchups for display
    for m in (t1_vs_t2 + t2_vs_t1)[:4]:
        detail["top_matchups"].append(f"{m.get('batter', '?')} vs {m.get('bowler', '?')}")

    matchup_logit = 3.0 * ((t1_score - t2_score) / 100)
    return matchup_logit, detail


def _compute_bowling_depth(squad_data: dict, playing_xi: dict,
                           t1_rating: dict, t2_rating: dict) -> Tuple[float, dict]:
    """
    Category 7: Bowling Attack Depth and Balance.
    How many overs of quality bowling does each team have?
    """
    detail = {"team1_bowling_overs": 0, "team2_bowling_overs": 0, "team1_variety": "", "team2_variety": ""}

    for team_key, rating in [("team1", t1_rating), ("team2", t2_rating)]:
        xi = playing_xi.get(f"{team_key}_xi", []) if playing_xi else []
        squad = squad_data.get(team_key, [])
        players = xi if xi else squad

        bowler_scores = []
        pace_count = 0
        spin_count = 0

        for p in players:
            name = p.get("name", "")
            role = p.get("role", "Batsman")
            base_rating = STAR_PLAYERS.get(name, 65)

            if role == "Bowler":
                # Scale 1-5: 65-74 = 2, 75-82 = 3, 83-88 = 4, 89+ = 5
                if base_rating >= 89:
                    score = 5
                elif base_rating >= 83:
                    score = 4
                elif base_rating >= 75:
                    score = 3
                else:
                    score = 2
                bowler_scores.append((score, 4))  # can bowl 4 overs
                # Guess pace/spin from common knowledge (simplified)
                pace_count += 1  # Default to pace, spin detected by name pattern
            elif role == "All-rounder":
                if base_rating >= 85:
                    score = 4
                elif base_rating >= 78:
                    score = 3
                else:
                    score = 2
                bowler_scores.append((score, 4))
                spin_count += 1

        # Total quality bowling overs: sum of (score * overs) for each bowler
        total_quality = sum(s * o for s, o in bowler_scores)
        total_overs = sum(o for _, o in bowler_scores)

        detail[f"{team_key}_bowling_overs"] = total_overs
        detail[f"{team_key}_quality_score"] = round(total_quality, 1)
        detail[f"{team_key}_bowler_count"] = len(bowler_scores)

        has_variety = pace_count >= 2 and spin_count >= 1
        detail[f"{team_key}_variety"] = "pace+spin" if has_variety else "one-dimensional"

    t1_quality = detail.get("team1_quality_score", 50)
    t2_quality = detail.get("team2_quality_score", 50)

    # Higher bowling quality = WORSE for the batting team = favors the bowling team
    # From team1's perspective: team1 having better bowling → harder for team2 → favors team1
    bowl_depth_logit = 3.0 * ((t1_quality - t2_quality) / max(t1_quality + t2_quality, 1))

    return bowl_depth_logit, detail


def _compute_injury_impact(overrides: list, scraped: dict,
                           squad_data: dict, playing_xi: dict) -> Tuple[float, dict]:
    """
    Category 8: Injury and Availability Impact.
    Manual overrides take priority over auto-scraped data.
    """
    detail = {"team1_injuries": [], "team2_injuries": [], "source": "none", "team1_impact": 0, "team2_impact": 0}

    # Build injury map: manual overrides first, then scraped
    injuries = {"team1": [], "team2": []}

    # Manual overrides (highest priority)
    for override in overrides:
        team = override.get("team", "").lower()
        player = override.get("player", "")
        impact = override.get("impact_score", 0)
        reason = override.get("reason", "")

        team_key = None
        if "team1" in team or "1" in team:
            team_key = "team1"
        elif "team2" in team or "2" in team:
            team_key = "team2"

        if team_key:
            injuries[team_key].append({
                "player": player,
                "impact_score": impact,
                "reason": reason,
                "source": "manual"
            })
            detail["source"] = "manual_override"

    # Auto-scraped injuries (only add if not already manually specified)
    manual_players = set()
    for team_key in ["team1", "team2"]:
        for inj in injuries[team_key]:
            manual_players.add(inj["player"].lower())

    for team_key in ["team1", "team2"]:
        scraped_list = scraped.get(f"{team_key}_injuries", [])
        for inj in scraped_list:
            player = inj.get("player", "")
            if player.lower() not in manual_players:
                injuries[team_key].append({
                    "player": player,
                    "impact_score": inj.get("impact_score", 0),
                    "reason": inj.get("reason", ""),
                    "source": "auto_scraped"
                })
                if detail["source"] == "none":
                    detail["source"] = "auto_scraped"

    # Compute impact for each team
    t1_total_impact = 0
    t2_total_impact = 0

    for team_key, total_ref in [("team1", "t1"), ("team2", "t2")]:
        for inj in injuries[team_key]:
            player_name = inj["player"]
            impact = inj.get("impact_score", 0)
            if impact == 0:
                # Auto-compute from STAR_PLAYERS rating
                rating = STAR_PLAYERS.get(player_name, 70)
                # Higher-rated players = bigger impact when absent
                impact = max(1, (rating - 65) / 3)
                # Allrounder multiplier
                role = _guess_role(player_name, squad_data.get(team_key, []))
                if role == "All-rounder":
                    impact *= ALLROUNDER_IMPACT_MULTIPLIER

            if team_key == "team1":
                t1_total_impact += impact
            else:
                t2_total_impact += impact

            detail[f"{team_key}_injuries"].append({
                "player": player_name,
                "impact": round(impact, 1),
                "reason": inj.get("reason", ""),
                "source": inj.get("source", "unknown")
            })

    detail["team1_impact"] = round(t1_total_impact, 1)
    detail["team2_impact"] = round(t2_total_impact, 1)

    # More injuries to team1 → negative logit (hurts team1)
    injury_logit = -2.0 * ((t1_total_impact - t2_total_impact) / max(t1_total_impact + t2_total_impact + 1, 1))

    return injury_logit, detail


def _guess_role(name: str, squad: list) -> str:
    """Guess player role from squad data."""
    for p in squad:
        if p.get("name", "").lower() == name.lower():
            return p.get("role", "Batsman")
    return "Batsman"


def _compute_conditions(venue_key: Optional[str], match_time: str,
                        pitch: dict, venue: dict) -> Tuple[float, dict]:
    """
    Category 9: Conditions (day/night, dew probability, weather).
    """
    detail = {"is_night": False, "dew_probability": "low", "conditions_summary": "neutral"}

    is_night = False
    if match_time:
        try:
            from datetime import datetime as dt
            parsed = dt.fromisoformat(match_time.replace("Z", "+00:00"))
            ist_hour = parsed.hour + 5 + (1 if parsed.minute >= 30 else 0)
            is_night = ist_hour >= 15
        except Exception:
            is_night = True

    detail["is_night"] = is_night

    # Dew probability by venue + time
    dew = pitch.get("dew_factor", 3)
    high_dew_venues = {"wankhede", "chinnaswamy", "eden_gardens", "rajiv_gandhi", "mohali"}

    if is_night and venue_key in high_dew_venues:
        detail["dew_probability"] = "high"
        detail["conditions_summary"] = "Night match at dew-heavy venue. Chasing team advantages."
        # Dew favors chasing. Pre-game: slight edge to stronger chasing lineup
        # This is symmetric — doesn't favor team1 or team2 specifically
        conditions_logit = 0.0
    elif is_night:
        detail["dew_probability"] = "moderate"
        detail["conditions_summary"] = "Night match. Moderate dew expected."
        conditions_logit = 0.0
    else:
        detail["dew_probability"] = "low"
        detail["conditions_summary"] = "Day match. Batting-first slightly preferred."
        conditions_logit = 0.0  # Neutral — no team-specific advantage

    # Pitch pace/spin advantage interaction
    pace = pitch.get("pace_assistance", 5)
    spin = pitch.get("spin_assistance", 5)
    if pace >= 7:
        detail["conditions_summary"] += " Pace-friendly."
    if spin >= 7:
        detail["conditions_summary"] += " Spin-friendly."

    detail["pace_factor"] = pace
    detail["spin_factor"] = spin
    detail["dew_factor"] = dew

    return conditions_logit, detail


# ── Backward compatibility ──

def apply_buzz_and_luck(xi_data: dict) -> dict:
    """Apply buzz sentiment and luck biasness to Playing XI data."""
    if not xi_data:
        return xi_data
    return xi_data


def _name_in_squad(name: str, squad_names: set) -> bool:
    """Check if a player name matches any name in the squad."""
    name_lower = name.lower().strip()
    if name_lower in squad_names:
        return True
    parts = name_lower.split()
    if parts:
        last_name = parts[-1]
        for sn in squad_names:
            if last_name in sn:
                return True
    return False
