"""Trends tab for the dashboard: history charts built only from committed tracker files (presentation only).

Nothing here changes a pick, a rule or a graded number. Each series is recomputed from data/live/ the same way the
dashboard's tables are; a chart with fewer than two weeks of history says so instead of filling the gap.
`payload(data, now)` returns the JSON the page script draws; `section(data, now)` is the tab's HTML.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import importlib.util
import json
import re
from pathlib import Path

import polars as pl

from nflbet.execution import evalues as V
from nflbet.gamesim import mix_live as Mx
from nflbet.props import market_ev as Mev

ROOT = Path(__file__).resolve().parents[3]
FIRST_WEEK = 9                                         # props mix and the DK/FD trackers start here
STALE_HOURS = 48                                       # display heuristic only; no tracker rule depends on it
PASS_N, PASS_WEEKS = 30, 5                             # K vs Mo pass rule, docs/ev_rules_2026_preregistration.md


def _f(x) -> float | None:
    try:
        return None if x in (None, "") else float(x)
    except (TypeError, ValueError):
        return None


def _cum(by_week: dict[int, float]) -> dict[int, float]:
    t, out = 0.0, {}
    for w in sorted(by_week):
        t += by_week[w]
        out[w] = round(t, 4)
    return out


def mix_weekly(rec: pl.DataFrame) -> dict:
    """Props mix, graded W/L only: wins, losses, units at DraftKings and at the best price, per week."""
    g = rec.filter(pl.col("result").is_in(["W", "L"])) if rec.height else rec
    wins, loss, u_dk, u_best = {}, {}, {}, {}
    for r in g.iter_rows(named=True):
        w = int(r["week"])
        (wins if r["result"] == "W" else loss)[w] = (wins if r["result"] == "W" else loss).get(w, 0) + 1
        u_dk[w] = u_dk.get(w, 0.0) + (_f(r["units"]) or 0.0)
        ub = _f(r.get("units_best"))
        u_best[w] = u_best.get(w, 0.0) + (ub if ub is not None else (_f(r["units"]) or 0.0))
    ws = sorted(set(wins) | set(loss))
    return {"W": {w: wins.get(w, 0) for w in ws}, "L": {w: loss.get(w, 0) for w in ws},
            "dk": _cum({w: u_dk.get(w, 0.0) for w in ws}), "best": _cum({w: u_best.get(w, 0.0) for w in ws})}


def rules_k_mo(rec: pl.DataFrame, best: pl.DataFrame | None) -> dict:
    rows = Mev.forward_rows(rec, best)
    out = {"K": {}, "Mo": {}, "n": {"K": 0, "Mo": 0}, "weeks": {"K": 0, "Mo": 0}}
    if not rows.height:
        return out
    for rule, col in Mev.FORWARD_RULES.items():
        g = rows.filter(pl.col(col) > 0)
        out["n"][rule], out["weeks"][rule] = g.height, g["week"].n_unique() if g.height else 0
        by = {}
        for r in g.iter_rows(named=True):
            by[r["week"]] = by.get(r["week"], 0.0) + r["units"]
        out[rule] = _cum(by)
    return out


def engine_weekly(interim: dict | None) -> dict:
    out = {"dk": {}, "A": {}, "B": {}, "n": {}}
    for w, r in ((interim or {}).get("by_week") or {}).items():
        try:
            wk = int(w)
        except ValueError:
            continue
        out["dk"][wk], out["n"][wk] = r.get("dk"), r.get("n")
        for e in ("A", "B"):
            if r.get(e) is not None:
                out[e][wk] = r[e]
    return out


def clv_weekly(clv: pl.DataFrame | None) -> dict:
    """Mean model-free CLV in EV points (clv_ev) per week and close source, graded rows only."""
    out: dict[str, dict[int, float]] = {}
    if clv is None or not clv.height or "clv_ev" not in clv.columns:
        return out
    acc: dict = {}
    for r in clv.iter_rows(named=True):
        v = _f(r["clv_ev"])
        if v is None:
            continue
        a = acc.setdefault((r["source"], int(r["week"])), [0.0, 0])
        a[0] += v
        a[1] += 1
    for (src, w), (t, n) in acc.items():
        out.setdefault(src, {})[w] = round(100 * t / n, 3)
    return out


def venue_share_weekly(best: pl.DataFrame | None, min_size: float = 10.0) -> dict:
    """Per week, the share of the week's mix picks on which each venue had the cheapest (or tied) price, using the same
    rule as the 'Who has the best price?' table (Mx.venue_table), one week at a time."""
    out: dict[str, dict[int, float]] = {}
    if best is None or not best.height:
        return out
    for w in sorted({int(x) for x in best["week"].to_list()}):
        vt = Mx.venue_table(best.filter(pl.col("week").cast(pl.Int64) == w), min_size)
        if not vt.height:
            continue
        n = max(int(vt.filter(pl.col("venue") == "DraftKings")["quoted"].sum()) if "DraftKings" in vt["venue"].to_list() else 0,
                int(vt["quoted"].max()))
        for r in vt.iter_rows(named=True):
            out.setdefault(r["venue"], {})[w] = round(100 * r["cheapest"] / n, 2) if n else 0.0
    return out


def tracker_units() -> tuple[dict, dict]:
    """Season-cumulative units and E-value at each week's end, per tracker (the weekly evidence meter, descriptive)."""
    live = ROOT / "data" / "live"
    files = {"S1": "s1_record_2026.csv", "S1 (ParlayAPI)": "s1pa_record_2026.csv", "ATS Bet Now": "ats_record_2026.csv",
             "Props mix": "mix_record_2026.csv"}
    series: dict[str, list[tuple[int, str, float]]] = {}
    for name, f in files.items():
        p = live / f
        if not p.exists() or not p.stat().st_size:
            continue
        with p.open() as fh:
            for r in csv.DictReader(fh):
                st = r.get("result_ats") or r.get("result") or ""
                if st in ("", "pending", "void") or _f(r.get("units")) is None or not r.get("week"):
                    continue
                if f.startswith("ats_") and r.get("label") != "Bet Now":
                    continue
                series.setdefault(name, []).append((int(float(r["week"])), r.get("start_time") or r.get("run_utc") or "", float(r["units"])))
    try:                                                # same wind rows as scripts/evalues.py; needs the nflverse schedule
        spec = importlib.util.spec_from_file_location("wind_live", ROOT / "scripts" / "wind_live.py")
        wl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wl)
        games = {g["game_id"]: g for g in wl.schedule()}
        for r in wl.grade_rows(wl.W.official(wl.read_records()), games):
            if r["pick"] == "under" and r["result"] in ("W", "L", "P"):
                series.setdefault("Wind unders", []).append((int(float(r["week"])), r.get("kickoff_utc") or "", float(r["units"])))
    except Exception as e:  # noqa: BLE001 - the page still builds without the wind source
        print(f"trends: wind unders left out: {type(e).__name__}: {e}")
    units, ev = {}, {}
    for name, rows in series.items():
        rows.sort(key=lambda x: (x[1], x[0]))
        by_week: dict[int, list[float]] = {}
        for w, _, u in rows:
            by_week.setdefault(w, []).append(u)
        seen: list[float] = []
        units[name], ev[name] = {}, {}
        for w in sorted(by_week):
            seen += by_week[w]
            units[name][w] = round(sum(seen), 3)
            ev[name][w] = round(float(V.eprocess(seen)[-1]), 3)
    return units, ev


