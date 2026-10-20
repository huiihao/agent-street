#!/usr/bin/env python
"""Analysis, tables and figures for the Agent Street ablation study."""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon, rankdata

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "experiments" / "results"
V1 = ROOT / "experiments" / "results_v1"
FIG = ROOT / "experiments" / "figures"
PAPER_FIG = ROOT / "paper" / "figures"
TABLES = RESULTS / "tables"
for directory in (FIG, PAPER_FIG, TABLES):
    directory.mkdir(parents=True, exist_ok=True)

CONDITIONS = ["static", "imitation_only", "no_imitation", "full"]
LABELS = {
    "static": "Static priors",
    "imitation_only": "Imitation only",
    "no_imitation": "Learning only",
    "full": "Full",
}
SHORT = {
    "static": "Static",
    "imitation_only": "Imit.",
    "no_imitation": "Learn",
    "full": "Full",
}
COLORS = {
    "static": "#6b6b6b",
    "imitation_only": "#1baf7a",
    "no_imitation": "#eb6834",
    "full": "#2a78d6",
}
LINESTYLES = {
    "static": (0, (1, 1)),
    "imitation_only": (0, (4, 2)),
    "no_imitation": (0, (6, 2, 2, 2)),
    "full": "-",
}
FAMILIES = ["momentum", "mean_reversion", "sentiment", "contrarian", "balanced"]
FAMILY_COLORS = {
    "momentum": "#2a78d6",
    "mean_reversion": "#eb6834",
    "sentiment": "#1baf7a",
    "contrarian": "#eda100",
    "balanced": "#9085e9",
}
PRIMARY = [
    "aggregateReturn",
    "meanMaxDrawdown",
    "strategyDiversity",
    "returnSD",
    "meanTradeSynchrony",
    "meanAbsOrderImbalance",
]
PRIMARY_LABELS = {
    "aggregateReturn": "Aggregate return (\\%)",
    "meanMaxDrawdown": "Max drawdown (\\%)",
    "strategyDiversity": "Strategy diversity",
    "returnSD": "Cross-sectional return SD (\\%)",
    "meanTradeSynchrony": "Trade synchrony",
    "meanAbsOrderImbalance": "|Order imbalance|",
}
CONTRASTS = [
    ("full", "static"),
    ("no_imitation", "static"),
    ("imitation_only", "static"),
    ("full", "no_imitation"),
    ("full", "imitation_only"),
]
SECONDARY = [
    "totalTrades",
    "totalConversations",
    "meanWinRate",
    "finalTrustDensity",
    "meanSocialCascade",
    "guildMomentum",
    "guildMeanReversion",
    "guildSentiment",
    "guildContrarian",
    "guildBalanced",
    "strategyGeneration",
    "totalAdaptations",
]


def configure_style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 8,
        "axes.titlesize": 9,
        "axes.labelsize": 8,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": "#e3e3df",
        "grid.linewidth": 0.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def rank_biserial(x, y):
    diff = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    diff = diff[np.abs(diff) > 1e-15]
    if len(diff) == 0:
        return 0.0
    ranks = rankdata(np.abs(diff))
    positive = ranks[diff > 0].sum()
    negative = ranks[diff < 0].sum()
    return (positive - negative) / (positive + negative)


def paired_tests(runs):
    piv = runs.pivot(index="seed", columns="condition")
    rng = np.random.default_rng(2026)
    rows = []
    for a, b in CONTRASTS:
        metrics = PRIMARY + SECONDARY
        raw = []
        for metric in metrics:
            x = piv[metric][a].astype(float).to_numpy()
            y = piv[metric][b].astype(float).to_numpy()
            diff = x - y
            if np.allclose(diff, 0):
                p = 1.0
            else:
                p = wilcoxon(x, y, alternative="two-sided", zero_method="wilcox").pvalue
            boot = []
            for _ in range(5000):
                idx = rng.integers(0, len(diff), len(diff))
                boot.append(diff[idx].mean())
            lo, hi = np.percentile(boot, [2.5, 97.5])
            raw.append({
                "contrast": f"{a} - {b}",
                "condition_a": a,
                "condition_b": b,
                "metric": metric,
                "mean_a": x.mean(),
                "mean_b": y.mean(),
                "mean_diff": diff.mean(),
                "ci_lo": lo,
                "ci_hi": hi,
                "p": p,
                "rank_biserial": rank_biserial(x, y),
            })
        # Holm correction within the six primary outcomes
        primary = [row for row in raw if row["metric"] in PRIMARY]
        order = np.argsort([row["p"] for row in primary])
        adjusted = [1.0] * len(primary)
        running = 0.0
        for rank, idx in enumerate(order):
            value = min(1.0, (len(primary) - rank) * primary[idx]["p"])
            running = max(running, value)
            adjusted[idx] = running
        for idx, row in enumerate(primary):
            row["p_holm"] = adjusted[idx]
        for row in raw:
            if row["metric"] not in PRIMARY:
                row["p_holm"] = np.nan
        rows.extend(raw)
    return pd.DataFrame(rows)


