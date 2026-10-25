"""
scats.core - pure-Python, simulator-independent SCATS-style algorithms.

Everything in this module is deliberately free of SUMO/TraCI so it can be
unit-tested and re-used (the website's JavaScript simulators mirror these
functions one-to-one).

IMPORTANT: SCATS is proprietary software owned by Transport for NSW. The
algorithms below are an *educational re-implementation* built from the
published literature (degree of saturation, plan voting, marriage/divorce,
etc.). Parameter values are illustrative defaults, not official SCATS values.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 1. Degree of saturation (DS) and reconstituted flow (VK)
# ---------------------------------------------------------------------------

def degree_of_saturation(g: float, T: float, n: int, h: float) -> float:
    """SCATS degree of saturation measured at a stop-line detector.

        DS = g' / g    with    g' = g - (T - n*h)

    g : available green time for the movement in the last cycle   [s]
    T : total *unoccupied* (gap) time at the detector during that green [s]
    n : number of vehicles (= number of spaces) detected during green
    h : standard space time - the unoccupied time between two vehicles
        that are discharging at saturation flow                   [s]

    (T - n*h) is "wasted" green: gap time beyond what a saturated stream
    would leave. g' is therefore the green that was *effectively used*.
    DS can exceed 1.0 when vehicles discharge with gaps smaller than h.
    """
    if g <= 0:
        return 0.0
    g_used = g - (T - n * h)
    return max(0.0, g_used / g)


def effective_green(g: float, T: float, n: int, h: float) -> float:
    """g' - the green that a saturated flow would need for the observed traffic."""
    return max(0.0, g - (T - n * h))


def reconstituted_flow(ds: float, g: float, mf: float) -> float:
    """VK: 'car-equivalent' volume reconstituted from DS.

        VK = DS * g * MF / 3600

    MF is the maximum (saturation) flow of the lane in veh/h of green.
    VK is independent of vehicle mix: a long truck occupies the loop like
    several cars, so it 'counts' as several car-equivalents.
    """
    return ds * g * mf / 3600.0


def update_max_flow(mf: float, n: int, g_used: float, alpha: float = 0.2,
                    min_g: float = 8.0) -> float:
    """Learn MF (saturation flow) on-line from cycles with a saturated discharge.

    SCATS calibrates MF automatically; here we keep the maximum observed flow
    rate over effectively-used green, smoothed so a single outlier cannot
    dominate.
    """
    if g_used < min_g or n < 3:
        return mf
    observed = 3600.0 * n / g_used
    if observed > mf:
        return (1 - alpha) * mf + alpha * observed
    return mf


# ---------------------------------------------------------------------------
# 2. Cycle length (RL) adaptation
# ---------------------------------------------------------------------------

@dataclass
class CycleParams:
    l_min: float = 40.0      # minimum cycle length (LMIN)
    l_max: float = 140.0     # maximum cycle length (LMAX)
    l_stretch: float = 110.0 # above this, extra time goes to the stretch phase
    target_ds: float = 0.90  # DS the subsystem tries to hold at the CI
    step_up: float = 6.0     # max increase per cycle
    step_up_fast: float = 9.0  # max increase when DS is above fast_ds
    step_down: float = 6.0   # max decrease per cycle
    fast_ds: float = 1.0


def next_cycle_length(current: float, ds: float, p: CycleParams) -> float:
    """Move the cycle length towards the value that would give target DS.

    If the critical intersection (CI) ran at DS with cycle C, then (to first
    order) the cycle that would yield target DS is C * DS / target. SCATS
    never jumps there directly: it moves in small, bounded steps every cycle,
    which keeps the network stable and lets offsets follow smoothly.
    """
    desired = current * ds / p.target_ds if ds > 0 else p.l_min
    up = p.step_up_fast if ds >= p.fast_ds else p.step_up
    delta = max(-p.step_down, min(up, desired - current))
    return max(p.l_min, min(p.l_max, current + delta))


# ---------------------------------------------------------------------------
# 3. Green allocation from a split plan
# ---------------------------------------------------------------------------

def allocate_greens(cycle: float, split: Dict[str, float],
                    intergreen: Dict[str, float],
                    min_green: Dict[str, float],
                    stretch_phase: Optional[str] = None,
                    l_stretch: Optional[float] = None) -> Dict[str, float]:
    """Turn a split plan (fractions of available green) into green times.

    available = cycle - sum(intergreens). Minimum greens are guaranteed; the
    remainder is shared according to the split fractions. If the cycle is
    above the stretch threshold, the extra time above l_stretch is given to
    the stretch phase only (usually the main-road phase).
    """
    phases = list(split.keys())
    lost = sum(intergreen[p] for p in phases)
    base_cycle = cycle
    extra = 0.0
    if stretch_phase and l_stretch and cycle > l_stretch:
        base_cycle, extra = l_stretch, cycle - l_stretch
    avail = max(0.0, base_cycle - lost)
    total = sum(split.values()) or 1.0
    greens = {p: avail * split[p] / total for p in phases}
    # enforce minimum greens by borrowing from phases with slack
    deficit = sum(max(0.0, min_green[p] - greens[p]) for p in phases)
    if deficit > 0:
        slack = {p: greens[p] - min_green[p] for p in phases if greens[p] > min_green[p]}
        slack_total = sum(slack.values()) or 1.0
        for p in phases:
            if greens[p] < min_green[p]:
                greens[p] = min_green[p]
            elif p in slack:
                greens[p] -= deficit * slack[p] / slack_total
    if extra and stretch_phase in greens:
        greens[stretch_phase] += extra
    return greens


# ---------------------------------------------------------------------------
# 4. Split plan selection (+ voting)
# ---------------------------------------------------------------------------

