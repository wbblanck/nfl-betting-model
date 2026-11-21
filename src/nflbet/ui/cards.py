"""Engine and Outliers visuals: price-ladder cards, edge meters, histograms, donut (presentation only).

Everything is drawn from the same committed rows the tables show, with plain HTML and CSS so it is selectable,
readable by screen readers (each graphic has a text equivalent) and works without scripts; the filter and sort
chips on the outlier cards are the only script. The sortable tables stay under each graphic as "Table view".
"""
from __future__ import annotations

import html
from typing import Callable

import polars as pl

VENUE_VAR = {"Novig": "--c1", "Kalshi": "--c2", "Polymarket US": "--c3", "DraftKings": "--c4", "FanDuel": "--c5"}
THRESH_EDGE, SCALE_EDGE = 0.03, 0.12                 # outlier rule: 3%+ edge; the meter runs to 12%
BINS = [0.03, 0.05, 0.07, 0.09, 0.11, 0.13, 0.15]    # engine edge histogram, last bin open-ended


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def am(p: float) -> str:
    """Cost per $1 of payout as an American price."""
    return f"{-100 * p / (1 - p):+.0f}" if p >= 0.5 else f"+{100 * (1 - p) / p:.0f}"


def _f(x) -> float | None:
    try:
        v = None if x in (None, "") else float(x)
    except (TypeError, ValueError):
        return None
    return None if v is not None and v != v else v


def pct(x: float | None, d: int = 1, sign: bool = False) -> str:
    return "–" if x is None else f"{x * 100:{'+' if sign else ''}.{d}f}%"


def venue_chip(v: str) -> str:
    var = VENUE_VAR.get(v, "--muted")
    return f'<span class="vchip" style="--vc:var({var})">{esc(v)}</span>'


def group_of(kind: str) -> str:
    return "Props" if kind.startswith("Prop") else kind


def meter(value: float | None, scale: float, tick: float | None, label: str) -> str:
    """A horizontal meter with an optional rule tick; the value is also written out."""
    if value is None:
        return '<span class="muted">–</span>'
    w = max(0.0, min(value / scale, 1.0)) * 100
    t = f'<b style="left:{tick / scale * 100:.1f}%" title="rule threshold"></b>' if tick is not None else ""
    ok = tick is None or value >= tick
    return (f'<span class="emeter" role="img" aria-label="{esc(label)}"><span class="etrack"><i class="{"ok" if ok else "lo"}" '
            f'style="width:{w:.1f}%"></i>{t}</span><span class="ev">{esc(label)}</span></span>')


def ladder(best: float, nxt: float | None, fair: float | None) -> tuple[str, str]:
    """(html, text) price ladder on a cost axis: cheaper left. Markers: best price, next best, Pinnacle fair."""
    pts = [v for v in (best, nxt, fair) if v is not None]
    lo, hi = max(min(pts) - 0.03, 0.0), min(max(pts) + 0.03, 1.0)
    span = (hi - lo) or 1.0
    pos = lambda v: max(0.0, min((v - lo) / span, 1.0)) * 100  # noqa: E731
    zone = ""
    if fair is not None and best < fair:
        zone = f'<span class="zone" style="left:{pos(best):.1f}%;width:{pos(fair) - pos(best):.1f}%"></span>'
    marks = ""
    if nxt is not None:
        marks += f'<span class="mk next" style="left:{pos(nxt):.1f}%" title="Next best {am(nxt)}"></span>'
    if fair is not None:
        marks += f'<span class="mk fair" style="left:{pos(fair):.1f}%" title="Pinnacle fair {am(fair)}"></span>'
    marks += f'<span class="mk best" style="left:{pos(best):.1f}%" title="Best {am(best)}"></span>'
    text = f"Best {am(best)}" + (f", next best {am(nxt)}" if nxt is not None else "") + (f", Pinnacle fair {am(fair)}" if fair is not None else "")
    return (f'<div class="ladder" role="img" aria-label="{esc(text)}"><div class="lrail">{zone}{marks}</div>'
            '<div class="lax"><span>cheaper</span><span>cost per $1 of payout</span><span>pricier</span></div></div>'), text


