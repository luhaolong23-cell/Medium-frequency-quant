from datetime import date

from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess, MarketRegimeView
from packages.shared.container import get_container
from packages.shared.errors import NotFoundError
from services.regime_service.app.api.schemas import (
    RegimeExplainResponse,
    RegimeListResponse,
    RegimeRunRequest,
    RegimeRunResponse,
    RegimeSnapshotResponse,
)

router = APIRouter(prefix="/v1/regime", tags=["regime"])


@router.post("/run/daily", response_model=RegimeRunResponse)
def run_daily(request: RegimeRunRequest) -> RegimeRunResponse:
    snapshots = get_container().regime_service.run_daily(
        trade_date=request.trade_date,
        market_codes=request.market_codes,
    )
    return ApiSuccess(
        data=[RegimeSnapshotResponse.model_validate(snapshot.__dict__) for snapshot in snapshots]
    )


@router.get("/markets/today", response_model=RegimeListResponse)
def list_today() -> RegimeListResponse:
    snapshots = get_container().regime_service.list_by_date(date.today())
    return ApiSuccess(
        data=[
            MarketRegimeView(
                market_code=snapshot.market_code,
                trade_date=snapshot.trade_date,
                regime_status=snapshot.regime_status,
                bull_score=snapshot.bull_score,
            )
            for snapshot in snapshots
        ]
    )


@router.get("/markets/{market_code}/explain", response_model=RegimeExplainResponse)
def explain_market(market_code: str, trade_date: date) -> RegimeExplainResponse:
    snapshot = get_container().regime_service.get_snapshot(market_code, trade_date)
    if snapshot is None:
        raise NotFoundError(code="regime_not_found", message=f"No regime snapshot found for {market_code} on {trade_date}.")
    return ApiSuccess(data=RegimeSnapshotResponse.model_validate(snapshot.__dict__))