def build_observer_windows(reports_path, ticks_path):
    ticks = pd.read_csv(ticks_path).sort_values(["condition", "seed", "tick"])
    reports = pd.read_csv(reports_path)
    social = reports[reports.observer == "social_engineer"].copy()
    rows = []
    for (condition, seed), group in ticks.groupby(["condition", "seed"]):
        g = group.sort_values("tick")
        ta = g.tick.to_numpy()
        equity = g.totalEquity.to_numpy()
        sentiment = g.sentiment.to_numpy()
        sync = g.tradeSynchrony.to_numpy()
        imbalance = g.orderImbalance.to_numpy()
        disp = g.dispersion.to_numpy()
        avg = g.avgReturn.to_numpy()
        soc = social[(social.condition == condition) & (social.seed == seed)]
        for _, report in soc.iterrows():
            tick = int(report.tick)
            pos = int(np.searchsorted(ta, tick))
            if pos >= len(ta) or ta[pos] != tick:
                continue
            i0 = int(np.searchsorted(ta, tick, side="right"))
            i1 = int(np.searchsorted(ta, tick + 20, side="right"))
            if i1 - i0 < 10:
                continue
            window = slice(i0, i1)
            base = equity[pos]
            rows.append({
                "condition": condition,
                "seed": seed,
                "tick": tick,
                "cascadeScore": report.get("cascadeScore", np.nan),
                "flowRiskScore": report.get("flowRiskScore", np.nan),
                "flowSynchrony": report.get("flowSynchrony", np.nan),
                "flowImbalance": report.get("flowImbalance", np.nan),
                "polarization": report.get("polarization", np.nan),
                "trustDensity": report.get("trustDensity", np.nan),
                "dominantShare": report.get("dominantShare", np.nan),
                "diversity": report.get("diversity", np.nan),
                "imitationRecent": report.get("imitationRecent", np.nan),
                "currentSynchrony": sync[pos],
                "currentAbsImbalance": abs(imbalance[pos]),
                "futureSynchrony": sync[window].mean(),
                "futureAbsImbalance": np.abs(imbalance[window]).mean(),
                "futureDispersion": disp[window].mean(),
                "futureAbsReturn": np.abs(avg[window]).mean(),
                "futureEquityDD": equity[window].min() / base - 1.0,
                "futureAbsDD": abs(equity[window].min() / base - 1.0),
                "futureReturn": equity[i1 - 1] / base - 1.0,
            })
    return pd.DataFrame(rows)


def observer_correlations(windows, level="run"):
    if level == "run":
        frame = windows.groupby(["condition", "seed"]).mean(numeric_only=True).reset_index()
    else:
        frame = windows.copy()
    predictors = [
        "cascadeScore", "flowRiskScore", "flowSynchrony", "flowImbalance",
        "polarization", "imitationRecent", "currentSynchrony", "currentAbsImbalance",
    ]
    outcomes = ["futureSynchrony", "futureAbsImbalance", "futureAbsDD", "futureReturn"]
    rng = np.random.default_rng(2027)
    rows = []
    for predictor in predictors:
        for outcome in outcomes:
            sub = frame[[predictor, outcome]].dropna()
            if len(sub) < 10 or sub[predictor].nunique() < 3 or sub[outcome].nunique() < 3:
                continue
            result = spearmanr(sub[predictor], sub[outcome])
            boot = []
            nboot = 4000 if level == "run" else 400
            x = sub[predictor].to_numpy()
            y = sub[outcome].to_numpy()
            for _ in range(nboot):
                idx = rng.integers(0, len(x), len(x))
                if len(np.unique(x[idx])) < 3 or len(np.unique(y[idx])) < 3:
                    continue
                boot.append(spearmanr(x[idx], y[idx]).statistic)
            lo, hi = np.percentile(boot, [2.5, 97.5]) if boot else (np.nan, np.nan)
            rows.append({
                "level": level,
                "predictor": predictor,
                "outcome": outcome,
                "rho": result.statistic,
                "p": result.pvalue,
                "ci_lo": lo,
                "ci_hi": hi,
                "n": len(sub),
            })
    return pd.DataFrame(rows)


