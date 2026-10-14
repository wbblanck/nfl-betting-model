"""Polymarket US vs DraftKings and FanDuel on this week's player props (docs/polymarket_compare.md).

Polymarket threshold markets ("Will X record N+ receiving yards?") equal a sportsbook over at N-0.5. Each matched prop
is compared on cost per $1 payout: the Polymarket Yes (over) or No (under) price against the book's implied cost
from American odds. Lower cost = better price for the buyer. Gross = before fees; net = with an assumed fee
(feeCoefficient x p x (1-p), a formula to confirm against Polymarket's fee schedule).
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

MAP = {"receptions": "rec", "receiving yards": "rec_yds", "rushing yards": "rush_yds", "rushing attempts": "rush_att",
       "passing yards": "pass_yds", "passing completions": "pass_cmp", "passing attempts": "pass_att"}
PAT = re.compile(r"^Will (.+?) record (\d+)\+ (.+?)\?$")
FEE = 0.0695
WEEK = 6                       # the upcoming slate; the search and the report header both follow this


def imp(a):
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


PM = "https://gateway.polymarket.us"


def fetch_polymarket(now_utc) -> list[dict]:
    """Week-5 game events and their prop markets from Polymarket US's public search (no key), keyed like the
    trimmed file: {event, question, marketSides, feeCoefficient}."""
    import urllib.parse
    import urllib.request
    from datetime import timedelta
    UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    out, seen = [], set()
    for q in (f"NFL Week {WEEK}", f"NFL week {WEEK} props"):
        req = urllib.request.Request(f"{PM}/v1/search?query={urllib.parse.quote(q)}&limit=20", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            events = json.loads(r.read()).get("events", [])
        for e in events:
            if " vs. " not in (e.get("title") or "") or e.get("title") in seen:
                continue
            start = (e.get("startTime") or e.get("startDate") or "").replace("Z", "+00:00")
            try:
                t = __import__("datetime").datetime.fromisoformat(start)
            except ValueError:
                continue
            if not (now_utc - timedelta(hours=4) <= t <= now_utc + timedelta(days=8)):
                continue
            seen.add(e["title"])
            for m in e.get("markets") or []:
                if "record" in (m.get("question") or "") or "score the first" in (m.get("question") or ""):
                    out.append({"event": e["title"], "question": m.get("question"), "marketSides": m.get("marketSides") or [],
                                "feeCoefficient": m.get("feeCoefficient") or e.get("feeCoefficient"),
                                "bestBid": m.get("bestBid"), "bestAsk": m.get("bestAsk"),
                                "lastTradePrice": m.get("lastTradePrice"), "liquidityNum": m.get("liquidityNum"),
                                "minimumTradeQty": m.get("minimumTradeQty")})
    return out


def poly_game(title: str) -> str | None:
    """'DEN Broncos vs. LA Chargers' -> 'DEN|LAC'. Polymarket writes both Los Angeles teams as 'LA', so each team is
    matched by its nickname (last word) to parlay.TEAMS, the same abbreviations the book lines use. None if unmapped."""
    def ab(side: str) -> str | None:
        nick = side.split()[-1]
        hits = {v for k, v in Pa.TEAMS.items() if k.split()[-1] == nick}
        return hits.pop() if len(hits) == 1 else None
    if " vs. " not in title:
        return None
    a, b = (ab(s) for s in title.split(" vs. ", 1))
    return "|".join(sorted((a, b))) if a and b else None


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
        # cost of each side = its `quote` value (marketSides[].quote.value). Live 2026-10-10 run: Yes+No quotes sum
        # to a median 1.03 on 2,578 threshold markets, while `price` sums to 0.81 and bestBid/bestAsk are absent.
        # Sides without a quote are counted, not compared.
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
                 f"mean {x['gross_diff'].mean()*100:+.2f} cents per $1; cheaper after assumed fee {(x['net_diff'] > 0).mean():.0%}, "
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
    L += ["", f"Fee (Polymarket docs, taker only): fee = C x feeRate x p x (1-p), applied per share at the side's price p. "
          f"feeRate = the market's feeCoefficient ({FEE} on every market in this run; fallback {FEE}). The public fee table lists "
          "0.05 for Sports, which does not match the market field; unresolved, and it would raise the net figures.", ""]
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
