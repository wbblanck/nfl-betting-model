"""Polymarket US vs DraftKings and FanDuel on this week's player props (docs/polymarket_compare.md).

Polymarket threshold markets ("Will X record N+ receiving yards?") equal a sportsbook over at N-0.5. Each matched prop
is compared on cost per $1 payout: the Polymarket Yes (over) or No (under) price against the book's implied cost
from American odds. Lower cost = better price for the buyer. Gross = before fees; net = with Polymarket US's taker fee
(0.0695 x p x (1-p) per contract, from its published fee schedule).
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, "src")
from nflbet import parlay as Pa, props as P  # noqa: E402

from nflbet.venues import PM as PM, PM_MAP as MAP, PM_PAT as PAT, pm_game as poly_game, pm_markets  # noqa: E402
FEE = 0.0695
WEEK = 6                       # the upcoming slate; the search and the report header both follow this


def imp(a):
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def fetch_polymarket(now_utc) -> list[dict]:
    return pm_markets(WEEK, now_utc)


def main():
    import datetime as dt
    import os
    if os.environ.get("PARLAY_API_KEY") and "--fetch" in sys.argv:
        from nflbet import parlay as Pa2
        now = dt.datetime.now(dt.timezone.utc)
        poly = fetch_polymarket(now)
        raw = Pa2.fetch()[0]
        book_now = Pa2.parse(raw)
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        Path(f"docs/evidence/polymarket_compare/{stamp}").mkdir(parents=True, exist_ok=True)
        with gzip.open(f"docs/evidence/polymarket_compare/{stamp}/polymarket_props.json.gz", "wt") as fh:
            json.dump(poly, fh)                       # full file: a 4 MB text cut made the saved JSON unparseable
        book = book_now
        poly_src = poly
    else:
        ev = Path(sorted(Path("docs/evidence/polymarket_us").glob("*/week5_props_trimmed.json"))[-1])
        poly_src = json.loads(ev.read_text())
        st = sorted(Path("data/live/parlay").glob("*2103Z_w5.json.gz"))[-1]
        book = Pa.parse(json.load(gzip.open(st, "rt")))
    poly = poly_src
    rows = []
    n_unquoted, n_thr, n_unmapped = 0, 0, 0
    for x in poly:
        m = PAT.match(x["question"] or "")
        if not m or m.group(3) not in MAP:
            continue
        n_thr += 1
        sides = {s["description"]: s for s in x["marketSides"]}
        # cost of each side = its `quote` value (marketSides[].quote.value): the buy price. Verified on saved data: the
        # Yes quote equals the market's bestAskQuote and the No quote equals 1 - bestBidQuote, so Yes+No-1 is the
        # bid-ask spread. Sides without a quote are counted, not compared.
        def q(side):
            v = (sides.get(side, {}).get("quote") or {}).get("value")
            return float(v) if v not in (None, "") else None
        yes, no = q("Yes"), q("No")
        if yes is None or no is None:
            n_unquoted += 1
            continue
        game = poly_game(x["event"])
        if game is None:
            n_unmapped += 1
            continue
        rows.append({"game": game, "nkey": P.norm_name(m.group(1)), "market": MAP[m.group(3)], "line": float(m.group(2)) - 0.5,
                     "poly_over": yes, "poly_under": no, "fee_coef": x.get("feeCoefficient") or FEE,
                     "poly_spread": yes + no - 1})
    poly_df = pl.DataFrame(rows, schema={"game": pl.Utf8, "nkey": pl.Utf8, "market": pl.Utf8, "line": pl.Float64,
                                         "poly_over": pl.Float64, "poly_under": pl.Float64, "fee_coef": pl.Float64,
                                         "poly_spread": pl.Float64})
    rows2 = []
    for r in poly_df.iter_rows(named=True):
        for bk in ("dk", "fd"):
            b = book.filter((pl.col("book") == bk) & (pl.col("game") == r["game"]) & (pl.col("nkey") == r["nkey"])
                            & (pl.col("market") == r["market"]) & (pl.col("line") == r["line"]))
            if not b.height:
                continue
            bo, bu = b["over"][0], b["under"][0]
            for side, pc, bc in (("over", r["poly_over"], bo), ("under", r["poly_under"], bu)):
                if pc is None:
                    continue
                book_cost = imp(bc)
                fee = r["fee_coef"] * pc * (1 - pc)
                rows2.append({"book": bk, "player": r["nkey"], "market": r["market"], "line": r["line"], "side": side,
                              "poly_cost": pc, "book_odds": bc, "book_cost": book_cost,
                              "gross_diff": book_cost - pc, "net_diff": book_cost - (pc + fee),
                              "book_hold": imp(bo) + imp(bu) - 1, "poly_spread": r["poly_spread"]})
    d = pl.DataFrame(rows2) if rows2 else pl.DataFrame(schema={"book": pl.Utf8, "player": pl.Utf8, "market": pl.Utf8, "line": pl.Float64,
                                                              "side": pl.Utf8, "poly_cost": pl.Float64, "book_odds": pl.Float64,
                                                              "book_cost": pl.Float64, "gross_diff": pl.Float64, "net_diff": pl.Float64})
    out = Path("docs/polymarket_compare.md")
    book_src = "live ParlayAPI and Polymarket US pulled together" if "--fetch" in sys.argv else "ParlayAPI 2026-10-09 21:03 UTC (stored), Polymarket US snapshot 2026-10-10 05:02 UTC (stored)"
    L = [f"# Polymarket US vs DraftKings and FanDuel, week {WEEK} player props", "",
         f"Props matched: {d.height} side-quotes across {d.select(pl.struct('player', 'market', 'line')).n_unique() if d.height else 0} player-lines, "
         f"source: {book_src}. Positive diff = Polymarket is cheaper.", ""]
    for bk in ("dk", "fd"):
        x = d.filter(pl.col("book") == bk)
        if not x.height:
            continue
        L.append(f"- vs {bk.upper()}: {x.height} sides; Polymarket cheaper gross {(x['gross_diff'] > 0).mean():.0%}, "
                 f"mean {x['gross_diff'].mean()*100:+.2f} cents per $1; cheaper after fee {(x['net_diff'] > 0).mean():.0%}, "
                 f"mean {x['net_diff'].mean()*100:+.2f} cents.")
    L += [f"Polymarket threshold markets with no bid/ask (not compared): {n_unquoted} of {n_thr}; "
          f"threshold markets quoted and compared: {poly_df.height}."]
    if d.height:
        ps = d.unique(subset=["player", "market", "line", "side"])["poly_spread"]
        bh = d.unique(subset=["book", "player", "market", "line"])
        for bk in ("dk", "fd"):
            hb = bh.filter(pl.col("book") == bk)["book_hold"]
            if hb.len():
                L.append(f"- {bk.upper()} hold on matched lines: median {hb.median()*100:.1f}% (over+under implied minus 1).")
        L.append(f"- Polymarket hold (quoted Yes + No minus 1, per binary market): median {ps.median()*100:.1f}% of $1.")
    L += ["", f"Fee: Polymarket US fee schedule (docs.polymarket.us, effective 2026-10-07): taker fee = Θ x C x p x (1-p) with "
          f"Θ = {FEE} for standard markets, Sports included (only Table Tennis differs, 0.10), charged per contract at the side's price p; "
          "the markets' own feeCoefficient field carries the same 0.0695. Not modelled: rounding of each fill's fee to the cent "
          "(banker's rounding) and taker rebates, which start at $250,000 a month in taker volume. Makers pay no taker fee.", ""]
    summ = {"run_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if "--fetch" in sys.argv else None,
            "source": book_src, "threshold_markets": n_thr, "quoted_compared": poly_df.height, "not_compared": n_unquoted,
            "side_quotes": d.height, "player_lines": d.select(pl.struct("player", "market", "line")).n_unique() if d.height else 0,
            "fee_rate": FEE, "books": {}, "polymarket_hold_median": None, "book_hold_median": {}}
    for bk in ("dk", "fd"):
        x = d.filter(pl.col("book") == bk)
        if not x.height:
            continue
        summ["books"][bk.upper()] = {"sides": x.height, "gross_cheaper": float((x["gross_diff"] > 0).mean()),
                                     "gross_mean_cents": float(x["gross_diff"].mean() * 100),
                                     "net_cheaper": float((x["net_diff"] > 0).mean()),
                                     "net_mean_cents": float(x["net_diff"].mean() * 100)}
    if d.height:
        summ["polymarket_hold_median"] = float(d.unique(subset=["player", "market", "line", "side"])["poly_spread"].median())
        bh = d.unique(subset=["book", "player", "market", "line"])
        summ["book_hold_median"] = {bk.upper(): float(bh.filter(pl.col("book") == bk)["book_hold"].median())
                                    for bk in ("dk", "fd") if bh.filter(pl.col("book") == bk).height}
    Path("docs/polymarket_compare.json").write_text(json.dumps(summ, indent=1) + "\n")
    out.write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(d.sort("gross_diff", descending=True).head(8))


if __name__ == "__main__":
    main()
