from datetime import date

from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess, SeedPoolView
from packages.shared.container import get_container
from packages.shared.sqlite import sqlite_session

router = APIRouter(prefix='/seeds', tags=['seeds'])


@router.get('/today', response_model=ApiSuccess[list[SeedPoolView]])
def seeds_today(market_code: str | None = None) -> ApiSuccess[list[SeedPoolView]]:
    container = get_container()
    trade_date = _latest_seed_trade_date(container.selection_repository) or date.today()
    seeds = container.selection_service.list_seed_pool(trade_date=trade_date, market_code=market_code)
    return ApiSuccess(data=[SeedPoolView.model_validate(seed.__dict__) for seed in seeds])


def _latest_seed_trade_date(repository) -> date | None:
    backend_name = getattr(repository, 'backend_name', 'unknown')
    if backend_name == 'memory':
        store = getattr(repository, '_seed_pool', {})
        if not store:
            return None
        return max(current_date for current_date, _, _ in store.keys())

    db_path = getattr(repository, '_db_path', None)
    if db_path is None:
        return None
    with sqlite_session(db_path) as connection:
        row = connection.execute('SELECT MAX(trade_date) AS trade_date FROM stock_seed_pool_daily').fetchone()
    if row is None or row['trade_date'] is None:
        return None
    return date.fromisoformat(row['trade_date'])
