from datetime import date

from fastapi import APIRouter

from packages.shared.api_models import (
    ApiSuccess,
    MarketRegimeView,
    PaperOrderView,
    PaperPositionView,
    SelectedStockView,
    SchedulerExecutionLogView,
    TradeSignalView,
    TrackedBullMarketView,
    WatchlistStockView,
    WorkflowLogsSummaryView,
)
from packages.shared.container import get_container
from packages.shared.scheduler_logs import list_scheduler_job_logs
from packages.shared.sqlite import sqlite_session

router = APIRouter(prefix="/workflow", tags=["workflow"])


@router.get('/logs/scheduler', response_model=ApiSuccess[list[SchedulerExecutionLogView]])
def list_scheduler_logs(limit: int = 30) -> ApiSuccess[list[SchedulerExecutionLogView]]:
    return ApiSuccess(
        data=[SchedulerExecutionLogView.model_validate(item) for item in list_scheduler_job_logs(limit=limit)]
    )


@router.get('/logs/latest-summary', response_model=ApiSuccess[WorkflowLogsSummaryView])
def latest_workflow_logs_summary() -> ApiSuccess[WorkflowLogsSummaryView]:
    container = get_container()
    regime_snapshots = container.regime_service.list_latest()
    tracked_bull = container.regime_service.list_tracked_bull()

    candidates_trade_date = _latest_trade_date(container.selection_repository, '_candidates', 'stock_candidates_daily')
    watchlist_trade_date = _latest_trade_date(container.selection_repository, '_watchlist', 'stock_watchlist_daily')
    signals_trade_date = _latest_trade_date(container.trading_repository, '_signals', 'trade_signals_daily')
    orders_trade_date = _latest_trade_date(container.trading_repository, '_orders', 'paper_orders')

    candidates = container.selection_service.list_candidates(candidates_trade_date) if candidates_trade_date else []
    watchlist = container.selection_service.list_watchlist(watchlist_trade_date) if watchlist_trade_date else []
    signals = container.trading_service.list_signals(signals_trade_date) if signals_trade_date else []
    orders = container.trading_service.list_orders(orders_trade_date) if orders_trade_date else []
    positions = container.trading_service.list_positions(status='OPEN')

    return ApiSuccess(
        data=WorkflowLogsSummaryView(
            regime_latest_trade_date=regime_snapshots[0].trade_date if regime_snapshots else None,
            latest_candidates_trade_date=candidates_trade_date,
            latest_watchlist_trade_date=watchlist_trade_date,
            latest_signals_trade_date=signals_trade_date,
            latest_orders_trade_date=orders_trade_date,
            tracked_bull_count=len(tracked_bull),
            open_position_count=len(positions),
            latest_market_regimes=[
                MarketRegimeView(
                    market_code=snapshot.market_code,
                    trade_date=snapshot.trade_date,
                    regime_status=snapshot.regime_status,
                    bull_score=snapshot.bull_score,
                )
                for snapshot in regime_snapshots
            ],
            tracked_bull_markets=[
                TrackedBullMarketView(
                    market_code=snapshot.market_code,
                    entered_bull_trade_date=snapshot.trade_date,
                    bull_score=snapshot.bull_score,
                    regime_status=snapshot.regime_status,
                )
                for snapshot in tracked_bull
            ],
            latest_candidates=[SelectedStockView.model_validate(candidate.__dict__) for candidate in candidates],
            latest_watchlist=[WatchlistStockView.model_validate(item.__dict__) for item in watchlist],
            latest_signals=[TradeSignalView.model_validate(signal.__dict__) for signal in signals],
            latest_orders=[PaperOrderView.model_validate(order.__dict__) for order in orders],
            open_positions=[PaperPositionView.model_validate(position.__dict__) for position in positions],
        )
    )


def _latest_trade_date(repository, memory_attr: str, sqlite_table: str) -> date | None:
    backend_name = getattr(repository, 'backend_name', 'unknown')
    if backend_name == 'memory':
        store = getattr(repository, memory_attr, {})
        if not store:
            return None
        if memory_attr == '_orders':
            return max(order.trade_date for order in store.values())
        if memory_attr == '_watchlist':
            return max(trade_date for trade_date, _ in store.keys())
        if memory_attr == '_signals':
            return max(key[0] for key in store.keys())
        return max(trade_date for _, _, trade_date in store.keys())

    db_path = getattr(repository, '_db_path', None)
    if db_path is None:
        return None
    with sqlite_session(db_path) as connection:
        row = connection.execute(f'SELECT MAX(trade_date) AS trade_date FROM {sqlite_table}').fetchone()
    if row is None or row['trade_date'] is None:
        return None
    return date.fromisoformat(row['trade_date'])
