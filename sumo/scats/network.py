"""
scats.network - builds the SUMO test networks used by every level.

A corridor of `n` signalised intersections J1..Jn on an east-west arterial,
each with a north and south side street. Generated from plain XML with
netconvert so you can change geometry from Python (spacing, lanes, lengths).

Arterial approaches have 3 lanes:  lane0 = right+through, lane1 = through,
lane2 = exclusive left turn (so a protected turn phase can be measured).
Side streets have 2 lanes:         lane0 = right+through, lane1 = through+left.

Every incoming lane gets a stop-line induction loop ("loop_<lane id>")
2 m before the stop line - the SUMO equivalent of a SCATS stop-line detector.
"""
from __future__ import annotations

import math
import os
import subprocess
from typing import Dict, List, Tuple

from sumolib import checkBinary

SPEED = 13.89  # 50 km/h


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def corridor_geometry(n: int, spacing: float, side_len: float, end_len: float):
    nodes: Dict[str, Tuple[float, float, str]] = {}
    xs = [i * spacing for i in range(n)]
    nodes["W"] = (-end_len, 0.0, "dead_end")
    nodes["E"] = (xs[-1] + end_len, 0.0, "dead_end")
    for i, x in enumerate(xs, start=1):
        nodes[f"J{i}"] = (x, 0.0, "traffic_light")
        nodes[f"N{i}"] = (x, side_len, "dead_end")
        nodes[f"S{i}"] = (x, -side_len, "dead_end")
    arterial = ["W"] + [f"J{i}" for i in range(1, n + 1)] + ["E"]
    edges: List[Tuple[str, str, str, int]] = []  # id, from, to, lanes
    for a, b in zip(arterial[:-1], arterial[1:]):
        edges.append((f"{a}_{b}", a, b, 3))
        edges.append((f"{b}_{a}", b, a, 3))
    for i in range(1, n + 1):
        for s in ("N", "S"):
            edges.append((f"{s}{i}_J{i}", f"{s}{i}", f"J{i}", 2))
            edges.append((f"J{i}_{s}{i}", f"J{i}", f"{s}{i}", 2))
    return nodes, edges, xs


def _turn(nodes, frm: str, via: str, to: str) -> str:
    """Classify a movement frm->via->to as 's', 'l' or 'r' from geometry."""
    ax, ay = nodes[via][0] - nodes[frm][0], nodes[via][1] - nodes[frm][1]
    bx, by = nodes[to][0] - nodes[via][0], nodes[to][1] - nodes[via][1]
    cross = ax * by - ay * bx
    if abs(cross) < 1e-6 * (math.hypot(ax, ay) * math.hypot(bx, by)):
        return "s"
    return "l" if cross > 0 else "r"


def build_corridor(outdir: str, n: int = 1, spacing: float = 300.0,
                   side_len: float = 200.0, end_len: float = 300.0) -> dict:
    """Generate <outdir>/corridor.net.xml and <outdir>/loops.add.xml.

    Returns a dict with paths and geometry useful to the controllers.
    """
    os.makedirs(outdir, exist_ok=True)
    nodes, edges, xs = corridor_geometry(n, spacing, side_len, end_len)

    nod = ['<nodes>']
    for nid, (x, y, t) in nodes.items():
        nod.append(f'  <node id="{nid}" x="{x:.2f}" y="{y:.2f}" type="{t}"/>')
    nod.append('</nodes>')

    edg = ['<edges>']
    for eid, a, b, lanes in edges:
        edg.append(f'  <edge id="{eid}" from="{a}" to="{b}" numLanes="{lanes}" speed="{SPEED}"/>')
    edg.append('</edges>')

    # explicit lane-to-lane connections
    con = ['<connections>']
    by_to = {}
    for eid, a, b, lanes in edges:
        by_to.setdefault(b, []).append((eid, a, lanes))
    out_of = {}
    for eid, a, b, lanes in edges:
        out_of.setdefault(a, []).append((eid, b, lanes))
    for j in [k for k in nodes if k.startswith("J")]:
        for in_id, frm, in_lanes in by_to[j]:
            for out_id, to, out_lanes in out_of[j]:
                if to == frm:
                    continue  # no U-turns
                turn = _turn(nodes, frm, j, to)
                if in_lanes == 3:  # arterial approach
                    pairs = {"s": [(0, 0), (1, 1)], "r": [(0, 0)], "l": [(2, out_lanes - 1)]}[turn]
                else:              # side-street approach
                    pairs = {"s": [(0, 0), (1, 1)], "r": [(0, 0)], "l": [(1, out_lanes - 1)]}[turn]
                for fl, tl in pairs:
                    con.append(f'  <connection from="{in_id}" to="{out_id}" fromLane="{fl}" toLane="{tl}"/>')
    con.append('</connections>')

    p = lambda name: os.path.join(outdir, name)
    _write(p("corridor.nod.xml"), "\n".join(nod))
    _write(p("corridor.edg.xml"), "\n".join(edg))
    _write(p("corridor.con.xml"), "\n".join(con))

    net = p("corridor.net.xml")
    subprocess.run([checkBinary("netconvert"),
                    "--node-files", p("corridor.nod.xml"),
                    "--edge-files", p("corridor.edg.xml"),
                    "--connection-files", p("corridor.con.xml"),
                    "--tls.default-type", "static",
                    "--no-turnarounds", "true",
                    "--output-file", net, "--no-warnings", "true"],
                   check=True, stdout=subprocess.DEVNULL)

    # stop-line loops on every lane entering a junction
    add = ['<additional>']
    for eid, a, b, lanes in edges:
        if b.startswith("J"):
            length = spacing if (a.startswith("J")) else (end_len if a in ("W", "E") else side_len)
            for li in range(lanes):
                add.append(f'  <inductionLoop id="loop_{eid}_{li}" lane="{eid}_{li}" '
                           f'pos="-2" period="86400" file="NUL"/>')
    add.append('</additional>')
    _write(p("loops.add.xml"), "\n".join(add))

    return {"net": net, "loops": p("loops.add.xml"), "xs": xs, "n": n,
            "spacing": spacing, "nodes": nodes}


