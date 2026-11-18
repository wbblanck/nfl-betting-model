"""Test M (docs/engine_preregistration.md, amendment of 2026-11-17): the frozen engines' P(over) at DraftKings' line
against DraftKings' de-vigged P(over), on 2026 weeks 11-18.

  python scripts/engine_test_m.py --counts 11     counts only for one week (props, matches, drops by reason); no
                                                  probability is compared with a price. Writes
                                                  data/live/engine_forecasts/2026_w11/counts.json
  python scripts/engine_test_m.py --grade         the test itself, once, after week 18; refuses if any week's
                                                  forecasts are missing or failed their checks, if a result exists,
                                                  or if the working tree has uncommitted changes
"""
import gzip
import json
import math
import subprocess
import sys
from collections import Counter

import numpy as np
import polars as pl

from nflbet.config import ROOT
from nflbet.engine import forecast as FO, scoring as S
from nflbet.engine.data import nflverse as N, player_week as PW
from nflbet.quant.odds import implied
from nflbet.sources import ids, parlay

SEASON, WEEKS, ENGINES, MIN_PROPS = 2026, tuple(range(11, 19)), ("A", "B"), 2000
LEVEL = 0.05 / len(ENGINES)
CLIP = (0.001, 0.999)
FC, PARLAY = ROOT / "data" / "live" / "engine_forecasts", ROOT / "data" / "live" / "parlay"
RESULT, REPORT = ROOT / "data" / "backtests" / "engine_test_m_2026.json", ROOT / "docs" / "engine" / "test_m_2026.md"


def fix(t: str) -> str:
    return ids.TEAM_FIX.get(t, t)


def dk_props(kickoffs: dict) -> tuple[pl.DataFrame, Counter]:
    """DraftKings props per target game from the last ParlayAPI snapshot stamped before its kickoff, screened.
    kickoffs: game_id -> kickoff (Eastern string). Returns rows (game_id, game, nkey, player, market, line, p_dk)."""
    names = sorted(p.name for p in PARLAY.glob("*.json.gz"))
    out, drop, cache = [], Counter(), {}
    for gid, ko in kickoffs.items():
        _, _, away, home = gid.split("_")
        snap = FO.snapshot_before(names, ko, max_hours=72.0)
        if snap is None:
            drop["game: no DraftKings snapshot before kickoff"] += 1
            continue
        if snap not in cache:
            cache[snap] = parlay.parse(json.load(gzip.open(PARLAY / snap, "rt")))
        d = cache[snap].filter((pl.col("book") == "dk") & (pl.col("game") == ids.game_key(fix(away), fix(home)))
                               & pl.col("market").is_in(list(FO.MARKETS)))
        for r in d.iter_rows(named=True):
            io, iu = implied(r["over"]), implied(r["under"])
            p, hold = io / (io + iu), io + iu - 1
            if r["line"] % 1 != 0.5:
                drop["prop: whole-number line"] += 1
            elif not (0.35 <= p <= 0.65) or hold >= 0.10:
                drop["prop: fails the price screens"] += 1
            else:
                out.append({"game_id": gid, "nkey": r["nkey"], "player": r["player"], "market": r["market"], "line": r["line"],
                            "p_dk": p, "snapshot": snap})
    schema = {"game_id": pl.Utf8, "nkey": pl.Utf8, "player": pl.Utf8, "market": pl.Utf8, "line": pl.Float64, "p_dk": pl.Float64, "snapshot": pl.Utf8}
    return pl.DataFrame(out, schema=schema), drop


def match(props: pl.DataFrame, fc: pl.DataFrame, players: pl.DataFrame) -> tuple[pl.DataFrame, Counter]:
    """Attach player_id: full normalized name, else last name + first initial, among the game's forecast rows."""
    who = fc.select("game_id", "player_id").unique().join(players.select(pl.col("gsis_id").alias("player_id"), "display_name"),
                                                          on="player_id", how="left")
    pool: dict = {}
    for g, pid, name in who.iter_rows():
        pool.setdefault(g, []).append((pid, ids.norm_name(name or ""), ids.last_name(name or "")))
    pids, drop = [], Counter()
    for g, nkey, player in props.select("game_id", "nkey", "player").iter_rows():
        got = None
        for k, val in ((1, nkey), (2, ids.last_name(player))):
            hits = {p[0] for p in pool.get(g, []) if p[k] == val}
            if len(hits) == 1:
                got = hits.pop()
                break
            if len(hits) > 1:
                drop["prop: player ambiguous"] += 1
                got = False
                break
        if got is None:
            drop["prop: player has no forecast (not on the projected list)"] += 1
        pids.append(got or None)
    return props.with_columns(pl.Series("player_id", pids, dtype=pl.Utf8)).filter(pl.col("player_id").is_not_null()), drop


def week_rows(week: int, players: pl.DataFrame, pw: pl.DataFrame | None) -> tuple[pl.DataFrame, dict, pl.DataFrame]:
    d = FC / f"{SEASON}_w{week:02d}"
    man = json.loads((d / "manifest.json").read_text())
    fc = pl.read_parquet(d / "forecasts.parquet")
    kick = {g: u["kickoff_et"] for g, u in man["games"].items() if u.get("injury_snapshot")}
    props, drop = dk_props(kick)
    props, d2 = match(props, fc, players)
    drop.update(d2)
    if pw is not None:                      # void unless the player played (a stat row or an offensive snap)
        played = pw.select("player_id", "game_id", *FO.MARKETS.values())
        n = props.height
        props = props.join(played, on=["player_id", "game_id"], how="inner")
        drop["prop: player did not play (void)"] += n - props.height
        props = props.with_columns(pl.struct(["market", *FO.MARKETS.values()]).map_elements(
            lambda s: s[FO.MARKETS[s["market"]]], return_dtype=pl.Int64).alias("y")).drop(list(FO.MARKETS.values()))
    return props.with_columns(pl.lit(week).alias("week")), {**man, "drops": dict(drop)}, fc


