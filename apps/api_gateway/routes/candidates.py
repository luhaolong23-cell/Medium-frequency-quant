from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.shared.api_models import ApiSuccess, SelectedStockView, StockScreenRunView
from packages.shared.container import get_container
from packages.shared.sqlite import sqlite_session

router = APIRouter(prefix='/candidates', tags=['candidates'])


class StockScreenRunRequest(BaseModel):
    trade_date: date | None = None
    market_codes: list[str] = Field(default_factory=lambda: ['ALL'])


@router.get('/today', response_model=ApiSuccess[list[SelectedStockView]])
def candidates_today(market_code: str | None = None) -> ApiSuccess[list[SelectedStockView]]:
    container = get_container()
    trade_date = _latest_candidates_trade_date(container.selection_repository)
    if trade_date is None:
        return ApiSuccess(data=[])

    candidates = container.selection_service.list_candidates(trade_date, market_code=market_code)
    return ApiSuccess(data=[SelectedStockView.model_validate(candidate.__dict__) for candidate in candidates])


@router.post('/run', response_model=ApiSuccess[StockScreenRunView])
def run_stock_screen(request: StockScreenRunRequest) -> ApiSuccess[StockScreenRunView]:
    container = get_container()
    container.refdata_service.list_markets()
    tracked_snapshots = _filter_tracked_snapshots(
        container.regime_service.list_tracked_bull(),
        request.market_codes,
    )
    tracked_market_codes = [snapshot.market_code for snapshot in tracked_snapshots]
    regime_trade_date = max((snapshot.trade_date for snapshot in tracked_snapshots), default=date.today())
    run_date = request.trade_date or regime_trade_date

    prepared_heat = container.selection_service.prepare_hot_themes(
        trade_date=run_date,
        market_codes=tracked_market_codes,
        replace_market_codes=tracked_market_codes,
    )
    candidates, watchlist = container.selection_service.run_daily_selection(
        trade_date=run_date,
        market_codes=tracked_market_codes,
        replace_market_codes=tracked_market_codes,
        regime_trade_date=regime_trade_date,
        prepared_heat_snapshots=prepared_heat,
    )
    selected_markets = set(tracked_market_codes)
    seed_count = len([item for item in container.selection_service.list_seed_pool(run_date) if item.market_code in selected_markets])

    return ApiSuccess(
        data=StockScreenRunView(
            trade_date=run_date,
            tracked_market_count=len(tracked_market_codes),
            tracked_market_codes=tracked_market_codes,
            seed_count=seed_count,
            processed_candidates=len(candidates),
            watchlist_count=len(watchlist),
            source_mode=container.selection_service.source_mode,
        )
    )


def _latest_candidates_trade_date(repository) -> date | None:
    backend_name = getattr(repository, 'backend_name', 'unknown')
    if backend_name == 'memory':
        store = getattr(repository, '_candidates', {})
        if not store:
            return None
        return max(trade_date for _, _, trade_date in store.keys())

    db_path = getattr(repository, '_db_path', None)
    if db_path is None:
        return None

    with sqlite_session(db_path) as connection:
        row = connection.execute('SELECT MAX(trade_date) AS trade_date FROM stock_candidates_daily').fetchone()

    if row is None or row['trade_date'] is None:
        return None
    return date.fromisoformat(row['trade_date'])


def _filter_tracked_snapshots(snapshots, requested_market_codes: list[str]):
    if requested_market_codes == ['ALL']:
        return snapshots
    wanted = set(requested_market_codes)
    return [snapshot for snapshot in snapshots if snapshot.market_code in wanted]
