"""
Pre-Match Prediction Engine — The Lucky 11 (IPL 2026)
8-Category Model (Matchups & Injuries REMOVED per user request)

Category                                Weight
1. Current Squad Strength and Balance    25%
2. Current Season Form (SportMonks)      21%
3. Venue and Pitch Profile + Home Adv    18%
4. Head-to-Head (recency-weighted)       11%
5. Toss Impact (venue-specific)           9%
6. Bowling Attack Depth and Balance       8%
7. Conditions (weather-based, dew)        5%
8. Team Momentum (last 2 matches W/L)    3%

Design Principles:
- NO web scraping. All data from DB squads, SportMonks API, or weather API.
- Squad data ONLY from ipl_squads collection (user-provided rosters).
- Current form from SportMonks last 15 matches.
- Conditions from real-time Open-Meteo weather data.
- Momentum from last 2 match results (W/L).
"""
import math
import logging
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)

# ── Weights (8 categories, sum = 1.0) ──
WEIGHTS = {
    "squad_strength": 0.25,
    "current_form": 0.21,
    "venue_pitch_home": 0.18,
    "h2h": 0.11,
    "toss_impact": 0.09,
    "bowling_depth": 0.08,
    "conditions": 0.05,
    "momentum": 0.03,
}

# ── Toss Lookup (from user-provided venue-specific data) ──
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
    "barsapara": {
        "city": "guwahati",
        "default_decision": "bowl",
        "conditions": {
            "night": {"preferred": "bowl", "toss_win_pct": 0.55, "chasing_bias": 0.05, "weight": "MED"},
        },
    },
    "hpca": {
        "city": "dharamshala",
        "default_decision": "bowl",
        "conditions": {
            "night": {"preferred": "bowl", "toss_win_pct": 0.56, "chasing_bias": 0.06, "weight": "MED"},
        },
    },
    "shaheed_veer_narayan": {
        "city": "raipur",
        "default_decision": "bowl",
        "conditions": {
            "night": {"preferred": "bowl", "toss_win_pct": 0.54, "chasing_bias": 0.04, "weight": "LOW"},
        },
    },
}