def predict_plan_ds(ds: Dict[str, float], g_now: Dict[str, float],
                    g_plan: Dict[str, float]) -> Dict[str, float]:
    """DS each phase *would* have under another plan with the same demand.

        DS_p(plan j) = DS_p * g_p(now) / g_p(plan j)

    (demand needs g' = DS*g seconds; give it a different g and DS scales.)
    """
    return {p: (ds[p] * g_now[p] / g_plan[p]) if g_plan.get(p, 0) > 0 else 9.9
            for p in ds}


def select_split_plan(ds: Dict[str, float], g_now: Dict[str, float],
                      plan_greens: Sequence[Dict[str, float]],
                      criterion: str = "max") -> Tuple[int, List[float]]:
    """Choose the split plan that best balances DS across phases.

    criterion='max'  : minimise the highest predicted phase DS (equalise DS)
    criterion='sum'  : minimise the sum of predicted phase DS
    Returns (best_index, score_per_plan).
    """
    scores = []
    for g_plan in plan_greens:
        pred = predict_plan_ds(ds, g_now, g_plan)
        scores.append(max(pred.values()) if criterion == "max" else sum(pred.values()))
    best = min(range(len(scores)), key=lambda i: scores[i])
    return best, scores


class Voter:
    """Plan voting: a plan is only *implemented* when it has won `needed`
    of the last `window` cycles. This damps noise - SCATS changes plans only
    when the evidence is consistent (e.g. 2 of 3 for splits, 4 of 5 for
    offsets).
    """

    def __init__(self, initial: int, window: int = 3, needed: int = 2):
        self.current = initial
        self.window, self.needed = window, needed
        self.history: deque = deque(maxlen=window)

    def vote(self, choice: int) -> int:
        self.history.append(choice)
        if choice != self.current and list(self.history).count(choice) >= self.needed:
            self.current = choice
        return self.current


# ---------------------------------------------------------------------------
# 5. Offset plans
# ---------------------------------------------------------------------------

OFFSET_PLAN_NAMES = ["OP1 inbound (eastbound) wave", "OP2 outbound (westbound) wave",
                     "OP3 balanced (simultaneous)", "OP4 alternate"]


def offsets_for_plan(plan: int, positions: Sequence[float], ref_index: int,
                     speed: float, cycle: float) -> List[float]:
    """Offsets (s, relative to the reference intersection's cycle start).

    OP1: progression for eastbound traffic: offset = travel time from ref
    OP2: progression for westbound traffic: offset = -travel time from ref
    OP3: all intersections start together (good for short, balanced links)
    OP4: alternate - every second intersection shifted by half a cycle
         (gives two-way progression when link travel time ~ C/2)
    """
    x0 = positions[ref_index]
    out = []
    for k, x in enumerate(positions):
        tt = (x - x0) / speed
        if plan == 0:
            o = tt
        elif plan == 1:
            o = -tt
        elif plan == 2:
            o = 0.0
        else:
            o = (cycle / 2.0) * ((k - ref_index) % 2)
        out.append(o % cycle)
    return out


def select_offset_plan(vk_east: float, vk_west: float, link_tt: float,
                       cycle: float, low_volume: float = 3.0,
                       ratio: float = 1.3) -> int:
    """Choose an offset plan from directional reconstituted volumes (VK).

    The dominant direction gets the green wave; balanced flows get a
    simultaneous or alternate pattern depending on how link travel time
    compares with half the cycle.
    """
    if vk_east + vk_west < low_volume:
        return 2
    if vk_east > ratio * vk_west:
        return 0
    if vk_west > ratio * vk_east:
        return 1
    return 3 if abs(link_tt - cycle / 2.0) < 0.2 * cycle else 2


# ---------------------------------------------------------------------------
# 6. Marriage / divorce of subsystems
# ---------------------------------------------------------------------------

@dataclass
class MarriageParams:
    marry_vk: float = 18.0      # link VK per cycle above which linking pays off
    divorce_vk: float = 10.0    # hysteresis: divorce below this
    max_cycle_gap: float = 25.0 # cycles must be compatible to marry
    votes_needed: int = 3       # consecutive votes to change state


class MarriageLogic:
    """Decides, cycle by cycle, whether two adjacent subsystems should run
    on a common cycle (married) or independently (divorced).

    Married subsystems adopt the larger of the two required cycle lengths
    and share one master clock so offsets between them are meaningful.
    Hysteresis (different marry/divorce thresholds) plus consecutive votes
    stop the pair flip-flopping.
    """

    def __init__(self, params: MarriageParams = MarriageParams(), married: bool = False):
        self.p = params
        self.married = married
        self.streak = 0

    def vote(self, link_vk: float, cycle_a: float, cycle_b: float) -> bool:
        if self.married:
            want = link_vk >= self.p.divorce_vk
        else:
            want = (link_vk >= self.p.marry_vk and
                    abs(cycle_a - cycle_b) <= self.p.max_cycle_gap)
        if want != self.married:
            self.streak += 1
            if self.streak >= self.p.votes_needed:
                self.married, self.streak = want, 0
        else:
            self.streak = 0
        return self.married


# ---------------------------------------------------------------------------
# 7. Webster (for comparison with fixed-time design)
# ---------------------------------------------------------------------------

def webster_cycle(lost_time: float, flow_ratios: Sequence[float]) -> float:
    """Webster's optimum fixed cycle: C0 = (1.5 L + 5) / (1 - Y)."""
    Y = sum(flow_ratios)
    if Y >= 0.95:
        return float("inf")
    return (1.5 * lost_time + 5.0) / (1.0 - Y)
