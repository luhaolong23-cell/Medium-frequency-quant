from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class StockSeed:
    market_code: str
    ticker: str
    company_name: str
    sector: str
    industry: str
    exchange: str
    currency: str
    country_code: str
    seed_type: str = "core"
    theme_tags: list[str] = field(default_factory=list)
    theme_score: float = 50.0
    valuation_score: float = 50.0
    size_score: float = 50.0
    valuation_band: str = "neutral"
    market_cap_bucket: str = "mid_cap"


@dataclass(frozen=True)
class StockSeedSnapshot:
    trade_date: date
    market_code: str
    ticker: str
    company_name: str
    sector: str
    industry: str
    exchange: str
    currency: str
    country_code: str
    seed_type: str
    theme_tags: list[str]
    theme_score: float
    valuation_score: float
    size_score: float
    valuation_band: str
    market_cap_bucket: str
    seed_reason: str


@dataclass(frozen=True)
class StockMetadata:
    market_code: str
    ticker: str
    company_name: str
    sector: str
    industry: str
    exchange: str
    currency: str
    country_code: str
    theme_tags: list[str]
    theme_score: float
    valuation_score: float
    size_score: float
    valuation_band: str
    market_cap_bucket: str
    updated_at: date


@dataclass(frozen=True)
class StockUniverseSnapshot:
    trade_date: date
    market_code: str
    ticker: str
    company_name: str
    sector: str
    industry: str
    exchange: str
    currency: str
    country_code: str
    market_cap: float
    price: float
    price_position: float | None
    momentum_pct: float
    volume_ratio: float
    ret_5d: float | None = None
    ret_20d: float | None = None
    ret_60d: float | None = None
    ma_20: float | None = None
    ma_60: float | None = None
    avg_dollar_volume_3d: float | None = None
    avg_dollar_volume_20d: float | None = None
    volume_ratio_3d: float | None = None
    volume_up_days_5d: int | None = None
    distance_to_60d_high: float | None = None
    momentum_acceleration: float | None = None
    vol_20d: float | None = None
    theme_tags: list[str] = field(default_factory=list)
    source: str = "selection"


@dataclass(frozen=True)
class StockDailyBar:
    market_code: str
    ticker: str
    trade_date: date
    close: float
    volume: float
    source: str = 'selection_history'



@dataclass(frozen=True)
class StockScreenObservation:
    market_code: str
    ticker: str
    trade_date: date
    close: float
    ma_20: float
    ma_60: float
    ma_120: float
    ma_200: float
    ret_5d: float
    ret_20d: float
    ret_60d: float
    avg_dollar_volume_3d: float
    avg_dollar_volume_5d: float
    avg_dollar_volume_20d: float
    volume_ratio_3d: float
    volume_ratio_5d: float
    volume_up_days_5d: int
    distance_to_60d_high: float
    momentum_acceleration: float
    vol_20d: float
    source: str = "mock"


@dataclass(frozen=True)
class StockCandidate:
    market_code: str
    ticker: str
    trade_date: date
    regime_trade_date: date | None
    company_name: str
    sector: str
    industry: str
    seed_type: str
    rank: int
    close: float
    ret_5d: float
    ret_20d: float
    ret_60d: float
    ma_20: float
    ma_60: float
    avg_dollar_volume_3d: float
    avg_dollar_volume_5d: float
    avg_dollar_volume_20d: float
    volume_ratio_3d: float
    volume_ratio_5d: float
    volume_up_days_5d: int
    distance_to_60d_high: float
    momentum_acceleration: float
    vol_20d: float
    coarse_score: float
    composite_score: float
    theme_score: float
    lagging_score: float
    trend_recovery_score: float
    momentum_acceleration_score: float
    volume_probe_score: float
    risk_control_score: float
    valuation_band: str
    market_cap_bucket: str
    theme_tags: list[str]
    source: str
    screen_flags: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class StockWatchItem:
    market_code: str
    ticker: str
    trade_date: date
    regime_trade_date: date | None
    watch_rank: int
    company_name: str
    sector: str
    industry: str
    close: float
    ret_5d: float
    ret_20d: float
    ret_60d: float
    ma_20: float
    ma_60: float
    avg_dollar_volume_3d: float
    avg_dollar_volume_5d: float
    avg_dollar_volume_20d: float
    volume_ratio_3d: float
    volume_ratio_5d: float
    volume_up_days_5d: int
    distance_to_60d_high: float
    momentum_acceleration: float
    vol_20d: float
    composite_score: float
    theme_score: float
    lagging_score: float
    trend_recovery_score: float
    momentum_acceleration_score: float
    volume_probe_score: float
    risk_control_score: float
    valuation_band: str
    market_cap_bucket: str
    theme_tags: list[str]
    source: str
    watch_reason: str


@dataclass(frozen=True)
class ThemeHeatSnapshot:
    trade_date: date
    market_code: str
    theme_type: str
    theme_name: str
    raw_heat_score: float
    smoothed_heat_score: float
    constituent_count: int
    source: str = "selection"
