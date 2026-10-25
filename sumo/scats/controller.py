"""
scats.controller - a SCATS-style adaptive controller running inside SUMO via TraCI.

Layers (mirroring SCATS):
  * Tactical  (Intersection)  - per-step: phase sequencing, minimum green,
                                gap-out / early termination, phase skipping,
                                public-transport priority, intergreens.
  * Strategic (Subsystem)     - per-cycle: cycle length from the critical
                                intersection's DS, split-plan voting,
                                offset-plan voting, master clock.
  * Region                    - marriage / divorce between subsystems and the
                                simulation loop glue.

Measurement uses stop-line induction loops: unoccupied time and vehicle
counts during green give the degree of saturation (see scats.core).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import sumolib
import traci
import traci.constants as tc

from . import core

# ---------------------------------------------------------------------------
# configuration and phase definitions
# ---------------------------------------------------------------------------


@dataclass
class PhaseDef:
    name: str
    rules: Dict[str, Dict[str, str]]  # {'art'|'side': {'s'|'l'|'r': 'G'|'g'}}
    min_green: float = 8.0
    yellow: float = 3.0
    all_red: float = 2.0
    skippable: bool = False           # demand-dependent phase

    @property
    def intergreen(self) -> float:
        return self.yellow + self.all_red


TWO_PHASE = [
    PhaseDef("A", {"art": {"s": "G", "r": "G", "l": "g"}}, min_green=10),
    PhaseDef("B", {"side": {"s": "G", "r": "G", "l": "g"}}, min_green=7),
]
TWO_PHASE_SPLITS = [
    {"A": 0.55, "B": 0.45}, {"A": 0.65, "B": 0.35},
    {"A": 0.45, "B": 0.55}, {"A": 0.75, "B": 0.25},
]

THREE_PHASE = [
    PhaseDef("A", {"art": {"s": "G", "r": "G", "l": "g"}}, min_green=10),
    PhaseDef("B", {"art": {"l": "G"}}, min_green=5, skippable=True),
    PhaseDef("C", {"side": {"s": "G", "r": "G", "l": "g"}}, min_green=7),
]
THREE_PHASE_SPLITS = [
    {"A": 0.50, "B": 0.15, "C": 0.35}, {"A": 0.60, "B": 0.12, "C": 0.28},
    {"A": 0.45, "B": 0.20, "C": 0.35}, {"A": 0.40, "B": 0.12, "C": 0.48},
]


@dataclass
class ControllerConfig:
    strategic: bool = True        # adapt cycle length / splits / offsets
    tactical: bool = True         # gap-out, phase skipping
    coordinated: bool = True      # follow subsystem master clock + offsets
    initial_cycle: float = 80.0
    initial_split: int = 0
    initial_offset_plan: int = 2
    cycle: core.CycleParams = field(default_factory=core.CycleParams)
    split_criterion: str = "max"
    gap_time: float = 3.0         # gap timer setting for gap-out
    space_time_h: float = 1.6     # standard space time per vehicle (calibrated: foundation/calibrate_h.py)
    mf_init: float = 1800.0
    learn_mf: bool = True
    transition: float = 0.2       # max fraction a cycle may be stretched/cut to re-sync
    progression_speed: float = 12.0
    # ablation switches (all True = full strategic SCATS)
    adapt_cycle: bool = True
    adapt_splits: bool = True
    adapt_offsets: bool = True
    # public transport priority
    bus_priority: bool = False
    bus_detect_dist: float = 100.0
    bus_ext_max: float = 12.0
    # research hooks -----------------------------------------------------
    ds_source: str = "loop"        # 'loop' or 'cv'
    cv_penetration: float = 1.0
    fault_handling: str = "none"   # 'none' | 'exclude' | 'impute'
    sensor_filter: Optional[Callable] = None     # (lane, occ, ids, t) -> (occ, ids)
    split_selector: Optional[Callable] = None    # (ix, ds, g_now, plan_greens) -> idx
    green_allocator: Optional[Callable] = None   # (ix, L, greens) -> greens
    on_cycle_end: Optional[Callable] = None      # (ix, record) -> None


def is_cv(veh_id: str, p: float) -> bool:
    """Deterministic 'is this vehicle connected?' draw (same answer every call)."""
    if p >= 1.0:
        return True
    h = int(hashlib.md5(veh_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return h < p


# ---------------------------------------------------------------------------
# lane meter: one stop-line loop
# ---------------------------------------------------------------------------


class LaneMeter:
    def __init__(self, lane: str, mf: float):
        self.lane = lane
        self.mf = mf
        self.gap = 99.0
        self.prev_ids: set = set()
        self.reset()
        # fault diagnostics
        self.zero_count_greens = 0
        self.full_occ_greens = 0
        self.faulty = False
        self.ds_avg: Optional[float] = None

    def reset(self):
        self.g = 0.0
        self.T = 0.0
        self.n = 0
        self.ids: List[str] = []
        self.occ_sum = 0.0

    def observe(self, occ_pct: float, ids, dt: float, in_green: bool):
        occ = max(0.0, min(1.0, occ_pct / 100.0))
        new = [v for v in ids if v not in self.prev_ids]
        self.prev_ids = set(ids)
        self.gap = 0.0 if occ > 0 else self.gap + dt
        if in_green:
            self.g += dt
            self.T += (1.0 - occ) * dt
            self.n += len(new)
            self.ids.extend(new)
            self.occ_sum += occ * dt

    def finish(self, cfg: ControllerConfig) -> Dict[str, float]:
        """Close a green window and return the measurement for this lane."""
        g = self.g
        # loop estimate (classic SCATS) and connected-vehicle estimate are both computed,
        # so research scripts can compare them; cfg.ds_source decides which one is used.
        ds_loop = core.degree_of_saturation(g, self.T, self.n, cfg.space_time_h)
        n_cv = sum(1 for v in self.ids if is_cv(v, cfg.cv_penetration))
        n_est = n_cv / max(cfg.cv_penetration, 1e-6)
        ds_cv = (n_est * 3600.0 / self.mf) / g if g > 0 else 0.0
        ds = ds_cv if cfg.ds_source == "cv" else ds_loop
        g_used = ds * g
        # detector alarm logic (simple SCATS-like plausibility checks)
        self.zero_count_greens = self.zero_count_greens + 1 if self.n == 0 and g > 0 else 0
        self.full_occ_greens = self.full_occ_greens + 1 if g > 0 and self.occ_sum >= 0.98 * g else 0
        self.faulty = self.full_occ_greens >= 2 or self.zero_count_greens >= 6
        if not self.faulty:
            self.ds_avg = ds if self.ds_avg is None else 0.8 * self.ds_avg + 0.2 * ds
            if cfg.learn_mf and cfg.ds_source == "loop":
                self.mf = core.update_max_flow(self.mf, self.n, g_used)
        vk = core.reconstituted_flow(ds, g, self.mf)
        out = {"g": g, "T": self.T, "n": self.n, "ds": ds, "vk": vk, "faulty": self.faulty,
               "ds_loop": ds_loop, "ds_cv": ds_cv, "ids": self.ids, "mf": self.mf}
        self.reset()
        return out


# ---------------------------------------------------------------------------
# intersection = tactical controller
# ---------------------------------------------------------------------------


class Intersection:
    def __init__(self, tls: str, net: sumolib.net.Net, phases: List[PhaseDef],
                 splits: List[Dict[str, float]], cfg: ControllerConfig, x: float = 0.0):
        self.tls, self.cfg, self.x = tls, cfg, x
        self.phases = phases
        self.names = [p.name for p in phases]
        self.pdef = {p.name: p for p in phases}
        self.splits = splits
        self.plan = cfg.initial_split
        self.split_voter = core.Voter(cfg.initial_split, window=3, needed=2)
        self.subsystem: Optional["Subsystem"] = None
        self.offset = 0.0
        self.bus_request: Optional[str] = None

        junction = net.getNode(tls)
        jx, jy = junction.getCoord()
        links = traci.trafficlight.getControlledLinks(tls)
        self.link_info = []
        self.link_out: List[str] = []
        for idx, lk in enumerate(links):
            in_lane, out_lane, _ = lk[0]
            lane_obj = net.getLane(in_lane)
            fx, fy = lane_obj.getEdge().getFromNode().getCoord()
            dx, dy = fx - jx, fy - jy
            appr = ("W" if dx < 0 else "E") if abs(dx) > abs(dy) else ("N" if dy > 0 else "S")
            turn = "s"
            for c in lane_obj.getOutgoing():
                if c.getToLane().getID() == out_lane:
                    d = c.getDirection().lower()
                    turn = "l" if d in ("l", "pl") else "r" if d in ("r", "pr") else "s"
            cls = "art" if appr in ("W", "E") else "side"
            self.link_info.append((in_lane, appr, turn, cls))
            self.link_out.append(out_lane)

        self.green_state = {}
        for p in phases:
            self.green_state[p.name] = "".join(
                p.rules.get(cls, {}).get(turn, "r") for (_, _, turn, cls) in self.link_info)

        self.in_lanes = sorted({li[0] for li in self.link_info})
        self.out_lanes = sorted({lk[0][1] for lk in links})
        self.lane_approach = {li[0]: li[1] for li in self.link_info}
        # strategic lanes: lanes with a protected ('G') movement in the phase, or
        # lanes that never get 'G' anywhere but are served permissively here.
        ever_G = {l for p in phases for (l, _, _, _), ch in zip(self.link_info, self.green_state[p.name]) if ch == "G"}
        self.phase_lanes: Dict[str, List[str]] = {}
        for p in phases:
            lanes = set()
            for (lane, _, _, _), ch in zip(self.link_info, self.green_state[p.name]):
                if ch == "G" or (ch == "g" and lane not in ever_G):
                    lanes.add(lane)
            self.phase_lanes[p.name] = sorted(lanes)
        self.meters = {l: LaneMeter(l, cfg.mf_init) for l in self.in_lanes}
        self.downstream = {l: sorted({o for (li, *_), o in zip(self.link_info, self.link_out) if li == l})
                           for l in self.in_lanes}
        # per-cycle accumulators (used by research modules: RL reward, max-pressure)
        self.q_in = {l: 0.0 for l in self.in_lanes}
        self.n_out = {l: 0.0 for l in self.out_lanes}
        self.acc_t = 0.0

        # runtime
        self.stage = "init"
        self.idx = 0
        self.stage_end = 0.0
        self.cycle_start = 0.0
        self.cycle_L = cfg.initial_cycle
        self.planned: Dict[str, float] = {}
        self.alloc = 0.0
        self.carry = 0.0
        self.green_start = 0.0
        self.ext_used = 0.0
        self.next_idx = 0
        self.record: Dict = {}
        self.last_cycle: Optional[Dict] = None
        self.history: List[Dict] = []

    # ---------------------------------------------------------------- state
    def _set(self, state: str):
        traci.trafficlight.setRedYellowGreenState(self.tls, state)

    def _transition_states(self, cur: str, nxt: str):
        a, b = self.green_state[cur], self.green_state[nxt]
        yellow = "".join(ca if (ca in "Gg" and cb in "Gg") else ("y" if ca in "Gg" else "r")
                         for ca, cb in zip(a, b))
        red = "".join(ca if (ca in "Gg" and cb in "Gg") else "r" for ca, cb in zip(a, b))
        return yellow, red

    # ---------------------------------------------------------------- cycle
    def start_cycle(self, t: float):
        if self.record:
            self._close_cycle(t)
        L = self.subsystem.local_cycle_length(self, t) if self.subsystem else self.cycle_L
        self.cycle_start, self.cycle_L = t, L
        inter = {p.name: p.intergreen for p in self.phases}
        mins = {p.name: p.min_green for p in self.phases}
        lstretch = self.cfg.cycle.l_stretch
        coord = self.cfg.coordinated and self.subsystem is not None
        C = (self.subsystem.master or self.subsystem).C if coord else L
        greens = core.allocate_greens(C, self.splits[self.plan], inter, mins, "A", lstretch)
        if self.cfg.green_allocator:
            greens = self.cfg.green_allocator(self, C, greens)
        if coord:
            # re-synchronisation time (L - C) is absorbed by the coordinated phase A
            first = self.names[0]
            greens[first] = max(self.pdef[first].min_green, greens[first] + (L - C))
        self.planned = greens
        self.carry = 0.0
        self.record = {"t": t, "tls": self.tls, "L": L, "plan": self.plan, "planned": dict(greens),
                       "g": {}, "ds": {}, "lanes": {}, "skipped": []}
        self._start_green(0, t)

    def _close_cycle(self, t: float):
        rec = self.record
        span = max(self.acc_t, 1.0)
        rec["queue"] = sum(self.q_in.values())                       # veh*s halted on approaches
        rec["q_lane"] = {l: v / span for l, v in self.q_in.items()}  # mean halted vehicles
        rec["n_out"] = {l: v / span for l, v in self.n_out.items()}  # mean vehicles downstream
        rec["dur"] = t - rec["t"]
        self.q_in = {l: 0.0 for l in self.in_lanes}
        self.n_out = {l: 0.0 for l in self.out_lanes}
        self.acc_t = 0.0
        for p in self.names:
            rec["ds"].setdefault(p, 0.0)
            rec["g"].setdefault(p, rec["planned"][p])
        self.last_cycle = rec
        self.history.append(rec)
        if self.cfg.strategic and self.cfg.adapt_splits:
            inter = {p.name: p.intergreen for p in self.phases}
            mins = {p.name: p.min_green for p in self.phases}
            plan_greens = [core.allocate_greens(rec["L"], s, inter, mins, "A", self.cfg.cycle.l_stretch)
                           for s in self.splits]
            g_now = {p: max(rec["g"][p], 1.0) for p in self.names}
            if self.cfg.split_selector:
                best = self.cfg.split_selector(self, rec["ds"], g_now, plan_greens)
                self.plan = best
            else:
                best, scores = core.select_split_plan(rec["ds"], g_now, plan_greens, self.cfg.split_criterion)
                self.plan = self.split_voter.vote(best)
            rec["vote"] = best
        if self.cfg.on_cycle_end:
            self.cfg.on_cycle_end(self, rec)

    def _start_green(self, idx: int, t: float):
        self.idx, self.stage = idx, "green"
        name = self.names[idx]
        self.green_start = t
        self.alloc = self.planned[name] + self.carry
        self.carry = 0.0
        self.ext_used = 0.0
        for l in self.phase_lanes[name]:
            self.meters[l].reset()
        self._set(self.green_state[name])

    def _has_demand(self, name: str, lane_data) -> bool:
        return any(lane_data.get(l, {}).get(tc.LAST_STEP_VEHICLE_NUMBER, 0) > 0
                   for l in self.phase_lanes[name])

    def _end_green(self, t: float, lane_data):
        name = self.names[self.idx]
        elapsed = t - self.green_start
        lane_meas = {l: self.meters[l].finish(self.cfg) for l in self.phase_lanes[name]}
        self.record["lanes"].update(lane_meas)
        self.record["g"][name] = elapsed
        healthy = [m["ds"] for l, m in lane_meas.items() if not (m["faulty"] and self.cfg.fault_handling != "none")]
        if self.cfg.fault_handling == "impute":
            healthy += [self.meters[l].ds_avg for l, m in lane_meas.items()
                        if m["faulty"] and self.meters[l].ds_avg is not None]
        self.record["ds"][name] = max(healthy) if healthy else 0.0
        self.carry = max(0.0, self.alloc - elapsed) - max(0.0, elapsed - self.alloc)
        # choose next phase (with demand-dependent skipping)
        nxt = self.idx + 1
        while nxt < len(self.names):
            p = self.pdef[self.names[nxt]]
            if self.cfg.tactical and p.skippable and not self._has_demand(p.name, lane_data):
                self.carry += self.planned[p.name] + p.intergreen
                self.record["skipped"].append(p.name)
                self.record["ds"][p.name] = 0.0
                self.record["g"][p.name] = self.planned[p.name]
                nxt += 1
                continue
            break
        self.next_idx = nxt
        nxt_name = self.names[nxt] if nxt < len(self.names) else self.names[0]
        y, r = self._transition_states(name, nxt_name)
        pd = self.pdef[name]
        self.stage, self.stage_end, self._red_state = "yellow", t + pd.yellow, r
        self._red_end = t + pd.intergreen
        self._set(y)

    # ---------------------------------------------------------------- step
    def step(self, t: float, dt: float, loop_data, lane_data):
        if self.stage == "init":
            self.start_cycle(t)
            return
        green_name = self.names[self.idx] if self.stage == "green" else None
        self.acc_t += dt
        for l in self.in_lanes:
            self.q_in[l] += lane_data.get(l, {}).get(tc.LAST_STEP_VEHICLE_HALTING_NUMBER, 0) * dt
        for l in self.out_lanes:
            self.n_out[l] += lane_data.get(l, {}).get(tc.LAST_STEP_VEHICLE_NUMBER, 0) * dt
        for l in self.in_lanes:
            d = loop_data.get("loop_" + l, {})
            occ = d.get(tc.LAST_STEP_OCCUPANCY, 0.0)
            ids = d.get(tc.LAST_STEP_VEHICLE_ID_LIST, ())
            if self.cfg.sensor_filter:
                occ, ids = self.cfg.sensor_filter(l, occ, ids, t)
            self.meters[l].observe(occ, ids, dt, green_name is not None and l in self.phase_lanes[green_name])

        if self.stage == "green":
            name = green_name
            pd = self.pdef[name]
            elapsed = t - self.green_start
            ignore = self.cfg.fault_handling != "none"
            lanes = [l for l in self.phase_lanes[name] if not (ignore and self.meters[l].faulty)]
            # the coordinated phase (A) is held to keep the green wave; others may gap out
            hold = self.cfg.coordinated and self.idx == 0
            gap_out = (self.cfg.tactical and not hold and elapsed >= pd.min_green and lanes and
                       all(self.meters[l].gap >= self.cfg.gap_time for l in lanes))
            terminate = elapsed >= self.alloc or gap_out
            # public transport priority (medium level: extend / early-terminate)
            if self.cfg.bus_priority and self.bus_request:
                if self.bus_request == name and elapsed >= self.alloc and self.ext_used < self.cfg.bus_ext_max:
                    terminate = False
                    self.ext_used += dt
                    self.alloc += dt
                elif self.bus_request != name and elapsed >= pd.min_green:
                    terminate = True
            if terminate:
                self._end_green(t, lane_data)
        elif self.stage == "yellow" and t >= self.stage_end:
            self.stage = "red"
            self._set(self._red_state)
        elif self.stage == "red" and t >= self._red_end:
            if self.next_idx >= len(self.names):
                self.start_cycle(t)
            else:
                self._start_green(self.next_idx, t)


# ---------------------------------------------------------------------------
# subsystem = strategic controller
# ---------------------------------------------------------------------------


class Subsystem:
    def __init__(self, name: str, members: List[Intersection], ci: Intersection,
                 cfg: ControllerConfig, east_lanes: List[str], west_lanes: List[str]):
        self.name, self.members, self.ci, self.cfg = name, members, ci, cfg
        self.C = cfg.initial_cycle
        self.cycle_start = 0.0
        self.offset_plan = cfg.initial_offset_plan
        self.offset_voter = core.Voter(cfg.initial_offset_plan, window=5, needed=4)
        self.east_lanes, self.west_lanes = east_lanes, west_lanes
        self.master: Optional["Subsystem"] = None   # set when married as a slave
        self.ref_x = members[0].x
        self.log: List[Dict] = []
        for m in members:
            m.subsystem = self
        self._apply_offsets(members, members[0])

    def required_cycle(self) -> float:
        rec = self.ci.last_cycle
        ds = max(rec["ds"].values()) if rec else self.cfg.cycle.target_ds
        if not self.cfg.adapt_cycle:
            return self.C, ds
        return core.next_cycle_length(self.C, ds, self.cfg.cycle), ds

    def directional_vk(self):
        east = west = 0.0
        for m in self.members:
            rec = m.last_cycle
            if not rec:
                continue
            for l, meas in rec["lanes"].items():
                if l in self.east_lanes:
                    east += meas["vk"]
                elif l in self.west_lanes:
                    west += meas["vk"]
        return east, west

    def _apply_offsets(self, members, ref, plan=None):
        plan = self.offset_plan if plan is None else plan
        xs = [m.x for m in members]
        offs = core.offsets_for_plan(plan, xs, members.index(ref), self.cfg.progression_speed, self.C)
        for m, o in zip(members, offs):
            m.offset = o if self.cfg.coordinated else 0.0

    def local_cycle_length(self, ix: Intersection, t: float) -> float:
        clock = self.master or self
        C = clock.C
        if not self.cfg.coordinated:
            return C
        rel = (t - (clock.cycle_start + ix.offset)) % C
        if rel > C / 2:
            rel -= C
        L = C - rel
        tr = self.cfg.transition
        return max(C * (1 - tr), min(C * (1 + tr), L))


class Region:
    """Owns subsystems, marriage logic and the TraCI loop glue."""

    def __init__(self, subsystems: List[Subsystem], cfg: ControllerConfig,
                 marriages: Optional[List[tuple]] = None, link_lanes: Optional[Dict] = None):
        self.subs, self.cfg = subsystems, cfg
        self.marriages = []
        for (a, b) in (marriages or []):
            self.marriages.append({"a": subsystems[a], "b": subsystems[b],
                                   "logic": core.MarriageLogic(), "lanes": link_lanes[(a, b)]})
        self.intersections = [m for s in subsystems for m in s.members]
        self.bus_ids: set = set()
        self.log: List[Dict] = []

    def _link_vk(self, lanes) -> float:
        vk = 0.0
        for ix in self.intersections:
            rec = ix.last_cycle
            if rec:
                vk += sum(meas["vk"] for l, meas in rec["lanes"].items() if l in lanes)
        return vk

    def _end_master_cycle(self, s: Subsystem, t: float):
        cfg = self.cfg
        slaves = [m["b"] for m in self.marriages if m["a"] is s and m["logic"].married]
        req, ds = s.required_cycle() if cfg.strategic else (s.C, 0.0)
        for sl in slaves:
            r2, d2 = sl.required_cycle() if cfg.strategic else (sl.C, 0.0)
            req, ds = max(req, r2), max(ds, d2)
        group = [s] + slaves
        members = [m for g in group for m in g.members]
        if cfg.strategic:
            east = sum(g.directional_vk()[0] for g in group)
            west = sum(g.directional_vk()[1] for g in group)
            xs = [m.x for m in members]
            link_tt = (xs[1] - xs[0]) / cfg.progression_speed if len(xs) > 1 else 0.0
            if cfg.adapt_offsets:
                choice = core.select_offset_plan(east, west, link_tt, req)
                s.offset_plan = s.offset_voter.vote(choice)
        else:
            east = west = 0.0
        s.cycle_start += s.C
        s.C = req
        s._apply_offsets(members, members[0])
        for sl in slaves:
            sl.C, sl.cycle_start, sl.master = s.C, s.cycle_start, s
            sl.offset_plan = s.offset_plan
        # marriage votes (evaluated by the upstream subsystem of each pair)
        married_flags = {}
        for m in self.marriages:
            if m["a"] is s:
                vk = self._link_vk(m["lanes"])
                req_b = m["b"].required_cycle()[0] if cfg.strategic else m["b"].C
                before = m["logic"].married
                now = m["logic"].vote(vk, s.C, req_b) if cfg.strategic else before
                if before and not now:   # divorce: slave gets its own clock again
                    m["b"].master = None
                    m["b"].cycle_start = t
                    m["b"]._apply_offsets(m["b"].members, m["b"].members[0])
                married_flags[m["b"].name] = (now, round(vk, 1))
        entry = {"t": t, "ss": s.name, "C": round(s.C, 1), "ds_ci": round(ds, 3),
                 "offset_plan": s.offset_plan, "vk_east": round(east, 1), "vk_west": round(west, 1),
                 "married": married_flags,
                 "splits": {m.tls: m.plan for m in members}}
        self.log.append(entry)

    def step(self, t: float, dt: float, loop_data, lane_data):
        # bus priority requests
        if self.cfg.bus_priority:
            for v in traci.simulation.getDepartedIDList():
                if traci.vehicle.getTypeID(v).startswith("bus"):
                    self.bus_ids.add(v)
            for v in traci.simulation.getArrivedIDList():
                self.bus_ids.discard(v)
            for ix in self.intersections:
                ix.bus_request = None
            for v in list(self.bus_ids):
                try:
                    lane = traci.vehicle.getLaneID(v)
                    pos = traci.vehicle.getLanePosition(v)
                except traci.TraCIException:
                    continue
                for ix in self.intersections:
                    if lane in ix.lane_approach:
                        if traci.lane.getLength(lane) - pos <= self.cfg.bus_detect_dist:
                            for p in ix.names:
                                if lane in ix.phase_lanes[p]:
                                    ix.bus_request = p
                                    break
        # master clocks
        for s in self.subs:
            if s.master is None and t >= s.cycle_start + s.C:
                self._end_master_cycle(s, t)
        for ix in self.intersections:
            ix.step(t, dt, loop_data, lane_data)
