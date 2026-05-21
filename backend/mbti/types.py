from dataclasses import dataclass, field

@dataclass(frozen=True)
class TraitProfile:
    extraversion: float  # 0=introvert, 1=extravert
    sensing: float       # 0=intuitive, 1=sensing
    thinking: float      # 0=feeling, 1=thinking
    judging: float       # 0=perceiving, 1=judging


@dataclass
class TradingParams:
    risk_tolerance: float
    contrarianism: float
    reaction_speed: float
    holding_period_ticks: int
    tech_weight: float
    panic_threshold: float
    greed_threshold: float
    trade_size_pct: float
    herding_weight: float
    volatility_tolerance: float


def derive_trading_params(t: TraitProfile) -> TradingParams:
    return TradingParams(
        risk_tolerance=0.3 + 0.4 * ((1 - t.thinking) + t.extraversion) / 2,
        contrarianism=0.8 * (1 - t.extraversion) + 0.2 * (1 - t.judging),
        reaction_speed=0.2 + 0.6 * t.judging,
        holding_period_ticks=int(3 + 12 * (1 - t.sensing) + 4 * (1 - t.judging)),
        tech_weight=0.3 + 0.5 * t.thinking,
        panic_threshold=-(0.05 + 0.15 * (1 - t.thinking)),
        greed_threshold=0.08 + 0.20 * t.thinking,
        trade_size_pct=0.05 + 0.20 * t.judging * t.extraversion,
        herding_weight=0.1 + 0.7 * t.extraversion * (1 - t.thinking),
        volatility_tolerance=0.3 + 0.4 * t.thinking + 0.3 * (1 - t.sensing),
    )
