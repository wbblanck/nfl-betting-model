"""Post-hoc diagnostic for docs/signals_report.md (not pre-registered): MSE, a level-only control (the same average
factor for every row) and, for A and D, the same factor applied to rows without the signal."""
import sys; sys.path.insert(0,'scripts')
import numpy as np, polars as pl, signals_eval as E
from nflbet.props import signals as S
rows=E.base(); fr,_=E.signal_frames(rows)
for name,key,markets in E.TESTS:
    f=fr[key].filter(pl.col("market").is_in(markets), pl.col("x").is_not_null())
    k=S.fit_k(f.filter(pl.col("season").is_in(E.TRAIN)), S.GRIDS[key])
    c=f.filter(pl.col("season").is_in(E.CONFIRM))
    for m in markets:
        z=c.filter(pl.col("market")==m)
        if key in("qb","wind"):
            other=z.filter(pl.col("x")==0); z=z.filter(pl.col("x")>0)
        p,y,x=z["proj"].to_numpy(),z["actual"].to_numpy(),z["x"].to_numpy()
        adj=p*np.exp(k[m]*x); lvl=p*np.exp(k[m]*x.mean())
        line=f"{name}:{m} k={k[m]:+g} mean_x={x.mean():+.3f} | MSE cur {np.mean((p-y)**2):.2f} adj {np.mean((adj-y)**2):.2f} | MAE cur {np.mean(abs(p-y)):.3f} adj {np.mean(abs(adj-y)):.3f} level-only {np.mean(abs(lvl-y)):.3f}"
        if key in("qb","wind"):
            po,yo=other["proj"].to_numpy(),other["actual"].to_numpy(); f2=np.exp(k[m]*x.mean())
            line+=f" | same factor on x=0 rows: MAE {np.mean(abs(po-yo)):.3f} -> {np.mean(abs(po*f2-yo)):.3f}, MSE {np.mean((po-yo)**2):.2f} -> {np.mean((po*f2-yo)**2):.2f}"
        print(line)
