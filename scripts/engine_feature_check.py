"""Engine phase 2 gate on the real warehouse: build the feature table, then scramble every raw row of every game
kicking off at or after a cut-off (player stats, snap counts, play-by-play, participation) and rebuild. Rows up to
the cut-off must be identical. Writes docs/engine/feature_check.md. Reads no outcome for modelling and no price."""
import sys

import numpy as np
import polars as pl

from nflbet.config import ROOT
from nflbet.engine.data import nflverse as N, player_week as PW
from nflbet.engine.features import build as B, facts as F

OUT = ROOT / "docs" / "engine" / "feature_check.md"
CUTS = ["2019-10-13 13:00", "2023-11-12 13:00", "2025-12-25 13:00"]


def load(seasons):
    part = [s for s in seasons if N.path("participation", s).exists()]
    snap = [s for s in seasons if N.path("snap_counts", s).exists()]
    return {"stats": N.read("player_stats", seasons), "snaps": N.read("snap_counts", snap),
            "pbp": N.read("pbp", seasons).select("game_id", "play_id", "posteam", "play_type", "qb_scramble", "two_point_attempt", "qb_dropback"),
            "part": N.read("participation", part).select("nflverse_game_id", "play_id", "offense_players"),
            "rosters": N.read("rosters_weekly", seasons).select("gsis_id", "season", "week", "team", "position", "status", "game_type")}


def features(raw, players, games, with_active=True):
    pw, rep = PW.build(raw["stats"], raw["snaps"], players)
    tg = F.team_game(raw["stats"], raw["pbp"], games)
    return B.build(pw, tg, F.on_field(raw["part"], raw["pbp"]), F.active(raw["rosters"], tg) if with_active else None), rep


def scramble(raw, late: set, seed=1):
    """Every numeric fact of the late games is replaced by noise; play types and on-field lists are shuffled among
    the late rows. Keys (who, which game) are kept, and a player with no snaps keeps none, so the same rows exist:
    whether a player has a row for a game depends on whether he played in it, which is not a feature."""
    rng = np.random.default_rng(seed)
    def noise(df, key, cols, keep_zero=False):
        m = pl.Series(df[key].is_in(late).to_numpy())
        new = []
        for c in (c for c in cols if c in df.columns):
            hit = (m & (pl.col(c).fill_null(0) > 0)) if keep_zero else m
            lo = 1 if keep_zero else 0
            new.append(pl.when(hit).then(pl.Series(rng.integers(lo, 80, df.height)).cast(df[c].dtype, strict=False)).otherwise(pl.col(c)).alias(c))
        return df.with_columns(new)
    def shuffle(df, key, cols):
        m = df[key].is_in(late).to_numpy()
        idx = np.arange(df.height)
        idx[m] = rng.permutation(idx[m])
        return df.with_columns([df[c].gather(idx).alias(c) for c in cols])
    return {"stats": noise(raw["stats"], "game_id", PW.STATS), "snaps": noise(raw["snaps"], "game_id", ["offense_snaps"], keep_zero=True),
            "pbp": shuffle(raw["pbp"], "game_id", ["play_type", "qb_scramble", "qb_dropback", "two_point_attempt"]),
            "part": shuffle(raw["part"], "nflverse_game_id", ["offense_players"]),
            "rosters": raw["rosters"]}                  # the active list is published before kickoff: not an outcome


def main() -> int:
    seasons = list(N.SEASONS)
    players, games = N.read("players"), F.games(N.read("schedules"))
    raw = load(seasons)
    base, rep = features(raw, players, games)
    N.DIR.joinpath("features").mkdir(parents=True, exist_ok=True)
    base.write_parquet(N.DIR / "features" / "player_game.parquet")
    L = ["# Feature leakage check (engine phase 2 gate)", "",
         "Written by `scripts/engine_feature_check.py` from the local warehouse. For each cut-off, every raw row of every",
         "game kicking off at or after it is scrambled (player stats, snap counts, play-by-play, participation), the whole",
         "pipeline is rebuilt, and the feature rows up to the cut-off are compared with the originals.", "",
         f"Feature table: {base.height:,} player-games ({int(base['played'].sum()):,} played, the rest on the game-day active list "
         f"without playing), {base.width} columns, seasons {seasons[0]}-{seasons[-1]}; "
         f"contents hash `{B.snapshot_hash(base)[:16]}`.", "",
         "| Cut-off kickoff | Games scrambled | Rows up to cut-off | Identical | Later rows changed |", "|---|---|---|---|---|"]
    ok = True
    for cut in CUTS:
        late = set(games.filter(pl.col("kickoff") >= cut)["game_id"])
        scr, _ = features(scramble(raw, late), players, games)
        keep = pl.col("kickoff") <= cut
        same = base.filter(keep).equals(scr.filter(keep))
        moved = not base.filter(~keep).equals(scr.filter(~keep))
        ok &= same and moved
        L.append(f"| {cut} | {len(late & set(base['game_id'])):,} | {base.filter(keep).height:,} | {'yes' if same else '**NO**'} | {'yes' if moved else '**NO**'} |")
    L += ["", "Rows at the cut-off kickoff itself are among those compared: their own game is scrambled and their features do not move.",
          "'Later rows changed' confirms the scramble was real.", "", f"Result: **{'PASS' if ok else 'FAIL'}**"]
    OUT.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
