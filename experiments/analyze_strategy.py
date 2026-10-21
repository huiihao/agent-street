#!/usr/bin/env python
"""Genome divergence, guild lineage and within-population dynamics."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.analyze_results import COLORS, CONDITIONS, LABELS, configure_style  # noqa: E402

RESULTS = ROOT / "experiments" / "results"
TABLES = RESULTS / "tables"
FIGURES = [ROOT / "experiments" / "figures", ROOT / "paper" / "figures"]
for directory in FIGURES + [TABLES]:
    directory.mkdir(parents=True, exist_ok=True)

GENES = ["w_trend", "w_reversion", "w_rsi", "w_herding", "w_influence", "w_memory"]
FAMILIES = ["momentum", "mean_reversion", "sentiment", "contrarian", "balanced"]
FAMILY_LABELS = {
    "momentum": "Momentum", "mean_reversion": "Mean rev.",
    "sentiment": "Sentiment", "contrarian": "Contrarian", "balanced": "Balanced",
}


def save(fig, name):
    for directory in FIGURES:
        fig.savefig(directory / f"{name}.pdf", bbox_inches="tight")
        fig.savefig(directory / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    configure_style()
    data = pd.read_csv(RESULTS / "strategy_tick_metrics.csv")
    data = data.dropna(subset=GENES)

    # Pairwise signal-weight distance -------------------------------------------------
    distance_rows = []
    for (condition, seed, tick), group in data.groupby(["condition", "seed", "tick"]):
        matrix = group[GENES].to_numpy(dtype=float)
        distance_rows.append({
            "condition": condition, "seed": seed, "tick": tick,
            "distance": float(np.mean(pdist(matrix, metric="euclidean"))),
        })
    distance = pd.DataFrame(distance_rows)
    summary = distance.groupby(["condition", "tick"]).distance.agg(
        ["mean", "std", "count"]
    ).reset_index()
    summary.to_csv(TABLES / "strategy_distance_trajectory.csv", index=False)

    final_tick = int(data.tick.max())
    final = distance[distance.tick == final_tick]
    final_stats = final.groupby("condition").distance.agg(
        ["mean", "std", "median"]
    ).round(4)
    final_stats.to_csv(TABLES / "strategy_distance_final.csv")

    # Guild switches and initial->final transitions ----------------------------------
    switch_rows = []
    transition_rows = []
    for (condition, seed, agent), group in data.groupby(["condition", "seed", "agent"]):
        group = group.sort_values("tick")
        families = group.family.tolist()
        initial, final_family = families[0], families[-1]
        switch_rows.append({
            "condition": condition, "seed": seed, "agent": agent,
            "initial": initial, "final": final_family,
            "switched": initial != final_family,
            "switch_count": sum(a != b for a, b in zip(families, families[1:])),
        })
        transition_rows.append({
            "condition": condition, "initial": initial, "final": final_family,
        })
    switches = pd.DataFrame(switch_rows)
    transitions = pd.DataFrame(transition_rows)
    switch_summary = switches.groupby("condition").agg(
        agents=("agent", "size"),
        switched=("switched", "sum"),
        switch_rate=("switched", "mean"),
        mean_switches=("switch_count", "mean"),
    ).round(4)
    switch_summary.to_csv(TABLES / "guild_switch_summary_current.csv")

    # Fraction of agents that have switched at least once by each tick.
    first_switch = []
    for (condition, seed, agent), group in data.groupby(["condition", "seed", "agent"]):
        group = group.sort_values("tick")
        families = group.family.tolist()
        tick_values = group.tick.tolist()
        switched = False
        for tick, family in zip(tick_values, families):
            switched = switched or family != families[0]
            first_switch.append({
                "condition": condition, "seed": seed, "agent": agent,
                "tick": tick, "switched": switched,
            })
    switch_curve = pd.DataFrame(first_switch).groupby(
        ["condition", "tick"]
    ).switched.mean().reset_index()
    switch_curve.to_csv(TABLES / "guild_switch_curve.csv", index=False)

    # Transition matrix for full (initial vs final).
    full = transitions[transitions.condition == "full"]
    matrix = pd.crosstab(full.initial, full.final).reindex(
        index=FAMILIES, columns=FAMILIES, fill_value=0
    )

    # Figure -------------------------------------------------------------------------
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 4.8))
    ax = axes[0, 0]
    for condition in CONDITIONS:
        part = summary[summary.condition == condition]
        ax.plot(part.tick, part["mean"], color=COLORS[condition], label=LABELS[condition])
        band = part["std"].fillna(0) / np.sqrt(part["count"].clip(lower=1))
        ax.fill_between(
            part.tick, part["mean"] - 1.96 * band, part["mean"] + 1.96 * band,
            color=COLORS[condition], alpha=0.12, linewidth=0,
        )
    ax.set_xlabel("simulation tick")
    ax.set_ylabel("mean pairwise genome distance")
    ax.set_title("Learning diverges, imitation homogenizes", loc="left")
    ax.grid(True)
    ax.legend(frameon=False, fontsize=6)

    ax = axes[0, 1]
    positions = np.arange(len(CONDITIONS))
    for index, condition in enumerate(CONDITIONS):
        values = final[final.condition == condition].distance.to_numpy()
        jitter = np.linspace(-0.08, 0.08, len(values))
        ax.scatter(
            index + jitter, values, s=8, color=COLORS[condition], alpha=0.45,
            linewidth=0,
        )
        ax.plot(
            [index - 0.22, index + 0.22], [values.mean(), values.mean()],
            color=COLORS[condition], linewidth=1.4,
        )
    ax.set_xticks(positions)
    ax.set_xticklabels([LABELS[c] for c in CONDITIONS], rotation=15)
    ax.set_ylabel(f"genome distance at tick {final_tick}")
    ax.set_title("Final divergence", loc="left")
    ax.grid(True, axis="y")

    ax = axes[1, 0]
    image = ax.imshow(matrix.to_numpy(), cmap="Blues")
    ax.set_xticks(range(len(FAMILIES)))
    ax.set_xticklabels([FAMILY_LABELS[f] for f in FAMILIES], rotation=30, ha="right")
    ax.set_yticks(range(len(FAMILIES)))
    ax.set_yticklabels([FAMILY_LABELS[f] for f in FAMILIES])
    ax.set_xlabel("final guild")
    ax.set_ylabel("initial guild")
    ax.set_title("Full: initial $\\rightarrow$ final guild", loc="left")
    for i in range(len(FAMILIES)):
        for j in range(len(FAMILIES)):
            value = int(matrix.iloc[i, j])
            if value:
                ax.text(j, i, str(value), ha="center", va="center", fontsize=6,
                        color="white" if value > matrix.to_numpy().max() * 0.55 else "#222222")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 1]
    for condition in CONDITIONS:
        part = switch_curve[switch_curve.condition == condition]
        ax.plot(part.tick, part.switched * 100, color=COLORS[condition],
                label=LABELS[condition])
    ax.set_xlabel("simulation tick")
    ax.set_ylabel("agents that ever switched guild (%)")
    ax.set_title("Guild switching (10-tick samples)", loc="left")
    ax.grid(True)
    ax.legend(frameon=False, fontsize=6)

    fig.tight_layout()
    save(fig, "fig_strategy_dynamics")

    table = final_stats.join(switch_summary, how="left")
    table.to_csv(TABLES / "strategy_dynamics.csv")
    print("final genome distance")
    print(final_stats.to_string())
    print("\nguild switches")
    print(switch_summary.to_string())
    print("\ntransition matrix (full)")
    print(matrix.to_string())
    print("figures written")


if __name__ == "__main__":
    main()
