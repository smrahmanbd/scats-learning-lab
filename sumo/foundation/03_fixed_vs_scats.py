"""
FOUNDATION 3 - Fixed time vs vehicle actuated vs SCATS (single intersection)
============================================================================
Same demand (off-peak -> peak -> off-peak), three controllers:

  fixed     : one 90 s plan all hour, no detectors used
  actuated  : gap-out on stop-line loops, fixed maximum greens (isolated)
  scats     : tactical gap-out + strategic cycle-length and split adaptation

Produces results/foundation/:
  summary.csv, compare.png, ds_by_phase.png, cycles_<mode>.csv

    python foundation/03_fixed_vs_scats.py            (headless)
    python foundation/03_fixed_vs_scats.py --gui      (watch the SCATS run)
"""
import _path  # noqa: F401
import os

from scats import cli, plots
from scats.runner import mode_config, run
from scats.scenarios import foundation


def main():
    args = cli.parser(__doc__).parse_args()
    out = cli.outdir(args, "foundation")
    scn = foundation(args.end or 3600)
    results = []
    for mode in ("fixed", "actuated", "scats"):
        results.append(run(scn, mode_config(mode), mode, out, seed=args.seed,
                           gui=args.gui and mode == "scats"))
    cli.write_summary(results, os.path.join(out, "summary.csv"))
    plots.compare_bars(results, os.path.join(out, "compare.png"), "Single intersection - one hour, peak in the middle")
    plots.ds_by_phase(results[-1]["_intersections"][0], os.path.join(out, "ds_by_phase.png"),
                      "SCATS: cycle length and greens follow the measured DS")
    print(f"\nFigures and CSVs in {out}")


if __name__ == "__main__":
    main()
