"""
scats.runner - one function that builds a scenario, runs SUMO with the SCATS
controller (or a baseline), and returns performance metrics + logs.
"""
from __future__ import annotations

import csv
import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional

import sumolib
import traci
import traci.constants as tc

from . import controller as ctl
from .network import build_corridor, write_demand

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Scenario:
    name: str
    n: int = 1
    spacing: float = 300.0
    phase_set: str = "two"            # 'two' or 'three'
    periods: List[dict] = field(default_factory=list)
    bus_headway: float = 0.0
    subsystems: List[List[int]] = field(default_factory=lambda: [[0]])  # junction indices
    ci: List[int] = field(default_factory=lambda: [0])
    marriages: List[tuple] = field(default_factory=list)                # (ss_a, ss_b)
    end: float = 3600.0


MODES = {
    "fixed":    dict(strategic=False, tactical=False, coordinated=True,
                     initial_cycle=90.0, initial_split=1, initial_offset_plan=0),
    "actuated": dict(strategic=False, tactical=True,  coordinated=False),
    "scats":    dict(strategic=True,  tactical=True,  coordinated=True),
}


def mode_config(mode: str, **overrides) -> ctl.ControllerConfig:
    cfg = ctl.ControllerConfig(**MODES[mode])
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _parse_tripinfo(path: str) -> Dict[str, float]:
    tot = {"n": 0, "duration": 0.0, "timeLoss": 0.0, "waiting": 0.0, "stops": 0}
    bus = {"n": 0, "timeLoss": 0.0}
    for _, el in ET.iterparse(path):
        if el.tag != "tripinfo":
            continue
        tl = float(el.get("timeLoss"))
        tot["n"] += 1
        tot["duration"] += float(el.get("duration"))
        tot["timeLoss"] += tl
        tot["waiting"] += float(el.get("waitingTime"))
        tot["stops"] += int(el.get("waitingCount"))
        if el.get("vType", "").startswith("bus"):
            bus["n"] += 1
            bus["timeLoss"] += tl
        el.clear()
    n = max(tot["n"], 1)
    return {"trips": tot["n"],
            "avg_travel_time": round(tot["duration"] / n, 2),
            "avg_delay": round(tot["timeLoss"] / n, 2),
            "avg_wait": round(tot["waiting"] / n, 2),
            "stops_per_veh": round(tot["stops"] / n, 3),
            "bus_avg_delay": round(bus["timeLoss"] / max(bus["n"], 1), 2) if bus["n"] else None}


