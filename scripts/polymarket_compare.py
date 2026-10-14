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

MAP = {"receptions": "rec", "receiving yards": "rec_yds", "rushing yards": "rush_yds", "rushing attempts": "rush_att",
       "passing yards": "pass_yds", "passing completions": "pass_cmp", "passing attempts": "pass_att"}
PAT = re.compile(r"^Will (.+?) record (\d+)\+ (.+?)\?$")
FEE = 0.0695
WEEK = 6                       # the upcoming slate; the search and the report header both follow this


def imp(a):
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


PM = "https://gateway.polymarket.us"


SLUG_CODE = {"LA": "lar"}      # nflverse -> Polymarket event-slug code where they differ (others: lower case)


def _pm_get(path: str):
    import urllib.request
    UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    with urllib.request.urlopen(urllib.request.Request(f"{PM}{path}", headers={"User-Agent": UA}), timeout=60) as r:
        return json.loads(r.read())


def week_slugs(now_utc) -> list[str]:
    """This week's game-event slugs: from the search (title 'X vs. Y', start within the window) and, as a backstop,
    built from the nflverse schedule as nfl-{away}-{home}-{ET date}. The search alone is capped at 20 events and shares
    them with season-long markets, so it can miss games."""
    import urllib.parse
    from datetime import datetime, timedelta
    slugs: list[str] = []
    for q in (f"NFL Week {WEEK}", f"NFL week {WEEK} props"):
        for e in _pm_get(f"/v1/search?query={urllib.parse.quote(q)}&limit=20").get("events", []):
            try:
                t = datetime.fromisoformat((e.get("startTime") or e.get("startDate") or "").replace("Z", "+00:00"))
            except ValueError:
                continue
            if " vs. " in (e.get("title") or "") and now_utc - timedelta(hours=4) <= t <= now_utc + timedelta(days=8):
                slugs.append(e["slug"])
    try:
        import nflreadpy as nfl
        sch = nfl.load_schedules(seasons=[now_utc.year if now_utc.month >= 3 else now_utc.year - 1])
        sch = sch.filter((pl.col("game_type") == "REG") & (pl.col("week") == WEEK))
        for r in sch.iter_rows(named=True):
            a, h = (SLUG_CODE.get(x, x.lower()) for x in (r["away_team"], r["home_team"]))
            slugs.append(f"nfl-{a}-{h}-{r['gameday']}")
    except Exception as e:  # noqa: BLE001 - the search slugs still stand
        print(f"schedule slugs unavailable: {e!r}"[:200])
    return list(dict.fromkeys(slugs))


def fetch_polymarket(now_utc) -> list[dict]:
    """This week's player-prop markets from Polymarket US (public, no key). Each game is fetched by slug from
    /v1/events/slug/{slug}: the search returns the games but embeds only part of their markets, without the player
    props (2026-10-14 diagnostic, docs/evidence/polymarket_week_probe/). Prints one line per game."""
    import urllib.error
    out = []
    for slug in week_slugs(now_utc):
        try:
            body = _pm_get(f"/v1/events/slug/{slug}")
        except urllib.error.HTTPError as e:
            print(f"  {slug}: HTTP {e.code}, skipped")
            continue
        e = body.get("event", body) if isinstance(body, dict) else {}
        if e.get("slug") != slug:
            print(f"  {slug}: no matching event, skipped")
            continue
        kept = 0
        for m in e.get("markets") or []:
            if "record" in (m.get("question") or "") or "score the first" in (m.get("question") or ""):
                kept += 1
                out.append({"event": e["title"], "question": m.get("question"), "marketSides": m.get("marketSides") or [],
                            "feeCoefficient": m.get("feeCoefficient") or e.get("feeCoefficient"),
                            "bestBidQuote": m.get("bestBidQuote"), "bestAskQuote": m.get("bestAskQuote"),
                            "lastTradePrice": m.get("lastTradePrice"), "liquidityNum": m.get("liquidityNum"),
                            "minimumTradeQty": m.get("minimumTradeQty")})
        print(f"  {slug}: {e.get('title')}, {len(e.get('markets') or [])} markets, {kept} kept")
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
