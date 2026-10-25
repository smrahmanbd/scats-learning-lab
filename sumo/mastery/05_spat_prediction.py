"""
MASTERY 5 - Predicting SPaT (time-to-change) for an adaptive controller
=======================================================================
Research question: connected-vehicle apps (green-light speed advice, eco-
driving, automated vehicles) need Signal Phase and Timing (SPaT) - *when*
will this green end? Fixed-time signals make that trivial; SCATS adapts
every cycle and gaps out, so the end of green is uncertain.

We log every green of every phase on the SCATS corridor and evaluate, at the
moment the green starts, three predictors of its duration:

  P1 planned      : the green allocated by the current split plan + carry-over
  P2 persistence  : the same phase's actual green in the previous cycle
  P3 regression   : least-squares fit  g = a*planned + b*DS_prev + c
                    (trained on the first half, tested on the second half)

    python mastery/05_spat_prediction.py
Extend: quantile / probabilistic predictions (give apps a confidence band),
gradient boosting with detector states, online learning.
"""
import _path  # noqa: F401
import os
import statistics

import numpy as np

from scats import cli, plots
from scats.runner import mode_config, run
from scats.scenarios import advanced


def main():
    args = cli.parser(__doc__).parse_args()
    out = cli.outdir(args, "mastery/spat")
    res = run(advanced(args.end or 5400), mode_config("scats", bus_priority=True), "scats", out, seed=args.seed)
    X, y, persist = [], [], []
    for ix in res["_intersections"]:
        prev = None
        for rec in ix.history:
            for p in ix.names:
                if p in rec["skipped"]:
                    continue
                if prev is not None and p not in prev["skipped"]:
                    X.append([rec["planned"][p], prev["ds"][p], 1.0])
                    y.append(rec["g"][p])
                    persist.append(prev["g"][p])
            prev = rec
    X, y, persist = np.array(X), np.array(y), np.array(persist)
    half = len(y) // 2
    coef, *_ = np.linalg.lstsq(X[:half], y[:half], rcond=None)
    test = slice(half, None)
    mae = {
        "P1 planned": float(np.mean(np.abs(X[test, 0] - y[test]))),
        "P2 persistence": float(np.mean(np.abs(persist[test] - y[test]))),
        "P3 regression": float(np.mean(np.abs(X[test] @ coef - y[test]))),
    }
    print(f"\nGreens evaluated (test half): {len(y) - half}")
    for k, v in mae.items():
        print(f"  {k:<16} MAE = {v:5.2f} s")
    print(f"  regression: g = {coef[0]:.2f}*planned + {coef[1]:.1f}*DS_prev + {coef[2]:.1f}")
    import csv
    with open(os.path.join(out, "spat_mae.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["predictor", "mae_s"])
        for k, v in mae.items():
            w.writerow([k, round(v, 3)])
    plots.line_compare(list(range(3)), {"MAE (s)": list(mae.values())}, os.path.join(out, "spat_mae.png"),
                       "Green-duration prediction error (0=planned, 1=persistence, 2=regression)",
                       "Predictor", "Mean absolute error (s)")


if __name__ == "__main__":
    main()
