"""
MASTERY 4 - Detector-fault resilience
=====================================
Research question: SCATS depends on stop-line loops. Real networks always
have some faulty detectors. How much does performance degrade, and which
fault-handling strategy recovers it?

At t = 20 min a random 30% of loops fail - half 'stuck-off' (never detect),
half 'stuck-on' (permanently occupied, no counts). Four runs:

  healthy   : no faults (reference)
  none      : faults, data used naively
  exclude   : SCATS-style detector alarms - implausible loops (no counts for
              6 greens, or ~100% occupancy for 2 greens) are excluded from DS
              and from gap-out decisions
  impute    : as 'exclude' but the faulty lane's DS is replaced by its own
              smoothed history (temporal imputation)

    python mastery/04_detector_faults.py --fail-share 0.3
"""
import _path  # noqa: F401
import os
import random

from scats import cli, plots
from scats.runner import mode_config, run
from scats.scenarios import advanced


def make_fault_filter(share, t_fail, seed):
    rng = random.Random(seed)
    decided = {}

    def filt(lane, occ, ids, t):
        if t < t_fail:
            return occ, ids
        if lane not in decided:
            r = rng.random()
            decided[lane] = "off" if r < share / 2 else "on" if r < share else "ok"
        mode = decided[lane]
        if mode == "off":
            return 0.0, ()
        if mode == "on":
            return 100.0, ()
        return occ, ids
    filt.decided = decided
    return filt


def main():
    p = cli.parser(__doc__)
    p.add_argument("--fail-share", type=float, default=0.3)
    args = p.parse_args()
    out = cli.outdir(args, "mastery/faults")
    end = args.end or 5400
    results = [run(advanced(end), mode_config("scats", bus_priority=True), "healthy", out, seed=args.seed)]
    for strategy in ("none", "exclude", "impute"):
        f = make_fault_filter(args.fail_share, 1200, seed=42)
        res = run(advanced(end), mode_config("scats", bus_priority=True, sensor_filter=f,
                                             fault_handling=strategy), f"faults_{strategy}", out, seed=args.seed)
        res["failed_loops"] = sum(1 for v in f.decided.values() if v != "ok")
        results.append(res)
    cli.write_summary(results, os.path.join(out, "faults.csv"))
    plots.compare_bars(results, os.path.join(out, "faults.png"),
                       f"{int(args.fail_share * 100)}% of loops fail at t=20 min")
    print(f"\nResults in {out}")


if __name__ == "__main__":
    main()
