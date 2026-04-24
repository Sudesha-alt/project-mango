"""
Runtime calibration for the 5-parameter pre-match model and Claude pre-match prompts.

Values are merged from ``backend/config/prematch_calibration.json`` (updated when a
learning proposal is approved). This avoids self-modifying Python source.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "prematch_calibration.json"


def _default_config() -> Dict[str, Any]:
    return {"weight_overrides": {}, "claude_prompt_addendum": "", "meta": {}}


def load_calibration() -> Dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return _default_config()
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default_config()
        data.setdefault("weight_overrides", {})
        data.setdefault("claude_prompt_addendum", "")
        data.setdefault("meta", {})
        return data
    except Exception as e:
        logger.warning("prematch_calibration: could not read %s: %s", _CONFIG_PATH, e)
        return _default_config()


def save_calibration(cfg: Dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "weight_overrides": dict(cfg.get("weight_overrides") or {}),
        "claude_prompt_addendum": str(cfg.get("claude_prompt_addendum") or ""),
        "meta": dict(cfg.get("meta") or {}),
    }
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
        f.write("\n")


def get_effective_weights(base: Dict[str, float]) -> Dict[str, float]:
    """Return base weights with optional overrides from JSON, renormalized to sum 1.0."""
    cfg = load_calibration()
    ov = cfg.get("weight_overrides") or {}
    if not ov:
        return dict(base)
    merged = {k: float(v) for k, v in base.items()}
    for k, v in ov.items():
        if k in merged:
            try:
                merged[k] = float(v)
            except (TypeError, ValueError):
                continue
    s = sum(merged.values())
    if s <= 1e-9:
        return dict(base)
    return {k: merged[k] / s for k in merged}


def get_claude_prompt_addendum() -> str:
    return str(load_calibration().get("claude_prompt_addendum") or "").strip()


def apply_learning_to_config(
    *,
    weight_overrides: Dict[str, float],
    claude_addendum: str = "",
    proposal_id: str = "",
) -> Dict[str, Any]:
    """
    Merge approved learning into on-disk calibration.
    ``weight_overrides`` are absolute target weights for the five keys (renormalized).
    """
    cfg = load_calibration()
    new_ov: Dict[str, float] = {}
    for k, v in (weight_overrides or {}).items():
        try:
            new_ov[k] = float(v)
        except (TypeError, ValueError):
            continue
    s = sum(new_ov.values())
    if s > 1e-9:
        cfg["weight_overrides"] = {k: round(v / s, 6) for k, v in new_ov.items()}
    add = (claude_addendum or "").strip()
    if add:
        prev = str(cfg.get("claude_prompt_addendum") or "").strip()
        cfg["claude_prompt_addendum"] = (prev + "\n\n" + add).strip() if prev else add
    meta = dict(cfg.get("meta") or {})
    if proposal_id:
        meta["last_applied_proposal_id"] = proposal_id
    cfg["meta"] = meta
    save_calibration(cfg)
    return cfg