def save_figure(fig, name):
    for directory in (FIG, PAPER_FIG):
        fig.savefig(directory / f"{name}.pdf", bbox_inches="tight")
        fig.savefig(directory / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def figure_dynamics(ticks):
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.4), sharex=True)
    specs = [
        ("strategyDiversity", "Strategy diversity", None),
        ("tradeSynchrony", "Trade synchrony", None),
        ("orderImbalance", "|Order imbalance|", "abs"),
        ("strategyGeneration", "Strategy generation", None),
    ]
    for ax, (metric, title, transform) in zip(axes.flat, specs):
        for condition in CONDITIONS:
            subset = ticks[ticks.condition == condition].sort_values(["seed", "tick"]).copy()
            if transform == "abs":
                subset["value"] = subset[metric].abs()
            else:
                subset["value"] = subset[metric]
            # Per-seed rolling mean removes tick-level noise; the band is a 95%
            # CI across seeds, not a ±1 SD envelope of the raw series.
            subset["smoothed"] = subset.groupby("seed")["value"].transform(
                lambda series: series.rolling(20, min_periods=5).mean()
            )
            grouped = subset.groupby("tick")["smoothed"].agg(["mean", "std", "count"]).reset_index()
            n = grouped["count"].clip(lower=1)
            ci = 1.96 * grouped["std"].fillna(0) / np.sqrt(n)
            ax.plot(
                grouped["tick"], grouped["mean"],
                color=COLORS[condition], linestyle=LINESTYLES[condition],
                linewidth=1.4, label=LABELS[condition],
            )
            ax.fill_between(
                grouped["tick"],
                grouped["mean"] - ci,
                grouped["mean"] + ci,
                color=COLORS[condition], alpha=0.10, linewidth=0,
            )
        ax.set_title(title, loc="left")
        ax.grid(True, axis="y")
        ax.set_xlim(0, ticks.tick.max())
    axes[0, 1].set_ylim(0, 1.05)
    axes[1, 0].set_ylim(0, 1.05)
    axes[0, 0].set_ylabel("diversity")
    axes[0, 1].set_ylabel("synchrony")
    axes[1, 0].set_ylabel("abs. imbalance")
    axes[1, 1].set_ylabel("generation")
    for ax in axes[1]:
        ax.set_xlabel("simulation tick")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save_figure(fig, "fig_dynamics")


def figure_primary(runs):
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.2))
    transforms = {
        "aggregateReturn": lambda s: s * 100,
        "meanMaxDrawdown": lambda s: abs(s) * 100,
        "strategyDiversity": lambda s: s,
        "returnSD": lambda s: s * 100,
        "meanTradeSynchrony": lambda s: s,
        "meanAbsOrderImbalance": lambda s: s,
    }
    for ax, metric in zip(axes.flat, PRIMARY):
        data = [transforms[metric](runs[runs.condition == c][metric].astype(float)) for c in CONDITIONS]
        bp = ax.boxplot(
            data, widths=0.55, patch_artist=True, showfliers=False,
            medianprops={"color": "#222222", "linewidth": 1.2},
            whiskerprops={"color": "#777777", "linewidth": 0.8},
            capprops={"color": "#777777", "linewidth": 0.8},
            boxprops={"linewidth": 0.8},
        )
        for patch, condition in zip(bp["boxes"], CONDITIONS):
            patch.set_facecolor(COLORS[condition])
            patch.set_alpha(0.35)
            patch.set_edgecolor(COLORS[condition])
        rng = np.random.default_rng(4)
        for index, (condition, values) in enumerate(zip(CONDITIONS, data), start=1):
            jitter = rng.uniform(-0.12, 0.12, len(values))
            ax.scatter(
                np.full(len(values), index) + jitter, values,
                s=9, color=COLORS[condition], alpha=0.8, linewidth=0,
            )
        ax.set_xticks(range(1, len(CONDITIONS) + 1))
        ax.set_xticklabels([SHORT[c] for c in CONDITIONS], rotation=0)
        ax.set_title(PRIMARY_LABELS[metric].replace("\\%", "%"), loc="left")
        ax.grid(True, axis="y")
        if metric == "aggregateReturn":
            ax.axhline(0, color="#999999", linewidth=0.7)
    fig.tight_layout()
    save_figure(fig, "fig_primary")


