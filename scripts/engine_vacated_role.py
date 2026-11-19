"""Vacated-role study (pre-registered in docs/engine/vacated_role_study.md, 2026-11-18). Engine tune seasons 2022-2023
only; frozen Engine A-1.0 parameters; reads no price and no 2024-2026 outcome.

  python scripts/engine_vacated_role.py --check   hand cases only
  python scripts/engine_vacated_role.py           simulate 2022-2023 (cached under data/cache/engine/vacated/), then
                                                  write docs/engine/vacated_role_results.md and data/backtests/vacated_role.json
"""
import gzip
import hashlib
import json
import pickle
import sys

import numpy as np
import polars as pl

import engine_a_tune as AT
from nflbet.config import ROOT
from nflbet.engine import scoring as S
from nflbet.engine.data import nflverse as N
from nflbet.engine.replication import model as MA

TUNE, SIMS, WINDOW = (2022, 2023), 2000, 3
RB_MIN, TGT_MIN = 0.50, 0.25
CACHE = N.DIR / "vacated" / "a10_runs_2022_2023.parquet"
OUT_MD, OUT_JSON = ROOT / "docs" / "engine" / "vacated_role_results.md", ROOT / "data" / "backtests" / "vacated_role.json"
MKT = {"rush_att": "carries", "rush_yds": "rushing_yards", "rec": "receptions", "rec_yds": "receiving_yards"}


# ---------- pure functions (checked on hand cases) ----------
def events(games: list[dict], kind: str) -> list[dict]:
    """games: one team's games in kickoff order, each {game_id, week, season, played: {pid: (pos, carries, targets)},
    active: set(pid)}. kind 'rb' or 'tgt'. Returns events with prior shares from the previous WINDOW team-games."""
    out = []
    for i, g in enumerate(games):
        prev = [h for h in games[max(0, i - WINDOW):i] if h["season"] == g["season"]]
        if len(prev) < 2:
            continue
        num, den = {}, 0.0
        for h in prev:
            for pid, (pos, car, tgt) in h["played"].items():
                v = car if kind == "rb" else tgt
                if kind == "rb" and pos != "RB":
                    continue
                num[pid] = num.get(pid, 0.0) + v
                den += v
        if den <= 0:
            continue
        share = {p: v / den for p, v in num.items()}
        lead = min(share, key=lambda p: (-share[p], p))
        lead_pos = prev[-1]["played"].get(lead, (None,))[0] or next(h["played"][lead][0] for h in prev if lead in h["played"])
        if share[lead] < (RB_MIN if kind == "rb" else TGT_MIN) or lead not in prev[-1]["played"] or lead in g["played"]:
            continue
        pos = "RB" if kind == "rb" else lead_pos
        bens = sorted(p for p in g["active"] if g["pos"].get(p) == pos and p != lead)
        if not bens:
            continue
        nxt = min(bens, key=lambda p: (-share.get(p, 0.0), p))
        out.append({"game_id": g["game_id"], "season": g["season"], "week": g["week"], "team": g["team"], "kind": kind,
                    "lead": lead, "s_lead": share[lead], "next": nxt, "s_next": share.get(nxt, 0.0), "beneficiaries": bens})
    return out


def predictors(s_lead: float, s_next: float) -> dict:
    p0 = s_next / (1 - s_lead) if s_lead < 1 else 1.0
    return {"P0": p0, "P1": s_lead, "P2": (p0 + s_lead) / 2}


