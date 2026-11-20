"""PinnRadar (Pinnacle) one-off harvest while the paid REST plan lasts (Will, 2026-11-19). Record only: raw prices,
never a pick input.

The API has no history (docs https://pinnradar.com/docs: boards are current snapshots, /api/drops keeps ~3 h), so the
only way to keep Pinnacle line history is to record it now. Each cycle (default every 60 s):
  - prematch football board with props as flat rows, delta-polled with `since` (full board every FULL_EVERY s)
  - live (in-play) football board, delta-polled the same way
  - prematch and live drops buffer (every DROPS_EVERY s)
  - /prematch/markets for every NFL game and /health (every MARKETS_EVERY s)
  - plan check through the hosted MCP tool `my_usage` (every USAGE_EVERY s)
Stops at the job budget, two minutes before the plan's expiry, on 401/403, or on any 429 (a 429 means the paid
plan is gone; each further call would eat the free 100-a-day budget the CLV job needs). On a plan or quota stop it
writes data/pinnacle/radar/STOP so later chained jobs make no calls.

Output, one folder per job: data/pinnacle/radar/<job stamp>/
  full_<ts>.json.gz            whole prematch football board (all games, alternates, all props)
  prematch_deltas.jsonl.gz     one line per poll: {"t": poll UTC, "last": cursor, "events": [changed events]}
  live_full_<ts>.json.gz, live_deltas.jsonl.gz   the same for the in-play board
  drops.jsonl.gz               one line per drops call
  markets.jsonl.gz             one line per (event, poll) /prematch/markets reply
  calls.jsonl                  every request: path, params, status, bytes, data-age headers (never the key)
  usage.jsonl                  my_usage replies
The key (secret PINN_API) is sent only as a request header and never written to disk.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://pinnradar.com"
MCP = "https://mcp.pinnradar.com/mcp"
SPORT = 5                       # docs "Sport IDs": 5 = Football (Pinnacle 15): NFL and NCAA
ROOT = Path("data/pinnacle/radar")
STOP = ROOT / "STOP"
POLL = 20                       # demo plan allows 10/s; ~3 calls a cycle
FULL_EVERY = 1800
DROPS_EVERY = 600
MARKETS_EVERY = 3600
USAGE_EVERY = 900
COMMIT_EVERY = 600


class Halt(Exception):
    pass


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def stamp(t: dt.datetime | None = None) -> str:
    return (t or now()).strftime("%Y%m%dT%H%M%SZ")


def key() -> str:
    k = os.environ.get("PINN_API", "").strip()
    if not k:
        sys.exit("PINN_API is not set")
    return k


class Recorder:
    def __init__(self, out: Path):
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.n = 0

    def log(self, name: str, rec: dict) -> None:
        with open(self.out / name, "a") as f:
            f.write(json.dumps(rec) + "\n")

    def gz_line(self, name: str, rec: dict) -> None:
        with gzip.open(self.out / name, "at") as f:   # each append is a gzip member; readers see one stream
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    def gz_file(self, name: str, obj) -> None:
        with gzip.open(self.out / name, "wt") as f:
            json.dump(obj, f, separators=(",", ":"))

    def get(self, path: str, params: dict) -> dict | list | None:
        t = now()
        url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"x-portal-apikey": key(), "Accept": "application/json",
                                                   "User-Agent": "nfl-betting-model-research"})
        status, hdr, body = None, {}, b""
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    status, hdr, body = r.status, dict(r.headers.items()), r.read()
                break
            except urllib.error.HTTPError as e:
                status, hdr, body = e.code, dict((e.headers or {}).items()), e.read(4000)
                if e.code >= 500:
                    time.sleep(2 ** attempt); continue
                break
            except Exception as e:  # noqa: BLE001
                status, body = f"{type(e).__name__}: {str(e)[:150]}", b""
                time.sleep(2 ** attempt)
        self.n += 1
        keep = {k: v for k, v in hdr.items() if k.lower().startswith(("x-data", "x-rate", "retry", "ratelimit"))}
        self.log("calls.jsonl", {"t": stamp(t), "path": path, "params": params, "status": status, "bytes": len(body),
                                 "headers": keep, **({"error": body[:500].decode("utf-8", "replace")} if status != 200 else {})})
        if status in (401, 403):
            raise Halt(f"{status} on {path}: {body[:200]!r}")
        if status == 429:
            raise Halt(f"429 on {path} (plan limit reached; paid REST plan likely over): {body[:200]!r}")
        if status != 200:
            print(f"{path} {params} -> {status}", flush=True)
            return None
        return json.loads(body)


def my_usage(rec: Recorder) -> dict | None:
    """Plan, limits, expiry and today's count from the hosted MCP tool (1 call on the plan). None if unreadable."""
    hdr = {"Authorization": f"Bearer {key()}", "Content-Type": "application/json",
           "Accept": "application/json, text/event-stream", "User-Agent": "nfl-betting-model-research"}

    def post(payload: dict, extra: dict | None = None) -> tuple[object, dict, str]:
        req = urllib.request.Request(MCP, data=json.dumps(payload).encode(), headers=hdr | (extra or {}), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, dict(r.headers.items()), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, dict((e.headers or {}).items()), e.read(2000).decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            return f"{type(e).__name__}: {str(e)[:150]}", {}, ""

    def parse(text: str):
        for chunk in [text] + [ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")]:
            try:
                return json.loads(chunk)
            except Exception:  # noqa: BLE001
                continue
        return None

    t = stamp()
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "nfl-betting-model-research", "version": "1"}}}
    s1, h1, _ = post(init)
    sid = {k: v for k, v in h1.items() if k.lower() == "mcp-session-id"}
    s2, _, body = post({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "my_usage", "arguments": {}}}, sid)
    msg = parse(body)
    text = None
    if isinstance(msg, dict):
        for c in (msg.get("result") or {}).get("content", []) or []:
            if c.get("type") == "text":
                text = c.get("text")
    if text:
        text = re.sub(r'"api_key[a-z_]*"\s*:\s*"[^"]*",?', "", text)   # never store any part of the key
    rec.log("usage.jsonl", {"t": t, "init_status": s1, "status": s2, "text": text,
                            **({"raw": body[:800]} if text is None else {})})
    if s2 in (401, 403, 429):
        raise Halt(f"my_usage returned {s2}")
    if text is None:
        return None
    try:
        info = json.loads(text)
    except Exception:  # noqa: BLE001
        info = {"text": text}
    return info if isinstance(info, dict) else {"value": info}


