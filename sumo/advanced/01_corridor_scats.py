"""
ADVANCED 1 - Full SCATS on a four-intersection arterial
=======================================================
J1 - J2 | J3 - J4      (300 m spacing, 3 phases: A main road, B main-road
 SS1    |  SS2          protected right/left turn (demand dependent), C side)

Concepts exercised in one run:
  * stop-line DS and VK on every lane, on-line MF learning
  * cycle length from the critical intersection (CI) with bounded steps,
    LMIN / LMAX and the stretch phase
  * split-plan selection by DS equalisation, 2-of-3 voting
  * offset plans (inbound / outbound / simultaneous / alternate),
    4-of-5 voting from directional VK
  * marriage / divorce of SS1 and SS2 from link VK with hysteresis
  * tactical: minimum greens, gap-out, demand-dependent phase skipping,
    coordinated phase hold
  * public transport priority (medium level: extension / early start)

Demand: low -> eastbound AM peak -> westbound PM peak -> low.

    python advanced/01_corridor_scats.py
    python advanced/01_corridor_scats.py --gui
Outputs: results/advanced/{summary.csv, compare.png, strategic_timeline.png,
         cycles_*.csv, strategic_*.json}
"""
import _path  # noqa: F401
import os

from scats import cli, plots
from scats.runner import mode_config, run
from scats.scenarios import advanced


def main():
    args = cli.parser(__doc__).parse_args()
    out = cli.outdir(args, "advanced")
    scn = advanced(args.end or 5400)
    results = [
        run(scn, mode_config("fixed"), "fixed", out, seed=args.seed),
        run(scn, mode_config("actuated"), "actuated", out, seed=args.seed),
        run(scn, mode_config("scats", bus_priority=True), "scats", out, seed=args.seed, gui=args.gui),
    ]
    cli.write_summary(results, os.path.join(out, "summary.csv"))
    plots.compare_bars(results, os.path.join(out, "compare.png"), "Arterial corridor - 90 minutes, tidal peaks")
    plots.strategic_timeline(results[-1]["_log"], results[-1]["_intersections"],
                             os.path.join(out, "strategic_timeline.png"),
                             "SCATS strategic decisions (cycle, DS, offsets, marriage, splits)")
    print("\nStrategic log (SS1, every 5th master cycle):")
    for e in [e for e in results[-1]["_log"] if e["ss"] == "SS1"][::5]:
        print(f"  t={e['t']:6.0f}s  C={e['C']:5.1f}  DS_CI={e['ds_ci']:.2f}  "
              f"offset plan=OP{e['offset_plan'] + 1}  VK E/W={e['vk_east']}/{e['vk_west']}  married={e['married']}")
    print(f"\nFigures and CSVs in {out}")


if __name__ == "__main__":
    main()
