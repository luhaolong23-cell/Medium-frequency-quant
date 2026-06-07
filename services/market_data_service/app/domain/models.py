from dataclasses import dataclass
from datetime import date

from packages.domain_core.market.entities import MarketFeature


@dataclass(frozen=True)
class ProviderObservation:
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
    source: str = "mock"


__all__ = ["ProviderObservation", "MarketFeature"]
