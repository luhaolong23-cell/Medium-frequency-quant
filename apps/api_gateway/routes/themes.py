from dataclasses import replace
from datetime import date

from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess, MarketLocalIndustryCatalogView, ThemeHeatView
from packages.shared.container import get_container
from packages.shared.sqlite import sqlite_session

router = APIRouter(prefix='/themes', tags=['themes'])


@router.get('/hot/today', response_model=ApiSuccess[list[ThemeHeatView]])
def hot_themes_today(market_code: str | None = None, theme_type: str | None = None) -> ApiSuccess[list[ThemeHeatView]]:
    container = get_container()
    trade_date = _latest_heat_trade_date(container.selection_repository) or date.today()
    snapshots = container.selection_service.list_heat_snapshots(
        trade_date=trade_date,
        market_code=market_code,
        theme_type=theme_type,
    )
    normalized_snapshots = [
        replace(item, theme_type='global_theme') if item.source == 'fixed_theme' and item.theme_type != 'global_theme' else item
        for item in snapshots
    ]
    return ApiSuccess(data=[ThemeHeatView.model_validate(item.__dict__) for item in normalized_snapshots])


def _latest_heat_trade_date(repository) -> date | None:
    backend_name = getattr(repository, 'backend_name', 'unknown')
    if backend_name == 'memory':
        store = getattr(repository, '_heat_snapshots', {})
        if not store:
            return None
        return max(current_date for current_date, _, _, _ in store.keys())

    db_path = getattr(repository, '_db_path', None)
    if db_path is None:
        return None
    with sqlite_session(db_path) as connection:
        row = connection.execute('SELECT MAX(trade_date) AS trade_date FROM selection_heat_daily').fetchone()
    if row is None or row['trade_date'] is None:
        return None
    return date.fromisoformat(row['trade_date'])


@router.get('/local-industry-catalog', response_model=ApiSuccess[list[MarketLocalIndustryCatalogView]])
def local_industry_catalog(market_code: str | None = None) -> ApiSuccess[list[MarketLocalIndustryCatalogView]]:
    container = get_container()
    catalogs = container.local_industry_indices_config.markets
    if market_code is not None:
        catalogs = [item for item in catalogs if item.market_code == market_code]
    return ApiSuccess(data=[MarketLocalIndustryCatalogView.model_validate(item.model_dump()) for item in catalogs])
