"""EndzoneAPI price check (evidence only, free): estimate_only for prop-call variants, to see which costs 10 credits
and which 20. Writes docs/evidence/endzone_estimates/<UTC stamp>.json. Key from ENDZONEAPI_API_KEY, never written."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ezp", ROOT / "scripts" / "audit" / "endzone_probe.py")
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)

G = P.GAME
MAHOMES = "00-0033873"
VARIANTS = [
    ("game", "get_player_props", {"game_id": G}),
    ("game_opening", "get_player_props", {"game_id": G, "snapshot_type": "opening"}),
    ("game_draftkings", "get_player_props", {"game_id": G, "bookmaker": "draftkings"}),
    ("game_rec_yds", "get_player_props", {"game_id": G, "market": "player_reception_yds"}),
    ("game_draftkings_rec_yds", "get_player_props", {"game_id": G, "bookmaker": "draftkings",
                                                     "market": "player_reception_yds"}),
    ("player_season_2023", "get_player_props", {"player_id": MAHOMES, "season": 2023}),
    ("player_season_2023_pass_yds", "get_player_props", {"player_id": MAHOMES, "season": 2023,
                                                         "market": "player_pass_yds"}),
    ("games_season_2023", "get_games", {"season": 2023, "limit": 500}),
    ("prop_history_mahomes_pass_yds", "get_prop_history", {"player_id": MAHOMES, "market": "player_pass_yds",
                                                           "limit": 200}),
]


def main() -> None:
    out = {}
    for name, tool, args in VARIANTS:
        status, hdr, body = P.call(tool, {**args, "estimate_only": True})
        out[name] = {"tool": tool, "args": args, "status": status, "credit_headers": hdr, "body": body}
        print(name, status, hdr, json.dumps(body)[:300], flush=True)
        if hdr.get("x-credits-used") not in (None, "0"):
            print("charged; stopping", flush=True)
            break
    d = ROOT / "docs" / "evidence" / "endzone_estimates"
    d.mkdir(parents=True, exist_ok=True)
    (d / (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")).write_text(
        json.dumps(out, indent=1, default=str)[:500_000])


if __name__ == "__main__":
    main()