def d_rules() -> list[dict]:
    """D1 and D2 progress from the committed interim report (docs/dkfd_rules_report.md): no per-week series is committed."""
    p = ROOT / "docs" / "dkfd_rules_report.md"
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        m = re.match(r"\|\s*(D\d)\S*\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)%\s*\|\s*([+-][\d.]+)%\s*\|\s*([^|]*)\|\s*([^|]*)\|", line)
        if m:
            out.append({"rule": m.group(1), "bets": int(m.group(2)), "weeks": int(m.group(3)), "under": float(m.group(4)),
                        "roi": float(m.group(5)), "interval": m.group(6).strip(), "verdict": m.group(7).strip()})
    return out


def freshness(data: dict, now: dt.datetime) -> list[dict]:
    """Latest timestamp in each committed source and how old it is at build time."""
    def last(df, col):
        return str(df[col].max()) if df is not None and getattr(df, "height", 0) and col in df.columns else None
    pq = data.get("pinn_runs")
    wind = ROOT / "data" / "live" / "wind" / "records_2026.csv"
    wl = None
    if wind.exists() and wind.stat().st_size:
        w = pl.read_csv(wind, infer_schema_length=0)
        wl = str(w["run_utc"].max()) if w.height else None
    items = [("Props mix run", last(data.get("mix_runs"), "run_utc")),
             ("Official S1 run", last(data.get("runs"), "run_utc")),
             ("Best-price snapshot", last(data.get("mix_best"), "run_utc")),
             ("Pinnacle snapshot", last(pq, "snap_utc")),
             ("Outliers poll", last(data.get("out_cur"), "poll_utc")),
             ("Wind tracker run", wl)]
    out = []
    for name, ts in items:
        age = None
        if ts:
            try:
                t = dt.datetime.strptime(ts[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=dt.timezone.utc)
                age = round((now - t).total_seconds() / 3600, 1)
            except ValueError:
                pass
        out.append({"name": name, "at": ts, "age": age, "stale": age is None or age > STALE_HOURS})
    return out


def payload(data: dict, now: dt.datetime) -> dict:
    mix = mix_weekly(data["mix_rec"]) if data.get("mix_rec") is not None and data["mix_rec"].height else mix_weekly(pl.DataFrame())
    km = rules_k_mo(data.get("mix_rec", pl.DataFrame()), data.get("mix_best"))
    eng = engine_weekly(data.get("engine_interim"))
    clv = clv_weekly(data.get("mix_clv"))
    vs = venue_share_weekly(data.get("mix_best"))
    units, ev = tracker_units()
    top = max([FIRST_WEEK] + [w for d in (mix["W"], mix["dk"], km["K"], km["Mo"], eng["dk"], *clv.values(), *vs.values(),
                                           *units.values()) for w in d])
    cur = int(data["runs"]["week"].cast(pl.Int64).max()) if data.get("runs") is not None and data["runs"].height else FIRST_WEEK
    top = max(top, cur)
    S = lambda name, d, cls="": {"name": name, "values": {str(k): v for k, v in d.items()}}  # noqa: E731
    charts = [
        {"id": "mixrec", "title": "Props mix: wins and losses by week", "type": "stack", "fmt": "n", "unit": "picks",
         "series": [S("Won", mix["W"]), S("Lost", mix["L"])], "tone": ["pos", "neg"],
         "note": "Graded picks only (pushes and voids excluded); pending picks are not counted."},
        {"id": "mixu", "title": "Props mix: cumulative units, DraftKings vs best price", "type": "line", "fmt": "u", "unit": "units",
         "series": [S("At DraftKings", mix["dk"]), S("At best price", mix["best"])], "zero": True,
         "note": "Season-cumulative at each week's end, 1 unit per pick, at the price recorded with the pick."},
        {"id": "kmo", "title": f"Rule K vs rule Mo, weeks 11-18 (cumulative units at best price)", "type": "line", "fmt": "u", "unit": "units",
         "series": [S("K: market EV > 0", km["K"]), S("Mo: model EV > 0", km["Mo"])], "zero": True,
         "note": f"Pre-registered test (PR #27): pass needs {PASS_N}+ bets over {PASS_WEEKS}+ weeks. So far K has {km['n']['K']} graded "
                 f"bets in {km['weeks']['K']} week(s), Mo {km['n']['Mo']} in {km['weeks']['Mo']}. Descriptive until week 18."},
        {"id": "eng", "title": "Engine Test M: log loss by week vs DraftKings no-vig", "type": "line", "fmt": "ll", "unit": "log loss",
         "series": [S("DraftKings", eng["dk"]), S("Engine A", eng["A"]), S("Engine B", eng["B"])], "lower": True,
         "note": "Lower is better. Interim and descriptive; the verdict is decided once after week 18. Appears after the first "
                 "Wednesday Test M run grades week 11."},
        {"id": "clv", "title": "Props CLV: mean closing-line value by week", "type": "bar", "fmt": "p", "unit": "EV points",
         "series": [S({"dk": "DraftKings close", "fd": "FanDuel close", "pinnacle": "Pinnacle close"}.get(k, k), clv[k])
                    for k in ("dk", "fd", "pinnacle") if k in clv], "zero": True,
         "note": "Record only (docs/props_clv_rules.md). Mean of clv_ev over picks with a close, in percentage points of EV."},
        {"id": "venue", "title": "Who has the best price? Share of picks by venue", "type": "line", "fmt": "pc", "unit": "% of picks",
         "series": [S(v, d) for v, d in sorted(vs.items(), key=lambda kv: -sum(kv[1].values()))[:5]],
         "note": "Per week, the share of picks where the venue was cheapest or tied (fees included, exchanges need $10+ behind the "
                 "price). Ties count for every tied venue, so a week's shares can add to more than 100%. Top five venues by total."},
        {"id": "units", "title": "All trackers: cumulative units", "type": "line", "fmt": "u", "unit": "units",
         "series": [S(k, d) for k, d in units.items()], "zero": True,
         "note": "Each tracker's own graded bets, 1 unit each, as recorded. S1 and ATS started earlier than the others, so their "
                 "history begins before week 9. Unvalidated trackers; no verdict is implied."},
        {"id": "evalue", "title": "Weekly evidence meter: E-value by tracker", "type": "line", "fmt": "e", "unit": "E",
         "series": [S(k, d) for k, d in ev.items()], "ref": {"y": 20, "label": "E = 20 (5% bar, one tracker)"},
         "note": "E-value method in docs/m20_evalues_preregistration.md, computed here over each tracker's whole recorded history "
                 "(the official readout starts at week 10, see docs/evalues_2026.md). E near 1 means no evidence of an edge."},
    ]
    for c in charts:
        c["weeks_with_data"] = sorted({int(w) for s in c["series"] for w in s["values"]})
    return {"first": FIRST_WEEK, "last": top, "charts": charts, "fresh": freshness(data, now), "d": d_rules(),
            "built": now.strftime("%Y-%m-%dT%H:%M:%SZ")}


def _esc(x) -> str:
    return html.escape(str(x), quote=True)


def section(data: dict, now: dt.datetime) -> str:
    try:
        p = payload(data, now)
    except Exception as e:  # noqa: BLE001 - the rest of the dashboard must still build
        print(f"trends skipped: {type(e).__name__}: {e}")
        return ('<section class="block"><div class="sechead"><div><p class="eyebrow">History</p><h2>Trends</h2></div></div>'
                '<p class="empty">Trend charts could not be built from the tracker files this time.</p></section>')
    weeks = list(range(p["first"], p["last"] + 1))
    opts = lambda sel: "".join(f'<option value="{w}"{" selected" if w == sel else ""}>Week {w}</option>' for w in weeks)  # noqa: E731
    def age_txt(f: dict) -> str:
        return "–" if f["age"] is None else "%.1f h" % f["age"]

    def age_chip(f: dict) -> str:
        return '<span class="chip" data-k="bad">stale</span>' if f["stale"] else '<span class="chip" data-k="ok">fresh</span>'
    fresh = "".join(f'<tr><td>{_esc(f["name"])}</td><td>{_esc(f["at"] or "never")}</td><td>{age_txt(f)}</td><td>{age_chip(f)}</td></tr>'
                    for f in p["fresh"])
    drows = "".join(
        f'<tr><td>{_esc(d["rule"])}</td><td>{d["bets"]}</td><td>{d["weeks"]}</td><td>{d["under"]:.1f}%</td><td>{d["roi"]:+.1f}%</td>'
        f'<td>{_esc(d["interval"])}</td>'
        f'<td><span class="chip" data-k="{"ok" if d["bets"] >= PASS_N and d["weeks"] >= PASS_WEEKS else "idle"}">'
        f'{"enough bets" if d["bets"] >= PASS_N and d["weeks"] >= PASS_WEEKS else "pending"}</span></td></tr>' for d in p["d"])
    dtable = ('<div class="card"><h3>D1 / D2 trackers (DK and FanDuel rules)</h3>'
              '<p class="note" style="margin-top:2px">From the committed interim report, weeks 9-18. Only the latest totals are saved, '
              'so there is no history to chart yet. Pass needs 30+ bets, 5+ weeks and an interval above zero (PR #8).</p>'
              '<div class="tablewrap"><table class="num"><thead><tr><th scope="col">Rule</th><th scope="col">Bets</th><th scope="col">Weeks</th>'
              '<th scope="col">Under won</th><th scope="col">ROI</th><th scope="col">Interval</th><th scope="col">Status</th></tr></thead>'
              f'<tbody>{drows}</tbody></table></div></div>') if drows else ""
    blob = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    return (
        '<section class="block" id="trends"><div class="sechead"><div><p class="eyebrow">History · from committed records only</p>'
        '<h2>Trends</h2></div>'
        '<div class="range" role="group" aria-label="Week range for all charts">'
        f'<label>From <select id="tr-from">{opts(p["first"])}</select></label>'
        f'<label>To <select id="tr-to">{opts(p["last"])}</select></label>'
        '<button type="button" id="tr-reset">Reset</button></div></div>'
        '<p class="lede">Every line is rebuilt from the saved tracker files at build time. Where a dataset has under two weeks of '
        'history the chart says so rather than drawing a trend. These are descriptive records of unvalidated trackers, not advice.</p>'
        '<div class="grid2" id="tr-charts"></div>'
        f'<div class="stack">{dtable}'
        '<div class="card"><h3>Data freshness</h3>'
        f'<p class="note" style="margin-top:2px">Latest record in each source, at build time. Flagged stale after {STALE_HOURS} hours; '
        'that is a display cue, and off days between games are normal.</p>'
        '<div class="tablewrap"><table class="num"><thead><tr><th scope="col">Source</th><th scope="col">Latest (UTC)</th>'
        f'<th scope="col">Age</th><th scope="col">Status</th></tr></thead><tbody>{fresh}</tbody></table></div></div></div>'
        f'<script type="application/json" id="tr-data">{blob}</script></section>')


CSS = """
/* Trends tab */
.range{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;font:600 12px var(--display);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.range select,.range button,.tsearch input{font:500 14px var(--body);letter-spacing:0;text-transform:none;background:var(--surface);color:var(--ink);
  border:1px solid var(--line);border-radius:5px;padding:5px 9px;min-height:32px}
.range button{cursor:pointer;color:var(--ink2)}.range button:hover,.range select:hover{border-color:var(--accent)}
.tchart{display:flex;flex-direction:column;gap:6px}
.tchart svg{width:100%;height:auto;display:block;overflow:visible}
.tchart .ax{stroke:var(--grid);stroke-width:1}.tchart .zero{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 3}
.tchart .refl{stroke:var(--warn-ink);stroke-width:1;stroke-dasharray:5 4}
.tchart text{fill:var(--muted);font:11px var(--mono)}
.tchart .ln{fill:none;stroke-width:2.25;stroke-linejoin:round;stroke-linecap:round}
.tchart .mk{stroke:var(--surface);stroke-width:1.5;cursor:default;outline:none}
.tchart .mk:hover,.tchart .mk:focus{stroke:var(--ink);stroke-width:2}
.tchart .hitcol{fill:transparent}.tchart .hitcol:hover,.tchart .hitcol:focus{fill:var(--accent-soft);opacity:.35;outline:none}
.tchart .badge{align-self:flex-start;font:600 12px var(--display);letter-spacing:.06em;text-transform:uppercase;background:var(--warn-bg);color:var(--warn-ink);
  padding:2px 9px;border-radius:999px}
.tchart .nodata{padding:34px 8px;text-align:center;color:var(--muted);font-size:14px;border:1px dashed var(--line);border-radius:6px}
.tchart details summary{font:600 13px var(--display);letter-spacing:.06em;text-transform:uppercase;color:var(--ink2);margin-top:4px}
.tlegend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12.5px;color:var(--ink2)}
.tlegend span{display:inline-flex;align-items:center;gap:6px}
.tlegend svg{width:22px;height:10px}
.chip[data-k=ok]{background:var(--good-bg);color:var(--good)}.chip[data-k=bad]{background:var(--bad-bg);color:var(--bad)}.chip[data-k=idle]{background:var(--idle-bg);color:var(--ink2)}
"""

JS = r"""
(function(){
  var el=document.getElementById('tr-data');if(!el)return;
  var D=JSON.parse(el.textContent),host=document.getElementById('tr-charts');
  var fromS=document.getElementById('tr-from'),toS=document.getElementById('tr-to');
  var COL=['var(--c1)','var(--c2)','var(--c3)','var(--c4)','var(--c5)'],DASH=['','6 3','2 3','8 3 2 3','1 4'];
  var NS='http://www.w3.org/2000/svg';
  function S(n,a,p){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e}
  var tip=document.createElement('div');tip.className='tip';tip.hidden=true;document.body.appendChild(tip);
  function showTip(t,x,y){tip.textContent='';var s=document.createElement('strong');s.textContent=t[0];tip.appendChild(s);
    for(var i=1;i<t.length;i++){var d=document.createElement('span');d.style.display='block';d.textContent=t[i];tip.appendChild(d)}
    tip.hidden=false;var w=tip.offsetWidth,h=tip.offsetHeight;
    tip.style.left=Math.max(8,Math.min(innerWidth-w-8,x+14))+'px';tip.style.top=Math.max(8,y-h-12)+'px'}
  function atEl(e){var r=e.getBoundingClientRect();showTip(JSON.parse(e.getAttribute('data-t')),r.left+r.width/2,r.top)}
  function bind(e){
    e.addEventListener('pointermove',function(ev){showTip(JSON.parse(e.getAttribute('data-t')),ev.clientX,ev.clientY)});
    e.addEventListener('pointerleave',function(){tip.hidden=true});
    e.addEventListener('focus',function(){atEl(e)});e.addEventListener('blur',function(){tip.hidden=true});
  }
  var FMT={n:function(v){return String(Math.round(v))},u:function(v){return(v>=0?'+':'−')+Math.abs(v).toFixed(2)},ll:function(v){return v.toFixed(4)},
    p:function(v){return(v>=0?'+':'−')+Math.abs(v).toFixed(1)+' pts'},pc:function(v){return v.toFixed(0)+'%'},e:function(v){return v.toFixed(2)}};
  function nice(lo,hi){if(lo===hi){lo-=1;hi+=1}var span=hi-lo,st=Math.pow(10,Math.floor(Math.log10(span/4)));
    var m=span/4/st;st*=m>5?10:m>2?5:m>1?2:1;return{lo:Math.floor(lo/st)*st,hi:Math.ceil(hi/st)*st,st:st}}
  function draw(c,card,a,b){
    var body=card.querySelector('.tbody');body.textContent='';
    var weeks=[];for(var w=a;w<=b;w++)weeks.push(w);
    var ser=c.series.filter(function(s){return weeks.some(function(w){return s.values[w]!=null})});
    var have=weeks.filter(function(w){return ser.some(function(s){return s.values[w]!=null})});
    var badge=card.querySelector('.badge');
    if(!ser.length){var n=document.createElement('div');n.className='nodata';n.textContent='No graded history in this range yet.';body.appendChild(n);badge.hidden=true;return}
    badge.hidden=have.length>=2;badge.textContent='Only '+have.length+' week'+(have.length===1?'':'s')+' of history';
    var W=520,H=250,m={l:46,r:12,t:26,b:30},iw=W-m.l-m.r,ih=H-m.t-m.b;
    var vals=[];ser.forEach(function(s){weeks.forEach(function(w){if(s.values[w]!=null)vals.push(s.values[w])})});
    var stack=c.type==='stack',lo=Math.min.apply(null,vals),hi=Math.max.apply(null,vals);
    if(stack){hi=Math.max.apply(null,weeks.map(function(w){return ser.reduce(function(t,s){return t+(s.values[w]||0)},0)}));lo=0}
    if(c.zero||c.type==='bar'||stack){lo=Math.min(lo,0);hi=Math.max(hi,0)}
    if(c.ref){hi=Math.max(hi,c.ref.y)}
    var sc=nice(lo,hi),yS=function(v){return m.t+ih-(v-sc.lo)/(sc.hi-sc.lo)*ih};
    var step=iw/weeks.length,xS=function(w){return m.l+(weeks.indexOf(w)+.5)*step};
    var svg=S('svg',{viewBox:'0 0 '+W+' '+H,role:'img','aria-label':c.title+'. '+have.length+' weeks of data; see the table below the chart.'});
    for(var v=sc.lo;v<=sc.hi+sc.st/2;v+=sc.st){S('line',{x1:m.l,x2:W-m.r,y1:yS(v),y2:yS(v),class:'ax'},svg);
      var t=S('text',{x:m.l-6,y:yS(v)+4,'text-anchor':'end'},svg);t.textContent=(FMT[c.fmt]===FMT.u?(Math.round(v*100)/100):Math.round(v*100)/100)}
    if(sc.lo<0&&sc.hi>0)S('line',{x1:m.l,x2:W-m.r,y1:yS(0),y2:yS(0),class:'zero'},svg);
    if(c.ref){S('line',{x1:m.l,x2:W-m.r,y1:yS(c.ref.y),y2:yS(c.ref.y),class:'refl'},svg);var rt=S('text',{x:W-m.r,y:yS(c.ref.y)-4,'text-anchor':'end'},svg);rt.textContent=c.ref.label}
    weeks.forEach(function(w){var t=S('text',{x:xS(w),y:H-10,'text-anchor':'middle'},svg);t.textContent=weeks.length>10?w:'W'+w});
    var yl=S('text',{x:4,y:10},svg);yl.textContent=c.unit;
    function tipFor(w){var o=[(c.title.split(':')[0])+' · week '+w];ser.forEach(function(s){var v=s.values[w];o.push(s.name+': '+(v==null?'no data':FMT[c.fmt](v)))});return JSON.stringify(o)}
    if(stack||c.type==='bar'){
      var k=ser.length,gw=Math.min(step*.78,60),bw=stack?gw:gw/k;
      weeks.forEach(function(w){
        var base=0;
        ser.forEach(function(s,i){var v=s.values[w];if(v==null)return;
          var col=stack&&c.tone?(c.tone[ser.indexOf(s)]==='neg'?'var(--neg)':'var(--accent)'):COL[i%5];
          var x=xS(w)-gw/2+(stack?0:i*bw),y0=yS(stack?base:0),y1=yS(stack?base+v:v);
          var r=S('rect',{x:x,y:Math.min(y0,y1),width:Math.max(bw-1,1),height:Math.max(Math.abs(y1-y0),1),fill:col,rx:2},svg);if(stack)base+=v;
        });
        var hc=S('rect',{x:xS(w)-step/2,y:m.t,width:step,height:ih,class:'hitcol',tabindex:0,'data-t':tipFor(w),'aria-label':tipFor(w).replace(/[\[\]"]/g,'')},svg);bind(hc);
      });
    }else{
      ser.forEach(function(s,i){
        var pts=weeks.filter(function(w){return s.values[w]!=null}),d='';
        pts.forEach(function(w,j){d+=(j?'L':'M')+xS(w).toFixed(1)+' '+yS(s.values[w]).toFixed(1)});
        var pl=S('path',{d:d,class:'ln',stroke:COL[i%5],'stroke-dasharray':DASH[i%5]},svg);
        pts.forEach(function(w){var x=xS(w),y=yS(s.values[w]),r=4.5,e;
          if(i%3===0)e=S('circle',{cx:x,cy:y,r:r},svg);
          else if(i%3===1)e=S('rect',{x:x-r,y:y-r,width:2*r,height:2*r},svg);
          else e=S('path',{d:'M'+x+' '+(y-r-1)+'L'+(x+r+1)+' '+y+'L'+x+' '+(y+r+1)+'L'+(x-r-1)+' '+y+'Z'},svg);
          e.setAttribute('fill',COL[i%5]);e.setAttribute('class','mk');e.setAttribute('tabindex','0');
          e.setAttribute('data-t',tipFor(w));e.setAttribute('aria-label',tipFor(w).replace(/[\[\]"]/g,''));bind(e)});
      });
    }
    body.appendChild(svg);
    var lg=document.createElement('div');lg.className='tlegend';
    ser.forEach(function(s,i){var sp=document.createElement('span'),sv=S('svg',{viewBox:'0 0 22 10'});
      if(stack||c.type==='bar')S('rect',{x:3,y:0,width:16,height:10,rx:2,fill:stack&&c.tone?(c.tone[c.series.indexOf(s)]==='neg'?'var(--neg)':'var(--accent)'):COL[i%5]},sv);
      else{S('line',{x1:0,x2:22,y1:5,y2:5,stroke:COL[i%5],'stroke-width':2.25,'stroke-dasharray':DASH[i%5]},sv);S('circle',{cx:11,cy:5,r:3,fill:COL[i%5]},sv)}
      sp.appendChild(sv);sp.appendChild(document.createTextNode(s.name));lg.appendChild(sp)});
    if(c.lower){var lo2=document.createElement('span');lo2.textContent='Lower is better';lg.appendChild(lo2)}
    body.appendChild(lg);
    var dt=document.createElement('details'),sm=document.createElement('summary');sm.textContent='Data table';dt.appendChild(sm);
    var wrap=document.createElement('div');wrap.className='tablewrap';var tb=document.createElement('table');tb.className='num';
    var h='<thead><tr><th scope="col">Week</th>'+ser.map(function(s){return'<th scope="col">'+s.name.replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</th>'}).join('')+'</tr></thead><tbody>';
    have.forEach(function(w){h+='<tr><td>Week '+w+'</td>'+ser.map(function(s){return'<td>'+(s.values[w]==null?'–':FMT[c.fmt](s.values[w]))+'</td>'}).join('')+'</tr>'});
    tb.innerHTML=h+'</tbody>';wrap.appendChild(tb);dt.appendChild(wrap);body.appendChild(dt);
    if(window.nflTables)window.nflTables(dt);
  }
  var cards=[];
  D.charts.forEach(function(c){
    var card=document.createElement('div');card.className='card tchart';
    var h=document.createElement('h3');h.textContent=c.title;card.appendChild(h);
    var b=document.createElement('span');b.className='badge';b.hidden=true;card.appendChild(b);
    var n=document.createElement('p');n.className='note';n.style.marginTop='0';n.textContent=c.note;card.appendChild(n);
    var body=document.createElement('div');body.className='tbody';card.appendChild(body);
    host.appendChild(card);cards.push([c,card]);
  });
  function render(){
    var a=+fromS.value,b=+toS.value;if(a>b){var t=a;a=b;b=t}
    try{localStorage.setItem('tr-range',a+','+b)}catch(e){}
    tip.hidden=true;cards.forEach(function(x){draw(x[0],x[1],a,b)});
  }
  try{var r=(localStorage.getItem('tr-range')||'').split(',').map(Number);
    if(r.length===2&&r[0]>=D.first&&r[1]<=D.last&&r[0]<=r[1]){fromS.value=r[0];toS.value=r[1]}}catch(e){}
  fromS.addEventListener('change',render);toS.addEventListener('change',render);
  document.getElementById('tr-reset').addEventListener('click',function(){fromS.value=D.first;toS.value=D.last;render()});
  render();
})();
"""

TABLE_CSS = """
/* every table: zebra rows, sticky header, sortable columns, search */
.tablewrap{max-height:70vh;overflow:auto;border:1px solid var(--line);border-radius:6px;background:var(--surface)}
.tablewrap table{border-collapse:separate;border-spacing:0}
.tablewrap thead th{position:sticky;top:0;z-index:1;background:var(--raised);border-bottom:2px solid var(--line)}
.tablewrap tbody tr:nth-child(even) td{background:color-mix(in srgb,var(--ink) 4%,transparent)}
.tablewrap tbody tr:hover td{background:var(--accent-soft)}
.tablewrap td{border-bottom:1px solid var(--grid)}
th[aria-sort] button{all:unset;cursor:pointer;display:inline-flex;gap:5px;align-items:center;color:inherit;font:inherit;letter-spacing:inherit;text-transform:inherit}
th[aria-sort] button:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
th[aria-sort] button::after{content:"↕";opacity:.45;font-size:11px}
th[aria-sort=ascending] button::after{content:"▲";opacity:1;color:var(--accent)}
th[aria-sort=descending] button::after{content:"▼";opacity:1;color:var(--accent)}
.tsearch{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;margin:0 0 6px}
.tsearch input{min-width:min(100%,240px)}
.tsearch .tcount{font:12px var(--mono);color:var(--muted)}
@media (max-width:760px){.tablewrap{max-height:none}}
"""

TABLE_JS = r"""
(function(){
  function num(s){var m=s.replace(/[,$−]/g,function(c){return c==='−'?'-':''}).match(/[-+]?\d*\.?\d+/);return m?parseFloat(m[0]):null}
  function enhance(t){
    if(t.dataset.enh)return;t.dataset.enh='1';
    var head=t.tHead&&t.tHead.rows[0],body=t.tBodies[0];if(!head||!body)return;
    var ths=[].slice.call(head.cells),rows=[].slice.call(body.rows);
    ths.forEach(function(th,i){
      th.setAttribute('scope','col');if(!th.textContent.trim())return;
      th.setAttribute('aria-sort','none');
      var b=document.createElement('button');b.type='button';b.innerHTML=th.innerHTML;th.textContent='';th.appendChild(b);
      b.addEventListener('click',function(){
        var dir=th.getAttribute('aria-sort')==='ascending'?'descending':'ascending';
        ths.forEach(function(o){if(o.hasAttribute('aria-sort'))o.setAttribute('aria-sort','none')});th.setAttribute('aria-sort',dir);
        var k=dir==='ascending'?1:-1,live=[].slice.call(body.rows);
        var nums=live.every(function(r){var c=r.cells[i];return !c||c.textContent.trim()===''||c.textContent.trim()==='–'||num(c.textContent)!==null});
        live.sort(function(a,c){
          var x=a.cells[i]?a.cells[i].textContent.trim():'',y=c.cells[i]?c.cells[i].textContent.trim():'';
          if(nums){var p=num(x),q=num(y);if(p===null&&q===null)return 0;if(p===null)return 1;if(q===null)return -1;return(p-q)*k}
          return x.localeCompare(y,undefined,{numeric:true})*k});
        live.forEach(function(r){body.appendChild(r)});
      });
    });
    if(rows.length>=8){
      var wrap=t.closest('.tablewrap'),bar=document.createElement('div');bar.className='tsearch';
      var lab=document.createElement('label'),inp=document.createElement('input'),cnt=document.createElement('span');
      var id='ts'+Math.random().toString(36).slice(2,8);inp.id=id;inp.type='search';inp.placeholder='Search this table';
      lab.htmlFor=id;lab.className='eyebrow';lab.style.margin='0';lab.textContent='Filter';cnt.className='tcount';cnt.setAttribute('aria-live','polite');
      bar.appendChild(lab);bar.appendChild(inp);bar.appendChild(cnt);wrap.parentNode.insertBefore(bar,wrap);
      var go=function(){var q=inp.value.toLowerCase().trim(),n=0;
        [].forEach.call(body.rows,function(r){var ok=!q||r.textContent.toLowerCase().indexOf(q)>-1;r.hidden=!ok;if(ok)n++});
        cnt.textContent=q?n+' of '+body.rows.length+' rows':body.rows.length+' rows'};
      inp.addEventListener('input',go);go();
    }
  }
  window.nflTables=function(root){[].forEach.call((root||document).querySelectorAll('.tablewrap table'),enhance)};
  window.nflTables();
})();
"""
