"""ATS hybrid: line moved 1.5+ from open to close and the frozen rating agrees; bet the moved side at the close
(docs/ats_hybrid_preregistration.md). Writes docs/ats_hybrid.md and data/backtests/ats_hybrid.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import ats_clv as C  # noqa: E402

from nflbet import config  # noqa: E402
from nflbet.props import core as P  # noqa: E402

LEVEL = 0.025 / 2   # one-sided 0.025, Bonferroni over 2 tests: lower bound = 1.25% quantile
MOVE = 1.5


def frame_sbro(seasons, k):
    return C.frame(seasons, k)


def frame_bet365(seasons, k):
    from nflbet.ats import rating as A
    tg = A.team_games(list(range(min(seasons) - 1, max(seasons) + 1)))
    x = A.fair(A.with_ratings(A.games(seasons), A.ratings(tg, k["h"], k["k"], k["r"])), k["c"], k["hfa"]).filter(pl.col("week") >= 2)
    ab = pl.read_csv(config.ROOT / "data" / "odds" / "asb_nfl_games.csv").select(
        "game_id", "home_open", "home_close", "home_close_odds", "away_close_odds")
    return x.join(ab, on="game_id").drop_nulls(["home_open", "home_close", "home_close_odds", "away_close_odds"])


def bets(x: pl.DataFrame, move: float = MOVE, rating: str = "agree") -> dict:
    """rating: 'agree' (sign(fair-open) = sign(move)), 'strict' (also sign(fair-close) = sign(move)), 'none'."""
    o, c, f, m = (x[k].to_numpy().astype(float) for k in ("home_open", "home_close", "fair", "result"))
    cl = (x["season"] * 100 + x["week"]).to_numpy()
    mv = c - o
    sel = np.abs(mv) >= move
    if rating in ("agree", "strict"):
        sel &= np.sign(f - o) == np.sign(mv)
    if rating == "strict":
        sel &= np.sign(f - c) == np.sign(mv)
    home = (mv > 0)[sel]
    cc, mm, cls = c[sel], m[sel], cl[sel]
    won = np.where(home, mm > cc, mm < cc)
    push = mm == cc
    px = (np.where(home, x["home_close_odds"].to_numpy()[sel], x["away_close_odds"].to_numpy()[sel]).astype(float)
          if "home_close_odds" in x.columns else np.full(len(mm), -110.0))
    pnl = np.where(push, 0.0, P.profit(px, won.astype(float))) if len(mm) else np.array([])
    r = {"n": int(sel.sum()), "weeks": int(len(np.unique(cls))),
         "cover": float(won[~push].mean()) if (~push).any() else None,
         "roi": float(pnl.mean()) if len(pnl) else None, "_pnl": pnl, "_cl": cls,
         "_cross": np.where(home, (o[sel] < 3) & (cc >= 3) | (o[sel] < 7) & (cc >= 7),
                            (o[sel] > -3) & (cc <= -3) | (o[sel] > -7) & (cc <= -7)) if len(mm) else np.array([], bool)}
    return r


def test(x: pl.DataFrame) -> dict:
    b = bets(x)
    ci = list(C.boot(lambda ix: b["_pnl"][ix].mean(), b["_cl"], LEVEL)) if b["n"] else [None, None]
    ok = bool(b["n"] >= 30 and b["weeks"] >= 10 and ci[0] is not None and ci[0] > 0)
    return {k: v for k, v in b.items() if not k.startswith("_")} | {"ci": ci, "pass": ok}


def describe(x: pl.DataFrame) -> dict:
    out = {}
    for t in (1.0, 1.5, 2.0, 3.0):
        for rt in ("agree", "none", "strict"):
            b = bets(x, t, rt)
            out[f"{rt}_{t}"] = {k: v for k, v in b.items() if not k.startswith("_")}
    b = bets(x)
    cr = b["_cross"]
    if cr.any():
        out["agree_1.5_crosses_3_or_7"] = {"n": int(cr.sum()), "roi": float(b["_pnl"][cr].mean())}
    by = {}
    for s in sorted(x["season"].unique().to_list()):
        bs = bets(x.filter(pl.col("season") == s))
        by[s] = {"n": bs["n"], "cover": bs["cover"], "roi": bs["roi"]}
    out["by_season"] = by
    return out


def fmt(v, p=True):
    return "–" if v is None else (f"{v:.1%}" if p else f"{v:+.1%}")


def main():
    k = json.loads((config.ROOT / "data" / "backtests" / "ats_constants.json").read_text())
    samples = {"H-A_sbro_2008_2021": frame_sbro(list(range(2008, 2022)), k),
               "H-B_bet365_2022_2024": frame_bet365([2022, 2023, 2024], k)}
    out = {n: {"test": test(x), "descriptive": describe(x)} for n, x in samples.items()}
    (config.ROOT / "data" / "backtests" / "ats_hybrid.json").write_text(json.dumps(out, indent=1, default=str))
    L = ["# ATS hybrid: line moves 1.5+ and the rating agrees", "",
         "Pre-registration: docs/ats_hybrid_preregistration.md. Bet the side the line moved toward, at the closing number.", ""]
    for n, r in out.items():
        t = r["test"]
        L += [f"## {n}", "", f"- **Test:** n {t['n']} in {t['weeks']} weeks, covers {fmt(t['cover'])}, ROI {fmt(t['roi'], False)}, "
              f"interval {fmt(t['ci'][0], False)} to {fmt(t['ci'][1], False)}: **{'PASS' if t['pass'] else 'FAIL'}**", "",
              "| Move ≥ | Rating | Bets | Covers | ROI |", "|---|---|---|---|---|"]
        for key, v in r["descriptive"].items():
            if key in ("by_season", "agree_1.5_crosses_3_or_7"):
                continue
            rt, th = key.rsplit("_", 1)
            L.append(f"| {th} | {rt} | {v['n']} | {fmt(v['cover'])} | {fmt(v['roi'], False)} |")
        if "agree_1.5_crosses_3_or_7" in r["descriptive"]:
            v = r["descriptive"]["agree_1.5_crosses_3_or_7"]
            L += ["", f"Crossing 3 or 7 (agree, 1.5+): n {v['n']}, ROI {fmt(v['roi'], False)}"]
        L += ["", "| Season | Bets | Covers | ROI |", "|---|---|---|---|"]
        L += [f"| {s} | {v['n']} | {fmt(v['cover'])} | {fmt(v['roi'], False)} |" for s, v in r["descriptive"]["by_season"].items()] + [""]
    (config.ROOT / "docs" / "ats_hybrid.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
