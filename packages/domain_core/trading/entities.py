from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class TradeSignal:
    market_code: str
    ticker: str
    trade_date: date
    side: str
    signal_type: str
    triggered: bool
    signal_reason: str
    close: float
    volume_ratio_5d: float
    threshold_volume_ratio: float
    order_notional: float
    source: str = "paper"


@dataclass(frozen=True)
class PaperOrder:
    order_id: str
    market_code: str
    ticker: str
    trade_date: date
    side: str
    order_type: str
    status: str
    signal_type: str
    signal_reason: str
    position_effect: str
    position_status_before: str
    position_status_after: str
    requested_notional: float
    quantity: float
    limit_price: float
    filled_price: float
    filled_at: datetime
    source: str = "paper"


@dataclass(frozen=True)
class PaperPosition:
    market_code: str
    ticker: str
    opened_trade_date: date
    last_trade_date: date
    quantity: float
    avg_price: float
    invested_notional: float
    peak_price: float
    last_close: float
    last_volume_ratio_5d: float
    consecutive_decline_days: int
    unrealized_pnl: float
    unrealized_return: float
    entry_signal_type: str
    last_signal_type: str
    last_signal_reason: str
    closed_trade_date: date | None = None
    closed_price: float | None = None
    status: str = "OPEN"
