from pathlib import Path

p = Path(r"c:\Users\SudeshaTr\project-mango\backend\services\pre_match_predictor.py")
text = p.read_text(encoding="utf-8")
idx = text.find('WEIGHTS["venue_pitch_home"] * venue_logit')
if idx == -1:
    raise SystemExit("anchor not found")
line_start = text.rfind("\n    # ", 0, idx) + 1
end_marker = "\n\n    raw_probability = 1.0 / (1.0 + math.exp(-combined_logit))"
end = text.find(end_marker, idx)
if end == -1:
    raise SystemExit("end not found")

new_block = """    top_order_consistency_logit = _top_order_consistency_logit(form_data)

    for name, orig in original_ratings.items():
        if orig is not None:
            STAR_PLAYERS[name] = orig
        else:
            STAR_PLAYERS.pop(name, None)

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
"""

new_text = text[:line_start] + new_block + text[end:]
p.write_text(new_text, encoding="utf-8")
print("replaced combined block")
