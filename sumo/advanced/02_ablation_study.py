"""
ADVANCED 2 - Ablation study: which SCATS mechanism earns its keep?
==================================================================
Switch SCATS mechanisms off one at a time on the advanced corridor and
measure the damage. This is the best way to *understand* each concept:

  full               everything on
  no_cycle_adapt     cycle length frozen at the initial value
  no_split_adapt     split plan frozen
  no_offset_adapt    offset plan frozen (OP3 simultaneous)
  no_marriage        SS1 and SS2 always run independently
  no_tactical        no gap-out / phase skipping (strategic only)
  no_bus_priority    PT priority off

    python advanced/02_ablation_study.py            (~1.5 min)
"""
import _path  # noqa: F401
import dataclasses
import os

from scats import cli, plots
from scats.runner import mode_config, run
from scats.scenarios import advanced

VARIANTS = {
    "full": {},
    "no_cycle_adapt": {"adapt_cycle": False},
    "no_split_adapt": {"adapt_splits": False},
    "no_offset_adapt": {"adapt_offsets": False},
    "no_marriage": "no_marriage",
    "no_tactical": {"tactical": False},
    "no_bus_priority": {"bus_priority": False},
}


def main():
    args = cli.parser(__doc__).parse_args()
    out = cli.outdir(args, "advanced/ablation")
    results = []
    for name, ov in VARIANTS.items():
        scn = advanced(args.end or 5400)
        kw = {"bus_priority": True}
        if ov == "no_marriage":
            scn = dataclasses.replace(scn, marriages=[])
        else:
            kw.update(ov)
        results.append(run(scn, mode_config("scats", **kw), name, out, seed=args.seed))
    cli.write_summary(results, os.path.join(out, "ablation.csv"))
    plots.compare_bars(results, os.path.join(out, "ablation.png"), "SCATS ablation on the arterial corridor")
    print(f"\nAblation table: {os.path.join(out, 'ablation.csv')}")


if __name__ == "__main__":
    main()