def outlier_card(r: dict, fmt_dt: Callable[[str], str]) -> str:
    c, g, fair = _f(r.get("best_cost")), _f(r.get("gap_next")), _f(r.get("fair_power"))
    edge, edge_m = _f(r.get("edge_power")), _f(r.get("edge_mult"))
    if c is None:
        return ""
    nxt = min(c * (1 + g), 0.999) if g is not None else None
    lad, _ = ladder(c, nxt, fair)
    dep = _f(r.get("best_depth"))
    mv = _f(r.get("move_pp"))
    mv_html = "–" if mv is None else f'<span class="mv {"up" if mv > 0 else "dn" if mv < 0 else ""}">{"▲" if mv > 0 else "▼" if mv < 0 else "•"} {mv:+.1f}pp</span>'
    starts = str(r.get("starts") or "")
    return (
        f'<article class="ocard" data-group="{esc(group_of(str(r["kind"])))}" data-edge="{edge or 0:.5f}" data-gap="{g or 0:.5f}" data-start="{esc(starts)}">'
        f'<header><span class="kind">{esc(r["kind"])}</span>{venue_chip(str(r["venue"]))}</header>'
        f'<h4>{esc(r["side"])}</h4><p class="ogame">{esc(r["game"])}</p>'
        f'<div class="price"><span class="pbig">{esc(am(c))}</span><span class="psub">best at {esc(r["venue"])}'
        + (f' · next best {esc(am(nxt))}' if nxt is not None else "") + '</span></div>'
        + lad +
        '<div class="erow"><span class="elab">Edge vs Pinnacle (power)</span>'
        + meter(edge, SCALE_EDGE, THRESH_EDGE, pct(edge, 1, True)) + '</div>'
        '<dl class="facts">'
        f'<div><dt>Gap to next</dt><dd>{pct(g, 1)}</dd></div>'
        f'<div><dt>Edge (prop.)</dt><dd>{pct(edge_m, 1, True)}</dd></div>'
        f'<div><dt>Depth</dt><dd>{"–" if dep is None else f"${dep:,.0f}"}</dd></div>'
        f'<div><dt>Pinn. move</dt><dd>{mv_html}</dd></div></dl>'
        f'<footer>Kickoff {esc(fmt_dt(starts) if starts else "–")} ET</footer></article>')


def outliers_overview(cur: pl.DataFrame, fmt_dt: Callable[[str], str]) -> str:
    """Tiles, venue split and the card grid for the newest poll's qualifying sides."""
    rows = [r for r in cur.sort("edge_power", descending=True).to_dicts() if _f(r.get("best_cost")) is not None]
    if not rows:
        return ""
    edges = [e for e in (_f(r.get("edge_power")) for r in rows) if e is not None]
    gaps = [e for e in (_f(r.get("gap_next")) for r in rows) if e is not None]
    by_v: dict[str, int] = {}
    for r in rows:
        by_v[r["venue"]] = by_v.get(r["venue"], 0) + 1
    groups = sorted({group_of(str(r["kind"])) for r in rows})
    tiles = (
        '<div class="otiles">'
        f'<div class="otile"><span class="k">Sides now</span><span class="v">{len(rows)}</span></div>'
        f'<div class="otile"><span class="k">Largest edge</span><span class="v">{pct(max(edges), 1, True) if edges else "–"}</span></div>'
        f'<div class="otile"><span class="k">Mean edge</span><span class="v">{pct(sum(edges) / len(edges), 1, True) if edges else "–"}</span></div>'
        f'<div class="otile"><span class="k">Mean gap to next</span><span class="v">{pct(sum(gaps) / len(gaps), 1) if gaps else "–"}</span></div></div>')
    seg = "".join(f'<span class="seg" style="flex:{n};--vc:var({VENUE_VAR.get(v, "--muted")})" title="{esc(v)}: {n}"></span>'
                  for v, n in sorted(by_v.items(), key=lambda kv: -kv[1]))
    leg = "".join(f'<span>{venue_chip(v)} {n}</span>' for v, n in sorted(by_v.items(), key=lambda kv: -kv[1]))
    split = ('<div class="card"><h3>Where the best price sits</h3>'
             f'<div class="vbar" role="img" aria-label="{esc(", ".join(f"{v} {n}" for v, n in by_v.items()))}">{seg}</div>'
             f'<div class="vleg">{leg}</div></div>')
    chips = ('<div class="filters" role="group" aria-label="Market filter"><button type="button" data-og="all" aria-pressed="true">All</button>'
             + "".join(f'<button type="button" data-og="{esc(g)}" aria-pressed="false">{esc(g)}</button>' for g in groups) + '</div>')
    sorter = ('<label class="osort">Sort <select id="osort"><option value="edge">Biggest edge</option>'
              '<option value="gap">Biggest gap to next</option><option value="start">Kickoff</option></select></label>')
    cards = "".join(outlier_card(r, fmt_dt) for r in rows)
    return (tiles + split + f'<div class="octl">{chips}{sorter}<span class="tcount" id="ocount" aria-live="polite"></span></div>'
            f'<div class="ogrid" id="ogrid">{cards}</div>')