# Venue alias mapping
VENUE_ALIASES = {
    "wankhede": ["wankhede", "mumbai"],
    "chepauk": ["chepauk", "chidambaram", "chennai"],
    "chinnaswamy": ["chinnaswamy", "bengaluru", "bangalore"],
    "narendra_modi": ["narendra modi", "motera", "ahmedabad"],
    "eden_gardens": ["eden garden", "kolkata"],
    "arun_jaitley": ["arun jaitley", "feroz shah", "delhi"],
    "rajiv_gandhi": ["rajiv gandhi", "uppal", "hyderabad"],
    "mohali": ["mohali", "chandigarh", "punjab", "new chandigarh"],
    "sawai_mansingh": ["sawai", "jaipur", "rajasthan"],
    "ekana": ["ekana", "lucknow", "bharat ratna"],
    "barsapara": ["barsapara", "guwahati"],
    "hpca": ["hpca", "dharamshala", "dharamsala"],
    "shaheed_veer_narayan": ["shaheed", "raipur"],
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


# ── IPL 2026 Player Ratings (from user-provided squad data) ──
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
    # All-rounders
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

ALLROUNDER_IMPACT_MULTIPLIER = 1.35

# Bowler type classification for conditions matching
PACE_BOWLERS = {
    "Jasprit Bumrah", "Mohammed Siraj", "Arshdeep Singh", "Josh Hazlewood",
    "Mitchell Starc", "Trent Boult", "Pat Cummins", "Kagiso Rabada", "Lockie Ferguson",
    "Bhuvneshwar Kumar", "Harshal Patel", "Jofra Archer", "Mohammed Shami",
    "Matheesha Pathirana", "Anrich Nortje", "Mayank Yadav", "Matt Henry",
    "Nathan Ellis", "Deepak Chahar", "Tushar Deshpande", "Harshit Rana",
    "Umran Malik", "Yash Dayal", "Avesh Khan", "Mustafizur Rahman",
    "Nuwan Thushara", "Dushmantha Chameera", "Lungi Ngidi", "T. Natarajan",
    "Xavier Bartlett", "Ben Dwarshuis", "Kwena Maphaka", "Nandre Burger",
    "Adam Milne", "Luke Wood", "Mohsin Khan", "Mukesh Choudhary",
    "Rasikh Salam", "Shivam Mavi", "Prasidh Krishna", "Kyle Jamieson",
    "Vyshak Vijaykumar", "Yash Thakur", "Kartik Tyagi", "Akash Deep",
    "Vaibhav Arora", "Jaydev Unadkat", "Mangesh Yadav", "Anshul Kamboj",
    "Mukesh Kumar", "Marco Jansen", "Sam Curran", "Shardul Thakur",
    "Brydon Carse", "Jamie Overton", "Jason Holder", "Corbin Bosch",
    "Hardik Pandya", "Cameron Green",
}

SPIN_BOWLERS = {
    "Yuzvendra Chahal", "Kuldeep Yadav", "Varun Chakaravarthy", "Ravi Bishnoi",
    "Noor Ahmad", "Rahul Chahar", "Manav Suthar", "Sai Kishore",
    "Manimaran Siddharth", "Jacob Duffy", "Eshan Malinga", "Prashant Solanki",
    "Suyash Sharma", "Gurjapneet Singh",
    "Rashid Khan", "Wanindu Hasaranga", "Sunil Narine", "Ravindra Jadeja",
    "Axar Patel", "Washington Sundar", "Krunal Pandya", "Shivam Dube",
    "Mitchell Santner", "Akeal Hosein", "Harpreet Brar", "Musheer Khan",
    "Allah Ghazanfar", "Shreyas Gopal", "Nishant Sindhu", "Shahbaz Ahmed",
    "Rahul Tewatia", "Jayant Yadav",
}


def _match_venue(venue_str: str) -> Optional[str]:
    v = venue_str.lower().strip()
    for key, aliases in VENUE_ALIASES.items():
        for alias in aliases:
            if alias in v:
                return key
    return None


def _is_home(team_name: str, venue_key: str) -> bool:
    team_home = HOME_GROUNDS.get(team_name.lower().strip())
    return team_home == venue_key if team_home else False


def compute_prediction(squad_data: Dict = None, match_info: Dict = None,
                        weather: Dict = None, form_data: Dict = None,
                        momentum_data: Dict = None) -> Dict:
    """
    8-Category Pre-Match Prediction Engine (The Lucky 11, IPL 2026).
    NO web scraping. All data from DB squads, SportMonks API, or weather API.
    """
    match_info = match_info or {}
    squad_data = squad_data or {}
    weather = weather or {}
    form_data = form_data or {}
    momentum_data = momentum_data or {}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue_str = match_info.get("venue", "")
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

    # ━━━━━━ Category 1: Current Squad Strength and Balance (25%) ━━━━━━
    if remapped_squads.get("team1") and remapped_squads.get("team2"):
        t1_rating, t2_rating, t1_squad_detail, t2_squad_detail = _compute_squad_ratings(remapped_squads)
    else:
        t1_rating = {"batting": 75, "bowling": 75, "allrounder_depth": 0}
        t2_rating = {"batting": 75, "bowling": 75, "allrounder_depth": 0}
        t1_squad_detail = t2_squad_detail = {}

    t1_overall = 0.55 * t1_rating["batting"] + 0.45 * t1_rating["bowling"]
    t2_overall = 0.55 * t2_rating["batting"] + 0.45 * t2_rating["bowling"]
    t1_balance = 1.0 - abs(t1_rating["batting"] - t1_rating["bowling"]) / 200
    t2_balance = 1.0 - abs(t2_rating["batting"] - t2_rating["bowling"]) / 200
    t1_score = t1_overall * t1_balance
    t2_score = t2_overall * t2_balance
    # Core squad strength logit from overall quality
    raw_squad_logit = 5.0 * ((t1_score - t2_score) / 100)
    # Balance bonus: reward well-balanced squads more aggressively
    balance_diff = t1_balance - t2_balance
    balance_bonus = 3.0 * balance_diff
    squad_logit = raw_squad_logit + balance_bonus

    # ━━━━━━ Category 2: Current Season Form — SportMonks API (21%) ━━━━━━
    t1_form = form_data.get("team1", {})
    t2_form = form_data.get("team2", {})
    t1_form_score = t1_form.get("form_score", 50)
    t2_form_score = t2_form.get("form_score", 50)
    t1_matches_played = t1_form.get("matches_played", 0)
    t2_matches_played = t2_form.get("matches_played", 0)
    min_matches = min(t1_matches_played, t2_matches_played)
    form_damping = min(1.0, min_matches / 3.0) if min_matches > 0 else 0.3
    form_logit = 3.5 * ((t1_form_score - t2_form_score) / 100) * form_damping

    # ━━━━━━ Category 3: Venue + Pitch + Home Advantage (18%) ━━━━━━
    is_t1_home = _is_home(team1, venue_key) if venue_key else False
    is_t2_home = _is_home(team2, venue_key) if venue_key else False
    home_logit = 0.0
    if is_t1_home:
        home_logit = 0.45
    elif is_t2_home:
        home_logit = -0.45
    venue_logit = home_logit

    # ━━━━━━ Category 4: Head-to-Head (11%) ━━━━━━
    h2h = form_data.get("h2h", {})
    t1_h2h = h2h.get("team1_wins", 0)
    t2_h2h = h2h.get("team2_wins", 0)
    total_h2h = t1_h2h + t2_h2h
    h2h_source = h2h.get("source", "season_2026")
    if total_h2h > 0:
        h2h_ratio = t1_h2h / total_h2h
        # For historical data (30+ matches), cap damping lower to avoid over-reliance
        if h2h_source == "historical_ipl" and total_h2h > 10:
            h2h_damping = 0.7  # Moderate weight for historical records
        else:
            h2h_damping = min(1.0, total_h2h / 4)
        h2h_logit = 2.5 * (h2h_ratio - 0.5) * h2h_damping
    else:
        h2h_logit = 0.0

    # ━━━━━━ Category 5: Toss Impact (venue-specific, 9%) ━━━━━━
    toss_logit, toss_detail = _compute_toss_impact(venue_key, match_time, weather)

    # ━━━━━━ Category 6: Bowling Attack Depth (8%) ━━━━━━
    bowl_depth_logit, bowl_detail = _compute_bowling_depth(remapped_squads, t1_rating, t2_rating)

    # ━━━━━━ Category 7: Conditions — Real Weather Data (5%) ━━━━━━
    conditions_logit, conditions_detail = _compute_conditions_from_weather(
        venue_key, match_time, weather, remapped_squads
    )

    # ━━━━━━ Category 8: Team Momentum — Last 2 Matches (3%) ━━━━━━
    t1_last2 = momentum_data.get("team1_last2", [])
    t2_last2 = momentum_data.get("team2_last2", [])
    t1_wins_last2 = sum(1 for r in t1_last2 if r == "W")
    t2_wins_last2 = sum(1 for r in t2_last2 if r == "W")
    momentum_logit = min(0.5, max(-0.5, 1.5 * ((t1_wins_last2 - t2_wins_last2) / 2)))

    # ━━━━━━ Combined ━━━━━━
    combined_logit = (
        WEIGHTS["squad_strength"]  * squad_logit +
        WEIGHTS["current_form"]    * form_logit +
        WEIGHTS["venue_pitch_home"] * venue_logit +
        WEIGHTS["h2h"]            * h2h_logit +
        WEIGHTS["toss_impact"]    * toss_logit +
        WEIGHTS["bowling_depth"]  * bowl_depth_logit +
        WEIGHTS["conditions"]     * conditions_logit +
        WEIGHTS["momentum"]       * momentum_logit
    )

    raw_probability = 1.0 / (1.0 + math.exp(-combined_logit))
    team1_win_prob = round(raw_probability * 100, 1)
    team2_win_prob = round(100 - team1_win_prob, 1)

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
        "model": "8-category-v2",
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
                **t1_squad_detail, **t2_squad_detail,
            },
            "current_form": {
                "weight": WEIGHTS["current_form"],
                "logit_contribution": round(WEIGHTS["current_form"] * form_logit, 4),
                "team1_form_score": round(t1_form_score, 1),
                "team2_form_score": round(t2_form_score, 1),
                "team1_matches_played": t1_matches_played,
                "team2_matches_played": t2_matches_played,
                "team1_wins": t1_form.get("wins", 0),
                "team2_wins": t2_form.get("wins", 0),
                "team1_nrr": t1_form.get("nrr", 0),
                "team2_nrr": t2_form.get("nrr", 0),
                "source": "sportmonks_api",
                "damping": round(form_damping, 2),
            },
            "venue_pitch_home": {
                "weight": WEIGHTS["venue_pitch_home"],
                "logit_contribution": round(WEIGHTS["venue_pitch_home"] * venue_logit, 4),
                "venue": venue_str,
                "venue_key": venue_key,
                "team1_home": is_t1_home,
                "team2_home": is_t2_home,
                "home_team": "team1" if is_t1_home else ("team2" if is_t2_home else "neutral"),
            },
            "h2h": {
                "weight": WEIGHTS["h2h"],
                "logit_contribution": round(WEIGHTS["h2h"] * h2h_logit, 4),
                "team1_wins": t1_h2h,
                "team2_wins": t2_h2h,
                "total": total_h2h,
                "source": h2h_source,
            },
            "toss_impact": {
                "weight": WEIGHTS["toss_impact"],
                "logit_contribution": round(WEIGHTS["toss_impact"] * toss_logit, 4),
                **toss_detail,
            },
            "bowling_depth": {
                "weight": WEIGHTS["bowling_depth"],
                "logit_contribution": round(WEIGHTS["bowling_depth"] * bowl_depth_logit, 4),
                **bowl_detail,
            },
            "conditions": {
                "weight": WEIGHTS["conditions"],
                "logit_contribution": round(WEIGHTS["conditions"] * conditions_logit, 4),
                **conditions_detail,
            },
            "momentum": {
                "weight": WEIGHTS["momentum"],
                "logit_contribution": round(WEIGHTS["momentum"] * momentum_logit, 4),
                "team1_last2": t1_last2,
                "team2_last2": t2_last2,
                "team1_wins_last2": t1_wins_last2,
                "team2_wins_last2": t2_wins_last2,
            },
        },
    }


