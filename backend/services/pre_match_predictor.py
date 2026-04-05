"""
Pre-Match Prediction Engine — IPL 2026 Post-Auction Era

5-Factor Model (user-defined weights):
  1. Form (35%) — Recent results in IPL 2026 season + player buzz
  2. Squad Strength / Availability (25%) — 2026 roster quality from STAR_PLAYERS db
  3. Team Combination / Strategy Clarity (20%) — XI settled-ness, role clarity, overseas balance
  4. Home Advantage (15%) — Venue familiarity, crowd, conditions knowledge
  5. H2H / Pitch Conditions (5%) — Historical head-to-head, pitch type
"""
import math
import logging
from typing import Dict

logger = logging.getLogger(__name__)

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


def compute_prediction(stats: Dict, playing_xi: Dict = None, squad_data: Dict = None) -> Dict:
    """
    5-Factor Pre-Match Prediction Engine (Post-Auction IPL 2026).

    Weights:
      Form                (0.35) — IPL 2026 season results + player buzz sentiment
      Squad Strength      (0.25) — 2026 roster quality (batting + bowling depth)
      Team Combination    (0.20) — XI clarity, overseas balance, role coverage
      Home Advantage      (0.15) — Venue familiarity, crowd, conditions
      H2H / Pitch         (0.05) — Head-to-head record + pitch type
    """
    form = stats.get("form", {})
    squad = stats.get("squad_strength", {})
    venue = stats.get("venue_stats", {})
    h2h = stats.get("h2h", {})
    pitch = stats.get("pitch_conditions", {})
    toss = stats.get("toss", {})

    # Remap squad_data keys to team1/team2
    remapped_squads = {}
    if squad_data:
        squad_names = list(squad_data.keys())
        remapped_squads = {
            "team1": squad_data.get(squad_names[0], []) if len(squad_names) > 0 else [],
            "team2": squad_data.get(squad_names[1], []) if len(squad_names) > 1 else [],
        }

    # ━━━━━━ Factor 1: Form (35%) ━━━━━━
    # IPL 2026 season results + player buzz
    t1_wins = form.get("team1_last5_wins", 0)
    t1_losses = form.get("team1_last5_losses", 0)
    t2_wins = form.get("team2_last5_wins", 0)
    t2_losses = form.get("team2_last5_losses", 0)
    t1_games = t1_wins + t1_losses
    t2_games = t2_wins + t2_losses

    # Win percentage with sample-size damping
    t1_form_pct = t1_wins / max(t1_games, 1)
    t2_form_pct = t2_wins / max(t2_games, 1)
    min_games = min(t1_games, t2_games)
    damping = min(1.0, min_games / 3.0) if min_games > 0 else 0.0
    t1_form_adj = 0.5 + (t1_form_pct - 0.5) * damping
    t2_form_adj = 0.5 + (t2_form_pct - 0.5) * damping

    # Player buzz overlay from playing XI
    form_logit = 3.0 * (t1_form_adj - t2_form_adj)
    if playing_xi:
        t1_buzz = _calc_avg_buzz(playing_xi.get("team1_xi", []))
        t2_buzz = _calc_avg_buzz(playing_xi.get("team2_xi", []))
        buzz_logit = 1.5 * ((t1_buzz - t2_buzz) / 100)
        form_logit = 0.6 * form_logit + 0.4 * buzz_logit

    # ━━━━━━ Factor 2: Squad Strength (25%) ━━━━━━
    if remapped_squads.get("team1") and remapped_squads.get("team2"):
        t1_rating, t2_rating = _compute_squad_ratings(remapped_squads, playing_xi)
    else:
        t1_rating = {"batting": squad.get("team1_batting_rating", 75), "bowling": squad.get("team1_bowling_rating", 75)}
        t2_rating = {"batting": squad.get("team2_batting_rating", 75), "bowling": squad.get("team2_bowling_rating", 75)}

    t1_overall = 0.55 * t1_rating["batting"] + 0.45 * t1_rating["bowling"]
    t2_overall = 0.55 * t2_rating["batting"] + 0.45 * t2_rating["bowling"]
    squad_logit = 5.0 * ((t1_overall - t2_overall) / 100)

    # ━━━━━━ Factor 3: Team Combination / Strategy (20%) ━━━━━━
    t1_combo, t2_combo = _compute_combination_score(remapped_squads, playing_xi)
    combo_logit = 3.0 * ((t1_combo - t2_combo) / 100)

    # ━━━━━━ Factor 4: Home Advantage (15%) ━━━━━━
    home_logit = 0.0
    if venue.get("is_team1_home"):
        home_logit = 0.5  # Significant home edge
    elif venue.get("is_team2_home"):
        home_logit = -0.5
    # Venue spin/pace factor based on squad composition
    t1_bowl_rating = t1_rating["bowling"] / 100
    t2_bowl_rating = t2_rating["bowling"] / 100
    pitch_type = pitch.get("pitch_type", "balanced")
    if pitch_type == "bowling":
        home_logit += 0.8 * (t1_bowl_rating - t2_bowl_rating)
    elif pitch_type == "batting":
        home_logit += 0.5 * ((t1_rating["batting"] - t2_rating["batting"]) / 100)

    # ━━━━━━ Factor 5: H2H + Pitch (5%) ━━━━━━
    t1_h2h = h2h.get("team1_wins", 0)
    t2_h2h = h2h.get("team2_wins", 0)
    total_h2h = t1_h2h + t2_h2h
    h2h_ratio = t1_h2h / max(total_h2h, 1)
    h2h_logit = 1.5 * (h2h_ratio - 0.5)
    # Dew factor
    dew = pitch.get("dew_factor", 3) / 10
    dew_logit = -0.15 * dew if dew > 0.4 else 0.0
    pitch_logit = h2h_logit + dew_logit

    # ━━━━━━ Combined ━━━━━━
    combined_logit = (
        0.35 * form_logit +
        0.25 * squad_logit +
        0.20 * combo_logit +
        0.15 * home_logit +
        0.05 * pitch_logit
    )

    # Sigmoid → probability
    raw_probability = 1.0 / (1.0 + math.exp(-combined_logit))
    calibrated = round(max(0.05, min(0.95, raw_probability)), 4)

    team1_win_prob = round(calibrated * 100, 1)
    team2_win_prob = round(100 - team1_win_prob, 1)

    return {
        "team1_win_prob": team1_win_prob,
        "team2_win_prob": team2_win_prob,
        "confidence": "high" if abs(combined_logit) > 0.3 else "medium" if abs(combined_logit) > 0.1 else "low",
        "raw_probability": round(raw_probability, 4),
        "calibrated_probability": calibrated,
        "combined_logit": round(combined_logit, 4),
        "factors": {
            "form": {
                "weight": 0.35,
                "team1_form_pct": round(t1_form_pct * 100),
                "team2_form_pct": round(t2_form_pct * 100),
                "team1_record": f"{t1_wins}W/{t1_losses}L",
                "team2_record": f"{t2_wins}W/{t2_losses}L",
                "logit_contribution": round(0.35 * form_logit, 4),
            },
            "squad_strength": {
                "weight": 0.25,
                "team1_batting": t1_rating["batting"],
                "team1_bowling": t1_rating["bowling"],
                "team1_overall": round(t1_overall, 1),
                "team2_batting": t2_rating["batting"],
                "team2_bowling": t2_rating["bowling"],
                "team2_overall": round(t2_overall, 1),
                "logit_contribution": round(0.25 * squad_logit, 4),
            },
            "team_combination": {
                "weight": 0.20,
                "team1_score": round(t1_combo, 1),
                "team2_score": round(t2_combo, 1),
                "logit_contribution": round(0.20 * combo_logit, 4),
            },
            "home_advantage": {
                "weight": 0.15,
                "team1_home": venue.get("is_team1_home", False),
                "team2_home": venue.get("is_team2_home", False),
                "logit_contribution": round(0.15 * home_logit, 4),
            },
            "h2h_pitch": {
                "weight": 0.05,
                "h2h_record": f"{t1_h2h}-{t2_h2h}",
                "pitch_type": pitch_type,
                "logit_contribution": round(0.05 * pitch_logit, 4),
            },
        },
    }


