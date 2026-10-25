# SCATS-style controller for SUMO

Python + TraCI. Runs on the SUMO installed by `pip install eclipse-sumo` (or any SUMO ≥ 1.18).

## Structure

```
scats/core.py        simulator-independent algorithms (unit tested)
                     DS, VK, MF learning, cycle length, green allocation + stretch,
                     split prediction/selection, Voter, offset plans, marriage logic, Webster
scats/controller.py  Intersection  - tactical: min green, gap-out, skipping, coordinated hold,
                                     intergreens, bus priority, DS measurement per loop
                     Subsystem     - strategic: CI cycle length, offset voting, master clock
                     Region        - marriage/divorce, bus detection, simulation glue
scats/network.py     corridor generator (netconvert), stop-line loops, time-varying demand
scats/runner.py      Scenario, run(), baselines ("fixed", "actuated", "scats"), metrics, logs
scats/scenarios.py   Foundation (1 junction) and Advanced (4 junctions, 2 subsystems)
scats/plots.py       figures
```

## Labs

| Script | What it does |
|---|---|
| `foundation/01_ds_lab.py` | prints g, T, n, wasted green, g', DS, VK per cycle for one loop |
| `foundation/02_calibrate_h.py` | measures standard space time h (≈1.6 s) and MF (≈1730 veh/h) |
| `foundation/03_fixed_vs_scats.py` | fixed vs actuated vs SCATS at one intersection |
| `advanced/01_corridor_scats.py` | every mechanism on the 4-junction corridor + strategic timeline |
| `advanced/02_ablation_study.py` | removes one mechanism at a time |
| `mastery/01_cv_ds_estimation.py` | DS from connected vehicles: accuracy vs penetration, closed loop |
| `mastery/02_rl_split_selection.py` | tabular Q-learning chooses split plans inside SCATS |
| `mastery/03_maxpressure_hybrid.py` | pure max-pressure and a SCATS × pressure hybrid |
| `mastery/04_detector_faults.py` | stuck-on / stuck-off loops; none / exclude / impute |
| `mastery/05_spat_prediction.py` | predicting green duration for connected-vehicle apps |

All scripts take `--gui --seed --end --out`.

## Research hooks (`ControllerConfig`)

`ds_source`, `cv_penetration`, `split_selector`, `green_allocator`, `sensor_filter`,
`fault_handling`, `on_cycle_end`, `adapt_cycle`, `adapt_splits`, `adapt_offsets`,
and `run(..., pure_controller=...)` to replace SCATS entirely.

```python
from scats.runner import run, mode_config
from scats.scenarios import advanced

def my_selector(ix, ds, g_now, plan_greens):
    return 0          # always SP1 - replace with your idea

res = run(advanced(), mode_config("scats", split_selector=my_selector), "mine", "results/mine")
```

Parameter defaults are illustrative teaching values, not official SCATS settings.