# ── Helper Functions ──

def _compute_squad_ratings(squad_data: dict) -> Tuple:
    """Compute squad ratings from DB roster data ONLY."""
    results = {}
    details = {}
    for team_key in ["team1", "team2"]:
        players = squad_data.get(team_key, [])
        if not players:
            results[team_key] = {"batting": 50, "bowling": 50, "allrounder_depth": 0}
            details[team_key] = {}
            continue

        bat_ratings = []
        bowl_ratings = []
        allrounder_ratings = []
        for p in players:
            name = p.get("name", "")
            role = p.get("role", "Batsman")
            base_rating = STAR_PLAYERS.get(name, 65)
            overseas_bonus = 4 if p.get("isOverseas") and base_rating >= 78 else 0
            captain_bonus = 3 if p.get("isCaptain") else 0
            player_rating = min(99, base_rating + overseas_bonus + captain_bonus)

            if role == "All-rounder":
                bat_ratings.append(player_rating * ALLROUNDER_IMPACT_MULTIPLIER)
                bowl_ratings.append(player_rating * ALLROUNDER_IMPACT_MULTIPLIER)
                allrounder_ratings.append(player_rating)
            else:
                weights = ROLE_WEIGHTS.get(role, {"batting": 5, "bowling": 5})
                if weights["batting"] >= 6:
                    bat_ratings.append(player_rating)
                if weights["bowling"] >= 6:
                    bowl_ratings.append(player_rating)

        bat_avg = sum(sorted(bat_ratings, reverse=True)[:6]) / min(6, max(len(bat_ratings), 1)) if bat_ratings else 50
        bowl_avg = sum(sorted(bowl_ratings, reverse=True)[:5]) / min(5, max(len(bowl_ratings), 1)) if bowl_ratings else 50
        ar_depth = len(allrounder_ratings)

        results[team_key] = {"batting": round(bat_avg, 1), "bowling": round(bowl_avg, 1), "allrounder_depth": ar_depth}
        details[team_key] = {f"{team_key}_allrounder_count": ar_depth, f"{team_key}_top_players": len(players)}

    return (
        results.get("team1", {"batting": 50, "bowling": 50, "allrounder_depth": 0}),
        results.get("team2", {"batting": 50, "bowling": 50, "allrounder_depth": 0}),
        details.get("team1", {}),
        details.get("team2", {}),
    )