def apply_buzz_and_luck(xi_data: dict) -> dict:
    """Apply buzz sentiment and luck biasness to Playing XI data."""
    if not xi_data:
        return xi_data
    return xi_data


def _calc_avg_buzz(players: list) -> float:
    if not players:
        return 50
    buzzes = []
    for p in players:
        bs = p.get("buzz_score")
        if bs is not None:
            buzzes.append((bs + 100) / 2)  # -100..+100 → 0..100
        else:
            buzzes.append(50)
    return sum(buzzes) / len(buzzes)


def _compute_squad_ratings(squad_data: dict, playing_xi: dict = None) -> tuple:
    """Compute batting/bowling ratings from actual 2026 squad roster."""
    results = {}
    for team_key in ["team1", "team2"]:
        players = squad_data.get(team_key, [])
        if not players:
            results[team_key] = {"batting": 50, "bowling": 50}
            continue

        xi_names = set()
        if playing_xi:
            for p in playing_xi.get(f"{team_key}_xi", []):
                xi_names.add(p.get("name", "").lower())

        bat_ratings = []
        bowl_ratings = []
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
            if weights["batting"] >= 6:
                bat_ratings.append(player_rating)
            if weights["bowling"] >= 6:
                bowl_ratings.append(player_rating)

        bat_avg = sum(sorted(bat_ratings, reverse=True)[:6]) / min(6, max(len(bat_ratings), 1)) if bat_ratings else 50
        bowl_avg = sum(sorted(bowl_ratings, reverse=True)[:5]) / min(5, max(len(bowl_ratings), 1)) if bowl_ratings else 50

        results[team_key] = {"batting": round(bat_avg, 1), "bowling": round(bowl_avg, 1)}

    return results.get("team1", {"batting": 50, "bowling": 50}), results.get("team2", {"batting": 50, "bowling": 50})