def figure_guilds(runs):
    means = []
    for condition in CONDITIONS:
        subset = runs[runs.condition == condition]
        means.append({
            "condition": condition,
            **{family: subset[f"guild{family.title().replace('_', '')}"].mean() for family in FAMILIES},
        })
    frame = pd.DataFrame(means).set_index("condition").loc[CONDITIONS]
    fig, ax = plt.subplots(figsize=(6.6, 2.8))
    left = np.zeros(len(frame))
    for family in FAMILIES:
        values = frame[family].to_numpy()
        ax.barh(
            range(len(frame)), values, left=left,
            color=FAMILY_COLORS[family], edgecolor="white", linewidth=0.8,
            label=family.replace("_", " ").title(),
        )
        left += values
    ax.set_yticks(range(len(frame)))
    ax.set_yticklabels([LABELS[c] for c in CONDITIONS])
    ax.set_xlabel("mean number of traders")
    ax.grid(True, axis="x")
    ax.legend(ncol=5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    ax.invert_yaxis()
    fig.tight_layout()
    save_figure(fig, "fig_guilds")


def figure_strategy_field(agents, runs):
    fig, axes = plt.subplots(2, 2, figsize=(6.4, 4.4), sharex=True, sharey=True)
    for ax, condition in zip(axes.flat, CONDITIONS):
        subset = runs[runs.condition == condition]
        target = subset.strategyDiversity.median()
        seed = subset.iloc[(subset.strategyDiversity - target).abs().argsort()].iloc[0].seed
        data = agents[(agents.condition == condition) & (agents.seed == seed)]
        for family in FAMILIES:
            fam = data[data.family == family]
            ax.scatter(
                fam.w_trend, fam.w_reversion,
                s=22, color=FAMILY_COLORS[family], edgecolor="white", linewidth=0.6,
                label=family.replace("_", " ").title() if condition == CONDITIONS[0] else None,
                alpha=0.95,
            )
        ax.set_title(f"{LABELS[condition]} (seed {int(seed)})", loc="left")
        ax.set_xlabel("trend weight")
        ax.set_ylabel("reversion weight")
        ax.grid(True)
        ax.set_xlim(0, 0.6)
        ax.set_ylim(0, 0.6)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save_figure(fig, "fig_strategy_field")


def figure_observer(v1_windows, v2_windows):
    v1 = v1_windows.groupby(["condition", "seed"]).mean(numeric_only=True).reset_index()
    v2 = v2_windows.groupby(["condition", "seed"]).mean(numeric_only=True).reset_index()
    merged = v2[["condition", "seed", "flowRiskScore", "polarization", "futureAbsDD"]].merge(
        v1[["condition", "seed", "cascadeScore"]], on=["condition", "seed"], how="left",
    )
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.5))
    panels = [
        ("flowRiskScore", "Flow risk score (v2)", axes[0]),
        ("cascadeScore", "Composite score (v1)", axes[1]),
        ("polarization", "Polarization", axes[2]),
    ]
    for predictor, xlabel, ax in panels:
        sub = merged[[predictor, "futureAbsDD", "condition"]].dropna()
        for condition in CONDITIONS:
            part = sub[sub.condition == condition]
            ax.scatter(part[predictor], part.futureAbsDD * 100,
                       s=12, color=COLORS[condition], alpha=0.8, linewidth=0, label=LABELS[condition])
        if len(sub) >= 10:
            result = spearmanr(sub[predictor], sub.futureAbsDD)
            slope, intercept = np.polyfit(sub[predictor], sub.futureAbsDD * 100, 1)
            xs = np.linspace(sub[predictor].min(), sub[predictor].max(), 20)
            ax.plot(xs, slope * xs + intercept, color="#222222", linewidth=1)
            ax.text(
                0.03, 0.96,
                f"$\\rho$={result.statistic:+.2f}\n$p$={result.pvalue:.1e}",
                transform=ax.transAxes, va="top", fontsize=6.5,
            )
        ax.set_xlabel(xlabel)
        ax.set_ylabel("future |drawdown| (%)")
        ax.grid(True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.05))
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save_figure(fig, "fig_observer")


