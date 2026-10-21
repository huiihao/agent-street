#!/usr/bin/env python
"""Multi-window replication, phase-map, network, benchmark and OOS audit."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon
from sklearn.metrics import roc_auc_score, roc_curve

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.analyze_results import (  # noqa: E402
    COLORS, CONDITIONS, FAMILY_COLORS, LABELS, SHORT,
    build_observer_windows, configure_style,
)

RESULTS = ROOT / "experiments" / "results"
WINDOW_RESULTS = ROOT / "experiments" / "results_windows"
SWEEP_RESULTS = ROOT / "experiments" / "results_sweep"
WINDOW_DATA = ROOT / "experiments" / "data" / "windows"
FIG = ROOT / "experiments" / "figures"
PAPER_FIG = ROOT / "paper" / "figures"
TABLES = RESULTS / "tables"
for directory in (FIG, PAPER_FIG, TABLES):
    directory.mkdir(parents=True, exist_ok=True)

WINDOW_LABELS = {
    "discovery": "Discovery",
    "w1_2026_08_24": "W1",
    "w2_2026_08_31": "W2",
    "w3_2026_09_14": "W3",
    "w4_2026_09_21": "W4",
    "w5_2026_09_28": "W5",
    "w6_2026_10_05": "W6",
}
CONTRASTS = [
    ("full", "static"),
    ("no_imitation", "static"),
    ("imitation_only", "static"),
    ("full", "no_imitation"),
]
EFFECT_METRICS = [
    "aggregateReturn", "drawdownMagnitude", "strategyDiversity",
    "returnSD", "meanTradeSynchrony", "meanAbsOrderImbalance", "meanExposure",
]


def save_figure(fig, name):
    for directory in (FIG, PAPER_FIG):
        fig.savefig(directory / f"{name}.pdf", bbox_inches="tight")
        fig.savefig(directory / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def market_stats(path: Path, start: int = 30, ticks: int = 300) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    closes = {s: [row[3] for row in rows] for s, rows in payload["bars"].items()}
    end = min(start + ticks - 1, len(payload["times"]) - 1)
    eq = [
        sum(closes[s][i] / closes[s][start] for s in closes) / len(closes)
        for i in range(start, end + 1)
    ]
    returns = [math.log(eq[i] / eq[i - 1]) for i in range(1, len(eq)) if eq[i - 1] > 0]
    peak, max_dd = eq[0], 0.0
    for value in eq:
        peak = max(peak, value)
        max_dd = min(max_dd, value / peak - 1.0)
    vol = float(np.std(returns, ddof=1) * math.sqrt(78 * 252)) if len(returns) > 1 else 0.0
    return {
        "start_index": start,
        "end_index": end,
        "return": eq[-1] - 1.0,
        "max_drawdown": max_dd,
        "annualized_vol": vol,
        "per_symbol_return": {
            s: closes[s][end] / closes[s][start] - 1.0 for s in closes
        },
    }


def load_runs():
    main = pd.read_csv(RESULTS / "run_summary.csv")
    main["window"] = "discovery"
    frames = [main]
    for directory in sorted(WINDOW_RESULTS.glob("w*")):
        frame = pd.read_csv(directory / "run_summary.csv")
        frame["window"] = directory.name
        frames.append(frame)
    runs = pd.concat(frames, ignore_index=True)
    runs["drawdownMagnitude"] = -runs["meanMaxDrawdown"]
    return runs


def load_window_metadata():
    meta = {}
    main_meta = json.loads(
        (ROOT / "experiments" / "data" / "snapshot_metadata.json").read_text()
    )
    meta["discovery"] = {
        **main_meta,
        "path": ROOT / "experiments" / "data" / "market_snapshot_5m_5d.json",
    }
    for directory in sorted(WINDOW_DATA.glob("w*")):
        item = json.loads((directory / "snapshot_metadata.json").read_text())
        item["path"] = directory / "market_snapshot_5m_5d.json"
        meta[directory.name] = item
    for name, item in meta.items():
        item["experiment_market"] = market_stats(Path(item["path"]))
        item["label"] = WINDOW_LABELS.get(name, name)
    return meta


def paired_diffs(runs, a, b, metric, window=None):
    frame = runs if window is None else runs[runs.window == window]
    pivot = frame.pivot_table(
        index=["window", "seed"], columns="condition", values=metric, aggfunc="mean",
    )
    if a not in pivot or b not in pivot:
        return pd.Series(dtype=float)
    return (pivot[a] - pivot[b]).dropna()


def bootstrap_mean(values, n=4000, seed=42):
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = [rng.choice(values, len(values), replace=True).mean() for _ in range(n)]
    return values.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def window_cluster_bootstrap(by_window, n=4000, seed=42):
    rng = np.random.default_rng(seed)
    windows = list(by_window)
    values = []
    for _ in range(n):
        chosen = rng.choice(len(windows), len(windows), replace=True)
        sample = np.concatenate([by_window[windows[i]] for i in chosen])
        values.append(sample.mean())
    return np.percentile(values, [2.5, 97.5])


def effect_rows(runs, meta):
    windows = [name for name in meta if name != "discovery"]
    rows = []
    for scope in ["discovery"] + windows + ["heldout"]:
        frame = runs[runs.window == scope] if scope not in ("discovery", "heldout") else (
            runs[runs.window == "discovery"] if scope == "discovery"
            else runs[runs.window.isin(windows)]
        )
        for a, b in CONTRASTS:
            for metric in EFFECT_METRICS:
                diffs = paired_diffs(frame, a, b, metric)
                if len(diffs) == 0:
                    continue
                if scope == "heldout":
                    grouped = {
                        window: paired_diffs(runs, a, b, metric, window).to_numpy()
                        for window in windows
                    }
                    lo, hi = window_cluster_bootstrap(grouped)
                else:
                    _, lo, hi = bootstrap_mean(diffs)
                p = wilcoxon(diffs, alternative="two-sided").pvalue if np.any(diffs != 0) else 1.0
                rows.append({
                    "scope": scope,
                    "contrast": f"{a} - {b}",
                    "condition_a": a,
                    "condition_b": b,
                    "metric": metric,
                    "mean_diff": diffs.mean(),
                    "ci_lo": lo,
                    "ci_hi": hi,
                    "p": p,
                    "positive": float((diffs > 0).mean()),
                    "negative": float((diffs < 0).mean()),
                    "n": int(len(diffs)),
                })
    return pd.DataFrame(rows)


def observer_tables():
    frames = []
    main_windows = build_observer_windows(
        RESULTS / "observer_reports.csv", RESULTS / "tick_metrics.csv",
    )
    main_windows["window"] = "discovery"
    frames.append(main_windows)
    for directory in sorted(WINDOW_RESULTS.glob("w*")):
        frame = build_observer_windows(
            directory / "observer_reports.csv", directory / "tick_metrics.csv",
        )
        frame["window"] = directory.name
        frames.append(frame)
    observations = pd.concat(frames, ignore_index=True)
    observations["scope"] = np.where(
        observations.window == "discovery", "discovery", "heldout",
    )
    predictors = [
        "flowRiskScore", "cascadeScore", "polarization",
        "imitationRecent", "currentSynchrony", "currentAbsImbalance",
    ]
    outcomes = ["futureSynchrony", "futureAbsImbalance", "futureAbsDD", "futureReturn"]
    rng = np.random.default_rng(2028)
    correlations = []
    for scope, frame in observations.groupby("scope"):
        agg = frame.groupby(
            ["window", "condition", "seed"]
        ).mean(numeric_only=True).reset_index()
        for predictor in predictors:
            for outcome in outcomes:
                sub = agg[[predictor, outcome]].dropna()
                x, y = sub[predictor].to_numpy(), sub[outcome].to_numpy()
                if len(sub) < 10 or len(np.unique(x)) < 3 or len(np.unique(y)) < 3:
                    continue
                result = spearmanr(x, y)
                boot = []
                for _ in range(3000):
                    idx = rng.integers(0, len(x), len(x))
                    if len(np.unique(x[idx])) < 3 or len(np.unique(y[idx])) < 3:
                        continue
                    boot.append(spearmanr(x[idx], y[idx]).statistic)
                lo, hi = np.percentile(boot, [2.5, 97.5]) if boot else (np.nan, np.nan)
                correlations.append({
                    "scope": scope, "predictor": predictor, "outcome": outcome,
                    "rho": result.statistic, "p": result.pvalue,
                    "ci_lo": lo, "ci_hi": hi, "n": len(sub),
                })
    correlations = pd.DataFrame(correlations)

    aucs = []
    for scope, frame in observations.groupby("scope"):
        threshold = frame.futureAbsDD.quantile(0.75)
        for predictor in ["flowRiskScore", "cascadeScore", "polarization",
                          "imitationRecent", "currentSynchrony"]:
            sub = frame[[predictor, "futureAbsDD"]].dropna()
            event = (sub.futureAbsDD > threshold).astype(int)
            if event.nunique() < 2:
                continue
            auc = roc_auc_score(event, sub[predictor])
            run_keys = frame.loc[
                sub.index, ["window", "condition", "seed"]
            ].astype(str).agg("|".join, axis=1).to_numpy()
            positions = {key: np.where(run_keys == key)[0] for key in np.unique(run_keys)}
            boot = []
            for _ in range(1000):
                chosen = rng.choice(list(positions), len(positions), replace=True)
                idx = np.concatenate([positions[key] for key in chosen])
                part = sub.iloc[idx]
                ev = (part.futureAbsDD > threshold).astype(int)
                if ev.nunique() > 1:
                    boot.append(roc_auc_score(ev, part[predictor]))
            lo, hi = np.percentile(boot, [2.5, 97.5]) if boot else (np.nan, np.nan)
            aucs.append({
                "scope": scope, "predictor": predictor, "threshold": threshold,
                "auc": auc, "ci_lo": lo, "ci_hi": hi, "n": len(sub),
            })

    # Run-level version: one row per run, event = top quartile of the run's
    # maximum future drawdown / synchrony. This matches the discovery-window
    # audit and shows how much of the apparent signal is pseudo-replication.
    run_agg = observations.groupby(
        ["scope", "window", "condition", "seed"]
    ).agg(
        flowRiskScore=("flowRiskScore", "mean"),
        cascadeScore=("cascadeScore", "mean"),
        polarization=("polarization", "mean"),
        futureAbsDD=("futureAbsDD", "max"),
        futureSynchrony=("futureSynchrony", "max"),
        futureAbsImbalance=("futureAbsImbalance", "max"),
    ).reset_index()
    run_aucs = []
    for scope, frame in run_agg.groupby("scope"):
        for outcome in ["futureAbsDD", "futureSynchrony"]:
            threshold = frame[outcome].quantile(0.75)
            event = (frame[outcome] > threshold).astype(int)
            if event.nunique() < 2:
                continue
            for predictor in ["flowRiskScore", "cascadeScore", "polarization"]:
                sub = frame[[predictor, outcome]].dropna()
                ev = (sub[outcome] > threshold).astype(int)
                if ev.nunique() < 2:
                    continue
                auc = roc_auc_score(ev, sub[predictor])
                boot = []
                for _ in range(1000):
                    idx = rng.integers(0, len(sub), len(sub))
                    part = sub.iloc[idx]
                    ev_boot = (part[outcome] > threshold).astype(int)
                    if ev_boot.nunique() > 1:
                        boot.append(roc_auc_score(ev_boot, part[predictor]))
                lo, hi = np.percentile(boot, [2.5, 97.5]) if boot else (np.nan, np.nan)
                run_aucs.append({
                    "scope": scope, "outcome": outcome, "predictor": predictor,
                    "threshold": threshold, "auc": auc,
                    "ci_lo": lo, "ci_hi": hi, "n": len(sub),
                    "events": int(ev.sum()),
                })
    return observations, correlations, pd.DataFrame(aucs), pd.DataFrame(run_aucs)


def sweep_tables():
    sweep = pd.read_csv(SWEEP_RESULTS / "run_summary.csv")
    sweep["drawdownMagnitude"] = -sweep["meanMaxDrawdown"]
    metrics = [
        ("aggregateReturn", "Return (%)", 100.0, "YlGnBu"),
        ("drawdownMagnitude", "Max drawdown (%)", 100.0, "YlOrRd"),
        ("meanTradeSynchrony", "Trade synchrony", 1.0, "YlOrRd"),
        ("strategyDiversity", "Strategy diversity", 1.0, "viridis"),
        ("returnSD", "Return SD (%)", 100.0, "YlOrRd"),
        ("meanExposure", "Exposure (%)", 100.0, "Blues"),
    ]
    long_rows = []
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 4.4))
    for ax, (metric, title, scale, cmap) in zip(axes.flat, metrics):
        table = sweep.pivot_table(
            index="learningScale", columns="imitationScale",
            values=metric, aggfunc="mean",
        ).sort_index().sort_index(axis=1)
        for learning in table.index:
            for imitation in table.columns:
                long_rows.append({
                    "metric": metric, "learningScale": learning,
                    "imitationScale": imitation, "mean": table.loc[learning, imitation],
                    "sd": sweep[
                        (sweep.learningScale == learning)
                        & (sweep.imitationScale == imitation)
                    ][metric].std(),
                    "n": len(sweep[
                        (sweep.learningScale == learning)
                        & (sweep.imitationScale == imitation)
                    ]),
                })
        values = table.to_numpy() * scale
        image = ax.imshow(values, origin="lower", aspect="auto", cmap=cmap)
        ax.set_xticks(range(len(table.columns)))
        ax.set_xticklabels([f"{v:g}" for v in table.columns])
        ax.set_yticks(range(len(table.index)))
        ax.set_yticklabels([f"{v:g}" for v in table.index])
        ax.set_xlabel("imitation scale")
        ax.set_ylabel("learning scale")
        ax.set_title(title, loc="left")
        if metric in ("aggregateReturn", "strategyDiversity"):
            best = np.unravel_index(np.nanargmax(values), values.shape)
        else:
            best = np.unravel_index(np.nanargmin(values), values.shape)
        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                value = values[i, j]
                text = f"{value:.1f}" if scale == 100.0 else f"{value:.3f}"
                ax.text(
                    j, i, text, ha="center", va="center", fontsize=5.5,
                    color="white" if image.norm(value) > 0.55 else "#222222",
                )
        ax.scatter(best[1], best[0], marker="*", s=90,
                   facecolors="none", edgecolors="white", linewidths=0.9)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(
        "Learning x imitation scale (mutation fixed at 1x; discovery window, 8 seeds)",
        y=1.02, fontsize=9,
    )
    fig.tight_layout()
    save_figure(fig, "fig_phase_map")
    pd.DataFrame(long_rows).to_csv(TABLES / "sweep_summary.csv", index=False)
    return sweep


def windows_figure(effects):
    display = [
        ("aggregateReturn", "Return effect (pp)", 100.0),
        ("meanTradeSynchrony", "Synchrony effect", 1.0),
        ("strategyDiversity", "Diversity effect", 1.0),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(7.6, 3.8), sharey=True)
    contrasts = [
        ("full - static", COLORS["full"], "o"),
        ("no_imitation - static", COLORS["no_imitation"], "s"),
        ("imitation_only - static", COLORS["imitation_only"], "^"),
    ]
    scopes = ["discovery", "w1_2026_08_24", "w2_2026_08_31", "w3_2026_09_14",
              "w4_2026_09_21", "w5_2026_09_28", "w6_2026_10_05", "heldout"]
    labels = ["Discovery", "W1", "W2", "W3", "W4", "W5", "W6", "Held-out"]
    for ax, (metric, title, scale) in zip(axes, display):
        for offset, (contrast, color, marker) in zip([-0.22, 0.0, 0.22], contrasts):
            for row, scope in enumerate(scopes):
                sub = effects[
                    (effects.scope == scope) & (effects.contrast == contrast)
                    & (effects.metric == metric)
                ]
                if sub.empty:
                    continue
                item = sub.iloc[0]
                left = max(0.0, (item.mean_diff - item.ci_lo) * scale)
                right = max(0.0, (item.ci_hi - item.mean_diff) * scale)
                ax.errorbar(
                    item.mean_diff * scale, row + offset, xerr=[[left], [right]],
                    fmt=marker, color=color, markersize=4, capsize=2, linewidth=1,
                )
        ax.axvline(0, color="#888888", linewidth=0.8)
        ax.set_title(title, loc="left")
        ax.grid(True, axis="x")
        ax.set_yticks(range(len(scopes)))
        ax.set_yticklabels(labels)
    handles = [
        plt.Line2D([], [], color=color, marker=marker, linestyle="none", label=contrast)
        for contrast, color, marker in contrasts
    ]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save_figure(fig, "fig_windows_forest")


def observer_figure(correlations, aucs):
    fig, axes = plt.subplots(1, 3, figsize=(7.6, 2.7))
    outcomes = ["futureSynchrony", "futureAbsImbalance", "futureAbsDD"]
    outcome_labels = ["Future synchrony", "Future |imbalance|", "Future |drawdown|"]
    for offset, scope, color in zip([-0.12, 0.12], ["discovery", "heldout"],
                                    ["#2a78d6", "#eb6834"]):
        for row, outcome in enumerate(outcomes):
            sub = correlations[
                (correlations.scope == scope)
                & (correlations.predictor == "flowRiskScore")
                & (correlations.outcome == outcome)
            ]
            if sub.empty:
                continue
            item = sub.iloc[0]
            axes[0].errorbar(
                item.rho, row + offset,
                xerr=[[max(0, item.rho - item.ci_lo)], [max(0, item.ci_hi - item.rho)]],
                fmt="o", color=color, markersize=4, capsize=2, linewidth=1,
            )
    axes[0].axvline(0, color="#888888", linewidth=0.8)
    axes[0].set_yticks(range(len(outcomes)))
    axes[0].set_yticklabels(outcome_labels)
    axes[0].set_xlabel("Spearman rho (flow risk)")
    axes[0].set_title("Flow risk vs future outcomes", loc="left")
    axes[0].grid(True, axis="x")
    axes[0].legend(handles=[
        plt.Line2D([], [], color="#2a78d6", marker="o", linestyle="none", label="Discovery"),
        plt.Line2D([], [], color="#eb6834", marker="o", linestyle="none", label="Held-out"),
    ], frameon=False, fontsize=6)

    predictors = ["flowRiskScore", "cascadeScore", "polarization"]
    labels = ["Flow risk", "v1 composite", "Polarization"]
    for offset, scope, color in zip([-0.12, 0.12], ["discovery", "heldout"],
                                    ["#2a78d6", "#eb6834"]):
        for row, predictor in enumerate(predictors):
            sub = correlations[
                (correlations.scope == scope)
                & (correlations.predictor == predictor)
                & (correlations.outcome == "futureAbsDD")
            ]
            if sub.empty:
                continue
            item = sub.iloc[0]
            axes[1].errorbar(
                item.rho, row + offset,
                xerr=[[max(0, item.rho - item.ci_lo)], [max(0, item.ci_hi - item.rho)]],
                fmt="o", color=color, markersize=4, capsize=2, linewidth=1,
            )
    axes[1].axvline(0, color="#888888", linewidth=0.8)
    axes[1].set_yticks(range(len(predictors)))
    axes[1].set_yticklabels(labels)
    axes[1].set_xlabel("Spearman rho (future |drawdown|)")
    axes[1].set_title("Sign instability", loc="left")
    axes[1].grid(True, axis="x")

    predictors = ["flowRiskScore", "cascadeScore", "polarization", "currentSynchrony"]
    labels = ["Flow", "v1", "Polar.", "Sync."]
    for offset, scope, color in zip([-0.12, 0.12], ["discovery", "heldout"],
                                    ["#2a78d6", "#eb6834"]):
        for row, predictor in enumerate(predictors):
            sub = aucs[(aucs.scope == scope) & (aucs.predictor == predictor)]
            if sub.empty:
                continue
            item = sub.iloc[0]
            axes[2].errorbar(
                item.auc, row + offset,
                xerr=[[max(0, item.auc - item.ci_lo)], [max(0, item.ci_hi - item.auc)]],
                fmt="o", color=color, markersize=4, capsize=2, linewidth=1,
            )
    axes[2].axvline(0.5, color="#888888", linewidth=0.8, linestyle="--")
    axes[2].set_yticks(range(len(predictors)))
    axes[2].set_yticklabels(labels)
    axes[2].set_xlabel("AUC for high future |drawdown|")
    axes[2].set_title("Event discrimination", loc="left")
    axes[2].set_xlim(0.35, 0.75)
    axes[2].grid(True, axis="x")
    fig.tight_layout()
    save_figure(fig, "fig_observer_oos")


def network_analysis():
    events = pd.read_csv(RESULTS / "imitation_events.csv")
    agents = pd.read_csv(RESULTS / "agent_metrics.csv")
    rows = []
    for condition, group in events.groupby("condition"):
        indegree = group.teacher.value_counts()
        shares = indegree / indegree.sum()
        hhi = float((shares ** 2).sum())
        rows.append({
            "condition": condition,
            "events": len(group),
            "runs": group.seed.nunique(),
            "events_per_run": len(group) / group.seed.nunique(),
            "unique_teachers": group.teacher.nunique(),
            "unique_learners": group.learner.nunique(),
            "effective_teachers": 1.0 / hhi if hhi else 0.0,
            "mean_trust": group.trust.mean(),
            "fitness_gap": (group.teacherFitness - group.learnerFitness).mean(),
            "family_change_rate": (
                group.learnerFamilyBefore != group.learnerFamilyAfter
            ).mean(),
            "top_locations": "|".join(
                f"{location}:{count}"
                for location, count in group.location.value_counts().head(4).items()
            ),
        })
    table = pd.DataFrame(rows)
    table.to_csv(TABLES / "imitation_network.csv", index=False)

    full = events[events.condition == "full"]
    edge_counts = full.groupby(["teacher", "learner"]).size().reset_index(name="count")
    edge_counts = edge_counts.sort_values("count", ascending=False).head(30)
    final = agents[agents.condition == "full"]
    modal_family = final.groupby("agent").family.agg(
        lambda series: series.mode().iloc[0]
    )
    node_ids = sorted(modal_family.index)
    graph = nx.DiGraph()
    graph.add_nodes_from(node_ids)
    for _, row in edge_counts.iterrows():
        if row.teacher in graph and row.learner in graph:
            graph.add_edge(row.teacher, row.learner, weight=row["count"])
    indegree = full.teacher.value_counts()
    positions = nx.circular_layout(graph)
    fig, axes = plt.subplots(
        1, 2, figsize=(7.4, 3.2), gridspec_kw={"width_ratios": [1.25, 1.0]},
    )
    ax = axes[0]
    nx.draw_networkx_edges(
        graph, positions, ax=ax, edge_color="#9aa4b6", alpha=0.35,
        width=[0.4 + 0.25 * graph[u][v]["weight"] for u, v in graph.edges()],
        arrows=True, arrowsize=6, connectionstyle="arc3,rad=0.08",
    )
    for family, color in FAMILY_COLORS.items():
        nodes = [node for node in node_ids if modal_family.get(node) == family]
        if nodes:
            nx.draw_networkx_nodes(
                graph, positions, nodelist=nodes, ax=ax, node_color=color,
                node_size=[180 + 35 * indegree.get(node, 0) for node in nodes],
                edgecolors="white", linewidths=0.6,
            )
    nx.draw_networkx_labels(graph, positions, ax=ax, font_size=5.5)
    ax.set_title("Imitation network (full, 16 seeds; top 30 edges)", loc="left")
    ax.axis("off")
    ax.legend(handles=[
        plt.Line2D([], [], marker="o", linestyle="none", color=color,
                   label=family.replace("_", " ").title())
        for family, color in FAMILY_COLORS.items()
    ], frameon=False, fontsize=5.5, loc="lower left", ncol=2)
    location_counts = full.location.value_counts()
    axes[1].barh(
        range(len(location_counts)), location_counts.values,
        color="#5a9ed4", edgecolor="white", linewidth=0.6,
    )
    axes[1].set_yticks(range(len(location_counts)))
    axes[1].set_yticklabels(
        [location.replace("_", " ") for location in location_counts.index]
    )
    axes[1].set_xlabel("imitation events (full, 16 seeds)")
    axes[1].set_title("Where imitation happens", loc="left")
    axes[1].grid(True, axis="x")
    axes[1].invert_yaxis()
    fig.tight_layout()
    save_figure(fig, "fig_network")
    return table, edge_counts


def benchmark_analysis(runs, meta):
    rows = []
    for window, item in meta.items():
        market = item["experiment_market"]
        for condition in CONDITIONS:
            subset = runs[(runs.window == window) & (runs.condition == condition)]
            if subset.empty:
                continue
            rows.append({
                "window": WINDOW_LABELS.get(window, window),
                "market_return": market["return"],
                "market_max_drawdown": market["max_drawdown"],
                "market_vol": market["annualized_vol"],
                "condition": condition,
                "return": subset.aggregateReturn.mean(),
                "drawdown": -subset.meanMaxDrawdown.mean(),
                "exposure": subset.meanExposure.mean(),
                "turnover": subset.meanTurnover.mean(),
                "residual": subset.aggregateReturn.mean()
                - subset.meanExposure.mean() * market["return"],
            })
    table = pd.DataFrame(rows)
    table.to_csv(TABLES / "benchmark.csv", index=False)

    fig, axes = plt.subplots(
        1, 2, figsize=(7.4, 2.8), gridspec_kw={"width_ratios": [1.5, 1.0]},
    )
    ax = axes[0]
    for condition in CONDITIONS:
        part = table[table.condition == condition]
        ax.scatter(
            part.market_return * 100, part["return"] * 100, s=15,
            color=COLORS[condition], alpha=0.85, linewidth=0,
            label=LABELS[condition],
        )
    x = np.linspace(table.market_return.min() * 100,
                    table.market_return.max() * 100, 40)
    ax.plot(x, x, color="#888888", linewidth=0.8, linestyle="--",
            label="100% invested")
    mean_exposure = table.exposure.mean()
    ax.plot(x, mean_exposure * x, color="#222222", linewidth=1.0,
            label=f"mean exposure ({mean_exposure:.0%})")
    ax.axhline(0, color="#bbbbbb", linewidth=0.6)
    ax.axvline(0, color="#bbbbbb", linewidth=0.6)
    ax.set_xlabel("equal-weight market return (%)")
    ax.set_ylabel("agent return (%)")
    ax.set_title("Performance is compressed toward cash", loc="left")
    ax.grid(True)
    ax.legend(frameon=False, fontsize=6)
    axes[1].boxplot(
        [table[table.condition == condition].exposure * 100 for condition in CONDITIONS],
        widths=0.55, showfliers=False,
        medianprops={"color": "#222222", "linewidth": 1},
    )
    axes[1].set_xticks(range(1, len(CONDITIONS) + 1))
    axes[1].set_xticklabels([SHORT[condition] for condition in CONDITIONS])
    axes[1].set_ylabel("mean exposure (%)")
    axes[1].set_title("Exposure by condition", loc="left")
    axes[1].grid(True, axis="y")
    fig.tight_layout()
    save_figure(fig, "fig_benchmark")
    return table


def main():
    configure_style()
    runs = load_runs()
    meta = load_window_metadata()
    effects = effect_rows(runs, meta)
    effects.to_csv(TABLES / "window_effects.csv", index=False)

    regimes = []
    for name, item in meta.items():
        market = item["experiment_market"]
        regimes.append({
            "window": WINDOW_LABELS.get(name, name),
            "snapshot": name,
            "first_utc": item.get("first_utc"),
            "last_utc": item.get("last_utc"),
            "bars": item.get("bars"),
            "experiment_market_return": market["return"],
            "experiment_market_max_drawdown": market["max_drawdown"],
            "experiment_market_vol": market["annualized_vol"],
            "sha256": item.get("sha256"),
        })
    pd.DataFrame(regimes).to_csv(TABLES / "window_regimes.csv", index=False)

    _, correlations, aucs, run_aucs = observer_tables()
    correlations.to_csv(TABLES / "observer_oos.csv", index=False)
    aucs.to_csv(TABLES / "observer_auc_oos.csv", index=False)
    run_aucs.to_csv(TABLES / "observer_run_auc.csv", index=False)
    sweep = sweep_tables()
    windows_figure(effects)
    observer_figure(correlations, aucs)
    network_table, _ = network_analysis()
    benchmark = benchmark_analysis(runs, meta)

    summary = {
        "runs": {
            "discovery": int((runs.window == "discovery").sum()),
            "heldout": int((runs.window != "discovery").sum()),
            "sweep": int(len(sweep)),
            "total": int(len(runs) + len(sweep)),
        },
        "discovery": runs[runs.window == "discovery"].groupby("condition")[
            ["aggregateReturn", "drawdownMagnitude", "strategyDiversity",
             "meanTradeSynchrony", "meanAbsOrderImbalance", "meanExposure"]
        ].mean().round(6).to_dict(orient="index"),
        "heldout": runs[runs.window != "discovery"].groupby("condition")[
            ["aggregateReturn", "drawdownMagnitude", "strategyDiversity",
             "meanTradeSynchrony", "meanAbsOrderImbalance", "meanExposure"]
        ].mean().round(6).to_dict(orient="index"),
        "windows": regimes,
        "effects": effects.to_dict(orient="records"),
        "observer_correlations": correlations.to_dict(orient="records"),
        "observer_auc": aucs.to_dict(orient="records"),
        "observer_run_auc": run_aucs.to_dict(orient="records"),
        "network": network_table.to_dict(orient="records"),
        "benchmark": benchmark.to_dict(orient="records"),
    }
    (RESULTS / "results_extensions.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8",
    )

    print("window regimes")
    print(pd.DataFrame(regimes).round(5).to_string(index=False))
    print("\nheld-out pooled effects (primary)")
    primary = effects[
        (effects.scope == "heldout")
        & (effects.metric.isin([
            "aggregateReturn", "drawdownMagnitude", "strategyDiversity",
            "meanTradeSynchrony", "meanAbsOrderImbalance",
        ]))
    ]
    print(primary.round(6).to_string(index=False))
    print("\nheld-out observer correlations")
    print(correlations[correlations.scope == "heldout"].round(4).to_string(index=False))
    print("\nheld-out observer AUC")
    print(aucs[aucs.scope == "heldout"].round(4).to_string(index=False))
    print("\nnetwork")
    print(network_table.round(4).to_string(index=False))
    print("\nfigures written to", FIG)


if __name__ == "__main__":
    main()