def check() -> None:
    def g(i, played, active, pos):
        return {"game_id": f"g{i}", "season": 2022, "week": i, "team": "T", "played": played, "active": active, "pos": pos}
    pos = {"L": "RB", "B": "RB", "C": "RB", "W": "WR"}
    full = {"L": ("RB", 18, 2), "B": ("RB", 4, 1), "C": ("RB", 2, 0), "W": ("WR", 0, 9)}
    games = [g(1, full, set(full), pos), g(2, full, set(full), pos), g(3, full, set(full), pos),
             g(4, {"B": ("RB", 20, 2), "C": ("RB", 3, 0), "W": ("WR", 0, 8)}, {"B", "C", "W"}, pos)]
    ev = events(games, "rb")
    assert len(ev) == 1 and ev[0]["game_id"] == "g4" and ev[0]["lead"] == "L" and ev[0]["next"] == "B", ev
    assert abs(ev[0]["s_lead"] - 0.75) < 1e-9 and abs(ev[0]["s_next"] - 4 / 24) < 1e-9
    p = predictors(0.75, 4 / 24)
    assert abs(p["P0"] - (4 / 24) / 0.25) < 1e-9 and p["P1"] == 0.75 and abs(p["P2"] - (p["P0"] + 0.75) / 2) < 1e-9
    assert events(games[:3], "rb") == []                                   # nobody absent: no event
    assert events([g(1, full, set(full), pos), g(2, full, set(full), pos)] + [games[3]], "rb")[0]["game_id"] == "g4"
    second = games + [g(5, {"B": ("RB", 20, 2), "C": ("RB", 3, 0)}, {"B", "C"}, pos)]
    assert [e["game_id"] for e in events(second, "rb")] == ["g4"]          # lead missed the previous game too: not new
    t = events(games, "tgt")                                               # W (targets 9/12) present throughout
    assert t == []
    print("hand cases: PASS")