def clv_status(s: dict) -> str:
    """Donut of recorded outliers by status plus tiles; every segment is also written in the legend."""
    parts = [("Graded", s.get("graded", 0), "--c3"), ("No close", s.get("no_close", 0), "--c2"), ("Waiting for kickoff", s.get("open", 0), "--c1")]
    total = sum(n for _, n, _ in parts) or 1
    r, circ, off, arcs = 42, 2 * 3.14159265 * 42, 0.0, ""
    for name, n, var in parts:
        if not n:
            continue
        ln = n / total * circ
        arcs += (f'<circle cx="60" cy="60" r="{r}" fill="none" stroke="var({var})" stroke-width="16" stroke-dasharray="{ln:.2f} {circ - ln:.2f}" '
                 f'stroke-dashoffset="{-off:.2f}" transform="rotate(-90 60 60)"><title>{esc(name)}: {n}</title></circle>')
        off += ln
    leg = "".join(f'<li><i style="background:var({v})"></i><span>{esc(n)}</span><b>{c:,}</b></li>' for n, c, v in parts)
    text = ", ".join(f"{n} {c}" for n, c, _ in parts)
    return (f'<div class="donutwrap"><svg viewBox="0 0 120 120" role="img" aria-label="Recorded outliers: {esc(text)}">{arcs}'
            f'<text x="60" y="58" text-anchor="middle" class="dnum">{s.get("recorded", 0):,}</text>'
            '<text x="60" y="74" text-anchor="middle" class="dlab">recorded</text></svg>'
            f'<ul class="dleg">{leg}</ul></div>')


# ------------------------------------------------------------------------------------------------ engine

def both_keys(df: pl.DataFrame) -> set:
    """(player_id, market, line, side) that both engines have in the same pre-game view."""
    if not df.height or df["engine"].n_unique() < 2:
        return set()
    k = [side_key_col(df), "market", "line", "side"]
    sets = [set(map(tuple, df.filter(pl.col("engine") == e).select(k).rows())) for e in df["engine"].unique().to_list()]
    return set.intersection(*sets)


def side_key_col(df: pl.DataFrame) -> str:
    return "player_id" if "player_id" in df.columns else "player"


def bar_cell(value: float | None, lo: float, hi: float, text: str, cls: str = "") -> str:
    if value is None:
        return '<span class="muted">–</span>'
    w = max(0.0, min((value - lo) / ((hi - lo) or 1.0), 1.0)) * 100
    return f'<span class="cbar {cls}"><span class="ct"><i style="width:{w:.0f}%"></i></span><span class="cv">{esc(text)}</span></span>'


def histogram(edges: dict[str, list[float]], names: dict[str, str]) -> str:
    """Grouped bars of edge by bucket, one color per engine; counts are written on the bars and in the label."""
    labels = [f"{a * 100:.0f}-{b * 100:.0f}%" for a, b in zip(BINS, BINS[1:])] + [f"{BINS[-1] * 100:.0f}%+"]
    counts: dict[str, list[int]] = {}
    for e, vals in edges.items():
        c = [0] * len(BINS)
        for v in vals:
            i = max(i for i, b in enumerate(BINS) if v >= b - 1e-12) if v >= BINS[0] - 1e-12 else None
            if i is not None:
                c[i] += 1
        counts[e] = c
    top = max([n for c in counts.values() for n in c] + [1])
    cols = ""
    for i, lab in enumerate(labels):
        bars = "".join(
            f'<span class="hb e{j % 2}" style="height:{counts[e][i] / top * 100:.1f}%" title="{esc(names.get(e, e))}: {counts[e][i]}">'
            f'<em>{counts[e][i]}</em></span>' for j, e in enumerate(sorted(counts)))
        cols += f'<div class="hcol"><div class="hbars">{bars}</div><span class="hl">{esc(lab)}</span></div>'
    leg = "".join(f'<span><i class="e{j % 2}"></i>{esc(names.get(e, e))}</span>' for j, e in enumerate(sorted(counts)))
    text = "; ".join(f"{names.get(e, e)}: " + ", ".join(f"{l} {n}" for l, n in zip(labels, c)) for e, c in sorted(counts.items()))
    return (f'<div class="card"><h3>How big are the edges?</h3><p class="note" style="margin-top:2px">Sides per edge bucket at the latest '
            f'recorded Novig book.</p><div class="hist" role="img" aria-label="{esc(text)}">{cols}</div><div class="vleg">{leg}</div></div>')


