"""
FOUNDATION 2 - Calibrating the standard space time h
=====================================================
DS is only meaningful if h (the unoccupied time between two vehicles that
discharge at saturation flow) matches your detectors and traffic.

This script overloads one intersection under a fixed plan so the main road
queue never clears, then measures T/n (unoccupied time per vehicle) during
the saturated greens. The median is your h. The same run also gives the
saturation flow MF = 3600 * n / g.

    python foundation/02_calibrate_h.py
"""
import _path  # noqa: F401
import statistics

from scats import cli
from scats.runner import Scenario, mode_config, run


def main():
    args = cli.parser(__doc__).parse_args()
    out = cli.outdir(args, "foundation")
    end = args.end or 1200
    scn = Scenario("calibrate", n=1, phase_set="two",
                   periods=[dict(begin=0, end=end, east=2800, west=2800, side=300, turn=0)], end=end)
    res = run(scn, mode_config("fixed"), "calibrate_h", out, seed=args.seed, gui=args.gui)
    ix = res["_intersections"][0]
    space, flows = [], []
    for rec in ix.history[3:]:                      # skip warm-up
        for lane, m in rec["lanes"].items():
            if lane.startswith(("W_", "E_")) and m["n"] >= 0.4 * m["g"]:   # saturated arterial lanes (~>1440 veh/h)
                space.append(m["T"] / m["n"])
                flows.append(3600 * m["n"] / m["g"])
    h = statistics.median(space)
    mf = statistics.median(flows)
    print(f"\nSaturated green windows analysed : {len(space)}")
    print(f"Median unoccupied time per vehicle: h  = {h:.2f} s")
    print(f"Median discharge rate             : MF = {mf:.0f} veh/h of green")
    print("\nUse this h in ControllerConfig(space_time_h=...). With the correct h a\n"
          "saturated green gives DS close to 1.0; too small an h under-estimates DS\n"
          "(SCATS would then shorten the cycle while queues grow).")


if __name__ == "__main__":
    main()
