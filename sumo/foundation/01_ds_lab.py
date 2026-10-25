"""
FOUNDATION 1 - Degree of Saturation lab
=======================================
Runs a single SCATS-controlled intersection and, for a chosen stop-line
detector, prints the full DS calculation for each cycle:

    wasted green = T - n*h
    g'  (used)   = g - wasted
    DS           = g' / g
    VK           = DS * g * MF / 3600

Try:  python foundation/01_ds_lab.py --lane W_J1_1 --cycles 12
      python foundation/01_ds_lab.py --h 1.2      (what happens if h is wrong?)
"""
import _path  # noqa: F401
import csv
import os

from scats import cli
from scats.runner import mode_config, run
from scats.scenarios import foundation


def main():
    p = cli.parser(__doc__)
    p.add_argument("--lane", default="W_J1_1", help="incoming lane whose loop to inspect")
    p.add_argument("--cycles", type=int, default=15)
    p.add_argument("--h", type=float, default=1.6, help="standard space time h (s)")
    args = p.parse_args()
    out = cli.outdir(args, "foundation")
    scn = foundation(args.end or 3600)
    res = run(scn, mode_config("scats", space_time_h=args.h), "ds_lab", out, seed=args.seed, gui=args.gui)
    ix = res["_intersections"][0]

    rows = []
    print(f"\nDS walkthrough for loop on lane {args.lane}  (h = {args.h}s)\n")
    print(f"{'time':>6} {'g':>5} {'T':>6} {'n':>3} {'n*h':>6} {'wasted':>7} {'g_used':>7} {'DS':>5} {'VK':>5}")
    for rec in ix.history:
        m = rec["lanes"].get(args.lane)
        if not m:
            continue
        wasted = m["T"] - m["n"] * args.h
        row = dict(t=rec["t"], g=m["g"], T=round(m["T"], 2), n=m["n"], nh=round(m["n"] * args.h, 2),
                   wasted=round(wasted, 2), g_used=round(m["g"] - wasted, 2), DS=round(m["ds"], 3),
                   VK=round(m["vk"], 2))
        rows.append(row)
    step = max(1, len(rows) // args.cycles)
    for r in rows[::step][: args.cycles]:
        print(f"{r['t']:6.0f} {r['g']:5.0f} {r['T']:6.1f} {r['n']:3d} {r['nh']:6.1f} {r['wasted']:7.1f} "
              f"{r['g_used']:7.1f} {r['DS']:5.2f} {r['VK']:5.1f}")
    path = os.path.join(out, f"ds_lab_{args.lane}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nAll {len(rows)} cycles written to {path}")
    print("Exercise: compare DS in the peak (min 20-40) with off-peak. Why does DS rise\n"
          "even though green time also rises? (Hint: SCATS lengthens the cycle only\n"
          "until DS reaches the target - see 03_fixed_vs_scats.py.)")


if __name__ == "__main__":
    main()
