"""
MASTERY 1 - Connected-vehicle (CV) degree of saturation
========================================================
Research question: can SCATS run on probe / connected-vehicle data instead
of (or alongside) stop-line loops, and how much penetration is needed?

Estimator (simple, transparent baseline - extend it!):
    n_hat  = n_CV / p                      (scale CVs by penetration p)
    g'_hat = n_hat * 3600 / MF             (green a saturated stream would need)
    DS_CV  = g'_hat / g

Part A - accuracy: in a loop-driven run, compare DS_CV with DS_loop for every
         lane-cycle at several penetration rates (same vehicles, shadow mode).
Part B - control:  drive SCATS with DS_CV at each penetration and measure delay.

Ideas to go further: use CV queue-join positions (shockwave theory) to see
demand that has *not* crossed the stop line; Bayesian fusion of loop + CV;
penetration-rate estimation when p is unknown.

    python mastery/01_cv_ds_estimation.py
"""
import _path  # noqa: F401
import os
import statistics

from scats import cli, plots
from scats.controller import is_cv
from scats.runner import mode_config, run
from scats.scenarios import advanced

PENETRATIONS = [0.05, 0.1, 0.25, 0.5, 1.0]


def main():
    args = cli.parser(__doc__).parse_args()
    out = cli.outdir(args, "mastery/cv_ds")
    end = args.end or 5400

    # Part A: shadow accuracy from a loop-controlled run
    base = run(advanced(end), mode_config("scats", bus_priority=True), "loop_DS", out, seed=args.seed)
    # Every lane-cycle stores the IDs of the vehicles that crossed the stop line,
    # so we can replay the CV estimator for any penetration rate on the same traffic.
    print("\nPart A - DS estimation error (shadow mode, same traffic)")
    acc_rows = {}
    for p in PENETRATIONS:
        e = []
        for ix in base["_intersections"]:
            for r in ix.history:
                for m in r["lanes"].values():
                    if m["g"] <= 0 or m["ds_loop"] < 0.2:
                        continue
                    n_cv = sum(1 for v in m["ids"] if is_cv(v, p))
                    ds_cv = (n_cv / p) * 3600.0 / m["mf"] / m["g"]
                    e.append(abs(ds_cv - m["ds_loop"]))
        acc_rows[p] = statistics.mean(e)
        print(f"  p={p:4.2f}  mean |DS_CV - DS_loop| = {acc_rows[p]:.3f}  (lane-cycles: {len(e)})")

    # Part B: closed loop control with CV DS
    print("\nPart B - SCATS driven by CV-estimated DS")
    delays = {}
    results = [base]
    for p in PENETRATIONS:
        res = run(advanced(end), mode_config("scats", bus_priority=True, cv_penetration=p, ds_source="cv"),
                  f"cv_p{p}", out, seed=args.seed)
        delays[p] = res["avg_delay"]
        results.append(res)
    cli.write_summary(results, os.path.join(out, "cv_control.csv"))
    plots.line_compare(PENETRATIONS, {"mean |DS_CV - DS_loop|": [acc_rows[p] for p in PENETRATIONS]},
                       os.path.join(out, "cv_accuracy.png"), "CV-based DS estimation error",
                       "CV penetration rate", "Mean absolute DS error")
    plots.line_compare(PENETRATIONS, {"SCATS on CV DS": [delays[p] for p in PENETRATIONS],
                                      "SCATS on loops": [base["avg_delay"]] * len(PENETRATIONS)},
                       os.path.join(out, "cv_delay.png"), "Network delay vs CV penetration",
                       "CV penetration rate", "Mean delay (s/veh)")
    print(f"\nResults in {out}")


if __name__ == "__main__":
    main()
