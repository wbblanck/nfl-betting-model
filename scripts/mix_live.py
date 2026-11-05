"""Props-mix live tracker (docs/mix_live_rules.md). Unvalidated; tracker records, not recommendations.

  python scripts/mix_live.py run     # score this week's DraftKings props from the newest saved ParlayAPI snapshot
  python scripts/mix_live.py grade   # settle official picks, write data/live/mix_record_2026.csv and docs/mix_live.md
"""
from __future__ import annotations

import sys

import polars as pl

from nflbet import config
from nflbet.props import live as Lv
from nflbet.gamesim import mix_live as M


def do_run() -> None:
    week = Lv.current_week(M.SEASON)
    if week is None:
        print("season over"); return
    snap = M.latest_snapshot()
    if snap is None or not snap.name.endswith(f"_w{week}.json.gz"):
        print(f"props mix, week {week}: no ParlayAPI snapshot for this week yet ({snap.name if snap else 'none'}); nothing to score")
        return
    tmp = Lv.LIVE / "tmp" / "mix_dk_lines.csv"
    n = M.lines_file(snap, M.SEASON, week, tmp)
    if not n:
        print(f"props mix, week {week}: snapshot {snap.name} has no DraftKings rows for this week's games"); return
    when = Lv.now_utc()
    props, log = M.score(M.SEASON, tmp, when, snap.name)
    Lv.append(props, M.PROPS)
    Lv.append(log, M.RUNS)
    pk = M.picks_from(props)
    print(f"props mix, week {week}: {log.height} games not yet started, {props.height} props scored, {pk.height} picks "
          f"(snapshot {snap.name})")
    for r in pk.iter_rows(named=True):
        print(f"  {r['away']}@{r['home']}  {r['player']:24s} {r['market']:9s} {r['side']:5s} {r['line']:6} {r['odds']:+.0f}  "
              f"mix {r['p_side']:.1%}  edge {r['edge']:+.1%}")


def do_grade() -> None:
    if not M.PROPS.exists() or not M.PROPS.stat().st_size:
        print("props mix: no runs yet"); return
    props = pl.read_csv(M.PROPS, infer_schema_length=0)
    runs = pl.read_csv(M.RUNS, infer_schema_length=0)
    g = M.grade(props, runs)
    g.write_csv(M.RECORD)
    t = Lv.record(g)
    j = M.judge(props, runs)
    print(f"props mix: {t['W']}-{t['L']}-{t['P']}, {t['units']:+.2f} units (pending {t['pending']}, void {t['void']}); "
          f"log loss on {j.get('n', 0)} official props: mix {j.get('ll_mix', float('nan')):.4f} vs DK {j.get('ll_dk', float('nan')):.4f}")
    lines = [f"# Props mix live tracker, {M.SEASON}", "",
             "Rules: docs/mix_live_rules.md. **Unvalidated.** A pick is a side the M1 mix gives 55% or more, at DraftKings' price.",
             f"Updated {Lv.now_utc().strftime('%Y-%m-%d %H:%M')} UTC.", "",
             f"**Picks: {t['W']}-{t['L']}" + (f"-{t['P']}" if t["P"] else "") +
             (f", {t['units']:+.2f} units, ROI {t['roi']:+.1%}" if t["win_pct"] is not None else "") +
             f"** ({t['pending']} pending, {t['void']} void).", "",
             f"Log loss on {j.get('n', 0)} official props from final games: mix {j.get('ll_mix', float('nan')):.4f}, DraftKings "
             f"{j.get('ll_dk', float('nan')):.4f} (lower is better; judged after week 18 on weeks 10-18).", ""]
    (config.ROOT / "docs" / "mix_live.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    {"run": do_run, "grade": do_grade}[sys.argv[1]]()
