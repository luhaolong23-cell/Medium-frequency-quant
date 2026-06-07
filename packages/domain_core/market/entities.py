from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class MarketProxy:
    symbol: str
    proxy_type: str
    exchange_code: str
    currency: str
    priority: int


@dataclass(frozen=True)
class Market:
    market_code: str
    market_name: str
    country_code: str
    region: str
    proxies: tuple[MarketProxy, ...]


@dataclass(frozen=True)
class MarketObservation:
    market_code: str
    trade_date: date
    price_proxy: str
    close: float
    ma_120: float
    ma_200: float
    ret_60d: float
    ret_120d: float
    vol_20d: float
    drawdown_60d: float
    relative_strength_world: float
    fx_ret_60d: float
    avg_volume_recent: float
    avg_volume_prior: float
    volume_ratio_5d: float
    consecutive_up_weeks: int
    ma_5: float = 0.0
    ma_10: float = 0.0
    ma_20: float = 0.0
    ma_60: float = 0.0
    ret_1d: float = 0.0
    ret_5d: float = 0.0
    turnover_ratio_20d: float = 0.0
    avg_turnover_ratio_3d: float = 0.0
    volume_up_days_2d: int = 0
    volume_up_days_3d: int = 0
    consecutive_up_days: int = 0
    source: str = "mock"


@dataclass(frozen=True)
class MarketFeature:
    market_code: str
    trade_date: date
    price_proxy: str
    close: float
    ma_120: float
    ma_200: float
    ret_60d: float
    ret_120d: float
    vol_20d: float
    drawdown_60d: float
    relative_strength_world: float
    fx_ret_60d: float
    avg_volume_recent: float
    avg_volume_prior: float
    volume_ratio_5d: float
    consecutive_up_weeks: int
    ma_5: float = 0.0
    ma_10: float = 0.0
    ma_20: float = 0.0
    ma_60: float = 0.0
    ret_1d: float = 0.0
    ret_5d: float = 0.0
    turnover_ratio_20d: float = 0.0
    avg_turnover_ratio_3d: float = 0.0
    volume_up_days_2d: int = 0
    volume_up_days_3d: int = 0
    consecutive_up_days: int = 0
    source: str = "mock"


@dataclass(frozen=True)
class RegimeSnapshot:
    market_code: str
    trade_date: date
    regime_status: str
    bull_score: float
    trend_score: float
    relative_strength_score: float
    risk_penalty_score: float
    trigger_flags: dict[str, bool] = field(default_factory=dict)
    source_used: dict[str, str] = field(default_factory=dict)