def _compute_combination_score(squad_data: dict, playing_xi: dict = None) -> tuple:
    """
    Score team combination quality: role coverage, overseas balance, settled XI.
    Higher = better combination clarity.
    """
    scores = []
    for team_key in ["team1", "team2"]:
        xi = playing_xi.get(f"{team_key}_xi", []) if playing_xi else []
        squad = squad_data.get(team_key, [])
        players = xi if xi else squad

        if not players:
            scores.append(50)
            continue

        score = 50  # base

        # Role coverage: need at least 3 batsmen, 2 all-rounders, 4 bowlers, 1 keeper
        roles = {"Batsman": 0, "All-rounder": 0, "Bowler": 0, "Wicketkeeper": 0}
        overseas_count = 0
        star_count = 0
        for p in players:
            role = p.get("role", "Batsman")
            roles[role] = roles.get(role, 0) + 1
            if p.get("is_overseas") or p.get("isOverseas"):
                overseas_count += 1
            if STAR_PLAYERS.get(p.get("name", ""), 0) >= 83:
                star_count += 1

        # Good balance bonus
        if roles.get("Batsman", 0) >= 3:
            score += 5
        if roles.get("All-rounder", 0) >= 2:
            score += 8  # all-rounders = depth
        if roles.get("Bowler", 0) >= 4:
            score += 5
        if roles.get("Wicketkeeper", 0) >= 1:
            score += 3

        # Overseas optimization (4 = perfect, <3 = wasted slot, >4 = impossible)
        if overseas_count == 4:
            score += 6
        elif overseas_count == 3:
            score += 3
        elif overseas_count < 3:
            score -= 3  # not using overseas slots well

        # Star power: more high-rated players = clearer XI
        score += min(15, star_count * 3)

        # XI settled-ness: if we have exactly 11 from playing_xi, it's "settled"
        if xi and len(xi) == 11:
            score += 5

        scores.append(min(100, max(0, score)))

    return scores[0] if len(scores) > 0 else 50, scores[1] if len(scores) > 1 else 50


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