def plan_view(info: dict) -> tuple[str, dt.datetime | None]:
    """Best-effort read of plan name and expiry from my_usage, whatever its exact field names."""
    flat = json.dumps(info).lower()
    plan = "unknown"
    p = info.get("plan")
    if isinstance(p, dict):                       # my_usage 2026-11-19: {"plan": {"id": "demo_3d", ...}}
        plan = str(p.get("id") or p.get("label") or "unknown").lower()
    elif isinstance(p, str):
        plan = p.lower()
    elif re.search(r"\bplan\W+(free|rest|edge|scale|drops)\b", flat):
        plan = re.search(r"\bplan\W+(free|rest|edge|scale|drops)\b", flat).group(1)
    if plan == "unknown" or "free" in plan or info.get("status") not in (None, "active"):
        plan = "free?" if plan == "unknown" else f"free? ({plan}, status {info.get('status')})"  # never risk the CLV quota
    exp = None
    m = re.search(r'"(?:expires?|expiry|expires_at|expiration|valid_until|renews?_at|plan_expires[a-z_]*)"\s*:\s*"?([0-9t:\-\.z+ ]{10,})"?', flat)
    if m:
        try:
            exp = dt.datetime.fromisoformat(m.group(1).strip().upper().replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            exp = None
    return plan, exp


def commit(msg: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    branch = os.environ["GITHUB_REF_NAME"]
    subprocess.run(["git", "add", str(ROOT)], check=False)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        return
    subprocess.run(["git", "commit", "-q", "-m", msg], check=False)
    for i in range(5):
        if (subprocess.run(["git", "pull", "-q", "--rebase", "origin", branch]).returncode == 0 and
                subprocess.run(["git", "push", "-q", "origin", f"HEAD:{branch}"]).returncode == 0):
            return
        time.sleep(2 ** (i + 1))
    print("push failed; data stays for the next commit", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=5.6)
    a = ap.parse_args()
    if STOP.exists():
        print(f"{STOP} present: {STOP.read_text().strip()}; no calls made")
        return
    start = now()
    deadline = start + dt.timedelta(hours=a.hours)
    rec = Recorder(ROOT / stamp(start))
    reason = "job budget reached"
    stop_file = False
    cur = {"prematch": None, "live": None}
    last = {"full": 0.0, "live_full": 0.0, "drops": 0.0, "markets": 0.0, "usage": 0.0, "commit": time.time()}
    nfl_games: dict[int, dict] = {}
    try:
        while now() < deadline:
            t0 = time.time()
            if t0 - last["usage"] >= USAGE_EVERY:
                info = my_usage(rec)
                last["usage"] = t0
                if info is None:
                    raise Halt("my_usage unreadable: plan unknown, stopping to protect the free quota")
                if info is not None:
                    plan, exp = plan_view(info)
                    print(f"plan={plan} expires={exp}", flush=True)
                    if plan.startswith(("free", "drops")) or "free" in plan:
                        stop_file = True
                        raise Halt(f"plan is {plan}: REST paid access over")
                    if exp is not None and exp - dt.timedelta(minutes=2) < deadline:
                        deadline = exp - dt.timedelta(minutes=2)
                        reason = f"plan expires {exp:%Y-%m-%dT%H:%M:%SZ}"
                        stop_file = True   # later chained jobs must not spend the free quota
            ts = stamp()
            for board, path in (("prematch", "/kit/v1/prematch/fixtures"), ("live", "/kit/v1/markets")):
                fk = "full" if board == "prematch" else "live_full"
                full = cur[board] is None or t0 - last[fk] >= FULL_EVERY
                params = {"sport_id": SPORT, "include_specials": 1} | ({} if full else {"since": cur[board]})
                b = rec.get(path, params)
                if b is None:
                    continue
                if isinstance(b, dict) and b.get("last") is not None:
                    cur[board] = b["last"]
                evs = b.get("events", []) if isinstance(b, dict) else []
                if full:
                    rec.gz_file(f"{'full' if board == 'prematch' else 'live_full'}_{ts}.json.gz", {"t": ts, **b})
                    last[fk] = t0
                    if board == "prematch":
                        nfl_games = {e["event_id"]: e for e in evs if e.get("league_name") == "NFL" and not e.get("parent_id")
                                     and e.get("is_have_periods")}
                else:
                    rec.gz_line(f"{board}_deltas.jsonl.gz", {"t": ts, "last": cur[board], "events": evs})
            if t0 - last["drops"] >= DROPS_EVERY:
                for mode in ("prematch", "live"):
                    d = rec.get("/api/drops", {"mode": mode, "sport_id": SPORT, "min_drop_pct": 4.8,
                                               "max_age_sec": 10800 if last["drops"] == 0 else 900, "limit": 5000})
                    if d is not None:
                        rec.gz_line("drops.jsonl.gz", {"t": ts, "mode": mode, "reply": d})
                last["drops"] = t0
            if t0 - last["markets"] >= MARKETS_EVERY:
                h = rec.get("/health", {})
                if h is not None:
                    rec.log("health.jsonl", {"t": ts, **h})
                for eid in sorted(nfl_games):
                    m = rec.get("/kit/v1/prematch/markets", {"event_id": eid})
                    if m is not None:
                        rec.gz_line("markets.jsonl.gz", {"t": ts, "event_id": eid, "reply": m})
                last["markets"] = t0
            if time.time() - last["commit"] >= COMMIT_EVERY:
                commit(f"data: PinnRadar harvest {ts} ({rec.n} calls so far)")
                last["commit"] = time.time()
            time.sleep(max(1.0, POLL - (time.time() - t0)))
    except Halt as e:
        reason = str(e)
        stop_file = True
    finally:
        if stop_file:
            STOP.write_text(f"{stamp()} {reason}\n")
        rec.log("calls.jsonl", {"t": stamp(), "end": reason, "calls": rec.n})
        print(f"stopped: {reason}; {rec.n} calls", flush=True)
        commit(f"data: PinnRadar harvest end ({reason[:60]})")


if __name__ == "__main__":
    main()
