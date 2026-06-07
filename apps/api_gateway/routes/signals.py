from datetime import date

from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess, TradeSignalView
from packages.shared.container import get_container
from packages.shared.sqlite import sqlite_session

router = APIRouter(prefix='/signals', tags=['signals'])


@router.get('/today', response_model=ApiSuccess[list[TradeSignalView]])
def signals_today(market_code: str | None = None) -> ApiSuccess[list[TradeSignalView]]:
    container = get_container()
    trade_date = _latest_signals_trade_date(container.trading_repository)
    if trade_date is None:
        return ApiSuccess(data=[])

    signals = container.trading_service.list_signals(trade_date, market_code=market_code)
    return ApiSuccess(data=[TradeSignalView.model_validate(signal.__dict__) for signal in signals])


def _latest_signals_trade_date(repository) -> date | None:
    backend_name = getattr(repository, 'backend_name', 'unknown')
    if backend_name == 'memory':
        store = getattr(repository, '_signals', {})
        if not store:
            return None
        return max(key[0] for key in store.keys())

    db_path = getattr(repository, '_db_path', None)
    if db_path is None:
        return None

    with sqlite_session(db_path) as connection:
        row = connection.execute('SELECT MAX(trade_date) AS trade_date FROM trade_signals_daily').fetchone()

    if row is None or row['trade_date'] is None:
        return None
    return date.fromisoformat(row['trade_date'])
