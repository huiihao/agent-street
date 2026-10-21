#!/usr/bin/env python
"""Target-specific observer audit and delta-flow event study.

Each observer receives one pre-specified target:

  Physicist        avgVol        -> future absolute market return (volatility)
  Mathematician    brokerDegree  -> future trust density (network structure)
  Social Engineer  flowRisk      -> future trade synchrony (coordination)
  Mystic           sentiment     -> future agent return (placebo/persistence)

The six held-out windows are the confirmatory sample.  For each target we
separate the between-run/window relation from the within-window relation, so a
market-level metric such as the Physicist's volatility is not pseudo-replicated
across runs.  The delta-flow experiment asks whether the *change* in flow risk,
rather than its level, is an earlier event-level drawdown signal.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.analyze_results import configure_style  # noqa: E402

RESULTS = ROOT / "experiments" / "results"
WINDOW_RESULTS = ROOT / "experiments" / "results_windows"
FIGURES = [ROOT / "experiments" / "figures", ROOT / "paper" / "figures"]
TABLES = RESULTS / "tables"
for directory in FIGURES + [TABLES]:
    directory.mkdir(parents=True, exist_ok=True)

TARGETS = {
    "physicist": {
        "metric": "d_avgVol",
        "target": "f_absret",
        "label": "future absolute market return",
        "control": None,
        "interpretation": "between-window volatility regime; not a within-window forecast",
    },
    "mathematician": {
        "metric": "d_brokerDegree",
        "target": "f_trust",
        "label": "future trust density",
        "control": "d_components",
        "interpretation": "trust-structure persistence / centrality",
    },
    "social_engineer": {
        "metric": "d_flowRiskScore",
        "target": "f_sync",
        "label": "future trade synchrony",
        "control": "d_flowSynchrony",
        "interpretation": "between-run coordination descriptor; level weak within-run",
    },
    "mystic": {
        "metric": "d_sentiment",
        "target": "f_ret",
        "label": "future agent return",
        "control": None,
        "interpretation": "placebo / current-state persistence; sign unstable",
    },
}


def save_figure(fig, name):
    for directory in FIGURES:
        fig.savefig(directory / f"{name}.pdf", bbox_inches="tight")
        fig.savefig(directory / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def future_stats(tick_frame, tick, horizon=20):
    frame = tick_frame.sort_values("tick")
    a = {c: frame[c].to_numpy() for c in [
        "tick", "totalEquity", "tradeSynchrony", "orderImbalance",
        "dispersion", "avgReturn", "conversations", "totalAdaptations",
        "trustDensity",
    ]}
    pos = int(np.searchsorted(a["tick"], tick))
    if pos >= len(a["tick"]) or a["tick"][pos] != tick:
        return None
    i0 = pos + 1
    i1 = int(np.searchsorted(a["tick"], tick + horizon, side="right"))
    if i1 - i0 < max(10, horizon // 4):
        return None
    sl = slice(i0, i1)
    base = a["totalEquity"][pos]
    return {
        "f_sync": a["tradeSynchrony"][sl].mean(),
        "f_absimb": np.abs(a["orderImbalance"][sl]).mean(),
        "f_absdd": abs(a["totalEquity"][sl].min() / base - 1.0),
        "f_ret": a["totalEquity"][i1 - 1] / base - 1.0,
        "f_disp": a["dispersion"][sl].mean(),
        "f_absret": np.abs(a["avgReturn"][sl]).mean(),
        "f_conv": a["conversations"][sl].sum(),
        "f_adapt": a["totalAdaptations"][sl].sum() - a["totalAdaptations"][pos],
        "f_trust": a["trustDensity"][i1 - 1],
    }


def load_reports(reports_path, ticks_path, scope, window):
    reports = pd.read_csv(reports_path)
    flat = pd.json_normalize(reports["data"].apply(json.loads))
    flat.index = reports.index
    rep = pd.concat([reports.drop(columns=["data"]), flat.add_prefix("d_")], axis=1)
    ticks = pd.read_csv(ticks_path)
    rows = []
    for (condition, seed), group in ticks.groupby(["condition", "seed"]):
        tick_frame = group.sort_values("tick")
        subset = rep[(rep.condition == condition) & (rep.seed == seed)]
        for _, report in subset.iterrows():
            stats = future_stats(tick_frame, int(report.tick), 20)
            if stats is None:
                continue
            row = {
                "scope": scope, "window": window,
                "condition": condition, "seed": int(seed),
                "tick": int(report.tick), "observer": report.observer,
                "confidence": report.confidence,
            }
            row.update(stats)
            for key in [
                "d_avgVol", "d_sentiment", "d_components", "d_brokerDegree",
                "d_flowRiskScore", "d_flowSynchrony", "d_flowImbalance",
                "d_polarization", "d_trustDensity", "d_dominantShare",
                "d_diversity", "d_imitationRecent", "d_cascadeScore",
            ]:
                if key in report and pd.notna(report[key]):
                    row[key] = report[key]
            rows.append(row)
    return pd.DataFrame(rows)


def safe_spearman(x, y):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(x) < 4 or len(np.unique(x)) < 3 or len(np.unique(y)) < 3:
        return np.nan, np.nan
    result = spearmanr(x, y)
    return result.statistic, result.pvalue


def bootstrap_rho(x, y, nboot=4000, seed=42):
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(nboot):
        idx = rng.integers(0, len(x), len(x))
        if len(np.unique(np.asarray(x)[idx])) < 3 or len(np.unique(np.asarray(y)[idx])) < 3:
            continue
        values.append(spearmanr(np.asarray(x)[idx], np.asarray(y)[idx]).statistic)
    return (
        np.percentile(values, 2.5) if values else np.nan,
        np.percentile(values, 97.5) if values else np.nan,
    )


def partial_rho(x, y, z):
    xr, yr, zr = rankdata(x), rankdata(y), rankdata(z)
    Z = np.column_stack([np.ones(len(zr)), zr])
    bx = np.linalg.lstsq(Z, xr, rcond=None)[0]
    by = np.linalg.lstsq(Z, yr, rcond=None)[0]
    return spearmanr(xr - Z @ bx, yr - Z @ by)


def holm(pvalues):
    order = np.argsort(pvalues)
    adjusted = np.empty(len(pvalues))
    running = 0.0
    for rank, index in enumerate(order):
        value = min(1.0, (len(pvalues) - rank) * pvalues[index])
        running = max(running, value)
        adjusted[index] = running
    return adjusted


def target_table(obs):
    records = []
    for observer, spec in TARGETS.items():
        metric, target = spec["metric"], spec["target"]
        subset = obs[obs.observer == observer].dropna(subset=[metric, target]).copy()
        rows = {}
        for scope in ["discovery", "heldout"]:
            frame = subset[subset.scope == scope].copy()
            frame["xr"] = frame.groupby("window")[metric].transform(rankdata)
            frame["yr"] = frame.groupby("window")[target].transform(rankdata)
            within_rho, within_p = safe_spearman(frame.xr, frame.yr)
            keys = ["window", "condition", "seed"]
            agg = {metric: "mean", target: "mean"}
            if spec["control"]:
                agg[spec["control"]] = "mean"
            run = frame.groupby(keys).agg(agg).reset_index()
            window = frame.groupby("window").agg(agg).reset_index()
            run_rho, run_p = safe_spearman(run[metric], run[target])
            window_rho, window_p = safe_spearman(window[metric], window[target])
            rows[f"{scope}_within_rho"] = within_rho
            rows[f"{scope}_within_p"] = within_p
            rows[f"{scope}_within_n"] = len(frame)
            rows[f"{scope}_run_rho"] = run_rho
            rows[f"{scope}_run_p"] = run_p
            rows[f"{scope}_run_n"] = len(run)
            rows[f"{scope}_window_rho"] = window_rho
            rows[f"{scope}_window_p"] = window_p
            rows[f"{scope}_window_n"] = len(window)
            if scope == "heldout":
                rows["heldout_run_ci_lo"], rows["heldout_run_ci_hi"] = bootstrap_rho(
                    run[metric].to_numpy(), run[target].to_numpy(),
                )
                if spec["control"]:
                    partial = partial_rho(
                        run[metric].to_numpy(), run[target].to_numpy(),
                        run[spec["control"]].to_numpy(),
                    )
                    rows["partial_rho"] = partial.statistic
                    rows["partial_p"] = partial.pvalue
                else:
                    rows["partial_rho"] = np.nan
                    rows["partial_p"] = np.nan
        if observer == "physicist":
            rows["primary_p"] = rows["heldout_window_p"]
            rows["between_label"] = "window (n=6)"
        else:
            rows["primary_p"] = rows["heldout_run_p"]
            rows["between_label"] = "run (n=192)"
        rows.update({
            "observer": observer, "metric": metric, "target": target,
            "target_label": spec["label"], "control": spec["control"] or "",
            "interpretation": spec["interpretation"],
        })
        records.append(rows)
    table = pd.DataFrame(records)
    table["holm_p"] = holm(table.primary_p.to_numpy())
    table = table[[
        "observer", "metric", "target", "target_label",
        "discovery_within_rho", "discovery_within_p",
        "heldout_within_rho", "heldout_within_p",
        "heldout_run_rho", "heldout_run_ci_lo", "heldout_run_ci_hi",
        "heldout_run_p", "heldout_run_n",
        "heldout_window_rho", "heldout_window_p", "heldout_window_n",
        "primary_p", "holm_p", "between_label",
        "partial_rho", "partial_p", "control", "interpretation",
    ]]
    table.to_csv(TABLES / "observer_targets.csv", index=False)
    return table


def social_delta(obs):
    social = obs[obs.observer == "social_engineer"].copy()
    social = social.sort_values(["scope", "window", "condition", "seed", "tick"])
    social["flow"] = social["d_flowRiskScore"]
    social["delta_flow"] = social.groupby(
        ["scope", "window", "condition", "seed"]
    ).flow.diff()
    for lag in [-2, -1, 1]:
        social[f"flow_lag{lag}"] = social.groupby(
            ["scope", "window", "condition", "seed"]
        ).flow.shift(-lag)
        social[f"delta_lag{lag}"] = social.groupby(
            ["scope", "window", "condition", "seed"]
        ).delta_flow.shift(-lag)
    return social.dropna(subset=["flow", "delta_flow"])


def auc_bootstrap(frame, predictor, outcome, threshold, cluster_cols, nboot=1500, seed=42):
    sub = frame[[predictor, outcome]].dropna()
    event = (sub[outcome] > threshold).astype(int)
    if event.nunique() < 2:
        return None
    auc = roc_auc_score(event, sub[predictor])
    keys = frame.loc[sub.index, cluster_cols].astype(str).agg("|".join, axis=1).to_numpy()
    positions = {key: np.where(keys == key)[0] for key in np.unique(keys)}
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(nboot):
        chosen = rng.choice(list(positions), len(positions), replace=True)
        idx = np.concatenate([positions[key] for key in chosen])
        part = sub.iloc[idx]
        ev = (part[outcome] > threshold).astype(int)
        if ev.nunique() > 1:
            boot.append(roc_auc_score(ev, part[predictor]))
    lo, hi = np.percentile(boot, [2.5, 97.5]) if boot else (np.nan, np.nan)
    return {"auc": auc, "ci_lo": lo, "ci_hi": hi, "n": len(sub), "events": int(event.sum())}


def delta_flow_tests(social):
    predictors = [
        "flow", "delta_flow", "flowSynchrony",
        "flow_lag-1", "delta_lag-1", "flow_lag-2", "delta_lag-2",
    ]
    auc_rows = []
    for scope in ["discovery", "heldout"]:
        frame = social[social.scope == scope].copy()
        threshold = frame.f_absdd.quantile(0.75)
        for predictor in predictors:
            if predictor not in frame:
                continue
            result = auc_bootstrap(
                frame, predictor, "f_absdd", threshold,
                ["window", "condition", "seed"],
            )
            if result:
                auc_rows.append({
                    "scope": scope, "level": "report", "predictor": predictor,
                    "outcome": "future_absdd", "threshold": threshold, **result,
                })
        agg = {predictor: "mean" for predictor in predictors if predictor in frame}
        agg["f_absdd"] = "max"
        run = frame.groupby(["window", "condition", "seed"]).agg(agg).reset_index()
        run_threshold = run.f_absdd.quantile(0.75)
        for predictor in predictors:
            if predictor not in run:
                continue
            result = auc_bootstrap(
                run, predictor, "f_absdd", run_threshold,
                ["window", "condition", "seed"],
            )
            if result:
                auc_rows.append({
                    "scope": scope, "level": "run", "predictor": predictor,
                    "outcome": "future_absdd", "threshold": run_threshold, **result,
                })
    auc_table = pd.DataFrame(auc_rows)
    auc_table.to_csv(TABLES / "delta_flow_auc.csv", index=False)

    event_rows = []
    for scope in ["discovery", "heldout"]:
        frame = social[social.scope == scope].copy()
        threshold = frame.f_absdd.quantile(0.75)
        frame["event"] = frame.f_absdd > threshold
        for lag in [-2, -1, 0, 1]:
            level_col = "flow" if lag == 0 else f"flow_lag{lag}"
            delta_col = "delta_flow" if lag == 0 else f"delta_lag{lag}"
            for event, group in frame.groupby("event"):
                sub = group[[level_col, delta_col, "window", "condition", "seed"]].dropna()
                if sub.empty:
                    continue
                for metric, col in [("flow_level", level_col), ("delta_flow", delta_col)]:
                    values = sub[col].to_numpy()
                    keys = sub[["window", "condition", "seed"]].astype(str).agg("|".join, axis=1).to_numpy()
                    positions = {key: np.where(keys == key)[0] for key in np.unique(keys)}
                    rng = np.random.default_rng(2029)
                    boot = []
                    for _ in range(1500):
                        chosen = rng.choice(list(positions), len(positions), replace=True)
                        idx = np.concatenate([positions[key] for key in chosen])
                        boot.append(values[idx].mean())
                    lo, hi = np.percentile(boot, [2.5, 97.5])
                    event_rows.append({
                        "scope": scope, "lag": lag, "event": bool(event),
                        "metric": metric, "mean": values.mean(),
                        "ci_lo": lo, "ci_hi": hi, "n": len(sub),
                    })
    event_table = pd.DataFrame(event_rows)
    event_table.to_csv(TABLES / "delta_flow_event.csv", index=False)
    return auc_table, event_table


def per_window_delta(social):
    """Per-window consistency of the level and delta-flow event signals."""
    predictors = ["flow", "delta_flow", "flow_lag-1", "delta_lag-1", "delta_lag-2"]
    rows = []
    for window, frame in social[social.scope == "heldout"].groupby("window"):
        threshold = frame.f_absdd.quantile(0.75)
        event = frame.f_absdd > threshold
        for predictor in predictors:
            result = auc_bootstrap(
                frame, predictor, "f_absdd", threshold,
                ["condition", "seed"], nboot=300,
            )
            if result:
                rows.append({
                    "window": window, "predictor": predictor,
                    "auc": result["auc"], "n": result["n"],
                    "events": result["events"],
                })
        rows.append({
            "window": window, "predictor": "delta_lag-1_event_minus_non",
            "auc": frame.loc[event, "delta_lag-1"].mean()
            - frame.loc[~event, "delta_lag-1"].mean(),
            "n": len(frame), "events": int(event.sum()),
        })
    table = pd.DataFrame(rows)
    table.to_csv(TABLES / "delta_flow_per_window.csv", index=False)
    return table


def delta_figure(auc_table, event_table):
    fig, axes = plt.subplots(1, 3, figsize=(7.6, 2.8))
    held = event_table[event_table.scope == "heldout"]

    ax = axes[0]
    for event, linestyle, label in [(True, "-", "event"), (False, "--", "non-event")]:
        part = held[(held.metric == "flow_level") & (held.event == event)].sort_values("lag")
        ax.plot(part.lag, part["mean"], linestyle=linestyle, marker="o",
                color="#2a78d6", markersize=3, label=label)
        ax.fill_between(part.lag, part.ci_lo, part.ci_hi, color="#2a78d6", alpha=0.10)
    ax.set_xticks([-2, -1, 0, 1])
    ax.set_xticklabels(["-40", "-20", "0", "+20"])
    ax.set_xlabel("report lag (ticks)")
    ax.set_ylabel("mean flow-risk level")
    ax.set_title("Level is persistent", loc="left")
    ax.grid(True)
    ax.legend(frameon=False, fontsize=6)

    ax = axes[1]
    for event, linestyle, label in [(True, "-", "event"), (False, "--", "non-event")]:
        part = held[(held.metric == "delta_flow") & (held.event == event)].sort_values("lag")
        ax.plot(part.lag, part["mean"], linestyle=linestyle, marker="o",
                color="#eb6834", markersize=3, label=label)
        ax.fill_between(part.lag, part.ci_lo, part.ci_hi, color="#eb6834", alpha=0.10)
    ax.axhline(0, color="#888888", linewidth=0.7)
    ax.set_xticks([-2, -1, 0, 1])
    ax.set_xticklabels(["-40", "-20", "0", "+20"])
    ax.set_xlabel("report lag (ticks)")
    ax.set_ylabel("mean $\\Delta$flow")
    ax.set_title("Change rises before the event", loc="left")
    ax.grid(True)
    ax.legend(frameon=False, fontsize=6)

    ax = axes[2]
    order = ["flow", "delta_flow", "flow_lag-1", "delta_lag-1", "flow_lag-2", "delta_lag-2"]
    labels = {
        "flow": "flow t", "delta_flow": "$\\Delta$flow t",
        "flow_lag-1": "flow t-1", "delta_lag-1": "$\\Delta$flow t-1",
        "flow_lag-2": "flow t-2", "delta_lag-2": "$\\Delta$flow t-2",
    }
    colors = ["#2a78d6", "#eb6834", "#7aa6df", "#f08a62", "#a9c4e8", "#f4b49a"]
    held_auc = auc_table[
        (auc_table.scope == "heldout") & (auc_table.level == "report")
    ].set_index("predictor")
    available = [p for p in order if p in held_auc.index]
    held_auc = held_auc.loc[available]
    positions = np.arange(len(held_auc))
    ax.bar(
        positions, held_auc.auc,
        yerr=[held_auc.auc - held_auc.ci_lo, held_auc.ci_hi - held_auc.auc],
        capsize=2.5, color=colors[:len(held_auc)],
    )
    ax.axhline(0.5, color="#888888", linestyle="--", linewidth=0.8)
    ax.set_xticks(positions)
    ax.set_xticklabels([labels.get(p, p) for p in held_auc.index], rotation=25, ha="right")
    ax.set_ylim(0.35, 0.70)
    ax.set_ylabel("AUC for high future |DD|")
    ax.set_title("Event discrimination (held-out)", loc="left")
    ax.grid(True, axis="y")
    fig.tight_layout()
    save_figure(fig, "fig_delta_flow")


def main():
    configure_style()
    frames = [load_reports(
        RESULTS / "observer_reports.csv", RESULTS / "tick_metrics.csv",
        "discovery", "discovery",
    )]
    for directory in sorted(WINDOW_RESULTS.glob("w*")):
        frames.append(load_reports(
            directory / "observer_reports.csv", directory / "tick_metrics.csv",
            "heldout", directory.name,
        ))
    obs = pd.concat(frames, ignore_index=True)
    obs.to_csv(TABLES / "observer_target_observations.csv", index=False)

    table = target_table(obs)
    social = social_delta(obs)
    social.to_csv(TABLES / "delta_flow_observations.csv", index=False)
    auc_table, event_table = delta_flow_tests(social)
    window_table = per_window_delta(social)
    delta_figure(auc_table, event_table)

    print("observer target table")
    print(table.round(4).to_string(index=False))
    print("\ndelta-flow AUC")
    print(auc_table.round(4).to_string(index=False))
    print("\ndelta-flow event study (held-out)")
    print(event_table[event_table.scope == "heldout"].round(4).to_string(index=False))
    print("\ndelta-flow per-window AUC")
    print(window_table.pivot(index="predictor", columns="window", values="auc").round(3).to_string())
    print("\nfigures written")


if __name__ == "__main__":
    main()
