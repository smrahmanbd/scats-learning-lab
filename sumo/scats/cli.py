"""Shared command-line options for the level scripts."""
import argparse
import os
import sys


def parser(desc: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--gui", action="store_true", help="open sumo-gui for the SCATS run")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--end", type=float, default=None, help="demand duration in seconds")
    p.add_argument("--out", default=None, help="output folder (default: results/<level>)")
    return p


def outdir(args, level: str) -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = args.out or os.path.join(here, "results", level)
    os.makedirs(d, exist_ok=True)
    return d


def write_summary(rows, path):
    import csv
    keys = [k for k in rows[0].keys() if not k.startswith("_")]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in keys})
