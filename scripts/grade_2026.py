"""Grade the rules locked for 2026 (docs/selective_props_confirm.md R1-R3, docs/projection_props_confirm.md P1,
docs/simulator_confirm.md S1).

Writes data/backtests/grade_2026.json and docs/grade_2026.md. Until every 2026 regular-season game is final the
output is marked INTERIM: descriptive only, no rule passes or fails before then (per the pre-registrations).
"""
from __future__ import annotations

import datetime as dt
import json

import polars as pl

from nflbet import config
from nflbet.props import projection as R
from nflbet.props import selective as S
from nflbet.props import screener as Sc
from nflbet.props.sim import Simulator

SEASON = 2026


def season_complete() -> tuple[bool, int, int]:
    import nflreadpy as nfl

    g = nfl.load_schedules(seasons=[SEASON]).filter(pl.col("game_type") == "REG")
    done = g.filter(pl.col("result").is_not_null()).height
    return done == g.height, done, g.height


def main() -> None:
    final, done, total = season_complete()
    sim = Simulator(fit_season=2024, seasons=[2023, 2024, SEASON - 1, SEASON])
    s1 = S.evaluate(Sc.bets_frame(Sc.rule_s1(Sc.scored(SEASON, sim))), level=0.025)
    res = {**S.run(SEASON), **R.run(SEASON), "S1_all_four_signals_agree": s1}
    out = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "season": SEASON,
           "status": "FINAL" if final else "INTERIM (descriptive only)", "games_final": f"{done}/{total}",
           "rules": res}
    (config.ROOT / "data" / "backtests" / "grade_2026.json").write_text(json.dumps(out, indent=1))
    lines = [f"# 2026 prop rules: {out['status']}", "",
             f"Regular-season games final: {done} of {total}. Generated {out['generated_utc'][:16]} UTC.", "",
             "| Rule | Bets | Weeks | Under won | ROI | Interval | Verdict |", "|---|---|---|---|---|---|---|"]
    for k, v in res.items():
        if not v.get("n"):
            lines.append(f"| {k} | 0 | 0 | | | | |")
            continue
        verdict = ("PASS" if v["pass"] else "FAIL") if final else "not judged yet"
        lines.append(f"| {k} | {v['n']} | {v['weeks']} | {v['under_rate']:.1%} | {v['roi']:+.1%} | "
                     f"{v['roi_ci'][0]:+.1%} to {v['roi_ci'][1]:+.1%} | {verdict} |")
    lines += ["", "R1-R3: docs/selective_props_confirm.md (interval at one-sided 2.5%/3). "
              "P1: docs/projection_props_confirm.md, S1: docs/simulator_confirm.md (one-sided 2.5%). "
              "For S1 'Under won' is the bet side's win rate. Pass needs n >= 30 bets in >= 10 weeks and the "
              "interval's lower end above 0."]
    (config.ROOT / "docs" / "grade_2026.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
