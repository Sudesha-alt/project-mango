"""
Pre-Match Prediction Engine — The Lucky 11 (IPL 2026)
16-Category Model — logit sum → sigmoid → team1 win %

Weights sum to 1.0. Categories combine structural squad data, SportMonks form,
venue/pitch, toss/weather, and phase-specific proxies (PP/death) where data allows.

Design Principles:
- NO web scraping. All data from DB squads, SportMonks API, or weather API.
- Squad data from ipl_squads / Expected XI paths.
- New factors use deterministic rules; missing data → neutral logit 0.
"""
import math
import re
import logging
import contextvars
from difflib import SequenceMatcher
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)
_RATINGS_OVERRIDE: contextvars.ContextVar = contextvars.ContextVar("ratings_override", default=None)

# ── Weights (16 categories, sum = 1.0) ──
# User-directed split:
# - Core composition buckets at 8% each:
#   batting_strength, batting_depth, bowling_strength, bowling_depth,
#   allrounder_strength, allrounder_depth.
# - Remaining contextual factors are rebalanced to keep total = 100%.
WEIGHTS = {
    "batting_strength": 0.08,
    "batting_depth": 0.08,
    "bowling_strength": 0.08,
    "bowling_depth": 0.08,
    "allrounder_strength": 0.08,
    "allrounder_depth": 0.08,
    "current_form": 0.08,
    "venue_pitch": 0.08,
    "home_ground_advantage": 0.04,
    "h2h": 0.065,
    "conditions": 0.05,
    "momentum": 0.035,
    "powerplay_performance": 0.055,
    "death_overs_performance": 0.055,
    "key_players_availability": 0.03,
    "top_order_consistency": 0.03,
}

