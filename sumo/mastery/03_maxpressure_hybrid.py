"""
MASTERY 3 - SCATS x Max-Pressure hybrid
=======================================
Research question: DS measures how well green is *used* but is blind to
downstream spill-back. Max-pressure (Varaiya 2013) uses queue *differences*
(upstream - downstream) and is throughput-optimal in theory but acyclic and
hard to coordinate. Can we take the best of both?

Three controllers on the same corridor:
  scats        : standard SCATS (DS-based splits)
  mp_pure      : acyclic max-pressure - every 5 s after min green, serve the
                 phase with the largest pressure (no cycle, no offsets)
  scats_mp     : SCATS cycle length + offsets, but each cycle's greens are
                 blended:  g = (1-beta)*g_SCATS + beta*g_pressure
                 where g_pressure shares available green in proportion to each
                 phase's mean pressure in the last cycle.

    python mastery/03_maxpressure_hybrid.py --beta 0.5
"""
import _path  # noqa: F401
import os

import traci
import traci.constants as tc

from scats import cli, plots
from scats import controller as ctl
from scats.runner import mode_config, run
from scats.scenarios import advanced


def phase_pressure(ix, name, q_lane, n_out):
    """Pressure of a phase = sum over its lanes of (queue upstream - mean load downstream)."""
    p = 0.0
    for lane in ix.phase_lanes[name]:
        down = ix.downstream.get(lane, [])
        down_load = sum(n_out.get(o, 0.0) for o in down) / max(len(down), 1)
        p += q_lane.get(lane, 0.0) - 0.5 * down_load
    return max(p, 0.0)


def make_hybrid_allocator(beta):
    def allocate(ix, C, greens):
        rec = ix.last_cycle
        if not rec or "q_lane" not in rec:
            return greens
        pres = {p: phase_pressure(ix, p, rec["q_lane"], rec["n_out"]) + 0.5 for p in ix.names}
        avail = sum(greens.values())
        tot = sum(pres.values())
        g_mp = {p: avail * pres[p] / tot for p in ix.names}
        blended = {p: (1 - beta) * greens[p] + beta * g_mp[p] for p in ix.names}
        for p in ix.names:  # respect minimum greens
            blended[p] = max(blended[p], ix.pdef[p].min_green)
        scale = avail / sum(blended.values())
        return {p: max(ix.pdef[p].min_green, g * scale) for p, g in blended.items()}
    return allocate


class MaxPressureController:
    """Acyclic max-pressure, using SCATS Intersection objects only for phase states."""

    def __init__(self, net, tls_ids, min_green=8.0, decision=5.0):
        cfg = ctl.ControllerConfig(strategic=False, tactical=False, coordinated=False)
        self.ixs = [ctl.Intersection(t, net, ctl.THREE_PHASE, ctl.THREE_PHASE_SPLITS, cfg) for t in tls_ids]
        self.in_lanes = [l for ix in self.ixs for l in ix.in_lanes]
        self.out_lanes = [l for ix in self.ixs for l in ix.out_lanes]
        self.min_green, self.decision = min_green, decision
        self.state = {ix.tls: {"phase": "A", "stage": "green", "since": 0.0, "until": 0.0, "next": None}
                      for ix in self.ixs}
        for ix in self.ixs:
            ix._set(ix.green_state["A"])
        self.log = []

    def step(self, t, dt, loop_data, lane_data):
        q = {l: d.get(tc.LAST_STEP_VEHICLE_HALTING_NUMBER, 0) for l, d in lane_data.items()}
        n = {l: d.get(tc.LAST_STEP_VEHICLE_NUMBER, 0) for l, d in lane_data.items()}
        for ix in self.ixs:
            st = self.state[ix.tls]
            if st["stage"] == "green":
                if t - st["since"] < self.min_green or (t - st["since"]) % self.decision:
                    continue
                pres = {p: phase_pressure(ix, p, q, n) for p in ix.names}
                best = max(pres, key=pres.get)
                if best != st["phase"] and pres[best] > pres[st["phase"]]:
                    y, r = ix._transition_states(st["phase"], best)
                    pd = ix.pdef[st["phase"]]
                    ix._set(y)
                    st.update(stage="yellow", until=t + pd.yellow, red_until=t + pd.intergreen, next=best, red=r)
            elif st["stage"] == "yellow" and t >= st["until"]:
                ix._set(st["red"])
                st["stage"] = "red"
            elif st["stage"] == "red" and t >= st["red_until"]:
                st.update(phase=st["next"], stage="green", since=t)
                ix._set(ix.green_state[st["next"]])


def main():
    p = cli.parser(__doc__)
    p.add_argument("--beta", type=float, default=0.5, help="weight of pressure in the hybrid split")
    args = p.parse_args()
    out = cli.outdir(args, "mastery/maxpressure")
    end = args.end or 5400
    results = [
        run(advanced(end), mode_config("scats", bus_priority=True), "scats", out, seed=args.seed),
        run(advanced(end), None, "mp_pure", out, seed=args.seed, pure_controller=MaxPressureController),
        run(advanced(end), mode_config("scats", bus_priority=True, adapt_splits=False,
                                       green_allocator=make_hybrid_allocator(args.beta)),
            f"scats_mp_b{args.beta}", out, seed=args.seed),
    ]
    cli.write_summary(results, os.path.join(out, "maxpressure.csv"))
    plots.compare_bars(results, os.path.join(out, "maxpressure.png"), "SCATS vs max-pressure vs hybrid")
    print(f"\nResults in {out}")


if __name__ == "__main__":
    main()
