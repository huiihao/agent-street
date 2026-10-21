#!/usr/bin/env python
"""Reproducible experiments for Agent Street.

Designs
-------
base   four mechanism conditions (static / imitation only / learning only / full)
sweep  a 2-D grid of learning-rate and imitation-rate scales

The market path is a frozen, validated snapshot; no network is used during a
run. Every run is seeded and records per-tick metrics, per-agent exposure and
turnover, strategy trajectories, imitation events, observer reports and
reliability checks.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import INITIAL_CASH  # noqa: E402
from backend.engine.market_data import HistoricalDataProvider  # noqa: E402
from backend.engine.simulation import SimulationLoop  # noqa: E402

SNAPSHOT = ROOT / "experiments" / "data" / "market_snapshot_5m_5d.json"
METADATA = ROOT / "experiments" / "data" / "snapshot_metadata.json"
RESULTS = ROOT / "experiments" / "results"

BASE_CONDITIONS = {
    "full": {
        "enable_learning": True, "enable_imitation": True, "enable_mutation": True,
        "learning_scale": 1.0, "imitation_scale": 1.0, "mutation_scale": 1.0,
    },
    "no_imitation": {
        "enable_learning": True, "enable_imitation": False, "enable_mutation": True,
        "learning_scale": 1.0, "imitation_scale": 0.0, "mutation_scale": 1.0,
    },
    "imitation_only": {
        "enable_learning": False, "enable_imitation": True, "enable_mutation": True,
        "learning_scale": 0.0, "imitation_scale": 1.0, "mutation_scale": 1.0,
    },
    "static": {
        "enable_learning": False, "enable_imitation": False, "enable_mutation": False,
        "learning_scale": 0.0, "imitation_scale": 0.0, "mutation_scale": 0.0,
    },
}

TICK_FIELDS = [
    "condition", "seed", "tick", "barIndex", "worldTime",
    "totalEquity", "totalReturnPct", "fees", "activePositions",
    "tradesThisTick", "crossedShares", "houseShares", "rejectedIntents",
    "sentiment", "breadth", "avgReturn", "dispersion", "avgVol", "regime",
    "buyShares", "sellShares", "buyAgents", "sellAgents", "tradeAgents",
    "orderImbalance", "tradeSynchrony",
    "conversations", "conversationParticipants", "conversationLocations",
    "trustDensity",
    "guildMomentum", "guildMeanReversion", "guildSentiment",
    "guildContrarian", "guildBalanced",
    "guildDominant", "strategyDiversity", "strategyGeneration",
    "totalAdaptations", "strategyClosedTrades",
    "socialCascadeScore", "socialFlowRisk", "socialFlowSynchrony",
    "socialFlowImbalance", "socialPolarization", "socialTrustDensity",
    "socialDominantShare", "socialDiversity", "socialImitationRecent",
    "socialReportTick", "invariantFailures",
]

AGENT_FIELDS = [
    "condition", "seed", "agent", "family", "generation", "fitness",
    "wins", "losses", "adaptations", "equity", "returnPct", "cash",
    "realizedPnl", "maxDrawdown", "winRate", "totalSells", "positions",
    "meanExposure", "exposureSD", "maxExposure", "turnover",
    "tradeCount", "buyCount", "sellCount", "feesPaid", "meanPositions",
    "w_trend", "w_reversion", "w_rsi", "w_herding", "w_influence", "w_memory",
    "t_risk", "t_patience", "t_contrarian", "t_noise",
]

OBSERVER_FIELDS = [
    "condition", "seed", "tick", "observer", "confidence",
    "cascadeScore", "flowRiskScore", "flowSynchrony", "flowImbalance",
    "polarization", "trustDensity", "dominantShare",
    "diversity", "imitationRecent", "orderParameter", "dispersion",
    "susceptibility", "components", "brokerDegree", "data",
]

STRATEGY_TICK_FIELDS = [
    "condition", "seed", "tick", "agent", "family", "generation", "fitness",
    "equity", "exposure",
    "w_trend", "w_reversion", "w_rsi", "w_herding", "w_influence", "w_memory",
    "t_risk", "t_patience", "t_contrarian", "t_noise",
]

IMITATION_FIELDS = [
    "condition", "seed", "tick", "learner", "teacher", "location", "trust",
    "learnerFitness", "teacherFitness", "learnerFamilyBefore",
    "learnerFamilyAfter", "teacherFamily",
]

RUN_FIELDS = [
    "condition", "seed", "ticks", "finalBarIndex", "finalWorldTime",
    "learningScale", "imitationScale", "mutationScale",
    "aggregateReturn", "meanAgentReturn", "medianAgentReturn", "returnSD",
    "meanMaxDrawdown", "meanWinRate", "totalSells",
    "finalEquity", "totalFees", "totalTrades", "totalConversations",
    "meanTradeSynchrony", "meanAbsOrderImbalance",
    "meanExposure", "meanTurnover", "meanTradeCount",
    "finalTrustDensity", "meanSocialCascade", "meanSocialFlowRisk",
    "guildMomentum", "guildMeanReversion", "guildSentiment",
    "guildContrarian", "guildBalanced", "dominantGuild",
    "strategyDiversity", "strategyGeneration", "totalAdaptations",
    "strategyClosedTrades", "imitationEvents", "invariantFailures",
    "weightSumsOK", "trustSymmetric", "conversationParticipantsOK",
    "tradesValid", "tickMetricsFinite",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--design", choices=["base", "sweep"], default="base")
    parser.add_argument("--ticks", type=int, default=300)
    parser.add_argument("--seeds", type=str, default=",".join(str(i) for i in range(1, 17)))
    parser.add_argument(
        "--conditions",
        type=str,
        default="full,no_imitation,imitation_only,static",
    )
    parser.add_argument("--learning-scales", type=str, default="0,0.5,1,2")
    parser.add_argument("--imitation-scales", type=str, default="0,0.5,1,2")
    parser.add_argument("--snapshot", type=str, default=str(SNAPSHOT))
    parser.add_argument("--metadata", type=str, default=str(METADATA))
    parser.add_argument("--out", type=str, default=str(RESULTS))
    return parser.parse_args()


def load_snapshot(snapshot_path: str, metadata_path: str):
    snapshot_path = Path(snapshot_path)
    metadata_path = Path(metadata_path)
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if metadata_path.exists():
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        meta = {
            "sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
            "source": payload.get("source", "snapshot"),
            "bars": len(payload.get("times", [])),
            "first_utc": payload.get("times", [""])[0],
            "last_utc": payload.get("times", [""])[-1],
        }
    digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    if meta.get("sha256") and digest != meta["sha256"]:
        raise RuntimeError("snapshot hash mismatch")
    return payload, meta, digest


def make_provider(payload):
    provider = HistoricalDataProvider()
    source = payload.get("source", "snapshot")
    provider.load_snapshot(payload, label=f"snapshot:{source}")
    return provider


def guild_counts(ecosystem):
    counts = {family: 0 for family in ("momentum", "mean_reversion", "sentiment", "contrarian", "balanced")}
    for guild in (ecosystem or {}).get("guilds", []):
        counts[guild.get("family", "balanced")] = guild.get("count", 0)
    return counts


def finite(value):
    return value is None or (isinstance(value, (int, float)) and math.isfinite(value))


async def run_one(condition, flags, seed, ticks, payload):
    sim = SimulationLoop(seed=seed, **flags)
    sim.market = make_provider(payload)
    # Experiments must not depend on, or pollute, the demo trade log.
    sim._log_trade = lambda trade: None

    tick_rows = []
    observer_rows = []
    strategy_rows = []
    agent_stats: dict[str, dict] = {}
    checks = {
        "conversation_participants_ok": True,
        "trades_valid": True,
        "tick_metrics_finite": True,
    }
    last_frame = {"frame": None}
    latest_social = {}
    social_tick = None

    def stats_for(pid):
        return agent_stats.setdefault(pid, {
            "expSum": 0.0, "expSq": 0.0, "expN": 0,
            "maxExp": 0.0, "posSum": 0.0,
            "notional": 0.0, "tradeCount": 0,
            "buyCount": 0, "sellCount": 0, "fees": 0.0,
        })

    async def collect(frame):
        nonlocal social_tick
        last_frame["frame"] = frame

        for report in frame.observer_reports:
            if report.get("observerId") == "social_engineer":
                latest_social.clear()
                latest_social.update(report.get("data") or {})
                social_tick = report.get("tick")
            data = report.get("data") or {}
            observer_rows.append({
                "condition": condition, "seed": seed,
                "tick": report.get("tick"),
                "observer": report.get("observerId"),
                "confidence": report.get("confidence"),
                "cascadeScore": data.get("cascadeScore"),
                "flowRiskScore": data.get("flowRiskScore"),
                "flowSynchrony": data.get("flowSynchrony"),
                "flowImbalance": data.get("flowImbalance"),
                "polarization": data.get("polarization"),
                "trustDensity": data.get("trustDensity"),
                "dominantShare": data.get("dominantShare"),
                "diversity": data.get("diversity"),
                "imitationRecent": data.get("imitationRecent"),
                "orderParameter": data.get("orderParameter"),
                "dispersion": data.get("dispersion"),
                "susceptibility": data.get("susceptibility"),
                "components": data.get("components"),
                "brokerDegree": data.get("brokerDegree"),
                "data": json.dumps(data, sort_keys=True),
            })

        trades = frame.trades or []
        buy_shares = sum(t.shares for t in trades if t.direction == "BUY")
        sell_shares = sum(t.shares for t in trades if t.direction == "SELL")
        buy_agents = len({t.persona_id for t in trades if t.direction == "BUY"})
        sell_agents = len({t.persona_id for t in trades if t.direction == "SELL"})
        trade_agents = len({t.persona_id for t in trades})
        gross = buy_shares + sell_shares
        order_imbalance = (buy_shares - sell_shares) / gross if gross else 0.0
        trade_synchrony = (
            max(buy_agents, sell_agents) / trade_agents if trade_agents else 0.0
        )
        for trade in trades:
            if trade.shares <= 0 or trade.price <= 0:
                checks["trades_valid"] = False
            stat = stats_for(trade.persona_id)
            notional = trade.price * trade.shares
            stat["notional"] += notional
            stat["tradeCount"] += 1
            stat["fees"] += trade.fee
            if trade.direction == "BUY":
                stat["buyCount"] += 1
            else:
                stat["sellCount"] += 1

        for persona in frame.personas:
            if persona.is_observer:
                continue
            equity = persona.equity or (persona.cash + sum(
                h.get("marketValue", 0.0) for h in (persona.holdings or [])
            ))
            holdings_value = max(0.0, equity - persona.cash)
            exposure = holdings_value / equity if equity > 0 else 0.0
            stat = stats_for(persona.persona_id)
            stat["expSum"] += exposure
            stat["expSq"] += exposure * exposure
            stat["expN"] += 1
            stat["maxExp"] = max(stat["maxExp"], exposure)
            stat["posSum"] += persona.positions

        conversations = frame.conversations or []
        for conv in conversations:
            if any(pid not in sim.personas for pid in conv.participants):
                checks["conversation_participants_ok"] = False

        trust_density = sim.influence_network.trust_summary(threshold=0.2)["density"]
        guilds = guild_counts(frame.ecosystem)
        stats = frame.stats or {}
        metrics = frame.metrics or {}
        row = {
            "condition": condition, "seed": seed, "tick": frame.tick,
            "barIndex": frame.bar_index, "worldTime": frame.world_time,
            "totalEquity": stats.get("totalEquity"),
            "totalReturnPct": stats.get("totalReturnPct"),
            "fees": stats.get("fees"),
            "activePositions": stats.get("activePositions"),
            "tradesThisTick": stats.get("tradesThisTick"),
            "crossedShares": stats.get("crossedShares"),
            "houseShares": stats.get("houseShares"),
            "rejectedIntents": stats.get("rejectedIntents"),
            "sentiment": frame.sentiment,
            "breadth": metrics.get("breadth"),
            "avgReturn": metrics.get("avgReturn"),
            "dispersion": metrics.get("dispersion"),
            "avgVol": metrics.get("avgVol"),
            "regime": metrics.get("regime"),
            "buyShares": buy_shares, "sellShares": sell_shares,
            "buyAgents": buy_agents, "sellAgents": sell_agents,
            "tradeAgents": trade_agents,
            "orderImbalance": round(order_imbalance, 6),
            "tradeSynchrony": round(trade_synchrony, 6),
            "conversations": len(conversations),
            "conversationParticipants": sum(len(c.participants) for c in conversations),
            "conversationLocations": "|".join(sorted({c.location for c in conversations})),
            "trustDensity": round(trust_density, 6),
            "guildMomentum": guilds["momentum"],
            "guildMeanReversion": guilds["mean_reversion"],
            "guildSentiment": guilds["sentiment"],
            "guildContrarian": guilds["contrarian"],
            "guildBalanced": guilds["balanced"],
            "guildDominant": (frame.ecosystem or {}).get("dominant"),
            "strategyDiversity": (frame.ecosystem or {}).get("diversity"),
            "strategyGeneration": (frame.ecosystem or {}).get("generation"),
            "totalAdaptations": (frame.ecosystem or {}).get("totalAdaptations"),
            "strategyClosedTrades": (frame.ecosystem or {}).get("closedTrades"),
            "socialCascadeScore": latest_social.get("cascadeScore"),
            "socialFlowRisk": latest_social.get("flowRiskScore"),
            "socialFlowSynchrony": latest_social.get("flowSynchrony"),
            "socialFlowImbalance": latest_social.get("flowImbalance"),
            "socialPolarization": latest_social.get("polarization"),
            "socialTrustDensity": latest_social.get("trustDensity"),
            "socialDominantShare": latest_social.get("dominantShare"),
            "socialDiversity": latest_social.get("diversity"),
            "socialImitationRecent": latest_social.get("imitationRecent"),
            "socialReportTick": social_tick,
            "invariantFailures": stats.get("invariantFailures"),
        }
        for key, value in row.items():
            if key not in (
                "condition", "regime", "worldTime", "guildDominant",
                "conversationLocations",
            ):
                if not finite(value):
                    checks["tick_metrics_finite"] = False
        tick_rows.append(row)

        if frame.tick % 10 == 0:
            for persona in frame.personas:
                if persona.is_observer:
                    continue
                strategy = persona.strategy or {}
                weights = strategy.get("weights", {}) or {}
                traits = strategy.get("traits", {}) or {}
                equity = persona.equity or 0.0
                exposure = max(0.0, (equity - persona.cash) / equity) if equity > 0 else 0.0
                strategy_rows.append({
                    "condition": condition, "seed": seed, "tick": frame.tick,
                    "agent": persona.persona_id,
                    "family": strategy.get("family"),
                    "generation": strategy.get("generation"),
                    "fitness": strategy.get("fitness"),
                    "equity": persona.equity,
                    "exposure": round(exposure, 6),
                    "w_trend": weights.get("trend"),
                    "w_reversion": weights.get("reversion"),
                    "w_rsi": weights.get("rsi"),
                    "w_herding": weights.get("herding"),
                    "w_influence": weights.get("influence"),
                    "w_memory": weights.get("memory"),
                    "t_risk": traits.get("risk"),
                    "t_patience": traits.get("patience"),
                    "t_contrarian": traits.get("contrarian"),
                    "t_noise": traits.get("noise"),
                })

    sim.on_frame(collect)
    await sim.run_headless(ticks)
    sim.stop()

    frame = last_frame["frame"]
    if frame is None:
        raise RuntimeError("no frame produced")

    agents = [p for p in frame.personas if not p.is_observer]
    agent_rows = []
    for persona in agents:
        strategy = persona.strategy or {}
        weights = strategy.get("weights", {}) or {}
        traits = strategy.get("traits", {}) or {}
        stat = stats_for(persona.persona_id)
        n = max(stat["expN"], 1)
        mean_exp = stat["expSum"] / n
        variance = max(0.0, stat["expSq"] / n - mean_exp * mean_exp)
        agent_rows.append({
            "condition": condition, "seed": seed,
            "agent": persona.persona_id,
            "family": strategy.get("family"),
            "generation": strategy.get("generation"),
            "fitness": strategy.get("fitness"),
            "wins": strategy.get("wins"),
            "losses": strategy.get("losses"),
            "adaptations": strategy.get("adaptations"),
            "equity": persona.equity,
            "returnPct": persona.return_pct,
            "cash": persona.cash,
            "realizedPnl": persona.realized_pnl,
            "maxDrawdown": persona.max_drawdown,
            "winRate": persona.win_rate,
            "totalSells": persona.total_sells,
            "positions": persona.positions,
            "meanExposure": round(mean_exp, 6),
            "exposureSD": round(math.sqrt(variance), 6),
            "maxExposure": round(stat["maxExp"], 6),
            "turnover": round(stat["notional"] / INITIAL_CASH, 6),
            "tradeCount": stat["tradeCount"],
            "buyCount": stat["buyCount"],
            "sellCount": stat["sellCount"],
            "feesPaid": round(stat["fees"], 4),
            "meanPositions": round(stat["posSum"] / n, 4),
            "w_trend": weights.get("trend"),
            "w_reversion": weights.get("reversion"),
            "w_rsi": weights.get("rsi"),
            "w_herding": weights.get("herding"),
            "w_influence": weights.get("influence"),
            "w_memory": weights.get("memory"),
            "t_risk": traits.get("risk"),
            "t_patience": traits.get("patience"),
            "t_contrarian": traits.get("contrarian"),
            "t_noise": traits.get("noise"),
        })

    # Reliability checks
    weight_sums_ok = True
    for genome in sim.strategy_engine.genomes.values():
        total = sum(getattr(genome, gene) for gene in (
            "trend", "reversion", "rsi", "herding", "influence", "memory",
        ))
        if abs(total - 1.0) > 1e-6:
            weight_sums_ok = False
            break

    asymmetric = 0
    for a, targets in sim.influence_network.edges.items():
        for b, edge in targets.items():
            if edge.weight < 0.05:
                continue
            reverse = sim.influence_network.edges.get(b, {}).get(a)
            if reverse is None or abs(reverse.weight - edge.weight) > 1e-9:
                asymmetric += 1
    trust_symmetric = asymmetric == 0

    guilds = guild_counts(frame.ecosystem)
    stats = frame.stats or {}
    returns = [p.return_pct for p in agents]
    run_row = {
        "condition": condition, "seed": seed, "ticks": ticks,
        "finalBarIndex": frame.bar_index, "finalWorldTime": frame.world_time,
        "learningScale": flags.get("learning_scale", 0.0),
        "imitationScale": flags.get("imitation_scale", 0.0),
        "mutationScale": flags.get("mutation_scale", 0.0),
        "aggregateReturn": stats.get("totalReturnPct"),
        "meanAgentReturn": statistics.fmean(returns) if returns else None,
        "medianAgentReturn": statistics.median(returns) if returns else None,
        "returnSD": statistics.stdev(returns) if len(returns) > 1 else 0.0,
        "meanMaxDrawdown": statistics.fmean([p.max_drawdown for p in agents]),
        "meanWinRate": statistics.fmean([p.win_rate for p in agents]),
        "totalSells": sum(p.total_sells for p in agents),
        "finalEquity": stats.get("totalEquity"),
        "totalFees": stats.get("fees"),
        "totalTrades": sum(row["tradesThisTick"] for row in tick_rows),
        "totalConversations": sum(row["conversations"] for row in tick_rows),
        "meanTradeSynchrony": statistics.fmean([row["tradeSynchrony"] for row in tick_rows]),
        "meanAbsOrderImbalance": statistics.fmean([abs(row["orderImbalance"]) for row in tick_rows]),
        "meanExposure": statistics.fmean([row["meanExposure"] for row in agent_rows]),
        "meanTurnover": statistics.fmean([row["turnover"] for row in agent_rows]),
        "meanTradeCount": statistics.fmean([row["tradeCount"] for row in agent_rows]),
        "finalTrustDensity": tick_rows[-1]["trustDensity"],
        "meanSocialCascade": statistics.fmean([
            row["socialCascadeScore"] for row in tick_rows
            if row["socialCascadeScore"] is not None
        ]) if any(row["socialCascadeScore"] is not None for row in tick_rows) else None,
        "meanSocialFlowRisk": statistics.fmean([
            row["socialFlowRisk"] for row in tick_rows
            if row["socialFlowRisk"] is not None
        ]) if any(row["socialFlowRisk"] is not None for row in tick_rows) else None,
        "guildMomentum": guilds["momentum"],
        "guildMeanReversion": guilds["mean_reversion"],
        "guildSentiment": guilds["sentiment"],
        "guildContrarian": guilds["contrarian"],
        "guildBalanced": guilds["balanced"],
        "dominantGuild": (frame.ecosystem or {}).get("dominant"),
        "strategyDiversity": (frame.ecosystem or {}).get("diversity"),
        "strategyGeneration": (frame.ecosystem or {}).get("generation"),
        "totalAdaptations": (frame.ecosystem or {}).get("totalAdaptations"),
        "strategyClosedTrades": (frame.ecosystem or {}).get("closedTrades"),
        "imitationEvents": len(sim.strategy_engine.imitation_events),
        "invariantFailures": sim._invariant_failures,
        "weightSumsOK": weight_sums_ok,
        "trustSymmetric": trust_symmetric,
        "conversationParticipantsOK": checks["conversation_participants_ok"],
        "tradesValid": checks["trades_valid"],
        "tickMetricsFinite": checks["tick_metrics_finite"],
    }

    trust_rows = []
    for a, targets in sim.influence_network.edges.items():
        for b, edge in targets.items():
            if edge.weight >= 0.05:
                trust_rows.append({
                    "condition": condition, "seed": seed, "a": a, "b": b,
                    "weight": round(edge.weight, 6),
                    "conversations": edge.conversations,
                })

    imitation_rows = [
        {**event, "condition": condition, "seed": seed}
        for event in sim.strategy_engine.imitation_events
    ]

    reliability = {
        "condition": condition, "seed": seed,
        "invariant_failures": sim._invariant_failures,
        "weight_sums_ok": weight_sums_ok,
        "trust_symmetric": trust_symmetric,
        "asymmetric_edges": asymmetric,
        "conversation_participants_ok": checks["conversation_participants_ok"],
        "trades_valid": checks["trades_valid"],
        "tick_metrics_finite": checks["tick_metrics_finite"],
        "agents": len(agents),
        "observers": len([p for p in frame.personas if p.is_observer]),
        "closed_trades": sim.strategy_engine.closed_trades,
        "imitation_events": len(sim.strategy_engine.imitation_events),
        "final_bar_index": frame.bar_index,
    }
    return {
        "tick_rows": tick_rows,
        "agent_rows": agent_rows,
        "observer_rows": observer_rows,
        "strategy_rows": strategy_rows,
        "imitation_rows": imitation_rows,
        "run_row": run_row,
        "trust_rows": trust_rows,
        "reliability": reliability,
    }


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sweep_conditions(learning_scales, imitation_scales):
    conditions = {}
    for learning in learning_scales:
        for imitation in imitation_scales:
            label = f"L{learning:g}_I{imitation:g}"
            conditions[label] = {
                "enable_learning": learning > 0,
                "enable_imitation": imitation > 0,
                "enable_mutation": True,
                "learning_scale": learning,
                "imitation_scale": imitation,
                "mutation_scale": 1.0,
            }
    return conditions


async def main():
    args = parse_args()
    seeds = [int(item) for item in args.seeds.split(",") if item.strip()]
    if args.design == "sweep":
        learning_scales = [float(item) for item in args.learning_scales.split(",") if item.strip()]
        imitation_scales = [float(item) for item in args.imitation_scales.split(",") if item.strip()]
        conditions = sweep_conditions(learning_scales, imitation_scales)
        condition_names = list(conditions)
    else:
        condition_names = [item.strip() for item in args.conditions.split(",") if item.strip()]
        conditions = BASE_CONDITIONS
        for name in condition_names:
            if name not in conditions:
                raise SystemExit(f"unknown condition: {name}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload, meta, digest = load_snapshot(args.snapshot, args.metadata)
    config = {
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "design": args.design,
        "ticks": args.ticks,
        "seeds": seeds,
        "conditions": {name: conditions[name] for name in condition_names},
        "snapshot_path": str(Path(args.snapshot)),
        "snapshot_sha256": digest,
        "snapshot_source": meta.get("source"),
        "snapshot_bars": meta.get("bars"),
        "snapshot_first_utc": meta.get("first_utc"),
        "snapshot_last_utc": meta.get("last_utc"),
    }
    (out / "run_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    all_ticks, all_agents, all_observers = [], [], []
    all_strategy, all_imitation, all_runs, all_trust = [], [], [], []
    reliability_runs = []
    started = time.time()

    for condition in condition_names:
        for seed in seeds:
            t0 = time.time()
            result = await run_one(condition, conditions[condition], seed, args.ticks, payload)
            all_ticks.extend(result["tick_rows"])
            all_agents.extend(result["agent_rows"])
            all_observers.extend(result["observer_rows"])
            all_strategy.extend(result["strategy_rows"])
            all_imitation.extend(result["imitation_rows"])
            all_runs.append(result["run_row"])
            all_trust.extend(result["trust_rows"])
            reliability_runs.append(result["reliability"])
            elapsed = time.time() - t0
            print(
                f"{condition:14s} seed={seed:02d} "
                f"tick={result['run_row']['finalBarIndex']:3d} "
                f"ret={result['run_row']['aggregateReturn']:+.4%} "
                f"exp={result['run_row']['meanExposure']:.2f} "
                f"div={result['run_row']['strategyDiversity']:.3f} "
                f"sync={result['run_row']['meanTradeSynchrony']:.3f} "
                f"imit={result['run_row']['imitationEvents']:3d} "
                f"({elapsed:.1f}s)"
            )

    write_csv(out / "tick_metrics.csv", TICK_FIELDS, all_ticks)
    write_csv(out / "agent_metrics.csv", AGENT_FIELDS, all_agents)
    write_csv(out / "observer_reports.csv", OBSERVER_FIELDS, all_observers)
    write_csv(out / "strategy_tick_metrics.csv", STRATEGY_TICK_FIELDS, all_strategy)
    write_csv(out / "imitation_events.csv", IMITATION_FIELDS, all_imitation)
    write_csv(out / "run_summary.csv", RUN_FIELDS, all_runs)
    write_csv(
        out / "trust_edges.csv",
        ["condition", "seed", "a", "b", "weight", "conversations"],
        all_trust,
    )
    reliability_summary = {
        "runs": len(reliability_runs),
        "all_weight_sums_ok": all(r["weight_sums_ok"] for r in reliability_runs),
        "all_trust_symmetric": all(r["trust_symmetric"] for r in reliability_runs),
        "all_conversation_participants_ok": all(r["conversation_participants_ok"] for r in reliability_runs),
        "all_trades_valid": all(r["trades_valid"] for r in reliability_runs),
        "all_tick_metrics_finite": all(r["tick_metrics_finite"] for r in reliability_runs),
        "total_invariant_failures": sum(r["invariant_failures"] for r in reliability_runs),
        "total_imitation_events": sum(r["imitation_events"] for r in reliability_runs),
        "min_agents": min(r["agents"] for r in reliability_runs),
        "min_observers": min(r["observers"] for r in reliability_runs),
        "runs_detail": reliability_runs,
    }
    (out / "reliability.json").write_text(json.dumps(reliability_summary, indent=2), encoding="utf-8")
    config["finished_at"] = datetime.now(tz=timezone.utc).isoformat()
    config["elapsed_sec"] = round(time.time() - started, 2)
    config["runs_completed"] = len(all_runs)
    (out / "run_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"\ncompleted {len(all_runs)} runs in {time.time() - started:.1f}s")
    print(f"invariant failures: {reliability_summary['total_invariant_failures']}")
    print(f"results: {out}")


if __name__ == "__main__":
    asyncio.run(main())
