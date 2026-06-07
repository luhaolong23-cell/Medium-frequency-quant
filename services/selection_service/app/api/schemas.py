from datetime import date

from pydantic import BaseModel, Field

from packages.shared.api_models import ApiSuccess


class DailySelectionRequest(BaseModel):
    trade_date: date
    market_codes: list[str] = Field(default_factory=lambda: ['ALL'])
    replace_market_codes: list[str] | None = None
    regime_trade_date: date | None = None


class DailySelectionResult(BaseModel):
    trade_date: date
    processed_candidates: int
    watchlist_count: int
    source_mode: str


class CandidateResponse(BaseModel):
    market_code: str
    ticker: str
    trade_date: date
    regime_trade_date: date | None = None
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
    screen_flags: dict[str, bool]


class WatchlistResponse(BaseModel):
    market_code: str
    ticker: str
    trade_date: date
    regime_trade_date: date | None = None
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


class CandidateListResponse(ApiSuccess[list[CandidateResponse]]):
    pass


class HeatSnapshotResponse(BaseModel):
    trade_date: date
    market_code: str
    theme_type: str
    theme_name: str
    raw_heat_score: float
    smoothed_heat_score: float
    constituent_count: int
    source: str


class HeatSnapshotListResponse(ApiSuccess[list[HeatSnapshotResponse]]):
    pass


class SeedPoolResponse(BaseModel):
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


class SeedPoolListResponse(ApiSuccess[list[SeedPoolResponse]]):
    pass


class WatchlistListResponse(ApiSuccess[list[WatchlistResponse]]):
    pass


class DailySelectionRunResponse(ApiSuccess[DailySelectionResult]):
    pass


class CoarseScreenRequest(DailySelectionRequest):
    pass


class CoarseScreenResult(DailySelectionResult):
    pass


class CoarseScreenResponse(ApiSuccess[CoarseScreenResult]):
    pass
