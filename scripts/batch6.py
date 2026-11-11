"""Batch 6 (docs/batch6_preregistration.md).

  python scripts/batch6.py fit  <cache>   reads nflverse closes and margins for the fit seasons only; writes
                                          data/backtests/batch6_constants.json and docs/batch6_fit.txt
  python scripts/batch6.py test <cache>   runs P1 and P2 once on the test seasons; writes data/backtests/batch6.json
"""
from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl

from nflbet import config
from nflbet.ats import batch5 as B5
from nflbet.ats import batch6 as B6

BT = config.ROOT / "data" / "backtests"
# era: fit seasons -> test seasons (2015 extra-point change splits the eras)
ERAS = {"old": (list(range(1999, 2007)), list(range(2007, 2015))),
        "new": (list(range(2016, 2021)), [2015, 2021])}
B, ALPHA = 2000, 0.05


def games(d, seasons):
    s = pl.read_parquet(f"{d}/schedules.parquet").filter(pl.col("season").is_in(seasons), pl.col("game_type") == "REG",
                                                       pl.col("spread_line").is_not_null(), pl.col("result").is_not_null())
    return s.select("season", "week", "game_id", "spread_line", "result")


def fit(d):
    out, lines = {}, []
    for era, (fs, _) in ERAS.items():
        g = games(d, fs)
        c, m = g["spread_line"].to_numpy(), g["result"].to_numpy().astype(float)
        f = B6.fit(c, m)
        out[era] = f
        dd1 = B6.d_off_market(c, c + 0.5 * np.sign(np.where(c == 0, 1, c)), m, f["k2"], f["sigma_n"])
        whole = c == np.round(c)
        dd2 = B6.d_push(c[whole], m[whole], f["k2"], f["sigma_n"])
        w = f["k2"]["w"]
        lines.append(f"{era} ({fs[0]}-{fs[-1]}, {len(g)} games): sigma N {f['sigma_n']:.3f}, K2 {f['k2']['sigma']:.3f}; "
                     + ", ".join(f"w{k} {w[k]:.2f}" for k in B6.KEYS)
                     + f"; per-game SD of d in the fit seasons: P1-like (line half a point off the close) {dd1.std():.3f},"
                       f" P2 {dd2.std():.3f}")
    (BT / "batch6_constants.json").write_text(json.dumps(out, indent=1))
    (config.ROOT / "docs" / "batch6_fit.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def boot(x, cl, seed=7):
    ids = np.unique(cl)
    grp = [np.where(cl == c)[0] for c in ids]
    rng = np.random.default_rng(seed)
    return np.array([x[np.concatenate([grp[j] for j in rng.integers(0, len(ids), len(ids))])].mean() for _ in range(B)])


def test(d):
    k = json.loads((BT / "batch6_constants.json").read_text())
    sb = pl.read_csv(config.ROOT / "data" / "odds" / "sbro_nfl_games.csv").filter(~pl.col("sign_flag")) \
        .select("game_id", "home_open")
    p1, p2, desc = [], [], {}
    for era, (_, ts) in ERAS.items():
        f = k[era]
        g = games(d, ts).join(sb, on="game_id", how="left").with_columns(
            (pl.col("season").cast(pl.Utf8) + "_" + pl.col("week").cast(pl.Utf8)).alias("cl"))
        c, m = g["spread_line"].to_numpy(), g["result"].to_numpy().astype(float)
        op = g["home_open"].to_numpy().astype(float)
        mv = ~np.isnan(op) & (op != c)
        p1.append(pl.DataFrame({"era": era, "cl": g["cl"].to_numpy()[mv],
                                "d": B6.d_off_market(c[mv], op[mv], m[mv], f["k2"], f["sigma_n"]),
                                "crosses": ((np.minimum(op, c) < 3) & (np.maximum(op, c) > 3)
                                            | (np.minimum(op, c) < 7) & (np.maximum(op, c) > 7)
                                            | (np.minimum(op, c) < -3) & (np.maximum(op, c) > -3)
                                            | (np.minimum(op, c) < -7) & (np.maximum(op, c) > -7))[mv]}))
        wh = c == np.round(c)
        pk = B6.outcome_probs(B5.k1_dist(c[wh], f["k2"]["sigma"], f["k2"]["w"]), c[wh])[:, 1]
        pn = B6.outcome_probs(B5.k1_dist(c[wh], f["sigma_n"], np.ones(B5.KMAX + 1)), c[wh])[:, 1]
        p2.append(pl.DataFrame({"era": era, "cl": g["cl"].to_numpy()[wh], "c": c[wh],
                                "push": (m[wh] == c[wh]).astype(float), "pk": pk, "pn": pn,
                                "d": B6.d_push(c[wh], m[wh], f["k2"], f["sigma_n"])}))
        desc[era] = {"games": len(g), "no_opener": int(np.isnan(op).sum())}
    p1, p2 = pl.concat(p1), pl.concat(p2)
    res = {}
    for name, x in (("P1", p1), ("P2", p2)):
        dr = boot(x["d"].to_numpy(), x["cl"].to_numpy())
        res[name] = {"n": len(x), "weeks": int(x["cl"].n_unique()), "mean": float(x["d"].mean()),
                     "p": float(np.mean(dr <= 0)), "draws": dr}
    order = sorted(res, key=lambda n: res[n]["p"])
    stop = False
    for i, n in enumerate(order):
        lvl = ALPHA / (len(order) - i)
        ok = (not stop) and res[n]["p"] <= lvl
        dr = res[n].pop("draws")
        res[n].update({"holm_level": lvl, "pass": bool(ok), "ci": [float(np.quantile(dr, lvl)), float(np.quantile(dr, 1 - lvl))]})
        stop = stop or not ok
    # descriptive
    for era in ERAS:
        x = p1.filter(pl.col("era") == era)
        desc[era]["p1_n"], desc[era]["p1_mean"] = len(x), float(x["d"].mean())
        z = p2.filter(pl.col("era") == era)
        desc[era]["p2_n"], desc[era]["p2_mean"] = len(z), float(z["d"].mean())
    desc["p1_crossing_3_or_7"] = {"n": int(p1["crosses"].sum()), "mean": float(p1.filter(pl.col("crosses"))["d"].mean())}
    pushes = {}
    for lab, flt in (("all", pl.lit(True)), ("3", pl.col("c").abs() == 3), ("7", pl.col("c").abs() == 7)):
        z = p2.filter(flt)
        pushes[lab] = {"n": len(z), "actual": float(z["push"].mean()), "N": float(z["pn"].mean()), "K2": float(z["pk"].mean())}
    desc["push_rate"] = pushes
    f = k["new"]
    half = {}
    for key in (3, 7):
        pm = B5.k1_dist([float(key)], f["k2"]["sigma"], f["k2"]["w"])
        lo, at, hi = (B6.outcome_probs(pm, [x])[0] for x in (key - 0.5, float(key), key + 0.5))
        # favorite (home, close = key) laying key+0.5 vs key: buying the half point turns a push into a no-loss
        half[key] = {"P_push_at_key": float(at[1]), "P_fav_covers": {f"{key - 0.5}": float(lo[0]), f"{key}": float(at[0]),
                                                                       f"{key + 0.5}": float(hi[0])}}
    desc["half_points_new_era"] = half
    out = {"tests": res, "descriptive": desc}
    (BT / "batch6.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"fit": fit, "test": test}[sys.argv[1]](sys.argv[2])