def market_mix(df: pl.DataFrame, names: dict[str, str], labels: dict[str, str]) -> str:
    mk = sorted(df["market"].unique().to_list())
    var = {m: f"--c{i + 1}" if i < 5 else "--muted" for i, m in enumerate(mk)}
    rows = ""
    for e in sorted(df["engine"].unique().to_list()):
        d = df.filter(pl.col("engine") == e)
        segs = "".join(f'<span class="seg" style="flex:{n};--vc:var({var[m]})" title="{esc(labels.get(m, m))}: {n}">{n}</span>'
                       for m in mk if (n := d.filter(pl.col("market") == m).height))
        rows += f'<div class="mrow"><span class="mname">{esc(names.get(e, e))}</span><div class="vbar">{segs}</div></div>'
    leg = "".join(f'<span><i style="background:var({var[m]})"></i>{esc(labels.get(m, m))}</span>' for m in mk)
    return f'<div class="card"><h3>What they are betting on</h3>{rows}<div class="vleg">{leg}</div></div>'


def engine_overview(df: pl.DataFrame, names: dict[str, str], labels: dict[str, str], run_label: str = "") -> str:
    """Tiles per engine, both-engine agreement, edge histogram and market mix for the pre-game view."""
    if not df.height:
        return ""
    d = df.with_columns(pl.col("edge").cast(pl.Float64))
    both = both_keys(d)
    engines = sorted(d["engine"].unique().to_list())
    tiles = ""
    for e in engines:
        x = d.filter(pl.col("engine") == e)
        tiles += (f'<div class="otile eng"><span class="k">{esc(names.get(e, e))}</span><span class="v">{x.height:,}</span>'
                  f'<span class="s">sides · mean edge {x["edge"].mean():.3f} · top {x["edge"].max():.3f}</span></div>')
    if len(engines) > 1:
        tiles += (f'<div class="otile glow"><span class="k">Both engines agree</span><span class="v">{len(both):,}</span>'
                  '<span class="s">same player, market, line and side</span></div>')
    edges = {e: d.filter(pl.col("engine") == e)["edge"].to_list() for e in engines}
    return (f'<div class="otiles">{tiles}</div><div class="grid2">{histogram(edges, names)}{market_mix(d, names, labels)}</div>')