def engine_p(props: pl.DataFrame, fc: pl.DataFrame, engine: str) -> np.ndarray:
    e = fc.filter(pl.col("engine") == engine)
    out = []
    for g, pid, m, line in props.select("game_id", "player_id", "market", "line").iter_rows():
        h = e.filter((pl.col("game_id") == g) & (pl.col("player_id") == pid) & (pl.col("market") == m))
        out.append(FO.p_over(h, line) if h.height else math.nan)
    return np.array(out)


def log_loss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, *CLIP)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    players = N.read("players")
    if mode == "--counts" and len(sys.argv) == 3:
        week = int(sys.argv[2])
        props, man, _ = week_rows(week, players, None)
        out = {"week": week, "games_forecast": sum(1 for u in man["games"].values() if u.get("injury_snapshot")),
               "player_games_forecast": man["player_games"], "props_matched": props.height, "drops": man["drops"],
               "by_market": dict(Counter(props["market"].to_list()))}
        (FC / f"{SEASON}_w{week:02d}" / "counts.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        print(json.dumps(out, indent=1))
        return 0
    if mode != "--grade":
        print(__doc__)
        return 2
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    missing = [w for w in WEEKS if not (FC / f"{SEASON}_w{w:02d}" / "manifest.json").exists()]
    failed = [w for w in WEEKS if w not in missing and not all(json.loads((FC / f"{SEASON}_w{w:02d}" / "manifest.json").read_text())[k]
                                                                for k in ("engine_a_frozen_matches", "engine_b_frozen_matches"))]
    if RESULT.exists() or dirty or missing or failed:
        print(f"REFUSED: result exists={RESULT.exists()}, uncommitted={bool(dirty)}, missing weeks={missing}, failed checks={failed}")
        return 1
    import nflreadpy as nr
    pw, _ = PW.build(nr.load_player_stats([SEASON]), nr.load_snap_counts([SEASON]), players)
    frames, drops = [], Counter()
    for w in WEEKS:
        props, man, fc = week_rows(w, players, pw)
        for e in ENGINES:
            props = props.with_columns(pl.Series(f"p_{e}", engine_p(props, fc, e)))
        drops.update(man["drops"])
        frames.append(props)
    df = pl.concat(frames).drop_nans([f"p_{e}" for e in ENGINES])          # the same rows for both engines
    y, week = (df["y"].to_numpy() > df["line"].to_numpy()).astype(float), df["week"].to_numpy()
    ll_dk = log_loss(df["p_dk"].to_numpy(), y)
    res = {"props": df.height, "weeks": int(len(np.unique(week))), "level": LEVEL, "drops": dict(drops), "dk_log_loss": float(ll_dk.mean()),
           "engines": {}, "by_market": {}}
    for e in ENGINES:
        ll = log_loss(df[f"p_{e}"].to_numpy(), y)
        d, lo, hi = S.paired_bootstrap(ll - ll_dk, week, level=LEVEL)
        enough = df.height >= MIN_PROPS and res["weeks"] >= len(WEEKS)
        res["engines"][e] = {"log_loss": float(ll.mean()), "diff": [d, lo, hi],
                             "verdict": ("PASS" if hi < 0 else "FAIL") if enough else "INCONCLUSIVE"}
    a, b = log_loss(df["p_A"].to_numpy(), y), log_loss(df["p_B"].to_numpy(), y)
    res["a_minus_b"] = list(S.paired_bootstrap(a - b, week, level=0.05))
    for m in FO.MARKETS:
        k = (df["market"] == m).to_numpy()
        if k.any():
            res["by_market"][m] = {"n": int(k.sum()), "dk": float(ll_dk[k].mean()),
                                   **{e: float(log_loss(df[f"p_{e}"].to_numpy()[k], y[k]).mean()) for e in ENGINES}}
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    res["commit"] = head
    L = [f"# Test M: engines A-1.0 and B-1.0 vs DraftKings, {SEASON} weeks {WEEKS[0]}-{WEEKS[-1]}", "",
         "Pre-registration: docs/engine_preregistration.md (amendment of 2026-11-17). Written by `scripts/engine_test_m.py`",
         f"at commit `{head[:10]}`, once. {df.height:,} props over {res['weeks']} weeks; DraftKings log loss {res['dk_log_loss']:.4f}.", "",
         f"| Engine | Log loss | Engine minus DraftKings ({100 * (1 - LEVEL):.1f}% interval) | Verdict |", "|---|---|---|---|"]
    for e, r in res["engines"].items():
        L.append(f"| {e} | {r['log_loss']:.4f} | {r['diff'][0]:+.4f} ({r['diff'][1]:+.4f} to {r['diff'][2]:+.4f}) | **{r['verdict']}** |")
    L += ["", f"A minus B (reported, not tested): {res['a_minus_b'][0]:+.4f} ({res['a_minus_b'][1]:+.4f} to {res['a_minus_b'][2]:+.4f}).", "",
          "| Market | Props | DraftKings | A | B |", "|---|---|---|---|---|"]
    L += [f"| {m} | {r['n']:,} | {r['dk']:.4f} | {r['A']:.4f} | {r['B']:.4f} |" for m, r in res["by_market"].items()]
    L += ["", "Dropped: " + "; ".join(f"{k} {v:,}" for k, v in sorted(drops.items())) + "."]
    RESULT.write_text(json.dumps(res, indent=1) + "\n")
    REPORT.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