def _compute_toss_impact(venue_key: Optional[str], match_time: str, weather: dict) -> Tuple[float, dict]:
    """Category 5: Venue-specific toss impact with dew from weather."""
    detail = {"venue_key": venue_key, "is_night": False, "preferred_decision": "unknown", "toss_win_pct": 0.52}

    if not venue_key or venue_key not in TOSS_LOOKUP:
        detail["preferred_decision"] = "bowl"
        detail["toss_win_pct"] = 0.53
        # Even unknown venues have a slight chasing bias
        return 0.09, detail  # 3.0 * (0.53 - 0.50) = 0.09

    venue_data = TOSS_LOOKUP[venue_key]
    is_night = _is_night_match(match_time)
    detail["is_night"] = is_night

    # Check for dew from weather data
    dew_factor = "none"
    cricket_impact = weather.get("cricket_impact", {})
    if cricket_impact:
        dew_factor = cricket_impact.get("dew_factor", "none")

    conditions = venue_data["conditions"]
    if is_night and dew_factor in ("heavy", "moderate") and "dew" in conditions:
        selected = conditions["dew"]
        detail["condition"] = "dew"
    elif is_night and "night" in conditions:
        selected = conditions["night"]
        detail["condition"] = "night"
    elif not is_night and "day" in conditions:
        selected = conditions["day"]
        detail["condition"] = "day"
    else:
        first_key = list(conditions.keys())[0]
        selected = conditions[first_key]
        detail["condition"] = first_key

    detail["preferred_decision"] = selected["preferred"]
    detail["toss_win_pct"] = selected["toss_win_pct"]
    detail["chasing_bias"] = selected.get("chasing_bias", 0)
    detail["dew_factor"] = dew_factor

    # Compute toss logit: how much the toss winner's advantage deviates from 50%
    # A toss_win_pct of 0.625 means a 12.5% edge → logit reflects this
    toss_win_pct = selected["toss_win_pct"]
    chasing_bias = selected.get("chasing_bias", 0)
    # The logit represents venue-inherent toss advantage (not team-specific)
    # Positive = venue significantly rewards toss winner (applies pre-toss as neutral)
    # Since we don't know who wins the toss pre-match, we compute the magnitude
    # of the venue's toss sensitivity — higher values = more volatile venue
    toss_deviation = toss_win_pct - 0.50  # How much above 50% the toss winner gets
    toss_logit = 3.0 * toss_deviation + 2.0 * chasing_bias
    # Cap at reasonable range
    toss_logit = max(-1.0, min(1.0, toss_logit))
    detail["toss_logit_raw"] = round(toss_logit, 4)

    return toss_logit, detail