# ---------------------------------------------------------------------------
# demand
# ---------------------------------------------------------------------------

VTYPES = """  <vType id="car" vClass="passenger" length="4.8" minGap="2.2" accel="2.6" decel="4.5" sigma="0.4" speedDev="0.1"/>
  <vType id="truck" vClass="truck" length="12.0" minGap="2.5" accel="1.3" decel="4.0" sigma="0.4"/>
  <vType id="bus" vClass="bus" length="12.0" minGap="2.5" accel="1.2" decel="4.0" sigma="0.2" color="0,160,255"/>
"""


def write_demand(path: str, n: int, periods: List[dict], bus_headway: float = 0,
                 truck_share: float = 0.05, seed_tag: str = "") -> None:
    """Write a .rou.xml with time-varying flows.

    periods: list of dicts {begin, end, east, west, side, turn}
      east/west : through veh/h on the arterial (whole corridor)
      side      : veh/h per side-street approach (N->S and S->N)
      turn      : veh/h per arterial left/right turn into each side street
    """
    rows = []  # (begin, xml) - sorted before writing, SUMO wants departure order
    fid = 0

    def flow(frm, to, vph, b, e, vtype="car"):
        nonlocal fid
        if vph <= 0:
            return
        fid += 1
        rows.append((b, f'  <flow id="f{fid}{seed_tag}" type="{vtype}" begin="{b}" end="{e}" '
                     f'from="{frm}" to="{to}" vehsPerHour="{vph:.1f}" departLane="best" departSpeed="max"/>'))

    for per in periods:
        b, e = per["begin"], per["end"]
        tshare = truck_share
        for vtype, share in (("car", 1 - tshare), ("truck", tshare)):
            flow("W_J1", f"J{n}_E", per["east"] * share, b, e, vtype)
            flow("E_J%d" % n, "J1_W", per["west"] * share, b, e, vtype)
        for i in range(1, n + 1):
            flow(f"N{i}_J{i}", f"J{i}_S{i}", per["side"], b, e)
            flow(f"S{i}_J{i}", f"J{i}_N{i}", per["side"], b, e)
            t = per.get("turn", 0)
            flow("W_J1", f"J{i}_N{i}", t, b, e)    # eastbound left
            flow("W_J1", f"J{i}_S{i}", t, b, e)    # eastbound right
            flow("E_J%d" % n, f"J{i}_S{i}", t, b, e)  # westbound left
            flow("E_J%d" % n, f"J{i}_N{i}", t, b, e)  # westbound right
            flow(f"N{i}_J{i}", f"J{n}_E", per.get("side_turn", 0), b, e)
            flow(f"S{i}_J{i}", "J1_W", per.get("side_turn", 0), b, e)
    if bus_headway > 0:
        end = max(pp["end"] for pp in periods)
        rows.append((30, f'  <flow id="busE{seed_tag}" type="bus" begin="30" end="{end}" period="{bus_headway}" '
                         f'from="W_J1" to="J{n}_E" departLane="0"/>'))
        rows.append((60, f'  <flow id="busW{seed_tag}" type="bus" begin="60" end="{end}" period="{bus_headway}" '
                         f'from="E_J{n}" to="J1_W" departLane="0"/>'))
    rows.sort(key=lambda r: r[0])
    _write(path, "\n".join(['<routes>', VTYPES.rstrip()] + [r[1] for r in rows] + ['</routes>']))