def run(scn: Scenario, cfg: ctl.ControllerConfig, label: str, outdir: str,
        seed: int = 1, gui: bool = False, pure_controller: Optional[Callable] = None,
        verbose: bool = True) -> Dict:
    """Run one simulation.

    pure_controller: optional factory (net, tls_ids) -> object with .step(t, dt, loop_data, lane_data)
                     used by research baselines that replace SCATS entirely (e.g. max-pressure).
    """
    os.makedirs(outdir, exist_ok=True)
    netdir = os.path.join(outdir, "net")
    info = build_corridor(netdir, n=scn.n, spacing=scn.spacing)
    rou = os.path.join(outdir, f"{scn.name}.rou.xml")
    write_demand(rou, scn.n, scn.periods, bus_headway=scn.bus_headway)
    trip = os.path.join(outdir, f"tripinfo_{label}.xml")

    binary = sumolib.checkBinary("sumo-gui" if gui else "sumo")
    cmd = [binary, "-n", info["net"], "-r", rou, "-a", info["loops"],
           "--step-length", "1", "--seed", str(seed), "--tripinfo-output", trip,
           "--no-step-log", "true", "--duration-log.disable", "true", "--no-warnings", "true",
           "--time-to-teleport", "300", "--end", str(scn.end + 900)]
    if gui:
        cmd += ["--start", "--delay", "50"]
    traci.start(cmd)
    net = sumolib.net.readNet(info["net"])
    tls_ids = [f"J{i}" for i in range(1, scn.n + 1)]

    phases = ctl.TWO_PHASE if scn.phase_set == "two" else ctl.THREE_PHASE
    splits = ctl.TWO_PHASE_SPLITS if scn.phase_set == "two" else ctl.THREE_PHASE_SPLITS

    if pure_controller is None:
        ixs = [ctl.Intersection(tid, net, phases, splits, cfg, x=info["xs"][k]) for k, tid in enumerate(tls_ids)]
        subs = []
        for si, members in enumerate(scn.subsystems):
            mem = [ixs[k] for k in members]
            east = [l for m in mem for l in m.in_lanes if m.lane_approach[l] == "W"]
            west = [l for m in mem for l in m.in_lanes if m.lane_approach[l] == "E"]
            subs.append(ctl.Subsystem(f"SS{si + 1}", mem, ixs[scn.ci[si]], cfg, east, west))
        link_lanes = {}
        for (a, b) in scn.marriages:
            last_a = ixs[scn.subsystems[a][-1]]
            first_b = ixs[scn.subsystems[b][0]]
            link_lanes[(a, b)] = [l for l in first_b.in_lanes if l.startswith(f"{last_a.tls}_{first_b.tls}_")] + \
                                 [l for l in last_a.in_lanes if l.startswith(f"{first_b.tls}_{last_a.tls}_")]
        brain = ctl.Region(subs, cfg, scn.marriages, link_lanes)
        all_in = [l for ix in ixs for l in ix.in_lanes]
        all_out = [l for ix in ixs for l in ix.out_lanes]
    else:
        brain = pure_controller(net, tls_ids)
        ixs = []
        all_in, all_out = brain.in_lanes, brain.out_lanes

    for l in all_in:
        traci.inductionloop.subscribe("loop_" + l, [tc.LAST_STEP_OCCUPANCY, tc.LAST_STEP_VEHICLE_ID_LIST])
    for l in set(all_in) | set(all_out):
        traci.lane.subscribe(l, [tc.LAST_STEP_VEHICLE_NUMBER, tc.LAST_STEP_VEHICLE_HALTING_NUMBER])

    dt = 1.0
    halting_sum = 0
    while True:
        traci.simulationStep()
        t = traci.simulation.getTime()
        loop_data = traci.inductionloop.getAllSubscriptionResults()
        lane_data = traci.lane.getAllSubscriptionResults()
        halting_sum += sum(d.get(tc.LAST_STEP_VEHICLE_HALTING_NUMBER, 0) for l, d in lane_data.items() if l in all_in)
        brain.step(t, dt, loop_data, lane_data)
        if t >= scn.end and traci.simulation.getMinExpectedNumber() == 0:
            break
        if t >= scn.end + 900:
            break
    traci.close()

    metrics = _parse_tripinfo(trip)
    metrics["queue_veh_s"] = int(halting_sum)
    metrics["label"] = label

    # logs -----------------------------------------------------------------
    if ixs:
        with open(os.path.join(outdir, f"cycles_{label}.csv"), "w", newline="") as f:
            w = csv.writer(f)
            phase_names = [p.name for p in phases]
            w.writerow(["t", "tls", "cycle_L", "split_plan"] + [f"g_{p}" for p in phase_names] +
                       [f"DS_{p}" for p in phase_names] + ["skipped"])
            for ix in ixs:
                for r in ix.history:
                    w.writerow([r["t"], r["tls"], round(r["L"], 1), r["plan"]] +
                               [round(r["g"][p], 1) for p in phase_names] +
                               [round(r["ds"][p], 3) for p in phase_names] + ["|".join(r["skipped"])])
        with open(os.path.join(outdir, f"strategic_{label}.json"), "w") as f:
            json.dump(brain.log, f, indent=1)
    if verbose:
        print(f"[{label:>16}] trips={metrics['trips']:5d}  delay={metrics['avg_delay']:6.1f}s  "
              f"travel={metrics['avg_travel_time']:6.1f}s  stops/veh={metrics['stops_per_veh']:.2f}"
              + (f"  bus_delay={metrics['bus_avg_delay']}s" if metrics['bus_avg_delay'] is not None else ""))
    metrics["_intersections"] = ixs
    metrics["_log"] = getattr(brain, "log", [])
    return metrics