def main():
    configure_style()
    runs = pd.read_csv(RESULTS / "run_summary.csv")
    ticks = pd.read_csv(RESULTS / "tick_metrics.csv")
    agents = pd.read_csv(RESULTS / "agent_metrics.csv")
    reliability = json.loads((RESULTS / "reliability.json").read_text())
    metadata = json.loads((ROOT / "experiments" / "data" / "snapshot_metadata.json").read_text())
    run_config = json.loads((RESULTS / "run_config.json").read_text())

    # Condition summary
    summary_rows = []
    for condition in CONDITIONS:
        subset = runs[runs.condition == condition]
        row = {"condition": condition, "n": len(subset)}
        for metric in PRIMARY + SECONDARY:
            row[f"{metric}_mean"] = subset[metric].mean()
            row[f"{metric}_sd"] = subset[metric].std(ddof=1)
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(TABLES / "condition_means.csv", index=False)

    tests = paired_tests(runs)
    tests.to_csv(TABLES / "paired_tests.csv", index=False)

    guild_means = []
    for condition in CONDITIONS:
        subset = runs[runs.condition == condition]
        guild_means.append({
            "condition": condition,
            **{family: subset[f"guild{family.title().replace('_', '')}"].mean() for family in FAMILIES},
        })
    guilds = pd.DataFrame(guild_means)
    guilds.to_csv(TABLES / "guild_composition.csv", index=False)

    v2_windows = build_observer_windows(RESULTS / "observer_reports.csv", RESULTS / "tick_metrics.csv")
    v1_windows = build_observer_windows(V1 / "observer_reports.csv", V1 / "tick_metrics.csv")
    v2_windows.to_csv(RESULTS / "observer_windows.csv", index=False)
    v1_windows.to_csv(V1 / "observer_windows.csv", index=False)

    obs_runs_v2 = observer_correlations(v2_windows, "run")
    obs_runs_v1 = observer_correlations(v1_windows, "run")
    obs_reports_v2 = observer_correlations(v2_windows, "report")
    obs_reports_v1 = observer_correlations(v1_windows, "report")
    obs_runs_v2["version"] = "v2"
    obs_runs_v1["version"] = "v1"
    obs_reports_v2["version"] = "v2"
    obs_reports_v1["version"] = "v1"
    observer_table = pd.concat([obs_runs_v1, obs_runs_v2], ignore_index=True)
    observer_reports_table = pd.concat([obs_reports_v1, obs_reports_v2], ignore_index=True)
    observer_table.to_csv(TABLES / "observer_correlations_run.csv", index=False)
    observer_reports_table.to_csv(TABLES / "observer_correlations_report.csv", index=False)

    reliability_table = pd.DataFrame([
        {"check": "runs", "value": reliability["runs"]},
        {"check": "invariant_failures", "value": reliability["total_invariant_failures"]},
        {"check": "all_weight_sums_ok", "value": reliability["all_weight_sums_ok"]},
        {"check": "all_trust_symmetric", "value": reliability["all_trust_symmetric"]},
        {"check": "all_conversation_participants_ok", "value": reliability["all_conversation_participants_ok"]},
        {"check": "all_trades_valid", "value": reliability["all_trades_valid"]},
        {"check": "all_tick_metrics_finite", "value": reliability["all_tick_metrics_finite"]},
        {"check": "snapshot_sha256", "value": metadata["sha256"]},
        {"check": "snapshot_bars", "value": metadata["bars"]},
        {"check": "crosscheck_all_exact", "value": all(
            item.get("max_relative_difference") == 0.0 for item in metadata["crosscheck"].values()
        )},
    ])
    reliability_table.to_csv(TABLES / "reliability.csv", index=False)

    figure_dynamics(ticks)
    figure_primary(runs)
    figure_guilds(runs)
    figure_strategy_field(agents, runs)
    figure_observer(v1_windows, v2_windows)

    # A compact JSON for paper writing and downstream checks.
    def rec(df, **filters):
        for key, value in filters.items():
            df = df[df[key] == value]
        return df.to_dict(orient="records")

    paper_numbers = {
        "snapshot": metadata,
        "run_config": run_config,
        "condition_means": summary.to_dict(orient="records"),
        "primary_tests": tests[tests.metric.isin(PRIMARY)].to_dict(orient="records"),
        "secondary_tests": tests[tests.metric.isin(SECONDARY)].to_dict(orient="records"),
        "guild_composition": guilds.to_dict(orient="records"),
        "observer_run_correlations_v1": obs_runs_v1.to_dict(orient="records"),
        "observer_run_correlations_v2": obs_runs_v2.to_dict(orient="records"),
        "observer_report_correlations_v2": obs_reports_v2.to_dict(orient="records"),
        "reliability": reliability,
    }
    (RESULTS / "results.json").write_text(json.dumps(paper_numbers, indent=2, default=str), encoding="utf-8")

    print("condition means")
    print(summary.round(5).to_string(index=False))
    print("\nprimary paired tests")
    print(tests[tests.metric.isin(PRIMARY)].round(5).to_string(index=False))
    print("\nobserver run-level v1")
    print(obs_runs_v1.round(4).to_string(index=False))
    print("\nobserver run-level v2")
    print(obs_runs_v2.round(4).to_string(index=False))
    print("\nfigures written to", FIG)
    print("tables written to", TABLES)


if __name__ == "__main__":
    main()
