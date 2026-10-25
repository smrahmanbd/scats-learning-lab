"""Matplotlib helpers that turn controller logs into teaching figures."""
from __future__ import annotations

import os
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLORS = ["#1f6feb", "#d1495b", "#2a9d8f", "#e9a23b", "#7b61ff", "#6c757d"]


def compare_bars(results: List[Dict], path: str, title: str,
                 keys=("avg_delay", "stops_per_veh", "bus_avg_delay")) -> None:
    keys = [k for k in keys if all(r.get(k) is not None for r in results)]
    fig, axes = plt.subplots(1, len(keys), figsize=(4 * len(keys), 3.4))
    if len(keys) == 1:
        axes = [axes]
    labels = [r["label"] for r in results]
    nice = {"avg_delay": "Mean delay (s/veh)", "stops_per_veh": "Stops per vehicle",
            "bus_avg_delay": "Bus delay (s/bus)", "avg_travel_time": "Travel time (s)"}
    for ax, k in zip(axes, keys):
        vals = [r[k] for r in results]
        ax.bar(labels, vals, color=COLORS[:len(vals)])
        ax.set_title(nice.get(k, k), fontsize=10)
        ax.tick_params(axis="x", rotation=25, labelsize=8)
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v:.1f}" if v >= 2 else f"{v:.2f}", ha="center", va="bottom", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def strategic_timeline(log: List[Dict], intersections, path: str, title: str) -> None:
    """Cycle length, CI degree of saturation, offset plan, marriage state and split plans over time."""
    subs = sorted({e["ss"] for e in log})
    fig, axes = plt.subplots(5, 1, figsize=(9, 10), sharex=True,
                             gridspec_kw={"height_ratios": [1.3, 1.1, 0.8, 0.6, 0.9]})
    for i, s in enumerate(subs):
        es = [e for e in log if e["ss"] == s]
        t = [e["t"] / 60 for e in es]
        lab = s + (" (follows SS1 while married)" if i else "")
        axes[0].step(t, [e["C"] for e in es], where="post", color=COLORS[i], label=lab)
        axes[1].plot(t, [e["ds_ci"] for e in es], ".-", color=COLORS[i], label=s, ms=3, lw=1)
        axes[2].step(t, [e["offset_plan"] + 1 for e in es], where="post", color=COLORS[i], label=s)
        mar = [list(e["married"].values())[0][0] if e["married"] else None for e in es]
        if any(m is not None for m in mar):
            axes[3].fill_between(t, [1 if m else 0 for m in mar], step="post", color=COLORS[2], alpha=0.5,
                                 label="SS1 + SS2 married")
    for ix_i, ix in enumerate(intersections):
        t = [r["t"] / 60 for r in ix.history]
        axes[4].step(t, [r["plan"] + 1 + 0.07 * (ix_i - 1.5) for r in ix.history], where="post", lw=1,
                     color=COLORS[ix_i % len(COLORS)], label=ix.tls)
    axes[0].set_ylabel("Cycle (s)")
    axes[1].set_ylabel("DS at CI")
    axes[1].axhline(0.9, color="grey", ls="--", lw=0.8)
    axes[2].set_ylabel("Offset plan")
    axes[2].set_yticks([1, 2, 3, 4], ["OP1 E", "OP2 W", "OP3 sim", "OP4 alt"])
    axes[3].set_ylabel("Married")
    axes[3].set_yticks([0, 1], ["no", "yes"])
    axes[4].set_ylabel("Split plan")
    axes[4].set_yticks([1, 2, 3, 4], ["SP1", "SP2", "SP3", "SP4"])
    axes[4].set_xlabel("Time (min)")
    for ax in axes:
        ax.legend(fontsize=7, loc="upper left", ncol=4)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def ds_by_phase(ix, path: str, title: str) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9, 5.5), sharex=True)
    t = [r["t"] / 60 for r in ix.history]
    axes[0].plot(t, [r["L"] for r in ix.history], color="black", lw=1.2, label="cycle length used")
    for i, p in enumerate(ix.names):
        axes[0].plot(t, [r["g"][p] for r in ix.history], color=COLORS[i], lw=0.9, label=f"green {p}")
        axes[1].plot(t, [r["ds"][p] for r in ix.history], ".-", ms=3, color=COLORS[i], label=f"DS {p}")
    axes[1].axhline(0.9, color="grey", ls="--", lw=0.8, label="target DS")
    axes[0].set_ylabel("Seconds")
    axes[1].set_ylabel("Degree of saturation")
    axes[1].set_xlabel("Time (min)")
    for ax in axes:
        ax.legend(fontsize=7, ncol=4)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def line_compare(xs, series: Dict[str, List[float]], path: str, title: str, xlabel: str, ylabel: str):
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, (k, v) in enumerate(series.items()):
        ax.plot(xs, v, "o-", color=COLORS[i % len(COLORS)], label=k)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=11)
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