def _compute_bowling_depth(squad_data: dict, t1_rating: dict, t2_rating: dict) -> Tuple[float, dict]:
    """Category 6: Bowling Attack Depth from DB squad data (top 5 bowlers only, like Playing XI)."""
    detail = {}
    for team_key in ["team1", "team2"]:
        players = squad_data.get(team_key, [])
        bowler_entries = []
        pace_count = 0
        spin_count = 0

        for p in players:
            name = p.get("name", "")
            role = p.get("role", "Batsman")
            base_rating = STAR_PLAYERS.get(name, 65)

            if role in ("Bowler", "All-rounder"):
                if base_rating >= 89:
                    score = 5
                elif base_rating >= 83:
                    score = 4
                elif base_rating >= 75:
                    score = 3
                else:
                    score = 2
                bowler_entries.append({
                    "name": name, "score": score * 4, "rating": base_rating,
                    "is_pace": name in PACE_BOWLERS,
                    "is_spin": name in SPIN_BOWLERS,
                })

        # Sort by score descending & take top 5 (Playing XI bowlers)
        bowler_entries.sort(key=lambda x: x["score"], reverse=True)
        top5 = bowler_entries[:5]
        for b in top5:
            if b["is_pace"]:
                pace_count += 1
            elif b["is_spin"]:
                spin_count += 1
            else:
                pace_count += 1  # default

        total_quality = sum(b["score"] for b in top5)
        has_variety = pace_count >= 2 and spin_count >= 1
        detail[f"{team_key}_quality_score"] = round(total_quality, 1)
        detail[f"{team_key}_bowler_count"] = len(top5)
        detail[f"{team_key}_pace_count"] = pace_count
        detail[f"{team_key}_spin_count"] = spin_count
        detail[f"{team_key}_variety"] = "pace+spin" if has_variety else "one-dimensional"
        detail[f"{team_key}_variety_bonus"] = 0.3 if has_variety else 0.0

    t1_q = detail.get("team1_quality_score", 50)
    t2_q = detail.get("team2_quality_score", 50)
    t1_variety_bonus = detail.get("team1_variety_bonus", 0)
    t2_variety_bonus = detail.get("team2_variety_bonus", 0)
    # Base logit from quality difference + variety bonus
    bowl_depth_logit = 3.0 * ((t1_q - t2_q) / max(t1_q + t2_q, 1)) + (t1_variety_bonus - t2_variety_bonus)
    return bowl_depth_logit, detail


