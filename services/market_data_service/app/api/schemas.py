from datetime import date

from pydantic import BaseModel, Field

from packages.shared.api_models import ApiSuccess


class DailyIngestRequest(BaseModel):
    market_codes: list[str] = Field(default_factory=lambda: ["ALL"])
    trade_date: date


class DailyIngestResult(BaseModel):
    processed: int
    trade_date: date
    source_mode: str


class MarketFeatureResponse(BaseModel):
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
    source: str


DailyIngestResponse = ApiSuccess[DailyIngestResult]
MarketFeatureEnvelope = ApiSuccess[MarketFeatureResponse]