CSS = """
/* ---- engine and outlier visuals */
.otiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.otile{position:relative;background:linear-gradient(160deg,var(--raised),var(--surface));border:1px solid var(--line);border-radius:10px;padding:12px 14px;
  display:flex;flex-direction:column;gap:2px;overflow:hidden}
.otile::after{content:"";position:absolute;right:-30px;top:-30px;width:90px;height:90px;border-radius:50%;
  background:radial-gradient(circle,color-mix(in srgb,var(--accent) 30%,transparent),transparent 70%)}
.otile .k{font:600 12px var(--display);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.otile .v{font:600 30px/1.1 var(--mono);font-variant-numeric:tabular-nums}
.otile .s{font:12px var(--mono);color:var(--muted)}
.otile.glow{border-color:color-mix(in srgb,var(--c3) 60%,var(--line));box-shadow:0 0 22px -8px var(--c3)}
.vchip{display:inline-flex;align-items:center;gap:6px;font:600 12px var(--display);letter-spacing:.06em;text-transform:uppercase;padding:2px 9px;border-radius:999px;
  border:1px solid color-mix(in srgb,var(--vc) 65%,var(--line));background:color-mix(in srgb,var(--vc) 14%,transparent);color:var(--ink)}
.vchip::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--vc)}
.vbar{display:flex;height:22px;border-radius:6px;overflow:hidden;gap:2px;margin:8px 0}
.vbar .seg{background:var(--vc);display:flex;align-items:center;justify-content:center;font:600 11px var(--mono);color:#0b1117;min-width:6px}
.vleg{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12.5px;color:var(--ink2)}
.vleg span{display:inline-flex;align-items:center;gap:6px}.vleg i{width:10px;height:10px;border-radius:3px;display:inline-block}
.mrow{display:grid;grid-template-columns:minmax(110px,150px) 1fr;align-items:center;gap:10px}.mname{font-size:13px;color:var(--ink2)}
.octl{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.osort{font:600 12px var(--display);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);display:inline-flex;gap:8px;align-items:center}
.osort select{font:500 14px var(--body);text-transform:none;letter-spacing:0;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:5px;padding:5px 9px;min-height:32px}
.ogrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,330px),1fr));gap:14px}
.ocard{position:relative;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:8px;overflow:hidden}
.ocard::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:linear-gradient(90deg,var(--c3),var(--accent))}
.ocard header{display:flex;justify-content:space-between;align-items:center;gap:8px}
.ocard .kind{font:600 12px var(--display);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.ocard h4{margin:0;font:600 19px/1.2 var(--display);letter-spacing:.01em}
.ocard .ogame{margin:0;font-size:13px;color:var(--ink2)}
.price{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.pbig{font:600 34px/1 var(--mono);font-variant-numeric:tabular-nums;color:var(--ink);text-shadow:0 0 18px color-mix(in srgb,var(--accent) 45%,transparent)}
.psub{font-size:12.5px;color:var(--muted)}
.ladder{margin-top:2px}
.lrail{position:relative;height:26px;margin:4px 6px 0}
.lrail::before{content:"";position:absolute;left:0;right:0;top:12px;height:2px;background:var(--line);border-radius:1px}
.zone{position:absolute;top:8px;height:10px;border-radius:5px;background:linear-gradient(90deg,color-mix(in srgb,var(--c3) 70%,transparent),color-mix(in srgb,var(--c3) 15%,transparent))}
.mk{position:absolute;top:6px;width:14px;height:14px;margin-left:-7px;box-sizing:border-box}
.mk.best{border-radius:50%;background:var(--accent);border:2px solid var(--ink);box-shadow:0 0 12px var(--accent);z-index:2}
.mk.next{border-radius:50%;background:var(--surface);border:2px solid var(--muted)}
.mk.fair{background:var(--c2);transform:rotate(45deg) scale(.8);border-radius:2px;border:2px solid var(--surface)}
.lax{display:flex;justify-content:space-between;font:11px var(--mono);color:var(--muted);margin:2px 6px 0}
.erow{display:grid;grid-template-columns:auto 1fr;gap:10px;align-items:center}.elab{font-size:12px;color:var(--ink2)}
.emeter{display:flex;align-items:center;gap:8px}
.etrack{position:relative;flex:1;min-width:70px;height:9px;border-radius:5px;background:var(--idle-bg)}
.etrack i{position:absolute;left:0;top:0;bottom:0;border-radius:5px;background:linear-gradient(90deg,var(--accent),var(--c3));box-shadow:0 0 8px color-mix(in srgb,var(--c3) 55%,transparent)}
.etrack i.lo{background:var(--muted);box-shadow:none}
.etrack b{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink);border-radius:1px}
.ev{font:600 13px var(--mono);min-width:54px;text-align:right}
.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:0}
.facts div{background:color-mix(in srgb,var(--ink) 4%,transparent);border-radius:6px;padding:5px 7px}
.facts dt{font:600 10.5px var(--display);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.facts dd{margin:0;font:600 13px var(--mono);font-variant-numeric:tabular-nums}
.facts dd{white-space:nowrap}.mv.up{color:var(--good)}.mv.dn{color:var(--bad)}
.ocard footer{font:12px var(--mono);color:var(--muted)}
@media (max-width:420px){.facts{grid-template-columns:repeat(2,1fr)}}
.donutwrap{display:flex;flex-wrap:wrap;align-items:center;gap:14px 26px}
.donutwrap svg{width:150px;height:150px;flex:none}
.dnum{font:600 22px var(--mono);fill:var(--ink)}.dlab{font:600 9px var(--display);letter-spacing:.1em;text-transform:uppercase;fill:var(--muted)}
.dleg{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px;font-size:14px}
.dleg li{display:flex;align-items:center;gap:8px}.dleg i{width:12px;height:12px;border-radius:3px}.dleg b{font:600 14px var(--mono);margin-left:6px}
.hist{display:flex;gap:8px;align-items:flex-end;height:170px;margin-top:10px;padding-top:6px;border-bottom:1px solid var(--line)}
.hcol{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;min-width:0}
.hbars{display:flex;align-items:flex-end;gap:3px;height:calc(100% - 20px);width:100%;justify-content:center}
.hb{position:relative;flex:1;max-width:26px;min-height:2px;border-radius:4px 4px 0 0}
.hb em{position:absolute;top:-16px;left:50%;transform:translateX(-50%);font:600 11px var(--mono);font-style:normal;color:var(--ink2)}
.hb.e0,.vleg i.e0{background:var(--c1)}.hb.e1,.vleg i.e1{background:var(--c2)}
.hl{font:10.5px var(--mono);color:var(--muted);margin-top:4px;white-space:nowrap}
.cbar{display:flex;align-items:center;gap:8px}.ct{display:block;width:70px;height:7px;border-radius:4px;background:var(--idle-bg);flex:none}
.ct i{display:block;height:100%;border-radius:4px;background:linear-gradient(90deg,var(--accent),var(--c3))}.cv{font:13px var(--mono);min-width:44px;text-align:right}
.bothchip{margin-left:6px;font:600 10.5px var(--display);letter-spacing:.06em;text-transform:uppercase;padding:1px 6px;border-radius:999px;
  background:color-mix(in srgb,var(--c3) 20%,transparent);color:var(--ink);border:1px solid color-mix(in srgb,var(--c3) 60%,var(--line))}
.waiting{display:flex;gap:14px;align-items:center;background:var(--surface);border:1px dashed var(--line);border-radius:10px;padding:16px 18px;color:var(--ink2)}
.waiting::before{content:"";width:12px;height:12px;border-radius:50%;background:var(--accent);flex:none}
details.tview{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:10px 14px}
details.tview summary{font:600 15px var(--display);letter-spacing:.05em;text-transform:uppercase;color:var(--ink2)}
@media (prefers-reduced-motion:no-preference){
  .waiting::before{animation:fxpulse 1.8s ease-out infinite;color:var(--accent)}
  .ocard{transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}
  .ocard:hover{transform:translateY(-3px);border-color:color-mix(in srgb,var(--accent) 55%,var(--line));box-shadow:0 14px 30px -16px color-mix(in srgb,var(--accent) 70%,transparent)}
  .hb{animation:fxrisey .7s cubic-bezier(.2,.8,.2,1);transform-origin:bottom}.vbar .seg{animation:fxfill .8s cubic-bezier(.2,.8,.2,1)}
  .donutwrap circle{animation:fxreveal 1s ease-out}
  .etrack i,.ct i{animation:fxfill .9s cubic-bezier(.2,.8,.2,1)}
  @keyframes fxrisey{from{transform:scaleY(0)}}
}
"""

JS = r"""
(function(){
  var grid=document.getElementById('ogrid');if(!grid)return;
  var cards=[].slice.call(grid.children),btns=document.querySelectorAll('button[data-og]'),sel=document.getElementById('osort'),cnt=document.getElementById('ocount');
  var group='all';
  function apply(){
    var n=0;cards.forEach(function(c){var ok=group==='all'||c.getAttribute('data-group')===group;c.hidden=!ok;if(ok)n++});
    var key=sel.value,list=cards.slice().sort(function(a,b){
      if(key==='start')return(a.getAttribute('data-start')||'').localeCompare(b.getAttribute('data-start')||'');
      return parseFloat(b.getAttribute('data-'+key))-parseFloat(a.getAttribute('data-'+key))});
    list.forEach(function(c){grid.appendChild(c)});
    btns.forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-og')===group?'true':'false')});
    cnt.textContent=n+' of '+cards.length+' sides';
  }
  btns.forEach(function(b){b.addEventListener('click',function(){group=b.getAttribute('data-og');apply()})});
  sel.addEventListener('change',apply);apply();
})();
"""