def _compute_conditions_from_weather(venue_key: Optional[str], match_time: str,
                                      weather: dict, squads: dict) -> Tuple[float, dict]:
    """Category 7: Conditions based on REAL weather data + bowler type support."""
    detail = {"is_night": False, "dew_factor": "none", "conditions_summary": "neutral",
              "temperature": None, "humidity": None, "wind_kmh": None}

    is_night = _is_night_match(match_time)
    detail["is_night"] = is_night

    if not weather or not weather.get("available"):
        detail["conditions_summary"] = "Weather data unavailable — neutral conditions assumed"
        return 0.0, detail

    current = weather.get("current", {})
    cricket_impact = weather.get("cricket_impact", {})
    detail["temperature"] = current.get("temperature")
    detail["humidity"] = current.get("humidity")
    detail["wind_kmh"] = current.get("wind_speed_kmh")
    detail["condition"] = current.get("condition", "Unknown")
    detail["dew_factor"] = cricket_impact.get("dew_factor", "none")
    detail["conditions_summary"] = cricket_impact.get("summary", "")
    detail["swing_conditions"] = cricket_impact.get("swing_conditions", "normal")

    conditions_logit = 0.0

    # Weather-based bowler advantage calculation
    humidity = current.get("humidity", 50) or 50
    temperature = current.get("temperature", 30) or 30
    wind = current.get("wind_speed_kmh", 0) or 0

    # Count pace/spin bowlers per team
    t1_pace = sum(1 for p in squads.get("team1", []) if p.get("name", "") in PACE_BOWLERS)
    t1_spin = sum(1 for p in squads.get("team1", []) if p.get("name", "") in SPIN_BOWLERS)
    t2_pace = sum(1 for p in squads.get("team2", []) if p.get("name", "") in PACE_BOWLERS)
    t2_spin = sum(1 for p in squads.get("team2", []) if p.get("name", "") in SPIN_BOWLERS)

    # Swing conditions favor pace: humid + overcast
    if humidity > 70 and temperature < 28:
        pace_bonus = 0.3 * ((t1_pace - t2_pace) / max(t1_pace + t2_pace, 1))
        conditions_logit += pace_bonus
        detail["pace_advantage"] = "team1" if t1_pace > t2_pace else "team2" if t2_pace > t1_pace else "equal"

    # Hot + dry = spin friendly
    if temperature > 35 and humidity < 40:
        spin_bonus = 0.3 * ((t1_spin - t2_spin) / max(t1_spin + t2_spin, 1))
        conditions_logit += spin_bonus
        detail["spin_advantage"] = "team1" if t1_spin > t2_spin else "team2" if t2_spin > t1_spin else "equal"

    # Strong wind penalizes shorter bowlers (lofted shots harder to control)
    if wind > 25:
        detail["wind_impact"] = "significant"

    return conditions_logit, detail


def _is_night_match(match_time: str) -> bool:
    """Determine if match is a night/evening match."""
    if not match_time:
        return True
    try:
        from datetime import datetime as dt
        parsed = dt.fromisoformat(match_time.replace("Z", "+00:00"))
        ist_hour = parsed.hour + 5 + (1 if parsed.minute >= 30 else 0)
        return ist_hour >= 15
    except Exception:
        return True


def _guess_role(name: str, squad: list) -> str:
    for p in squad:
        if p.get("name", "").lower() == name.lower():
            return p.get("role", "Batsman")
    return "Batsman"
