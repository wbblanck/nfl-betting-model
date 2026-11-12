"""Box-score accounting: the invariants every simulated team-game must satisfy, checked on every run.

A box is a dict of integer numpy arrays for one team in one game. Player arrays are [runs, players]; team arrays are
[runs]. Players must include every ball carrier and every targeted player, or the sums cannot reconcile.
  targets, rec, rec_yds, carries, rush_yds                          per player
  pass_att, pass_cmp, pass_yds, sacks, scrambles, dropbacks, team_carries    per team
Definitions: a sack is a dropback and not a pass attempt; a scramble is a dropback and a carry; pass_yds is gross
(sack yards not subtracted), so it equals the receivers' yards.
"""
from __future__ import annotations

import numpy as np

PLAYER = ("targets", "rec", "rec_yds", "carries", "rush_yds")
TEAM = ("pass_att", "pass_cmp", "pass_yds", "sacks", "scrambles", "dropbacks", "team_carries")
NON_NEGATIVE = ("targets", "rec", "carries", "pass_att", "pass_cmp", "sacks", "scrambles", "dropbacks", "team_carries")


def violations(box: dict[str, np.ndarray]) -> dict[str, int]:
    """Rule -> number of runs breaking it (rules with no breaks are omitted). An empty dict means the box reconciles."""
    missing = [k for k in PLAYER + TEAM if k not in box]
    if missing:
        raise KeyError(f"box is missing {missing}")
    n = len(box["pass_att"])
    for k in PLAYER + TEAM:
        a = box[k]
        if not np.issubdtype(a.dtype, np.integer):
            raise TypeError(f"{k} must be an integer array")
        if a.shape[0] != n or a.ndim != (2 if k in PLAYER else 1):
            raise ValueError(f"{k} has shape {a.shape}")
    b = box
    rules = {
        "negative count": np.any([(b[k] < 0).reshape(n, -1).any(axis=1) for k in NON_NEGATIVE], axis=0),
        "receptions > targets (player)": (b["rec"] > b["targets"]).any(axis=1),
        "completions > attempts": b["pass_cmp"] > b["pass_att"],
        "targets > pass attempts (team)": b["targets"].sum(axis=1) > b["pass_att"],
        "receptions != completions (team)": b["rec"].sum(axis=1) != b["pass_cmp"],
        "receiving yards != passing yards (team)": b["rec_yds"].sum(axis=1) != b["pass_yds"],
        "yards on zero receptions (player)": ((b["rec"] == 0) & (b["rec_yds"] != 0)).any(axis=1),
        "yards on zero carries (player)": ((b["carries"] == 0) & (b["rush_yds"] != 0)).any(axis=1),
        "player carries != team carries": b["carries"].sum(axis=1) != b["team_carries"],
        "scrambles > team carries": b["scrambles"] > b["team_carries"],
        "dropbacks != attempts + sacks + scrambles": b["dropbacks"] != b["pass_att"] + b["sacks"] + b["scrambles"],
    }
    return {k: int(v.sum()) for k, v in rules.items() if v.any()}
