from datetime import date

from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess
from packages.shared.container import get_container
from services.selection_service.app.api.schemas import (
    CandidateListResponse,
    CandidateResponse,
    CoarseScreenRequest,
    CoarseScreenResponse,
    CoarseScreenResult,
    DailySelectionRequest,
    DailySelectionRunResponse,
    DailySelectionResult,
    HeatSnapshotListResponse,
    HeatSnapshotResponse,
    SeedPoolListResponse,
    SeedPoolResponse,
    WatchlistListResponse,
    WatchlistResponse,
)

router = APIRouter(prefix='/v1/selection', tags=['selection'])


@router.post('/run-daily', response_model=DailySelectionRunResponse)
def run_daily_selection(request: DailySelectionRequest) -> DailySelectionRunResponse:
    candidates, watchlist = get_container().selection_service.run_daily_selection(
        trade_date=request.trade_date,
        market_codes=request.market_codes,
        replace_market_codes=request.replace_market_codes,
        regime_trade_date=request.regime_trade_date,
    )
    return ApiSuccess(
        data=DailySelectionResult(
            trade_date=request.trade_date,
            processed_candidates=len(candidates),
            watchlist_count=len(watchlist),
            source_mode=get_container().selection_service.source_mode,
        )
    )


@router.post('/coarse-screen', response_model=CoarseScreenResponse)
def coarse_screen(request: CoarseScreenRequest) -> CoarseScreenResponse:
    candidates, watchlist = get_container().selection_service.run_daily_selection(
        trade_date=request.trade_date,
        market_codes=request.market_codes,
        replace_market_codes=request.replace_market_codes,
        regime_trade_date=request.regime_trade_date,
    )
    return ApiSuccess(
        data=CoarseScreenResult(
            trade_date=request.trade_date,
            processed_candidates=len(candidates),
            watchlist_count=len(watchlist),
            source_mode=get_container().selection_service.source_mode,
        )
    )


@router.get('/seeds', response_model=SeedPoolListResponse)
def list_seed_pool(trade_date: date, market_code: str | None = None) -> SeedPoolListResponse:
    seeds = get_container().selection_service.list_seed_pool(trade_date=trade_date, market_code=market_code)
    return ApiSuccess(data=[SeedPoolResponse.model_validate(seed.__dict__) for seed in seeds])


@router.get('/candidates', response_model=CandidateListResponse)
def list_candidates(trade_date: date, market_code: str | None = None) -> CandidateListResponse:
    candidates = get_container().selection_service.list_candidates(trade_date=trade_date, market_code=market_code)
    return ApiSuccess(data=[CandidateResponse.model_validate(candidate.__dict__) for candidate in candidates])


@router.get('/watchlist', response_model=WatchlistListResponse)
def list_watchlist(trade_date: date, market_code: str | None = None) -> WatchlistListResponse:
    watchlist = get_container().selection_service.list_watchlist(trade_date=trade_date, market_code=market_code)
    return ApiSuccess(data=[WatchlistResponse.model_validate(item.__dict__) for item in watchlist])


@router.get('/hot-themes', response_model=HeatSnapshotListResponse)
def list_hot_themes(
    trade_date: date,
    market_code: str | None = None,
    theme_type: str | None = None,
) -> HeatSnapshotListResponse:
    snapshots = get_container().selection_service.list_heat_snapshots(
        trade_date=trade_date,
        market_code=market_code,
        theme_type=theme_type,
    )
    return ApiSuccess(data=[HeatSnapshotResponse.model_validate(item.__dict__) for item in snapshots])