# ── Toss Lookup (from user-provided venue-specific data) ──
TOSS_LOOKUP = {
    "wankhede": {
        "city": "mumbai",
        "default_decision": "bowl",
        "pitch_type": "batting-friendly",
        "avg_first_innings": 175,
        "batting_first_win_pct": 0.42,
        "pace_assist": 0.4,
        "spin_assist": 0.3,
        "conditions": {
            "night":     {"preferred": "bowl", "toss_win_pct": 0.65, "chasing_bias": 0.15, "weight": "HIGH"},
            "day":       {"preferred": "bat",  "toss_win_pct": 0.535, "chasing_bias": 0.0,  "weight": "MED"},
            "dew":       {"preferred": "bowl", "toss_win_pct": 0.70, "chasing_bias": 0.15, "weight": "VERY HIGH"},
        },
    },
    "chepauk": {
        "city": "chennai",
        "default_decision": "bat",
        "pitch_type": "spin-friendly",
        "avg_first_innings": 162,
        "batting_first_win_pct": 0.55,
        "pace_assist": 0.2,
        "spin_assist": 0.8,
        "conditions": {
            "normal":    {"preferred": "bat",  "toss_win_pct": 0.60, "chasing_bias": 0.0,  "weight": "HIGH"},
            "dry":       {"preferred": "bat",  "toss_win_pct": 0.65, "chasing_bias": 0.0,  "weight": "VERY HIGH"},
        },
    },
    "chinnaswamy": {
        "city": "bangalore",
        "default_decision": "bowl",
        "pitch_type": "high-scoring",
        "avg_first_innings": 183,
        "batting_first_win_pct": 0.40,
        "pace_assist": 0.5,
        "spin_assist": 0.2,
        "conditions": {
            "high_scoring": {"preferred": "bowl", "toss_win_pct": 0.575, "chasing_bias": 0.12, "weight": "HIGH"},
            "dew":          {"preferred": "bowl", "toss_win_pct": 0.65,  "chasing_bias": 0.12, "weight": "VERY HIGH"},
        },
    },
    "narendra_modi": {
        "city": "ahmedabad",
        "default_decision": "bowl",
        "pitch_type": "balanced",
        "avg_first_innings": 170,
        "batting_first_win_pct": 0.47,
        "pace_assist": 0.4,
        "spin_assist": 0.5,
        "conditions": {
            "black_soil": {"preferred": "bat",  "toss_win_pct": 0.58, "chasing_bias": 0.0,  "weight": "MED"},
            "red_soil":   {"preferred": "bowl", "toss_win_pct": 0.60, "chasing_bias": 0.0,  "weight": "MED"},
            "night":      {"preferred": "bowl", "toss_win_pct": 0.62, "chasing_bias": 0.0,  "weight": "HIGH"},
        },
    },
    "eden_gardens": {
        "city": "kolkata",
        "default_decision": "bowl",
        "pitch_type": "balanced",
        "avg_first_innings": 172,
        "batting_first_win_pct": 0.43,
        "pace_assist": 0.5,
        "spin_assist": 0.4,
        "conditions": {
            "night":      {"preferred": "bowl", "toss_win_pct": 0.625, "chasing_bias": 0.10, "weight": "HIGH"},
            "spin":       {"preferred": "bat",  "toss_win_pct": 0.55,  "chasing_bias": 0.0,  "weight": "MED"},
        },
    },
    "arun_jaitley": {
        "city": "delhi",
        "default_decision": "bat",
        "pitch_type": "slow-low",
        "avg_first_innings": 168,
        "batting_first_win_pct": 0.51,
        "pace_assist": 0.3,
        "spin_assist": 0.6,
        "conditions": {
            "slow":       {"preferred": "bat",  "toss_win_pct": 0.58, "chasing_bias": 0.0,  "weight": "HIGH"},
            "small":      {"preferred": "bowl", "toss_win_pct": 0.55, "chasing_bias": 0.0,  "weight": "MED"},
        },
    },
    "rajiv_gandhi": {
        "city": "hyderabad",
        "default_decision": "bowl",
        "pitch_type": "pace-friendly",
        "avg_first_innings": 176,
        "batting_first_win_pct": 0.44,
        "pace_assist": 0.7,
        "spin_assist": 0.2,
        "conditions": {
            "night":      {"preferred": "bowl", "toss_win_pct": 0.60, "chasing_bias": 0.08, "weight": "HIGH"},
        },
    },
    "mohali": {
        "city": "mohali",
        "default_decision": "bowl",
        "pitch_type": "pace-friendly",
        "avg_first_innings": 173,
        "batting_first_win_pct": 0.45,
        "pace_assist": 0.7,
        "spin_assist": 0.2,
        "conditions": {
            "night":      {"preferred": "bowl", "toss_win_pct": 0.625, "chasing_bias": 0.0, "weight": "HIGH"},
        },
    },
    "sawai_mansingh": {
        "city": "jaipur",
        "default_decision": "bowl",
        "pitch_type": "spin-friendly",
        "avg_first_innings": 167,
        "batting_first_win_pct": 0.48,
        "pace_assist": 0.3,
        "spin_assist": 0.7,
        "conditions": {
            "night":      {"preferred": "bowl", "toss_win_pct": 0.56, "chasing_bias": 0.06, "weight": "MED"},
        },
    },
    "ekana": {
        "city": "lucknow",
        "default_decision": "bowl",
        "pitch_type": "balanced",
        "avg_first_innings": 169,
        "batting_first_win_pct": 0.46,
        "pace_assist": 0.5,
        "spin_assist": 0.4,
        "conditions": {
            "night":      {"preferred": "bowl", "toss_win_pct": 0.57, "chasing_bias": 0.07, "weight": "MED"},
        },
    },
    "barsapara": {
        "city": "guwahati",
        "default_decision": "bowl",
        "pitch_type": "pace-friendly",
        "avg_first_innings": 171,
        "batting_first_win_pct": 0.44,
        "pace_assist": 0.6,
        "spin_assist": 0.3,
        "conditions": {
            "night": {"preferred": "bowl", "toss_win_pct": 0.55, "chasing_bias": 0.05, "weight": "MED"},
        },
    },
    "hpca": {
        "city": "dharamshala",
        "default_decision": "bowl",
        "pitch_type": "batting-friendly",
        "avg_first_innings": 178,
        "batting_first_win_pct": 0.42,
        "pace_assist": 0.5,
        "spin_assist": 0.2,
        "conditions": {
            "night": {"preferred": "bowl", "toss_win_pct": 0.56, "chasing_bias": 0.06, "weight": "MED"},
        },
    },
    "shaheed_veer_narayan": {
        "city": "raipur",
        "default_decision": "bowl",
        "pitch_type": "balanced",
        "avg_first_innings": 166,
        "batting_first_win_pct": 0.48,
        "pace_assist": 0.4,
        "spin_assist": 0.4,
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

# Home ground mapping (primary + secondary venues)
HOME_GROUNDS = {
    "mumbai indians": ["wankhede"],
    "chennai super kings": ["chepauk"],
    "royal challengers bengaluru": ["chinnaswamy"],
    "royal challengers bangalore": ["chinnaswamy"],
    "gujarat titans": ["narendra_modi"],
    "kolkata knight riders": ["eden_gardens"],
    "delhi capitals": ["arun_jaitley"],
    "sunrisers hyderabad": ["rajiv_gandhi"],
    "punjab kings": ["mohali", "hpca"],
    "rajasthan royals": ["sawai_mansingh", "barsapara"],
    "lucknow super giants": ["ekana"],
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
    "WK-Batsman": {"batting": 7, "bowling": 0},
    "All-rounder": {"batting": 6, "bowling": 6},
    "Bowler": {"batting": 2, "bowling": 9},
}

ALLROUNDER_IMPACT_MULTIPLIER = 1.35


def _canonical_xi_role(raw: Optional[str]) -> str:
    """Normalize XI role strings (Claude / DB / APIs) to ROLE_WEIGHTS keys."""
    if raw is None or not str(raw).strip():
        return "Batsman"
    r = str(raw).strip()
    if r in ROLE_WEIGHTS:
        return r
    s = r.lower().replace("-", " ").replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    if "wicket" in s or s in ("wk", "keeper", "wk batsman") or s.startswith("wk "):
        return "Wicketkeeper"
    if "all" in s and "round" in s:
        return "All-rounder"
    if "bowl" in s:
        return "Bowler"
    if "bat" in s:
        return "Batsman"
    return "Batsman"


def _normalize_remapped_squad_roles(remapped_squads: dict) -> None:
    for side in ("team1", "team2"):
        for p in remapped_squads.get(side) or []:
            if isinstance(p, dict):
                p["role"] = _canonical_xi_role(p.get("role"))


def _player_effective_rating(p: dict) -> float:
    name = p.get("name", "")
    base = float(resolve_star_player_rating(name))
    overseas_bonus = 4 if p.get("isOverseas") and base >= 78 else 0
    captain_bonus = 3 if p.get("isCaptain") else 0
    return float(min(99, base + overseas_bonus + captain_bonus))


def _team_batting_strength_index(players: list) -> float:
    """Top-6 batting pool by XI role (Batsman / WK / AR per ROLE_WEIGHTS)."""
    bat_ratings: List[float] = []
    for p in players:
        if not isinstance(p, dict):
            continue
        role = _canonical_xi_role(p.get("role"))
        pr = _player_effective_rating(p)
        if role == "All-rounder":
            bat_ratings.append(pr * ALLROUNDER_IMPACT_MULTIPLIER)
        else:
            weights = ROLE_WEIGHTS.get(role, {"batting": 5, "bowling": 5})
            if weights["batting"] >= 6:
                bat_ratings.append(pr)
    if not bat_ratings:
        return 50.0
    top6 = sorted(bat_ratings, reverse=True)[:6]
    return sum(top6) / len(top6)


def _team_bowling_strength_index(players: list) -> float:
    """Top-5 bowling pool by XI role (Bowler / AR / listed specialist)."""
    bowl_ratings: List[float] = []
    for p in players:
        if not isinstance(p, dict):
            continue
        role = _canonical_xi_role(p.get("role"))
        name = p.get("name", "")
        pr = _player_effective_rating(p)
        if role == "All-rounder":
            bowl_ratings.append(pr * ALLROUNDER_IMPACT_MULTIPLIER)
        else:
            weights = ROLE_WEIGHTS.get(role, {"batting": 5, "bowling": 5})
            if weights["bowling"] >= 6:
                bowl_ratings.append(pr)
            elif weights["bowling"] < 6 and _is_listed_primary_bowler(name):
                bowl_ratings.append(pr)
    if not bowl_ratings:
        return 50.0
    top5 = sorted(bowl_ratings, reverse=True)[:5]
    return sum(top5) / len(top5)


def _team_batting_depth_tail_index(players: list) -> float:
    """Avg rating of 7th–11th batting-role contributors (middle/lower order depth)."""
    br: List[float] = []
    for p in players:
        if not isinstance(p, dict):
            continue
        role = _canonical_xi_role(p.get("role"))
        rw = ROLE_WEIGHTS.get(role, {"batting": 5, "bowling": 5})
        pr = _player_effective_rating(p)
        if role == "All-rounder":
            br.append(pr)
        elif rw["batting"] >= 6:
            br.append(pr)
    br.sort(reverse=True)
    tail = br[6:11] if len(br) > 6 else []
    if not tail:
        return 50.0
    return sum(tail) / len(tail)


def _team_allrounder_ratings(players: list) -> List[float]:
    out: List[float] = []
    for p in players:
        if not isinstance(p, dict):
            continue
        if _canonical_xi_role(p.get("role")) == "All-rounder":
            out.append(_player_effective_rating(p))
    return out


def _duel_share_pct(a: float, b: float) -> Tuple[int, int]:
    """Split two non-negative scores into whole percentages (sum100) — who leads on this axis."""
    a = max(0.0, float(a))
    b = max(0.0, float(b))
    tot = a + b
    if tot <= 0:
        return 50, 50
    p1 = int(round(100.0 * a / tot))
    p1 = max(0, min(100, p1))
    return p1, 100 - p1


def _safe_mean(vals: List[float], default: float = 0.0) -> float:
    return float(sum(vals) / len(vals)) if vals else float(default)


def _safe_std(vals: List[float]) -> float:
    """Population std-dev with 0 fallback for <2 samples."""
    if len(vals) < 2:
        return 0.0
    mu = _safe_mean(vals, 0.0)
    var = sum((x - mu) ** 2 for x in vals) / len(vals)
    return math.sqrt(max(0.0, var))


def _percentile(values: List[float], q: float, default: float = 50.0) -> float:
    """Simple linear-interpolated percentile for q in [0,1]."""
    if not values:
        return float(default)
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    pos = max(0.0, min(1.0, q)) * (len(xs) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def compute_team_strength_metrics_from_impact(
    players: List[dict],
    *,
    n_bat: int = 5,
    m_bowl: int = 4,
    alpha: float = 0.5,
    theta_bowl: float = 50.0,
    theta_ar: float = 50.0,
    arip_max: float = 100.0,
) -> dict:
    """
    Compute 6 team metrics from per-player impact points.

    Required per player: player_role (BAT/BOWL/AR), BatIP, BowlIP.
    Optional: batting_position, bowling_order (informational/traceability).
    """
    rows = [p for p in (players or []) if isinstance(p, dict)]
    bat_ips = [max(0.0, min(100.0, float(p.get("BatIP", 0.0)))) for p in rows]
    bowl_ips = [max(0.0, min(100.0, float(p.get("BowlIP", 0.0)))) for p in rows]

    top_bat = sorted(bat_ips, reverse=True)[: max(1, n_bat)]
    while len(top_bat) < max(1, n_bat):
        top_bat.append(0.0)
    bat_weights = [(n_bat + 1 - i) / max(1, n_bat) for i in range(1, n_bat + 1)]
    bat_w_sum = sum(bat_weights) or 1.0
    batting_strength = sum(w * x for w, x in zip(bat_weights, top_bat)) / bat_w_sum
    bat_mean = _safe_mean(top_bat, 0.0)
    batting_depth = 1.0 - (_safe_std(top_bat) / bat_mean) if bat_mean > 0 else 0.0
    batting_depth = max(0.0, min(1.0, batting_depth))

    top_bowl = sorted(bowl_ips, reverse=True)[: max(1, m_bowl)]
    while len(top_bowl) < max(1, m_bowl):
        top_bowl.append(0.0)
    bowl_weights = [(m_bowl + 1 - j) / max(1, m_bowl) for j in range(1, m_bowl + 1)]
    bowl_w_sum = sum(bowl_weights) or 1.0
    bowling_strength = sum(v * x for v, x in zip(bowl_weights, top_bowl)) / bowl_w_sum
    bowling_depth = sum(1 for x in top_bowl if x >= float(theta_bowl)) / float(max(1, m_bowl))

    ar_rows = [p for p in rows if str(p.get("player_role", "")).upper() == "AR"]
    ar_ips = [
        max(0.0, min(100.0, alpha * float(p.get("BatIP", 0.0)) + (1.0 - alpha) * float(p.get("BowlIP", 0.0))))
        for p in ar_rows
    ]
    allrounder_strength = _safe_mean(ar_ips, 0.0) if ar_ips else 0.0
    if ar_ips:
        ar_count_ratio = sum(1 for x in ar_ips if x >= float(theta_ar)) / float(len(ar_ips))
        arip_cap = max(1e-6, float(arip_max))
        allrounder_depth = ar_count_ratio * (allrounder_strength / arip_cap)
    else:
        allrounder_depth = 0.0
    allrounder_depth = max(0.0, min(1.0, allrounder_depth))

    return {
        "batting_strength": round(float(batting_strength), 4),
        "batting_depth": round(float(batting_depth), 4),
        "bowling_strength": round(float(bowling_strength), 4),
        "bowling_depth": round(float(bowling_depth), 4),
        "allrounder_strength": round(float(allrounder_strength), 4),
        "allrounder_depth": round(float(allrounder_depth), 4),
    }


def compute_strength_metrics_for_match(
    team_players: Dict[str, List[dict]],
    *,
    n_bat: int = 5,
    m_bowl: int = 4,
    alpha: float = 0.5,
) -> dict:
    """
    Compute all 6 required metrics for team1/team2 with dataset thresholds.

    Thresholds are derived from the union of both teams' current player rows:
    - theta_bat: P50 of BatIP
    - theta_bowl: P50 of BowlIP
    - theta_AR: P50 of ARIP
    - ARIP_max: max ARIP
    """
    t1_rows = list(team_players.get("team1") or [])
    t2_rows = list(team_players.get("team2") or [])
    all_rows = [*t1_rows, *t2_rows]
    bat_all = [float(p.get("BatIP", 0.0)) for p in all_rows if isinstance(p, dict)]
    bowl_all = [float(p.get("BowlIP", 0.0)) for p in all_rows if isinstance(p, dict)]
    ar_all = [
        alpha * float(p.get("BatIP", 0.0)) + (1.0 - alpha) * float(p.get("BowlIP", 0.0))
        for p in all_rows
        if isinstance(p, dict) and str(p.get("player_role", "")).upper() == "AR"
    ]
    theta_bat = _percentile(bat_all, 0.5, default=50.0)
    theta_bowl = _percentile(bowl_all, 0.5, default=50.0)
    theta_ar = _percentile(ar_all, 0.5, default=50.0)
    arip_max = max(ar_all) if ar_all else 100.0

    config = {
        "N": int(n_bat),
        "M": int(m_bowl),
        "alpha": float(alpha),
        "theta_bat": round(theta_bat, 4),
        "theta_bowl": round(theta_bowl, 4),
        "theta_AR": round(theta_ar, 4),
        "ARIP_max": round(float(arip_max), 4),
    }
    return {
        "config": config,
        "team1": compute_team_strength_metrics_from_impact(
            t1_rows,
            n_bat=n_bat,
            m_bowl=m_bowl,
            alpha=alpha,
            theta_bowl=theta_bowl,
            theta_ar=theta_ar,
            arip_max=arip_max,
        ),
        "team2": compute_team_strength_metrics_from_impact(
            t2_rows,
            n_bat=n_bat,
            m_bowl=m_bowl,
            alpha=alpha,
            theta_bowl=theta_bowl,
            theta_ar=theta_ar,
            arip_max=arip_max,
        ),
    }


# Roles counted as batting contributors for dew/chase heuristics (must match DB seed labels)
BAT_ROLES_DEW = frozenset({"Batsman", "Wicketkeeper", "WK-Batsman", "All-rounder"})

# Short labels for overall favourite explanation (weighted driver)
FACTOR_SUMMARY_PHRASES = {
    "batting_strength": "top-order and core batting quality",
    "batting_depth": "middle and lower-order batting depth",
    "bowling_strength": "top-end bowling quality",
    "bowling_depth": "attack depth for this venue",
    "allrounder_strength": "all-rounder quality impact",
    "allrounder_depth": "all-rounder count and flexibility",
    "current_form": "recent league form",
    "venue_pitch": "pitch profile suitability (green/dry/dusty)",
    "home_ground_advantage": "home ground familiarity",
    "h2h": "head-to-head record",
    "conditions": "wet/dry weather-to-skill correlation",
    "momentum": "last-two-results momentum",
    "powerplay_performance": "powerplay batting/bowling profile",
    "death_overs_performance": "death overs specialists",
    "key_players_availability": "key player availability in the XI",
    "top_order_consistency": "top-order scoring consistency",
}

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
    team_venues = HOME_GROUNDS.get(team_name.lower().strip(), [])
    return venue_key in team_venues if team_venues else False


def _effective_player_rating(name: str) -> float:
    return float(resolve_star_player_rating(name or ""))


def _batting_strength_logit(t1_rating: dict, t2_rating: dict) -> float:
    """Uses squad batting indices (role-based top-6 batting pool)."""
    t1 = float(t1_rating.get("batting", 50))
    t2 = float(t2_rating.get("batting", 50))
    return 3.2 * ((t1 - t2) / 100.0)


def _batting_depth_logit(remapped_squads: dict) -> float:
    """7th–11th batting-role contributors — middle/lower order depth (XI roles)."""
    if not remapped_squads.get("team1") or not remapped_squads.get("team2"):
        return 0.0
    t1 = _team_batting_depth_tail_index(remapped_squads["team1"])
    t2 = _team_batting_depth_tail_index(remapped_squads["team2"])
    return 2.5 * ((t1 - t2) / 100.0)


def _bowling_strength_logit(remapped_squads: dict) -> float:
    """Top-5 bowling pool by XI role (Bowler / All-rounder / listed specialist)."""
    if not remapped_squads.get("team1") or not remapped_squads.get("team2"):
        return 0.0
    t1 = _team_bowling_strength_index(remapped_squads["team1"])
    t2 = _team_bowling_strength_index(remapped_squads["team2"])
    return 3.0 * ((t1 - t2) / 100.0)


def _allrounder_depth_logit(t1_rating: dict, t2_rating: dict) -> float:
    a1 = float(t1_rating.get("allrounder_depth", 0))
    a2 = float(t2_rating.get("allrounder_depth", 0))
    tot = max(1.0, a1 + a2)
    return 2.0 * ((a1 - a2) / tot)


def _allrounder_strength_logit(t1_rating: dict, t2_rating: dict) -> float:
    a1 = float(t1_rating.get("allrounder_strength", 50))
    a2 = float(t2_rating.get("allrounder_strength", 50))
    return 2.8 * ((a1 - a2) / 100.0)


def _powerplay_performance_logit(remapped_squads: dict) -> float:
    """Proxy: average rating of two strongest listed batters (PP batting profile)."""

    def top2_bat(players: list) -> float:
        bats = []
        for p in players:
            if _canonical_xi_role(p.get("role")) in BAT_ROLES_DEW:
                bats.append(_player_effective_rating(p))
        bats.sort(reverse=True)
        if not bats:
            return 50.0
        if len(bats) == 1:
            return bats[0]
        return (bats[0] + bats[1]) / 2

    if not remapped_squads.get("team1") or not remapped_squads.get("team2"):
        return 0.0
    t1, t2 = top2_bat(remapped_squads["team1"]), top2_bat(remapped_squads["team2"])
    return 2.0 * ((t1 - t2) / 100.0)


def _death_overs_performance_logit(remapped_squads: dict) -> float:
    """Proxy: blend top-3 bowler ratings with top-3 finisher batting ratings."""

    def death_idx(players: list) -> float:
        bowlers = []
        for p in players:
            nm = p.get("name", "")
            role = _canonical_xi_role(p.get("role"))
            rw = ROLE_WEIGHTS.get(role, {"batting": 5, "bowling": 5})
            if rw["bowling"] >= 6 or nm in PACE_BOWLERS or nm in SPIN_BOWLERS:
                bowlers.append(_player_effective_rating(p))
        bowlers.sort(reverse=True)
        bavg = sum(bowlers[:3]) / min(3, max(len(bowlers), 1)) if bowlers else 50.0
        bats = []
        for p in players:
            if _canonical_xi_role(p.get("role")) in BAT_ROLES_DEW:
                bats.append(_player_effective_rating(p))
        bats.sort(reverse=True)
        favg = sum(bats[:3]) / min(3, max(len(bats), 1)) if bats else 50.0
        return 0.55 * bavg + 0.45 * favg

    if not remapped_squads.get("team1") or not remapped_squads.get("team2"):
        return 0.0
    t1, t2 = death_idx(remapped_squads["team1"]), death_idx(remapped_squads["team2"])
    return 2.2 * ((t1 - t2) / 100.0)


def _key_players_availability_logit(remapped_squads: dict) -> float:
    """XI rows may set available=False or injury_status out/doubtful — tilts toward healthier side."""

    def issues(players: list) -> float:
        n = 0.0
        for pl in players:
            if pl.get("available") is False:
                n += 1.0
            st = (pl.get("injury_status") or pl.get("status") or "").lower()
            if st in ("out", "injured", "doubtful", "unavailable"):
                n += 1.0
        return n

    if not remapped_squads.get("team1") or not remapped_squads.get("team2"):
        return 0.0
    diff = issues(remapped_squads["team2"]) - issues(remapped_squads["team1"])
    return 0.35 * diff


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _player_perf_row_for_name(team_perf: dict, player_name: str) -> dict:
    if not team_perf or not player_name:
        return {}
    pnorm = _normalize_name(player_name)
    for _, row in team_perf.items():
        if not isinstance(row, dict):
            continue
        nm = row.get("name", "")
        if not nm:
            continue
        nn = _normalize_name(nm)
        if pnorm == nn or pnorm in nn or nn in pnorm:
            return row
    return {}


def _activity_points_from_perf(perf_row: dict) -> float:
    if not perf_row:
        return 0.0
    bat = perf_row.get("batting", {}) or {}
    bowl = perf_row.get("bowling", {}) or {}
    runs = float(bat.get("runs", 0) or 0)
    sr = float(bat.get("sr", 0) or 0)
    wickets = float(bowl.get("wickets", 0) or 0)
    econ = float(bowl.get("economy", 12) or 12)
    matches = float(perf_row.get("matches", 0) or 0)
    run_pts = 0.28 * runs
    sr_bonus = max(0.0, sr - 120.0) * 0.10
    wkt_pts = 18.0 * wickets
    econ_bonus = max(0.0, 8.5 - econ) * 8.0
    match_bonus = min(10.0, matches * 1.4)
    return max(0.0, min(160.0, run_pts + sr_bonus + wkt_pts + econ_bonus + match_bonus))


def _team_xi_activity_sum(team_players: list, team_perf: dict) -> float:
    total = 0.0
    for p in team_players or []:
        row = _player_perf_row_for_name(team_perf or {}, p.get("name", ""))
        total += _activity_points_from_perf(row)
    return total


def _allrounder_activity_indices(remapped_squads: dict, player_performance: dict) -> Tuple[float, float, float, float]:
    def team_vals(team_key: str) -> Tuple[float, float]:
        players = remapped_squads.get(team_key, []) or []
        perf = player_performance.get(team_key, {}) if isinstance(player_performance, dict) else {}
        ars = []
        depth = 0.0
        for p in players:
            if _canonical_xi_role(p.get("role")) != "All-rounder":
                continue
            depth += 1.0
            rt = _player_effective_rating(p)
            prow = _player_perf_row_for_name(perf, p.get("name", ""))
            ap = _activity_points_from_perf(prow)
            ars.append(0.65 * rt + 0.35 * min(100.0, ap))
            if prow:
                depth += 0.35  # reward actively used all-rounders in season sample
        strength = sum(sorted(ars, reverse=True)[:3]) / min(3, max(1, len(ars))) if ars else 50.0
        return strength, depth

    t1s, t1d = team_vals("team1")
    t2s, t2d = team_vals("team2")
    return t1s, t2s, t1d, t2d


def _powerplay_performance_logit_from_web(web_context: dict) -> Optional[float]:
    pp = (web_context or {}).get("powerplay") or {}
    try:
        t1_runs = float(pp.get("team1_avg_pp_score"))
        t2_runs = float(pp.get("team2_avg_pp_score"))
        t1_wk = float(pp.get("team1_avg_pp_wickets_lost"))
        t2_wk = float(pp.get("team2_avg_pp_wickets_lost"))
    except (TypeError, ValueError):
        return None
    t1 = (t1_runs / 60.0) - (t1_wk / 4.0)
    t2 = (t2_runs / 60.0) - (t2_wk / 4.0)
    return 2.8 * (t1 - t2)


def _death_overs_performance_logit_from_web(web_context: dict) -> Optional[float]:
    d = (web_context or {}).get("death_overs") or {}
    try:
        t1s = float(d.get("team1_avg_death_score"))
        t1c = float(d.get("team1_avg_death_conceded"))
        t2s = float(d.get("team2_avg_death_score"))
        t2c = float(d.get("team2_avg_death_conceded"))
    except (TypeError, ValueError):
        return None
    t1 = (t1s - t1c) / 30.0
    t2 = (t2s - t2c) / 30.0
    return 2.6 * (t1 - t2)


def _key_players_availability_logit_from_web(web_context: dict) -> Optional[float]:
    inj = (web_context or {}).get("injuries") or {}
    t1 = inj.get("team1_injuries") or []
    t2 = inj.get("team2_injuries") or []
    try:
        t1_impact = sum(float(x.get("impact_score", 0) or 0) for x in t1 if isinstance(x, dict))
        t2_impact = sum(float(x.get("impact_score", 0) or 0) for x in t2 if isinstance(x, dict))
    except (TypeError, ValueError):
        return None
    # More impact lost on team2 should favor team1 (positive logit)
    return 0.08 * (t2_impact - t1_impact)


def _top_order_consistency_logit(form_data: dict) -> float:
    """Lower spread in top-3 form_score among top_performers → higher consistency index."""

    def consistency(team_key: str) -> float:
        tp = (form_data.get(team_key) or {}).get("top_performers") or []
        scores = []
        for x in tp[:5]:
            if not isinstance(x, dict):
                continue
            s = x.get("form_score")
            if s is None:
                continue
            try:
                scores.append(float(s))
            except (TypeError, ValueError):
                continue
        if len(scores) < 2:
            return 50.0
        top3 = sorted(scores, reverse=True)[:3]
        if len(top3) < 2:
            return 50.0
        mean = sum(top3) / len(top3)
        var = sum((x - mean) ** 2 for x in top3) / len(top3)
        return max(0.0, min(100.0, 100.0 - min(40.0, var * 2.0)))

    t1c = consistency("team1")
    t2c = consistency("team2")
    return 1.8 * ((t1c - t2c) / 100.0)


def _favours_from_logit(logit: float, eps: float = 0.015) -> str:
    """Map a team1-oriented logit to which side is favoured."""
    if logit > eps:
        return "team1"
    if logit < -eps:
        return "team2"
    return "neutral"


def _norm_name_key(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _vaibhav_suryavanshi_family_key(name: str) -> Optional[str]:
    n = _norm_name_key(name)
    if "vaibhav" in n and "vanshi" in n:
        return "vaibhav_suryavanshi"
    return None


def resolve_star_player_rating(name: str) -> int:
    """Map SportMonks / XI name spellings to STAR_PLAYERS card rating (default 65)."""
    if not name or not str(name).strip():
        return 65
    name = str(name).strip()
    overrides = _RATINGS_OVERRIDE.get() or {}
    if name in overrides:
        return int(overrides[name])
    if name in STAR_PLAYERS:
        return STAR_PLAYERS[name]
    nl = name.lower()
    for k, v in overrides.items():
        if k.lower() == nl:
            return int(v)
    for k, v in STAR_PLAYERS.items():
        if k.lower() == nl:
            return v
    vk = _vaibhav_suryavanshi_family_key(name)
    if vk:
        for k, v in STAR_PLAYERS.items():
            if _vaibhav_suryavanshi_family_key(k):
                return v
    nn = _norm_name_key(name)
    if not nn:
        return 65
    nparts = nn.split()
    fi = nparts[0][0] if nparts and nparts[0] else ""
    best_rating = 65
    best_ratio = 0.0
    for k, v in STAR_PLAYERS.items():
        kn = _norm_name_key(k)
        if not kn:
            continue
        kparts = kn.split()
        ki = kparts[0][0] if kparts and kparts[0] else ""
        if fi and ki and fi != ki:
            continue
        ratio = SequenceMatcher(None, nn, kn).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_rating = v
    if best_ratio >= 0.88:
        return best_rating
    for k, v in STAR_PLAYERS.items():
        kn = _norm_name_key(k)
        if len(nn) >= 8 and kn and (nn in kn or kn in nn):
            return v
    return 65


def _name_matches_any_member(name: str, pool: set) -> bool:
    """Fuzzy match XI/API names to curated PACE_BOWLERS / SPIN_BOWLERS sets."""
    if not name or not pool:
        return False
    if name in pool:
        return True
    nn = _norm_name_key(name)
    if not nn:
        return False
    nparts = nn.split()
    fi = nparts[0][0] if nparts and nparts[0] else ""
    best_ratio = 0.0
    for candidate in pool:
        cn = _norm_name_key(candidate)
        if not cn:
            continue
        if nn == cn:
            return True
        if len(nn) >= 6 and len(cn) >= 6 and (nn in cn or cn in nn):
            return True
        cparts = cn.split()
        ci = cparts[0][0] if cparts and cparts[0] else ""
        if fi and ci and fi != ci:
            continue
        ratio = SequenceMatcher(None, nn, cn).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
    return best_ratio >= 0.86


def _is_listed_pace_bowler(name: str) -> bool:
    return _name_matches_any_member(name, PACE_BOWLERS)


def _is_listed_spin_bowler(name: str) -> bool:
    return _name_matches_any_member(name, SPIN_BOWLERS)


def _is_listed_primary_bowler(name: str) -> bool:
    return _is_listed_pace_bowler(name) or _is_listed_spin_bowler(name)


def _is_bowling_contributor(p: dict) -> bool:
    """True if this XI player should count in bowling depth / pace-spin tallies."""
    role = _canonical_xi_role(p.get("role"))
    if role in ("Bowler", "All-rounder"):
        return True
    return _is_listed_primary_bowler(p.get("name", ""))


def _chase_strength_index(players: List[dict]) -> float:
    """0–1 index: stronger top-order chasing depth → higher. Neutral 0.5 if no data."""
    ratings = []
    for p in players:
        if _canonical_xi_role(p.get("role")) not in BAT_ROLES_DEW:
            continue
        ratings.append(resolve_star_player_rating(p.get("name", "")))
    if not ratings:
        return 0.5
    top6 = sorted(ratings, reverse=True)[:6]
    avg = sum(top6) / len(top6)
    return max(0.0, min(1.0, (avg - 50.0) / 45.0))


def _team_label(team_key: str, team1: str, team2: str) -> str:
    return team1 if team_key == "team1" else team2 if team_key == "team2" else team_key


def compute_prediction(squad_data: Dict = None, match_info: Dict = None,
                        weather: Dict = None, form_data: Dict = None,
                        momentum_data: Dict = None, player_performance: Dict = None,
                        web_context: Dict = None, team_strength_metrics: Dict = None) -> Dict:
    """
    16-Category Pre-Match Prediction Engine (The Lucky 11, IPL 2026).
    NO web scraping. All data from DB squads, SportMonks API, or weather API.
    player_performance: Optional dict with "team1" and "team2" keys containing
    per-player batting/bowling stats from SportMonks.
    """
    match_info = match_info or {}
    squad_data = squad_data or {}
    weather = weather or {}
    form_data = form_data or {}
    momentum_data = momentum_data or {}
    player_performance = player_performance or {}
    web_context = web_context or {}
    team_strength_metrics = team_strength_metrics or {}

    team1 = match_info.get("team1", "")
    team2 = match_info.get("team2", "")
    venue_str = match_info.get("venue", "")
    venue_key = _match_venue(venue_str)
    match_time = match_info.get("dateTimeGMT", "")

    def _squad_list_for_team(label: str) -> list:
        if not label or not squad_data:
            return []
        if label in squad_data:
            return squad_data[label] or []
        ll = label.lower().strip()
        for k, v in squad_data.items():
            if (k or "").lower().strip() == ll:
                return v or []
        return []

    # Remap squad_data to team1/team2 using schedule labels (dict key order is not reliable)
    remapped_squads = {}
    if squad_data:
        remapped_squads = {
            "team1": _squad_list_for_team(team1),
            "team2": _squad_list_for_team(team2),
        }
    if remapped_squads.get("team1") and remapped_squads.get("team2"):
        _normalize_remapped_squad_roles(remapped_squads)

    # ── Enhance squad ratings with actual player performance stats ──
    # Override STAR_PLAYERS ratings with real form data where available
    perf_overrides = {}
    for team_key in ["team1", "team2"]:
        team_perf = player_performance.get(team_key, {})
        for pid, ps in team_perf.items():
            name = ps.get("name", "")
            if not name:
                continue
            matches = ps.get("matches", 0)
            if matches < 1:
                continue
            bat = ps.get("batting", {})
            bowl = ps.get("bowling", {})
            # Compute dynamic rating from actual performance
            base = resolve_star_player_rating(name)
            adj = 0
            if bat.get("innings", 0) > 0:
                bat_avg = bat.get("avg", 0)
                bat_sr = bat.get("sr", 0)
                # Avg 30+, SR 140+ = excellent form (+5 to +10)
                if bat_avg >= 30 and bat_sr >= 140:
                    adj += min(10, (bat_avg - 25) * 0.3 + (bat_sr - 130) * 0.05)
                elif bat_avg < 15:
                    adj -= min(8, (15 - bat_avg) * 0.4)  # Poor form penalty
            if bowl.get("innings", 0) > 0:
                economy = bowl.get("economy", 12)
                wpi = bowl.get("wickets", 0) / bowl["innings"]
                if economy < 7.5 and wpi > 1:
                    adj += min(8, (8 - economy) * 2 + wpi * 2)
                elif economy > 10:
                    adj -= min(6, (economy - 10) * 1.5)

            # Clamp adjustment and apply
            adj = max(-12, min(12, adj))
            perf_overrides[name] = round(max(50, min(99, base + adj)))

    # Per-request ratings override (context-local, avoids global mutable races).
    rtok = _RATINGS_OVERRIDE.set(perf_overrides)

    # ━━━━━━ Core team composition ratings (bat/bowl/all-round) ━━━━━━
    if remapped_squads.get("team1") and remapped_squads.get("team2"):
        t1_rating, t2_rating, t1_squad_detail, t2_squad_detail = _compute_squad_ratings(remapped_squads)
    else:
        t1_rating = {"batting": 75, "bowling": 75, "allrounder_depth": 0, "allrounder_strength": 50}
        t2_rating = {"batting": 75, "bowling": 75, "allrounder_depth": 0, "allrounder_strength": 50}
        t1_squad_detail = t2_squad_detail = {}

    t1_strength = team_strength_metrics.get("team1") if isinstance(team_strength_metrics, dict) else None
    t2_strength = team_strength_metrics.get("team2") if isinstance(team_strength_metrics, dict) else None
    has_impact_strength = isinstance(t1_strength, dict) and isinstance(t2_strength, dict)

    if has_impact_strength:
        t1_rating["batting"] = float(t1_strength.get("batting_strength", t1_rating.get("batting", 50)))
        t2_rating["batting"] = float(t2_strength.get("batting_strength", t2_rating.get("batting", 50)))
        t1_rating["bowling"] = float(t1_strength.get("bowling_strength", t1_rating.get("bowling", 50)))
        t2_rating["bowling"] = float(t2_strength.get("bowling_strength", t2_rating.get("bowling", 50)))
        t1_rating["allrounder_strength"] = float(
            t1_strength.get("allrounder_strength", t1_rating.get("allrounder_strength", 50))
        )
        t2_rating["allrounder_strength"] = float(
            t2_strength.get("allrounder_strength", t2_rating.get("allrounder_strength", 50))
        )
        t1_rating["allrounder_depth"] = float(
            t1_strength.get("allrounder_depth", t1_rating.get("allrounder_depth", 0))
        )
        t2_rating["allrounder_depth"] = float(
            t2_strength.get("allrounder_depth", t2_rating.get("allrounder_depth", 0))
        )

        batting_strength_logit = 3.2 * ((t1_rating["batting"] - t2_rating["batting"]) / 100.0)
        batting_depth_logit = 2.5 * (float(t1_strength.get("batting_depth", 0.0)) - float(t2_strength.get("batting_depth", 0.0)))
        bowling_strength_logit = 3.0 * ((t1_rating["bowling"] - t2_rating["bowling"]) / 100.0)
    else:
        batting_strength_logit = _batting_strength_logit(t1_rating, t2_rating)
        batting_depth_logit = _batting_depth_logit(remapped_squads)
        bowling_strength_logit = _bowling_strength_logit(remapped_squads)
    t1_ar_strength_act, t2_ar_strength_act, t1_ar_depth_act, t2_ar_depth_act = _allrounder_activity_indices(
        remapped_squads, player_performance
    )
    if not has_impact_strength:
        t1_rating["allrounder_strength"] = round(t1_ar_strength_act, 1)
        t2_rating["allrounder_strength"] = round(t2_ar_strength_act, 1)
        t1_rating["allrounder_depth"] = round(max(float(t1_rating.get("allrounder_depth", 0)), t1_ar_depth_act), 2)
        t2_rating["allrounder_depth"] = round(max(float(t2_rating.get("allrounder_depth", 0)), t2_ar_depth_act), 2)
    allrounder_depth_logit = _allrounder_depth_logit(t1_rating, t2_rating)
    allrounder_strength_logit = _allrounder_strength_logit(t1_rating, t2_rating)

    # These three factors consume web-search context when available, fallback to deterministic XI proxy.
    powerplay_logit = _powerplay_performance_logit_from_web(web_context)
    if powerplay_logit is None:
        powerplay_logit = _powerplay_performance_logit(remapped_squads)
    death_overs_logit = _death_overs_performance_logit_from_web(web_context)
    if death_overs_logit is None:
        death_overs_logit = _death_overs_performance_logit(remapped_squads)
    key_avail_logit = _key_players_availability_logit_from_web(web_context)
    if key_avail_logit is None:
        key_avail_logit = _key_players_availability_logit(remapped_squads)

    # ━━━━━━ Category 2: Current Season Form — SportMonks API (21%) ━━━━━━
    t1_form = form_data.get("team1", {})
    t2_form = form_data.get("team2", {})
    t1_form_score = t1_form.get("form_score", 50)
    t2_form_score = t2_form.get("form_score", 50)
    t1_matches_played = t1_form.get("matches_played", 0)
    t2_matches_played = t2_form.get("matches_played", 0)
    min_matches = min(t1_matches_played, t2_matches_played)
    form_damping = min(1.0, min_matches / 3.0) if min_matches > 0 else 0.3
    # Current form = sum of current-season player activity points for expected XI when available.
    if remapped_squads.get("team1") and remapped_squads.get("team2") and isinstance(player_performance, dict):
        t1_form_points = _team_xi_activity_sum(remapped_squads.get("team1", []), player_performance.get("team1", {}))
        t2_form_points = _team_xi_activity_sum(remapped_squads.get("team2", []), player_performance.get("team2", {}))
        if (t1_form_points + t2_form_points) > 0:
            t1_form_score = round(t1_form_points, 1)
            t2_form_score = round(t2_form_points, 1)
            form_logit = 3.0 * ((t1_form_points - t2_form_points) / max(t1_form_points + t2_form_points, 1.0))
        else:
            form_logit = 3.5 * ((t1_form_score - t2_form_score) / 100) * form_damping
    else:
        form_logit = 3.5 * ((t1_form_score - t2_form_score) / 100) * form_damping

    # ━━━━━━ Category 3: Venue + Pitch + Home Advantage ━━━━━━
    is_t1_home = _is_home(team1, venue_key) if venue_key else False
    is_t2_home = _is_home(team2, venue_key) if venue_key else False
    home_ground_logit = 0.0
    if is_t1_home:
        home_ground_logit = 0.45
    elif is_t2_home:
        home_ground_logit = -0.45

    # Pitch-based advantage: explicit profile scoring (green / dry / dusty).
    venue_pitch_logit = 0.0
    venue_info = TOSS_LOOKUP.get(venue_key, {}) if venue_key else {}
    pitch_type = venue_info.get("pitch_type", "balanced")
    avg_first_innings = venue_info.get("avg_first_innings", 170)
    batting_first_win_pct = venue_info.get("batting_first_win_pct", 0.47)
    pace_assist = venue_info.get("pace_assist", 0.4)
    spin_assist = venue_info.get("spin_assist", 0.4)

    pitch_profile = "dry"
    pt = (pitch_type or "").lower()
    if "pace" in pt or "green" in pt:
        pitch_profile = "green"
    elif "spin" in pt or "dust" in pt or "slow" in pt:
        pitch_profile = "dusty"
    elif "high-scoring" in pt or "batting" in pt:
        pitch_profile = "dry"
    elif spin_assist - pace_assist >= 0.2:
        pitch_profile = "dusty"
    elif pace_assist - spin_assist >= 0.2:
        pitch_profile = "green"

    if remapped_squads.get("team1") and remapped_squads.get("team2"):
        # Count pace vs spin bowlers in each team's top 5
        t1_pace, t1_spin, t2_pace, t2_spin = 0, 0, 0, 0
        for team_key, counters in [("team1", []), ("team2", [])]:
            players = remapped_squads.get(team_key, [])
            bowlers = [p for p in players if _is_bowling_contributor(p)]
            bowlers_rated = sorted(bowlers, key=lambda p: resolve_star_player_rating(p.get("name", "")), reverse=True)[:5]
            pace = sum(
                1
                for p in bowlers_rated
                if _is_listed_pace_bowler(p.get("name", ""))
                or not _is_listed_spin_bowler(p.get("name", ""))
            )
            spin = sum(1 for p in bowlers_rated if _is_listed_spin_bowler(p.get("name", "")))
            if team_key == "team1":
                t1_pace, t1_spin = pace, spin
            else:
                t2_pace, t2_spin = pace, spin

        t1_pace_share = t1_pace / max(1.0, t1_pace + t1_spin)
        t2_pace_share = t2_pace / max(1.0, t2_pace + t2_spin)
        t1_spin_share = t1_spin / max(1.0, t1_pace + t1_spin)
        t2_spin_share = t2_spin / max(1.0, t2_pace + t2_spin)

        t1_bat_strength = float(t1_rating.get("batting", 50))
        t2_bat_strength = float(t2_rating.get("batting", 50))
        t1_bowl_strength = float(t1_rating.get("bowling", 50))
        t2_bowl_strength = float(t2_rating.get("bowling", 50))

        if pitch_profile == "green":
            # Green tracks: seam bowling and bowling quality dominate.
            t1_fit = 0.45 * t1_pace_share + 0.40 * (t1_bowl_strength / 100.0) + 0.15 * (t1_bat_strength / 100.0)
            t2_fit = 0.45 * t2_pace_share + 0.40 * (t2_bowl_strength / 100.0) + 0.15 * (t2_bat_strength / 100.0)
        elif pitch_profile == "dusty":
            # Dusty/slow tracks: spin and all-round versatility dominate.
            t1_fit = 0.40 * t1_spin_share + 0.30 * (t1_bowl_strength / 100.0) + 0.30 * (float(t1_rating.get("allrounder_strength", 50)) / 100.0)
            t2_fit = 0.40 * t2_spin_share + 0.30 * (t2_bowl_strength / 100.0) + 0.30 * (float(t2_rating.get("allrounder_strength", 50)) / 100.0)
        else:
            # Dry/high-scoring tracks: batting quality and depth matter more.
            t1_fit = 0.45 * (t1_bat_strength / 100.0) + 0.30 * (1.0 + batting_depth_logit / 3.0) / 2.0 + 0.25 * (float(t1_rating.get("allrounder_strength", 50)) / 100.0)
            t2_fit = 0.45 * (t2_bat_strength / 100.0) + 0.30 * (1.0 - batting_depth_logit / 3.0) / 2.0 + 0.25 * (float(t2_rating.get("allrounder_strength", 50)) / 100.0)
        venue_pitch_logit = 2.4 * (t1_fit - t2_fit)

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

    # ━━━━━━ Category 5: Bowling Attack Depth ━━━━━━
    bowl_depth_logit, bowl_detail = _compute_bowling_depth(remapped_squads, t1_rating, t2_rating, venue_key=venue_key)
    if has_impact_strength:
        t1_bdepth = max(0.0, min(1.0, float(t1_strength.get("bowling_depth", 0.0))))
        t2_bdepth = max(0.0, min(1.0, float(t2_strength.get("bowling_depth", 0.0))))
        bowl_depth_logit = 2.6 * (t1_bdepth - t2_bdepth)
        b1, b2 = _duel_share_pct(t1_bdepth, t2_bdepth)
        bowl_detail["team1_depth_share_pct"] = b1
        bowl_detail["team2_depth_share_pct"] = b2
        bowl_detail["source"] = "impact_points"

    # ━━━━━━ Category 6: Conditions — Real Weather Data ━━━━━━
    conditions_logit, conditions_detail = _compute_conditions_from_weather(
        venue_key, match_time, weather, remapped_squads, team1=team1, team2=team2
    )

    # ━━━━━━ Category 7: Team Momentum — Last 2 Matches ━━━━━━
    # Momentum should meaningfully favour a team on a winning streak.
    # With 3% weight, the logit needs to be strong enough to create visible impact.
    # 2-0 streak diff → ~1.5% swing, 1-0 diff → ~0.7% swing
    t1_last2 = momentum_data.get("team1_last2", [])
    t2_last2 = momentum_data.get("team2_last2", [])
    t1_wins_last2 = sum(1 for r in t1_last2 if r == "W")
    t2_wins_last2 = sum(1 for r in t2_last2 if r == "W")
    win_diff = t1_wins_last2 - t2_wins_last2  # +2, +1, 0, -1, -2
    # Scale: +2 diff → logit +1.8, +1 diff → logit +0.9
    momentum_logit = min(2.0, max(-2.0, 0.9 * win_diff))
    # Add extra boost for dominant streak (2W-0L vs 0W-2L)
    if abs(win_diff) == 2:
        momentum_logit *= 1.3  # 2-0 streak is more impactful than just additive

    top_order_consistency_logit = _top_order_consistency_logit(form_data)

    _RATINGS_OVERRIDE.reset(rtok)

    combined_logit = (
        WEIGHTS["batting_strength"] * batting_strength_logit
        + WEIGHTS["batting_depth"] * batting_depth_logit
        + WEIGHTS["bowling_strength"] * bowling_strength_logit
        + WEIGHTS["bowling_depth"] * bowl_depth_logit
        + WEIGHTS["allrounder_strength"] * allrounder_strength_logit
        + WEIGHTS["allrounder_depth"] * allrounder_depth_logit
        + WEIGHTS["current_form"] * form_logit
        + WEIGHTS["venue_pitch"] * venue_pitch_logit
        + WEIGHTS["home_ground_advantage"] * home_ground_logit
        + WEIGHTS["h2h"] * h2h_logit
        + WEIGHTS["conditions"] * conditions_logit
        + WEIGHTS["momentum"] * momentum_logit
        + WEIGHTS["powerplay_performance"] * powerplay_logit
        + WEIGHTS["death_overs_performance"] * death_overs_logit
        + WEIGHTS["key_players_availability"] * key_avail_logit
        + WEIGHTS["top_order_consistency"] * top_order_consistency_logit
    )


    # Data-quality shrinkage: if many factors are fallback/neutral, pull confidence toward 50%.
    quality_sources = {
        "squads_ready": bool(remapped_squads.get("team1") and remapped_squads.get("team2")),
        "form_ready": bool(form_data),
        "weather_ready": bool(weather and weather.get("available")),
        "h2h_ready": bool(total_h2h > 0),
        "web_pp_ready": _powerplay_performance_logit_from_web(web_context) is not None,
        "web_death_ready": _death_overs_performance_logit_from_web(web_context) is not None,
        "web_inj_ready": _key_players_availability_logit_from_web(web_context) is not None,
    }
    quality_ratio = sum(1 for v in quality_sources.values() if v) / max(1, len(quality_sources))
    quality_shrink = 0.55 + 0.45 * quality_ratio
    adjusted_logit = combined_logit * quality_shrink
    raw_probability = 1.0 / (1.0 + math.exp(-adjusted_logit))
    team1_win_prob = round(raw_probability * 100, 1)
    team2_win_prob = round(100 - team1_win_prob, 1)

    spread = abs(team1_win_prob - 50)
    if spread > 15:
        confidence = "high"
    elif spread > 7:
        confidence = "medium"
    else:
        confidence = "low"

    # ── Human-readable attribution (logits are always team1 − team2 perspective)
    raw_logits = {
        "batting_strength": batting_strength_logit,
        "batting_depth": batting_depth_logit,
        "bowling_strength": bowling_strength_logit,
        "bowling_depth": bowl_depth_logit,
        "allrounder_strength": allrounder_strength_logit,
        "allrounder_depth": allrounder_depth_logit,
        "current_form": form_logit,
        "venue_pitch": venue_pitch_logit,
        "home_ground_advantage": home_ground_logit,
        "h2h": h2h_logit,
        "conditions": conditions_logit,
        "momentum": momentum_logit,
        "powerplay_performance": powerplay_logit,
        "death_overs_performance": death_overs_logit,
        "key_players_availability": key_avail_logit,
        "top_order_consistency": top_order_consistency_logit,
    }
    weighted_contribs = {k: WEIGHTS[k] * raw_logits[k] for k in WEIGHTS}
    is_t1_fav = team1_win_prob >= 50.0
    aligned = {k: (weighted_contribs[k] if is_t1_fav else -weighted_contribs[k]) for k in WEIGHTS}
    driver_key = max(WEIGHTS, key=lambda k: aligned[k])
    driver_aligned = aligned[driver_key]
    t1n, t2n = team1 or "Team 1", team2 or "Team 2"
    fav_name = t1n if is_t1_fav else t2n
    other_name = t2n if is_t1_fav else t1n
    if driver_aligned > 0.008:
        favourite_one_liner = (
            f"{fav_name} are tipped mainly on {FACTOR_SUMMARY_PHRASES[driver_key]} "
            f"versus {other_name}."
        )
    elif spread < 3:
        favourite_one_liner = (
            f"Essentially a coin-flip — {fav_name} shade the model only on fine margins."
        )
    else:
        favourite_one_liner = (
            f"{fav_name} edge it through several small factors combined; no single category dominates."
        )

    def _named(key: str) -> str:
        return _team_label(key, team1 or "Team 1", team2 or "Team 2")

    vp_f = _favours_from_logit(venue_pitch_logit)
    vp_line = (
        f"{_named(vp_f)} — better suited to this {pitch_profile} pitch profile."
        if vp_f != "neutral"
        else f"{pitch_profile.title()} pitch profile looks evenly matched between teams."
    )
    hg_f = _favours_from_logit(home_ground_logit)
    hg_line = (
        f"{_named(hg_f)} — home-ground edge at this venue."
        if hg_f != "neutral"
        else "No single home-ground advantage in the schedule mapping."
    )
    h2h_f = _favours_from_logit(h2h_logit)
    if total_h2h > 0:
        h2h_line = (
            f"{_named(h2h_f)} — {t1_h2h}-{t2_h2h} in the sampled H2H ({total_h2h} matches)."
            if h2h_f != "neutral"
            else f"H2H is balanced ({t1_h2h}-{t2_h2h} over {total_h2h} matches)."
        )
    else:
        h2h_line = "No head-to-head sample — this factor is left neutral."

    bd1 = bowl_detail.get("team1_depth_share_pct")
    bd2 = bowl_detail.get("team2_depth_share_pct")
    bowl_f = _favours_from_logit(bowl_depth_logit)
    if bd1 is not None and bd2 is not None:
        bowl_line = (
            f"{_named(bowl_f)} — venue-weighted bowling depth score ~{bd1}%–{bd2}% split."
            if bowl_f != "neutral"
            else f"Bowling depth is comparable (~{bd1}%–{bd2}% share for this venue)."
        )
    else:
        bowl_line = (
            f"{_named(bowl_f)} — deeper attack for this surface."
            if bowl_f != "neutral"
            else "Bowling depth nets out even for this venue."
        )

    cond_key = conditions_detail.get("favours_team", "neutral")
    cond_line = conditions_detail.get("one_liner") or conditions_detail.get(
        "conditions_edge_text", "Conditions relatively neutral for both teams"
    )

    mom_f = _favours_from_logit(momentum_logit)
    if win_diff > 0:
        momentum_line = f"{t1n} carry momentum ({t1_wins_last2} wins in last 2 vs {t2n}'s {t2_wins_last2})."
    elif win_diff < 0:
        momentum_line = f"{t2n} carry momentum ({t2_wins_last2} wins in last 2 vs {t1n}'s {t1_wins_last2})."
    else:
        momentum_line = f"Even momentum — {t1n} and {t2n} similar over the last two results."

    batstr_f = _favours_from_logit(batting_strength_logit)
    batstr_line = (
        f"{_named(batstr_f)} — stronger core batting quality."
        if batstr_f != "neutral"
        else "Core batting strength is closely matched."
    )
    form_f = _favours_from_logit(form_logit)
    form_line = (
        f"{_named(form_f)} — better recent season form (SportMonks)."
        if form_f != "neutral"
        else "Recent league form is neck-and-neck."
    )

    bdepth_f = _favours_from_logit(batting_depth_logit)
    bdepth_line = (
        f"{_named(bdepth_f)} — stronger middle/lower order on paper."
        if bdepth_f != "neutral"
        else "Batting depth through the order is comparable."
    )
    bstr_f = _favours_from_logit(bowling_strength_logit)
    bstr_line = (
        f"{_named(bstr_f)} — higher top-end bowling quality."
        if bstr_f != "neutral"
        else "Top bowling quality is evenly matched."
    )
    pp_f = _favours_from_logit(powerplay_logit)
    pp_line = (
        f"{_named(pp_f)} — stronger powerplay batting profile."
        if pp_f != "neutral"
        else "Powerplay batting profiles are even."
    )
    death_f = _favours_from_logit(death_overs_logit)
    death_line = (
        f"{_named(death_f)} — better death-overs specialist mix."
        if death_f != "neutral"
        else "Death overs profiles are balanced."
    )
    ka_f = _favours_from_logit(key_avail_logit)
    ka_line = (
        f"{_named(ka_f)} — fewer flagged availability issues in the XI."
        if ka_f != "neutral"
        else "No meaningful availability flags on either XI."
    )
    ar_f = _favours_from_logit(allrounder_depth_logit)
    ar_line = (
        f"{_named(ar_f)} — more all-round options in the squad."
        if ar_f != "neutral"
        else "All-rounder depth is similar."
    )
    ars_f = _favours_from_logit(allrounder_strength_logit)
    ars_line = (
        f"{_named(ars_f)} — higher all-rounder quality ceiling."
        if ars_f != "neutral"
        else "All-rounder quality is evenly matched."
    )
    toc_f = _favours_from_logit(top_order_consistency_logit)
    toc_line = (
        f"{_named(toc_f)} — more consistent top-order form scores."
        if toc_f != "neutral"
        else "Top-order consistency is even from recent performer data."
    )

    xi_t1 = remapped_squads.get("team1") or []
    xi_t2 = remapped_squads.get("team2") or []
    if has_impact_strength:
        t1_tail_f = 100.0 * max(0.0, min(1.0, float(t1_strength.get("batting_depth", 0.0))))
        t2_tail_f = 100.0 * max(0.0, min(1.0, float(t2_strength.get("batting_depth", 0.0))))
    else:
        t1_tail_f = _team_batting_depth_tail_index(xi_t1) if xi_t1 else 50.0
        t2_tail_f = _team_batting_depth_tail_index(xi_t2) if xi_t2 else 50.0
    t1_tail_bat_idx = round(t1_tail_f, 1) if xi_t1 else None
    t2_tail_bat_idx = round(t2_tail_f, 1) if xi_t2 else None
    bat_st_share1, bat_st_share2 = _duel_share_pct(t1_rating.get("batting", 50), t2_rating.get("batting", 50))
    bat_dp_share1, bat_dp_share2 = _duel_share_pct(t1_tail_f, t2_tail_f)
    bowl_st_share1, bowl_st_share2 = _duel_share_pct(t1_rating.get("bowling", 50), t2_rating.get("bowling", 50))
    ar_st_share1, ar_st_share2 = _duel_share_pct(
        t1_rating.get("allrounder_strength", 50), t2_rating.get("allrounder_strength", 50)
    )
    ar_dp_share1, ar_dp_share2 = _duel_share_pct(
        t1_rating.get("allrounder_depth", 0), t2_rating.get("allrounder_depth", 0)
    )
    bowl_dp_share1 = int(bowl_detail.get("team1_depth_share_pct", 50))
    bowl_dp_share2 = int(bowl_detail.get("team2_depth_share_pct", 50))

    return {
        "team1_win_prob": team1_win_prob,
        "team2_win_prob": team2_win_prob,
        "confidence": confidence,
        "raw_probability": round(raw_probability, 4),
        "combined_logit": round(adjusted_logit, 4),
        "raw_combined_logit": round(combined_logit, 4),
        "data_quality": {
            "score": round(quality_ratio, 3),
            "shrink_applied": round(quality_shrink, 3),
            "signals": quality_sources,
        },
        "model": "16-category-v2",
        "favourite_team": "team1" if is_t1_fav else "team2",
        "favourite_one_liner": favourite_one_liner,
        "factor_one_liners": {
            "batting_strength": {"favours": batstr_f, "one_liner": batstr_line},
            "current_form": {"favours": form_f, "one_liner": form_line},
            "venue_pitch": {"favours": vp_f, "one_liner": vp_line},
            "home_ground_advantage": {"favours": hg_f, "one_liner": hg_line},
            "h2h": {"favours": h2h_f, "one_liner": h2h_line},
            "bowling_depth": {"favours": bowl_f, "one_liner": bowl_line},
            "bowling_strength": {"favours": bstr_f, "one_liner": bstr_line},
            "conditions": {
                "favours": cond_key if cond_key in ("team1", "team2") else "neutral",
                "one_liner": cond_line,
            },
            "momentum": {"favours": mom_f, "one_liner": momentum_line},
            "batting_depth": {"favours": bdepth_f, "one_liner": bdepth_line},
            "powerplay_performance": {"favours": pp_f, "one_liner": pp_line},
            "death_overs_performance": {"favours": death_f, "one_liner": death_line},
            "key_players_availability": {"favours": ka_f, "one_liner": ka_line},
            "allrounder_strength": {"favours": ars_f, "one_liner": ars_line},
            "allrounder_depth": {"favours": ar_f, "one_liner": ar_line},
            "top_order_consistency": {"favours": toc_f, "one_liner": toc_line},
        },
        "attribution": {
            "primary_driver_factor": driver_key,
            "primary_driver_aligned_weight": round(driver_aligned, 4),
            "logits_team1_minus_team2": {k: round(v, 4) for k, v in raw_logits.items()},
        },
        "factors": {
            "batting_strength": {
                "weight": WEIGHTS["batting_strength"],
                "logit_contribution": round(WEIGHTS["batting_strength"] * batting_strength_logit, 4),
                "team1_batting": t1_rating["batting"],
                "team2_batting": t2_rating["batting"],
                "team1_share_pct": bat_st_share1,
                "team2_share_pct": bat_st_share2,
                "raw_logit": round(batting_strength_logit, 4),
                "source": "impact_points" if has_impact_strength else "xi_roles",
                "basis": "xi_roles_top6_batting_pool",
                **t1_squad_detail, **t2_squad_detail,
            },
            "current_form": {
                "weight": WEIGHTS["current_form"],
                "logit_contribution": round(WEIGHTS["current_form"] * form_logit, 4),
                "team1_form_score": round(t1_form_score, 1),
                "team2_form_score": round(t2_form_score, 1),
                "team1_wl_form": t1_form.get("wl_form_score", t1_form_score),
                "team2_wl_form": t2_form.get("wl_form_score", t2_form_score),
                "team1_player_form": t1_form.get("player_form_score", 0),
                "team2_player_form": t2_form.get("player_form_score", 0),
                "team1_matches_played": t1_matches_played,
                "team2_matches_played": t2_matches_played,
                "team1_wins": t1_form.get("wins", 0),
                "team2_wins": t2_form.get("wins", 0),
                "team1_top_performers": t1_form.get("top_performers", []),
                "team2_top_performers": t2_form.get("top_performers", []),
                "team1_nrr": t1_form.get("nrr", 0),
                "team2_nrr": t2_form.get("nrr", 0),
                "source": "sportmonks_api",
                "damping": round(form_damping, 2),
                "has_player_stats": bool(player_performance),
            },
            "venue_pitch": {
                "weight": WEIGHTS["venue_pitch"],
                "logit_contribution": round(WEIGHTS["venue_pitch"] * venue_pitch_logit, 4),
                "venue": venue_str,
                "venue_key": venue_key,
                "pitch_type": pitch_type,
                "pitch_profile": pitch_profile,
                "avg_first_innings": avg_first_innings,
                "batting_first_win_pct": round(batting_first_win_pct * 100, 1),
                "pace_assist": pace_assist,
                "spin_assist": spin_assist,
                "pitch_logit": round(venue_pitch_logit, 3),
                "raw_logit": round(venue_pitch_logit, 3),
            },
            "home_ground_advantage": {
                "weight": WEIGHTS["home_ground_advantage"],
                "logit_contribution": round(WEIGHTS["home_ground_advantage"] * home_ground_logit, 4),
                "team1_home": is_t1_home,
                "team2_home": is_t2_home,
                "home_team": "team1" if is_t1_home else ("team2" if is_t2_home else "neutral"),
                "home_logit": round(home_ground_logit, 3),
                "raw_logit": round(home_ground_logit, 3),
            },
            "h2h": {
                "weight": WEIGHTS["h2h"],
                "logit_contribution": round(WEIGHTS["h2h"] * h2h_logit, 4),
                "team1_wins": t1_h2h,
                "team2_wins": t2_h2h,
                "total": total_h2h,
                "source": h2h_source,
            },
            "bowling_depth": {
                "weight": WEIGHTS["bowling_depth"],
                "logit_contribution": round(WEIGHTS["bowling_depth"] * bowl_depth_logit, 4),
                "team1_share_pct": bowl_dp_share1,
                "team2_share_pct": bowl_dp_share2,
                "source": "impact_points" if has_impact_strength else "xi_roles",
                "basis": "xi_bowling_contributors_venue_weighted_top5",
                **bowl_detail,
            },
            "bowling_strength": {
                "weight": WEIGHTS["bowling_strength"],
                "logit_contribution": round(WEIGHTS["bowling_strength"] * bowling_strength_logit, 4),
                "raw_logit": round(bowling_strength_logit, 4),
                "team1_bowling_rating": t1_rating.get("bowling", 50),
                "team2_bowling_rating": t2_rating.get("bowling", 50),
                "team1_share_pct": bowl_st_share1,
                "team2_share_pct": bowl_st_share2,
                "source": "impact_points" if has_impact_strength else "xi_roles",
                "basis": "xi_roles_top5_bowling_pool",
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
                "raw_logit": round(momentum_logit, 4),
                "momentum_text": momentum_line,
            },
            "batting_depth": {
                "weight": WEIGHTS["batting_depth"],
                "logit_contribution": round(WEIGHTS["batting_depth"] * batting_depth_logit, 4),
                "raw_logit": round(batting_depth_logit, 4),
                "team1_share_pct": bat_dp_share1,
                "team2_share_pct": bat_dp_share2,
                "team1_tail_batting_index": t1_tail_bat_idx,
                "team2_tail_batting_index": t2_tail_bat_idx,
                "source": "impact_points" if has_impact_strength else "xi_roles",
                "basis": "xi_roles_positions_7_11_batting_tail",
            },
            "powerplay_performance": {
                "weight": WEIGHTS["powerplay_performance"],
                "logit_contribution": round(WEIGHTS["powerplay_performance"] * powerplay_logit, 4),
                "raw_logit": round(powerplay_logit, 4),
                "source": "openai_web" if _powerplay_performance_logit_from_web(web_context) is not None else "fallback_xi_proxy",
            },
            "death_overs_performance": {
                "weight": WEIGHTS["death_overs_performance"],
                "logit_contribution": round(WEIGHTS["death_overs_performance"] * death_overs_logit, 4),
                "raw_logit": round(death_overs_logit, 4),
                "source": "openai_web" if _death_overs_performance_logit_from_web(web_context) is not None else "fallback_xi_proxy",
            },
            "key_players_availability": {
                "weight": WEIGHTS["key_players_availability"],
                "logit_contribution": round(WEIGHTS["key_players_availability"] * key_avail_logit, 4),
                "raw_logit": round(key_avail_logit, 4),
                "source": "openai_web" if _key_players_availability_logit_from_web(web_context) is not None else "fallback_xi_proxy",
            },
            "allrounder_depth": {
                "weight": WEIGHTS["allrounder_depth"],
                "logit_contribution": round(WEIGHTS["allrounder_depth"] * allrounder_depth_logit, 4),
                "raw_logit": round(allrounder_depth_logit, 4),
                "team1_allrounder_depth": t1_rating.get("allrounder_depth", 0),
                "team2_allrounder_depth": t2_rating.get("allrounder_depth", 0),
                "team1_share_pct": ar_dp_share1,
                "team2_share_pct": ar_dp_share2,
                "source": "impact_points" if has_impact_strength else "xi_roles",
                "basis": "xi_allrounder_role_max_form_activity",
            },
            "allrounder_strength": {
                "weight": WEIGHTS["allrounder_strength"],
                "logit_contribution": round(WEIGHTS["allrounder_strength"] * allrounder_strength_logit, 4),
                "raw_logit": round(allrounder_strength_logit, 4),
                "team1_allrounder_strength": t1_rating.get("allrounder_strength", 50),
                "team2_allrounder_strength": t2_rating.get("allrounder_strength", 50),
                "team1_share_pct": ar_st_share1,
                "team2_share_pct": ar_st_share2,
                "source": "impact_points" if has_impact_strength else "xi_roles",
                "basis": "xi_allrounder_role_top3_mean_effective_rating",
            },
            "top_order_consistency": {
                "weight": WEIGHTS["top_order_consistency"],
                "logit_contribution": round(WEIGHTS["top_order_consistency"] * top_order_consistency_logit, 4),
                "raw_logit": round(top_order_consistency_logit, 4),
            },
        },
    }


# ── Helper Functions ──

def _compute_squad_ratings(squad_data: dict) -> Tuple:
    """Compute squad ratings from Expected XI using canonical roles (bat/bowl/AR pools)."""
    results = {}
    details = {}
    for team_key in ["team1", "team2"]:
        players = squad_data.get(team_key, [])
        if not players:
            results[team_key] = {"batting": 50, "bowling": 50, "allrounder_depth": 0, "allrounder_strength": 50}
            details[team_key] = {}
            continue

        bat_avg = _team_batting_strength_index(players)
        bowl_avg = _team_bowling_strength_index(players)
        allrounder_ratings = _team_allrounder_ratings(players)
        ar_depth = len(allrounder_ratings)
        ar_strength = (
            sum(sorted(allrounder_ratings, reverse=True)[:3]) / min(3, len(allrounder_ratings))
            if allrounder_ratings else 50.0
        )
        results[team_key] = {
            "batting": round(bat_avg, 1),
            "bowling": round(bowl_avg, 1),
            "allrounder_depth": ar_depth,
            "allrounder_strength": round(ar_strength, 1),
        }
        details[team_key] = {f"{team_key}_allrounder_count": ar_depth, f"{team_key}_top_players": len(players)}

    return (
        results.get("team1", {"batting": 50, "bowling": 50, "allrounder_depth": 0, "allrounder_strength": 50}),
        results.get("team2", {"batting": 50, "bowling": 50, "allrounder_depth": 0, "allrounder_strength": 50}),
        details.get("team1", {}),
        details.get("team2", {}),
    )


def _compute_toss_impact(
    venue_key: Optional[str],
    match_time: str,
    weather: dict,
    squads: Optional[Dict] = None,
    team1: str = "",
    team2: str = "",
) -> Tuple[float, dict]:
    """Category 5: Toss — venue/time sensitivity × (team1 chase strength − team2).

    Chase strength uses top-order batting ratings; pre-toss we only tilt by that gap so
    there is no fixed bias toward team1 when dew matters.
    """
    squads = squads or {}
    team1_name = team1 or "Team 1"
    team2_name = team2 or "Team 2"
    c1 = _chase_strength_index(squads.get("team1", []))
    c2 = _chase_strength_index(squads.get("team2", []))
    chase_diff = c1 - c2

    time_class = _classify_match_time(match_time)
    is_evening = time_class == "evening"
    is_afternoon = time_class == "afternoon"

    detail = {
        "venue_key": venue_key,
        "is_night": is_evening,
        "match_time_class": time_class,
        "preferred_decision": "unknown",
        "toss_win_pct": 0.52,
        "chase_strength_index_team1": round(c1, 3),
        "chase_strength_index_team2": round(c2, 3),
        "chase_diff_team1_minus_team2": round(chase_diff, 3),
    }

    if not venue_key or venue_key not in TOSS_LOOKUP:
        detail["preferred_decision"] = "bowl" if is_evening else "bat"
        detail["toss_win_pct"] = 0.53 if is_evening else 0.51
        detail["dew_factor"] = "none"
        if is_evening:
            detail["dew_impact_text"] = "Unknown venue — slight chasing bias assumed (evening match)"
        elif is_afternoon:
            detail["dew_impact_text"] = "Unknown venue — afternoon match, minimal dew expected. Toss less decisive."
        else:
            detail["dew_impact_text"] = "Unknown venue — day match, no dew."
        detail["dew_multiplier"] = 1.0 if is_evening else 0.6 if is_afternoon else 0.5
        unknown_sens = (0.14 if is_evening else 0.06 if is_afternoon else 0.05) * detail["dew_multiplier"]
        toss_logit = max(-1.5, min(1.5, unknown_sens * chase_diff))
        detail["toss_environment_logit"] = round(unknown_sens, 4)
        detail["toss_logit_raw"] = round(toss_logit, 4)
        ft = _favours_from_logit(toss_logit)
        if ft == "team1":
            detail["one_liner"] = (
                f"{team1_name} shade toss/dew value — stronger chase/top-order depth for this slot."
            )
        elif ft == "team2":
            detail["one_liner"] = (
                f"{team2_name} shade toss/dew value — stronger chase/top-order depth for this slot."
            )
        else:
            detail["one_liner"] = (
                "Toss is less decisive here, or both sides match up evenly for chasing in these conditions."
            )
        return toss_logit, detail

    venue_data = TOSS_LOOKUP[venue_key]

    # Check for dew from weather data
    dew_factor = "none"
    cricket_impact = weather.get("cricket_impact", {})
    if cricket_impact:
        dew_factor = cricket_impact.get("dew_factor", "none")

    # For afternoon matches, override dew_factor downward — dew is negligible at 3:30 PM
    if is_afternoon and dew_factor in ("heavy", "moderate"):
        dew_factor = "light"  # Afternoon matches don't have significant dew
        detail["dew_override_reason"] = "Afternoon match (3:30 PM IST) — dew downgraded, match ends before dark"

    conditions = venue_data["conditions"]
    
    # Select condition based on match time classification
    if is_evening and dew_factor in ("heavy", "moderate") and "dew" in conditions:
        selected = conditions["dew"]
        detail["condition"] = "dew"
    elif is_evening and "night" in conditions:
        selected = conditions["night"]
        detail["condition"] = "night"
    elif (is_afternoon or not is_evening) and "day" in conditions:
        selected = conditions["day"]
        detail["condition"] = "day"
    else:
        # Fallback: for afternoon at venues with no "day" condition, use first available
        # but apply damping since it's not a night match
        first_key = list(conditions.keys())[0]
        selected = conditions[first_key]
        detail["condition"] = first_key
        if is_afternoon:
            detail["condition_note"] = "No afternoon-specific data — using default with reduced weight"

    detail["preferred_decision"] = selected["preferred"]
    detail["toss_win_pct"] = selected["toss_win_pct"]
    detail["chasing_bias"] = selected.get("chasing_bias", 0)
    detail["dew_factor"] = dew_factor

    toss_win_pct = selected["toss_win_pct"]
    chasing_bias = selected.get("chasing_bias", 0)

    # ── Dew impact text and multiplier based on time classification ──
    if is_evening:
        if dew_factor == "heavy":
            detail["dew_impact_text"] = "Evening match + heavy dew — massive chasing advantage. Bowling second extremely difficult."
            detail["dew_multiplier"] = 1.5
        elif dew_factor == "moderate":
            detail["dew_impact_text"] = "Evening match + moderate dew — clear chasing advantage. Wet ball makes bowling harder in 2nd innings."
            detail["dew_multiplier"] = 1.2
        else:
            detail["dew_impact_text"] = "Evening match (7:30 PM IST) — some dew expected. Slight chasing edge."
            detail["dew_multiplier"] = 1.0
    elif is_afternoon:
        # Afternoon matches: significantly reduced dew impact
        detail["dew_impact_text"] = (
            "Afternoon match (3:30 PM IST) — match ends by ~7 PM before heavy dew sets in. "
            "Toss less decisive. Batting conditions similar in both innings."
        )
        detail["dew_multiplier"] = 0.55  # Much lower than evening
        # Reduce chasing bias for afternoon matches
        chasing_bias = chasing_bias * 0.3  # Chasing bias drops significantly without dew
        detail["chasing_bias_adjusted"] = round(chasing_bias, 3)
    else:
        detail["dew_impact_text"] = "Day match — no dew. Conditions neutral for both innings."
        detail["dew_multiplier"] = 0.5

    # Toss logit: venue toss sensitivity + dew-enhanced chasing bias
    toss_deviation = toss_win_pct - 0.50
    dew_multiplier = detail.get("dew_multiplier", 1.0)
    
    # For afternoon, also dampen the toss deviation itself
    if is_afternoon:
        toss_deviation = toss_deviation * 0.6  # Toss matters less in afternoon
        detail["toss_deviation_adjusted"] = round(toss_deviation, 4)
    
    base_env = (3.0 * toss_deviation + 2.5 * chasing_bias) * dew_multiplier
    base_env = max(-1.5, min(1.5, base_env))
    detail["toss_environment_logit"] = round(base_env, 4)
    toss_logit = max(-1.5, min(1.5, base_env * chase_diff))
    detail["toss_logit_raw"] = round(toss_logit, 4)

    ft = _favours_from_logit(toss_logit)
    if ft == "team1":
        detail["one_liner"] = (
            f"{team1_name} — chase/top-order depth fits this venue's toss and dew profile better."
        )
    elif ft == "team2":
        detail["one_liner"] = (
            f"{team2_name} — chase/top-order depth fits this venue's toss and dew profile better."
        )
    else:
        detail["one_liner"] = (
            "Even chase depth or a low dew/toss sensitivity keeps this category close."
        )

    return toss_logit, detail


def _compute_bowling_depth(squad_data: dict, t1_rating: dict, t2_rating: dict,
                           venue_key: Optional[str] = None) -> Tuple[float, dict]:
    """Category 6: Bowling Attack Depth — venue-aware, top 5 bowlers.
    
    At spin-friendly venues (Chepauk, Jaipur), team with more spinners gets a boost.
    At pace-friendly venues (Mohali, Hyderabad), team with more pacers gets a boost.
    Quality scores are weighted by venue surface to produce differentiated logits.
    """
    detail = {}
    venue_info = TOSS_LOOKUP.get(venue_key, {}) if venue_key else {}
    v_pace_assist = venue_info.get("pace_assist", 0.45)
    v_spin_assist = venue_info.get("spin_assist", 0.35)

    for team_key in ["team1", "team2"]:
        players = squad_data.get(team_key, [])
        bowler_entries = []
        pace_count = 0
        spin_count = 0

        for p in players:
            name = p.get("name", "")
            role = _canonical_xi_role(p.get("role"))
            base_rating = resolve_star_player_rating(name)

            if role in ("Bowler", "All-rounder") or _is_listed_primary_bowler(name):
                if base_rating >= 89:
                    score = 5
                elif base_rating >= 83:
                    score = 4
                elif base_rating >= 75:
                    score = 3
                else:
                    score = 2
                is_pace = _is_listed_pace_bowler(name)
                is_spin = _is_listed_spin_bowler(name)
                if not is_pace and not is_spin:
                    is_pace = True  # default unknown bowlers to pace
                # Venue-weighted score: pacers score more at pace venues, spinners at spin venues
                venue_multiplier = v_pace_assist if is_pace else v_spin_assist
                venue_score = score * 4 * (1 + venue_multiplier)
                bowler_entries.append({
                    "name": name, "score": score * 4, "venue_score": round(venue_score, 1),
                    "rating": base_rating, "is_pace": is_pace, "is_spin": is_spin,
                })

        if not bowler_entries and players:
            for p in sorted(
                players,
                key=lambda x: resolve_star_player_rating(x.get("name", "")),
                reverse=True,
            )[:5]:
                name = p.get("name", "")
                base_rating = resolve_star_player_rating(name)
                score = 2 + min(3, max(0, (base_rating - 60) // 10))
                is_pace, is_spin = True, False
                venue_score = score * 4 * (1 + v_pace_assist)
                bowler_entries.append({
                    "name": name or "Unknown",
                    "score": score * 4,
                    "venue_score": round(venue_score, 1),
                    "rating": base_rating,
                    "is_pace": is_pace,
                    "is_spin": is_spin,
                })
            detail[f"{team_key}_depth_fallback"] = True

        # Sort by venue_score descending & take top 5
        bowler_entries.sort(key=lambda x: x["venue_score"], reverse=True)
        top5 = bowler_entries[:5]
        for b in top5:
            if b["is_pace"]:
                pace_count += 1
            elif b["is_spin"]:
                spin_count += 1

        total_quality = sum(b["score"] for b in top5)
        total_venue_quality = sum(b["venue_score"] for b in top5)
        has_variety = pace_count >= 2 and spin_count >= 1
        detail[f"{team_key}_quality_score"] = round(total_quality, 1)
        detail[f"{team_key}_venue_quality"] = round(total_venue_quality, 1)
        detail[f"{team_key}_bowler_count"] = len(top5)
        detail[f"{team_key}_pace_count"] = pace_count
        detail[f"{team_key}_spin_count"] = spin_count
        detail[f"{team_key}_variety"] = "pace+spin" if has_variety else "one-dimensional"
        detail[f"{team_key}_variety_bonus"] = 0.3 if has_variety else 0.0
        detail[f"{team_key}_top_bowlers"] = [b["name"] for b in top5]

    t1_vq = detail.get("team1_venue_quality", 50)
    t2_vq = detail.get("team2_venue_quality", 50)
    t1_variety_bonus = detail.get("team1_variety_bonus", 0)
    t2_variety_bonus = detail.get("team2_variety_bonus", 0)
    # Use venue-weighted quality for the logit
    bowl_depth_logit = 3.0 * ((t1_vq - t2_vq) / max(t1_vq + t2_vq, 1)) + (t1_variety_bonus - t2_variety_bonus)
    vq_sum = t1_vq + t2_vq
    if vq_sum > 0:
        detail["team1_depth_share_pct"] = round(100 * t1_vq / vq_sum)
        detail["team2_depth_share_pct"] = round(100 * t2_vq / vq_sum)
    else:
        detail["team1_depth_share_pct"] = 50
        detail["team2_depth_share_pct"] = 50
    detail["venue_key"] = venue_key
    detail["venue_pace_assist"] = v_pace_assist
    detail["venue_spin_assist"] = v_spin_assist
    return bowl_depth_logit, detail


def _compute_conditions_from_weather(
    venue_key: Optional[str],
    match_time: str,
    weather: dict,
    squads: dict,
    team1: str = "",
    team2: str = "",
) -> Tuple[float, dict]:
    """Category 7: Conditions — team-specific advantage from real weather.
    
    Key logic:
    - Heavy dew → team with better BATTING benefits (chasing becomes easier) — EVENING ONLY
    - High humidity + cool temp → team with more PACE BOWLERS benefits (swing)
    - Hot + dry → team with more SPIN BOWLERS benefits
    - Strong wind → higher scoring, benefits better batting lineup
    - AFTERNOON matches: dew impact significantly reduced
    """
    time_class = _classify_match_time(match_time)
    is_evening = time_class == "evening"
    is_afternoon = time_class == "afternoon"
    
    detail = {"is_night": is_evening, "match_time_class": time_class,
              "dew_factor": "none", "conditions_summary": "neutral",
              "temperature": None, "humidity": None, "wind_kmh": None,
              "favours_team": "neutral", "conditions_edge_text": "No significant weather edge"}

    if not weather or not weather.get("available"):
        detail["conditions_summary"] = "Weather data unavailable — neutral conditions assumed"
        detail["one_liner"] = "Weather feed unavailable — this factor stays neutral."
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
    edge_reasons = []
    t1n = team1 or "Team 1"
    t2n = team2 or "Team 2"

    humidity = current.get("humidity", 50) or 50
    temperature = current.get("temperature", 30) or 30
    wind = current.get("wind_speed_kmh", 0) or 0
    dew_factor = cricket_impact.get("dew_factor", "none")

    # For afternoon matches, override dew factor — minimal dew before dark
    if is_afternoon and dew_factor in ("heavy", "moderate"):
        dew_factor = "light"
        detail["dew_override_reason"] = "Afternoon match — dew downgraded (match ends before dark)"

    # Count pace/spin bowlers per team (top 5 only)
    t1_pace, t1_spin, t2_pace, t2_spin = 0, 0, 0, 0
    for team_key in ["team1", "team2"]:
        players = squads.get(team_key, [])
        bowlers = [p for p in players if _is_bowling_contributor(p)]
        bowlers_rated = sorted(bowlers, key=lambda p: resolve_star_player_rating(p.get("name", "")), reverse=True)[:5]
        pace = sum(
            1
            for p in bowlers_rated
            if _is_listed_pace_bowler(p.get("name", ""))
            or not _is_listed_spin_bowler(p.get("name", ""))
        )
        spin = sum(1 for p in bowlers_rated if _is_listed_spin_bowler(p.get("name", "")))
        if team_key == "team1":
            t1_pace, t1_spin = pace, spin
        else:
            t2_pace, t2_spin = pace, spin

    detail["team1_pace_bowlers"] = t1_pace
    detail["team1_spin_bowlers"] = t1_spin
    detail["team2_pace_bowlers"] = t2_pace
    detail["team2_spin_bowlers"] = t2_spin

    def _team_bat_bowl_strength(players: list) -> Tuple[float, float]:
        bat_vals = []
        bowl_vals = []
        for p in players:
            nm = p.get("name", "")
            role = _canonical_xi_role(p.get("role"))
            rt = resolve_star_player_rating(nm)
            rw = ROLE_WEIGHTS.get(role, {"batting": 5, "bowling": 5})
            if role in BAT_ROLES_DEW or rw["batting"] >= 6:
                bat_vals.append(rt)
            if rw["bowling"] >= 6 or _is_listed_primary_bowler(nm):
                bowl_vals.append(rt)
        bat = sum(sorted(bat_vals, reverse=True)[:6]) / min(6, max(1, len(bat_vals))) if bat_vals else 50.0
        bowl = sum(sorted(bowl_vals, reverse=True)[:5]) / min(5, max(1, len(bowl_vals))) if bowl_vals else 50.0
        return bat, bowl

    t1_bat_strength, t1_bowl_strength = _team_bat_bowl_strength(squads.get("team1", []))
    t2_bat_strength, t2_bowl_strength = _team_bat_bowl_strength(squads.get("team2", []))
    detail["team1_batting_strength"] = round(t1_bat_strength, 1)
    detail["team2_batting_strength"] = round(t2_bat_strength, 1)
    detail["team1_bowling_strength"] = round(t1_bowl_strength, 1)
    detail["team2_bowling_strength"] = round(t2_bowl_strength, 1)

    # ── DEW EFFECT (biggest weather factor in T20) — EVENING MATCHES ONLY ──
    if dew_factor == "heavy" and is_evening:
        t1_players = squads.get("team1", [])
        t2_players = squads.get("team2", [])
        t1_batters = [p for p in t1_players if _canonical_xi_role(p.get("role")) in BAT_ROLES_DEW]
        t2_batters = [p for p in t2_players if _canonical_xi_role(p.get("role")) in BAT_ROLES_DEW]
        t1_bat_avg = sum(resolve_star_player_rating(p.get("name", "")) for p in t1_batters) / max(len(t1_batters), 1)
        t2_bat_avg = sum(resolve_star_player_rating(p.get("name", "")) for p in t2_batters) / max(len(t2_batters), 1)
        bat_diff = (t1_bat_avg - t2_bat_avg) / 100
        dew_logit = 0.6 * bat_diff
        conditions_logit += dew_logit
        if bat_diff > 0:
            edge_reasons.append(
                f"Heavy dew (evening) favours {t1n} (deeper batting for chasing)"
            )
        elif bat_diff < 0:
            edge_reasons.append(
                f"Heavy dew (evening) favours {t2n} (deeper batting for chasing)"
            )
        detail["dew_batting_edge"] = "team1" if bat_diff > 0 else "team2" if bat_diff < 0 else "equal"
    elif dew_factor == "moderate" and is_evening:
        t1_players = squads.get("team1", [])
        t2_players = squads.get("team2", [])
        t1_batters = [p for p in t1_players if _canonical_xi_role(p.get("role")) in BAT_ROLES_DEW]
        t2_batters = [p for p in t2_players if _canonical_xi_role(p.get("role")) in BAT_ROLES_DEW]
        t1_bat_avg = sum(resolve_star_player_rating(p.get("name", "")) for p in t1_batters) / max(len(t1_batters), 1)
        t2_bat_avg = sum(resolve_star_player_rating(p.get("name", "")) for p in t2_batters) / max(len(t2_batters), 1)
        bat_diff = (t1_bat_avg - t2_bat_avg) / 100
        dew_logit = 0.35 * bat_diff
        conditions_logit += dew_logit
        if bat_diff > 0:
            edge_reasons.append(f"Moderate dew (evening) slightly favours {t1n} (batting depth)")
        elif bat_diff < 0:
            edge_reasons.append(f"Moderate dew (evening) slightly favours {t2n} (batting depth)")
        detail["dew_batting_edge"] = "team1" if bat_diff > 0 else "team2" if bat_diff < 0 else "equal"
    elif is_afternoon:
        edge_reasons.append("Afternoon match (3:30 PM IST) — minimal dew impact, conditions similar for both innings")
        detail["dew_batting_edge"] = "neutral"

    # ── WET CONDITIONS correlation (humid/dewy) ──
    wet_index = min(1.0, max(0.0, ((humidity - 55) / 35.0) + (0.35 if dew_factor in ("heavy", "moderate") else 0.0)))
    if wet_index > 0.15:
        bat_diff = (t1_bat_strength - t2_bat_strength) / 100.0
        wet_bat_logit = 0.45 * wet_index * bat_diff
        conditions_logit += wet_bat_logit
        if bat_diff > 0.01:
            edge_reasons.append(f"Wet-ball batting correlation favours {t1n} (better wet chasing profile)")
        elif bat_diff < -0.01:
            edge_reasons.append(f"Wet-ball batting correlation favours {t2n} (better wet chasing profile)")

    # ── SWING CONDITIONS: humid + cool ──
    if humidity > 65 and temperature < 30:
        pace_diff = (t1_pace - t2_pace) / max(t1_pace + t2_pace, 1)
        swing_logit = 0.4 * pace_diff
        conditions_logit += swing_logit
        if t1_pace > t2_pace:
            edge_reasons.append(
                f"Swing conditions (humidity {humidity}%) favour {t1n} ({t1_pace} pacers vs {t2_pace})"
            )
        elif t2_pace > t1_pace:
            edge_reasons.append(
                f"Swing conditions (humidity {humidity}%) favour {t2n} ({t2_pace} pacers vs {t1_pace})"
            )
        detail["swing_edge"] = "team1" if t1_pace > t2_pace else "team2" if t2_pace > t1_pace else "equal"

    # ── HOT & DRY: spin-friendly ──
    if temperature > 33 and humidity < 45:
        spin_diff = (t1_spin - t2_spin) / max(t1_spin + t2_spin, 1)
        dry_logit = 0.35 * spin_diff
        conditions_logit += dry_logit
        if t1_spin > t2_spin:
            edge_reasons.append(
                f"Hot dry conditions ({temperature}C) favour {t1n} ({t1_spin} spinners vs {t2_spin})"
            )
        elif t2_spin > t1_spin:
            edge_reasons.append(
                f"Hot dry conditions ({temperature}C) favour {t2n} ({t2_spin} spinners vs {t1_spin})"
            )
        detail["dry_spin_edge"] = "team1" if t1_spin > t2_spin else "team2" if t2_spin > t1_spin else "equal"

    # ── DRY CONDITIONS correlation (grip, cutters, spin control) ──
    dry_index = min(1.0, max(0.0, ((temperature - 30) / 10.0) + ((50 - humidity) / 35.0)))
    if dry_index > 0.15:
        dry_bowl_diff = ((t1_bowl_strength + 0.7 * t1_spin) - (t2_bowl_strength + 0.7 * t2_spin)) / 100.0
        dry_bowl_logit = 0.38 * dry_index * dry_bowl_diff
        conditions_logit += dry_bowl_logit
        if dry_bowl_diff > 0.01:
            edge_reasons.append(f"Dry-surface bowling correlation favours {t1n} (spin/control resources)")
        elif dry_bowl_diff < -0.01:
            edge_reasons.append(f"Dry-surface bowling correlation favours {t2n} (spin/control resources)")

    # ── WIND: high-scoring games benefit stronger batting ──
    if wind > 20:
        detail["wind_impact"] = "significant — high scoring likely"
        edge_reasons.append(f"Strong wind ({wind} kmh) — higher scoring game expected")

    # Set summary
    if conditions_logit > 0.01:
        detail["favours_team"] = "team1"
    elif conditions_logit < -0.01:
        detail["favours_team"] = "team2"
    else:
        detail["favours_team"] = "neutral"

    detail["conditions_edge_text"] = " | ".join(edge_reasons) if edge_reasons else "Conditions relatively neutral for both teams"

    if conditions_logit > 0.01:
        detail["one_liner"] = f"{t1n} — net weather/dew/swing tilt from the factors above."
    elif conditions_logit < -0.01:
        detail["one_liner"] = f"{t2n} — net weather/dew/swing tilt from the factors above."
    else:
        detail["one_liner"] = "Conditions are close — dew, swing and surface effects largely balance out."

    return conditions_logit, detail


def _classify_match_time(match_time: str) -> str:
    """Classify match time into 'day', 'afternoon', or 'evening'.
    
    IPL scheduling:
    - 3:30 PM IST (10:00 UTC) → 'afternoon' — ends ~7 PM, minimal dew
    - 7:30 PM IST (14:00 UTC) → 'evening'   — ends ~11 PM, heavy dew in 2nd innings
    - Anything else before 2 PM IST → 'day'
    
    This distinction is critical for toss impact: afternoon matches have far less
    dew than evening matches, so the chasing advantage is reduced.
    """
    if not match_time:
        return "evening"  # Default assumption for IPL
    try:
        from datetime import datetime as dt
        parsed = dt.fromisoformat(match_time.replace("Z", "+00:00"))
        # Convert to IST (UTC + 5:30)
        ist_hour = parsed.hour + 5
        ist_minute = parsed.minute + 30
        if ist_minute >= 60:
            ist_hour += 1
            ist_minute -= 60
        
        if ist_hour < 14:
            return "day"
        elif ist_hour < 17:
            # 2 PM - 5 PM IST → afternoon slot (3:30 PM start matches)
            return "afternoon"
        else:
            # 5 PM+ IST → evening slot (7:30 PM start matches)
            return "evening"
    except Exception:
        return "evening"


def _is_night_match(match_time: str) -> bool:
    """Legacy wrapper — returns True for evening matches only."""
    return _classify_match_time(match_time) == "evening"


def _guess_role(name: str, squad: list) -> str:
    for p in squad:
        if p.get("name", "").lower() == name.lower():
            return _canonical_xi_role(p.get("role"))
    return "Batsman"
