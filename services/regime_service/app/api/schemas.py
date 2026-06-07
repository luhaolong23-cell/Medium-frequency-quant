from datetime import date

from pydantic import BaseModel, Field

from packages.shared.api_models import ApiSuccess, MarketRegimeView


class RegimeRunRequest(BaseModel):
    market_codes: list[str] = Field(default_factory=lambda: ["ALL"])
    trade_date: date


class RegimeSnapshotResponse(BaseModel):
    market_code: str
    trade_date: date
    regime_status: str
    bull_score: float
    trend_score: float
    relative_strength_score: float
    risk_penalty_score: float
    trigger_flags: dict[str, bool]
    source_used: dict[str, str]


RegimeRunResponse = ApiSuccess[list[RegimeSnapshotResponse]]
RegimeExplainResponse = ApiSuccess[RegimeSnapshotResponse]
RegimeListResponse = ApiSuccess[list[MarketRegimeView]]
