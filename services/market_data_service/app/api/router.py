from datetime import date

from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess
from packages.shared.container import get_container
from packages.shared.errors import NotFoundError
from services.market_data_service.app.api.schemas import (
    DailyIngestRequest,
    DailyIngestResponse,
    DailyIngestResult,
    MarketFeatureEnvelope,
    MarketFeatureResponse,
)

router = APIRouter(prefix="/v1/market-data", tags=["market-data"])


@router.post("/ingest/daily", response_model=DailyIngestResponse)
def ingest_daily(request: DailyIngestRequest) -> DailyIngestResponse:
    container = get_container()
    features = container.market_data_service.ingest_daily(
        trade_date=request.trade_date,
        market_codes=request.market_codes,
    )
    return ApiSuccess(
        data=DailyIngestResult(
            processed=len(features),
            trade_date=request.trade_date,
            source_mode=container.market_data_service.source_mode,
        )
    )


@router.get("/features/{market_code}", response_model=MarketFeatureEnvelope)
def get_feature(market_code: str, trade_date: date) -> MarketFeatureEnvelope:
    feature = get_container().market_data_service.get_feature(
        market_code=market_code,
        trade_date=trade_date,
    )
    if feature is None:
        raise NotFoundError(code="feature_not_found", message=f"No market feature found for {market_code} on {trade_date}.")
    return ApiSuccess(data=MarketFeatureResponse.model_validate(feature.__dict__))
