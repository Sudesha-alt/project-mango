from pathlib import Path

p = Path(r"c:\Users\SudeshaTr\project-mango\backend\services\pre_match_predictor.py")
s = p.read_text(encoding="utf-8")

s = s.replace(
    """    squad_logit = raw_squad_logit + balance_bonus

    # Restore original STAR_PLAYERS ratings
    for name, orig in original_ratings.items():
        if orig is not None:
            STAR_PLAYERS[name] = orig
        else:
            STAR_PLAYERS.pop(name, None)

""",
    """    squad_logit = raw_squad_logit + balance_bonus

    batting_depth_logit = _batting_depth_logit(remapped_squads)
    bowling_strength_logit = _bowling_strength_logit(remapped_squads)
    allrounder_depth_logit = _allrounder_depth_logit(t1_rating, t2_rating)
    powerplay_logit = _powerplay_performance_logit(remapped_squads)
    death_overs_logit = _death_overs_performance_logit(remapped_squads)
    key_avail_logit = _key_players_availability_logit(remapped_squads)

""",
)

s = s.replace(
    """    home_logit = 0.0
    if is_t1_home:
        home_logit = 0.45
    elif is_t2_home:
        home_logit = -0.45

    # Pitch-based advantage: compare team bowling strength vs venue pitch type
    pitch_logit = 0.0
""",
    """    home_ground_logit = 0.0
    if is_t1_home:
        home_ground_logit = 0.45
    elif is_t2_home:
        home_ground_logit = -0.45

    # Pitch-based advantage: compare team bowling strength vs venue pitch type
    venue_pitch_logit = 0.0
""",
)

s = s.replace(
    "            pitch_logit = 2.0 * ((t1_pitch_fit - t2_pitch_fit) / max(t1_pitch_fit + t2_pitch_fit, 1))\n\n    venue_logit = home_logit + pitch_logit\n\n",
    "            venue_pitch_logit = 2.0 * ((t1_pitch_fit - t2_pitch_fit) / max(t1_pitch_fit + t2_pitch_fit, 1))\n\n",
)

s = s.replace(
    """    # ��━━━━━ Combined ��━━━━━
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
""",
    """    top_order_consistency_logit = _top_order_consistency_logit(form_data)

    for name, orig in original_ratings.items():
        if orig is not None:
            STAR_PLAYERS[name] = orig
        else:
            STAR_PLAYERS.pop(name, None)

    # ��━━━━━ Combined (16 weighted logits) ��━━━━━
    combined_logit = (
        WEIGHTS["squad_strength"] * squad_logit
        + WEIGHTS["current_form"] * form_logit
        + WEIGHTS["venue_pitch"] * venue_pitch_logit
        + WEIGHTS["home_ground_advantage"] * home_ground_logit
        + WEIGHTS["h2h"] * h2h_logit
        + WEIGHTS["toss_impact"] * toss_logit
        + WEIGHTS["bowling_depth"] * bowl_depth_logit
        + WEIGHTS["bowling_strength"] * bowling_strength_logit
        + WEIGHTS["conditions"] * conditions_logit
        + WEIGHTS["momentum"] * momentum_logit
        + WEIGHTS["batting_depth"] * batting_depth_logit
        + WEIGHTS["powerplay_performance"] * powerplay_logit
        + WEIGHTS["death_overs_performance"] * death_overs_logit
        + WEIGHTS["key_players_availability"] * key_avail_logit
        + WEIGHTS["allrounder_depth"] * allrounder_depth_logit
        + WEIGHTS["top_order_consistency"] * top_order_consistency_logit
    )
""",
)

p.write_text(s, encoding="utf-8")
print("pre_match_predictor patched")