# ---------- run ----------
def simulate(df: pl.DataFrame) -> pl.DataFrame:
    path = ROOT / "data" / "backtests" / "engine_A-1.0_params.pkl.gz"
    shas = json.loads((ROOT / "data" / "backtests" / "engine_params_sha256.json").read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == shas[path.name], "A-1.0 params do not hash as recorded"
    with gzip.open(path, "rb") as f:
        a = pickle.load(f)                                                 # the repo's own committed, hash-checked file
    frame = df.sort("game_id", "team", "player_id")
    res = {f"{m}_{k}": np.zeros(frame.height) for m in MKT for k in ("mean", "p90", "crps")}
    at = 0
    for (gid,), game in frame.group_by(["game_id"], maintain_order=True):
        sides = [r for _, r in game.group_by(["team"], maintain_order=True)]
        seed = int.from_bytes(str(gid).encode(), "little") % (2 ** 32)
        for rows, (_, s) in zip(sides, MA.simulate_game(a["P"], a["tab"], sides, SIMS, np.random.default_rng([0, seed]))):
            sl = slice(at, at + rows.height)
            for m, col in MKT.items():
                x = np.asarray(s[col])
                res[f"{m}_mean"][sl] = x.mean(axis=1)
                res[f"{m}_p90"][sl] = np.quantile(x, 0.9, axis=1, method="inverted_cdf")
                res[f"{m}_crps"][sl] = S.crps_samples(x, rows[col].to_numpy())
            at += rows.height
    out = frame.select("player_id", "game_id", "season", "week", "team", "position", "played", *MKT.values()).with_columns(
        [pl.Series(k, v) for k, v in res.items()])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    out.write_parquet(CACHE)
    return out


def team_games(df: pl.DataFrame) -> dict[str, list[dict]]:
    out = {}
    for (team,), t in df.sort("kickoff").group_by(["team"], maintain_order=True):
        lst = []
        for (gid,), g in t.group_by(["game_id"], maintain_order=True):
            pl_ = g.filter(pl.col("played"))
            lst.append({"game_id": gid, "season": int(g["season"][0]), "week": int(g["week"][0]), "team": team,
                        "played": {r[0]: (r[1], int(r[2]), int(r[3])) for r in pl_.select("player_id", "position", "carries", "targets").iter_rows()},
                        "active": set(g["player_id"].to_list()), "pos": dict(zip(g["player_id"].to_list(), g["position"].to_list()))})
        out[team] = lst
    return out


def boot(x: np.ndarray, wk: np.ndarray, level: float) -> list[float]:
    return list(S.paired_bootstrap(x, wk, level=level))


def main() -> int:
    check()
    if "--check" in sys.argv:
        return 0
    df, _, _ = AT.load(list(TUNE))
    runs = pl.read_parquet(CACHE) if CACHE.exists() else simulate(df)
    tg = team_games(df)
    ev = [e for t in tg.values() for kind in ("rb", "tgt") for e in events(t, kind)]
    E = pl.DataFrame([{k: v for k, v in e.items() if k != "beneficiaries"} for e in ev])
    ben = pl.DataFrame([{"game_id": e["game_id"], "player_id": p, "kind": e["kind"], "is_next": p == e["next"]}
                        for e in ev for p in e["beneficiaries"]])
    r = runs.filter(pl.col("played")).join(ben, on=["game_id", "player_id"], how="left")
    R = {"events": {k: {str(s): int(E.filter((pl.col("kind") == k) & (pl.col("season") == s)).height) for s in TUNE} for k in ("rb", "tgt")},
         "team_games": int(sum(len(v) for v in tg.values())), "played_rows": int(r.height)}
    for kind, mkts in (("rb", ("rush_att", "rush_yds")), ("tgt", ("rec", "rec_yds"))):
        for m in mkts:
            b = r.filter(pl.col("kind") == kind)
            o = r.filter(pl.col("kind").is_null() & (pl.col(f"{m}_mean") >= 1.0))      # other rows the engine gives volume
            nx = b.filter(pl.col("is_next"))
            err = (nx[f"{m}_mean"] - nx[MKT[m]]).to_numpy()
            wk = (nx["season"] * 100 + nx["week"]).to_numpy()
            R[m] = {"beneficiary_rows": b.height, "beneficiary_crps": float(b[f"{m}_crps"].mean()), "other_crps": float(o[f"{m}_crps"].mean()),
                    "beneficiary_share_of_total_crps": float(b[f"{m}_crps"].sum() / r[f"{m}_crps"].sum()),
                    "next_n": nx.height, "next_mean_engine": float(nx[f"{m}_mean"].mean()), "next_mean_actual": float(nx[MKT[m]].mean()),
                    "next_signed_error": boot(err, wk, 0.05),
                    "next_above_p90": float((nx[MKT[m]] > nx[f"{m}_p90"]).mean())}
    # Team style (RB events)
    rb = E.filter(pl.col("kind") == "rb")
    team_car = r.group_by("game_id", "team").agg(pl.col("carries").filter(pl.col("position") == "RB").sum().alias("rb_car"))
    act = r.select("game_id", "player_id", "carries")
    rows = rb.join(act, left_on=["game_id", "next"], right_on=["game_id", "player_id"]).join(team_car, on=["game_id", "team"])
    rows = rows.filter(pl.col("rb_car") > 0).with_columns((pl.col("carries") / pl.col("rb_car")).alias("y"))
    P = {k: np.array([predictors(a, b)[k] for a, b in zip(rows["s_lead"], rows["s_next"])]) for k in ("P0", "P1", "P2")}
    y, wk = rows["y"].to_numpy(), (rows["season"] * 100 + rows["week"]).to_numpy()
    R["style"] = {"n": len(y), "actual_mean_share": float(y.mean()),
                  "mae": {k: float(np.abs(v - y).mean()) for k, v in P.items()},
                  "P1_minus_P0": boot(np.abs(P["P1"] - y) - np.abs(P["P0"] - y), wk, 0.025),
                  "P2_minus_P0": boot(np.abs(P["P2"] - y) - np.abs(P["P0"] - y), wk, 0.025)}
    ra = R["rush_att"]
    real = ra["next_signed_error"][2] < 0 and ra["next_above_p90"] >= 0.20
    helps = R["style"]["P1_minus_P0"][2] < 0 or R["style"]["P2_minus_P0"][2] < 0
    R["verdict"] = {"problem_is_real": real, "team_style_helps": helps,
                    "recommendation": ("build a team-style reallocation rule as a candidate version (own Test S on 2024-2025)" if real and helps
                                       else "flag affected teams instead of a new model" if real else "nothing to fix at scale")}
    OUT_JSON.write_text(json.dumps(R, indent=1) + "\n")
    print(json.dumps(R, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
