from datetime import date

from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess, DataSourceAgentRequestView, DataSourceAgentResponseView, ThemeHeatView, ThemeStrategyAgentRequestView, ThemeStrategyAgentResponseView
from packages.shared.container import get_container
from packages.shared.sqlite import sqlite_session

router = APIRouter(prefix='/agent', tags=['agent'])


@router.post('/themes/compose', response_model=ApiSuccess[ThemeStrategyAgentResponseView])
def compose_theme_strategy(request: ThemeStrategyAgentRequestView) -> ApiSuccess[ThemeStrategyAgentResponseView]:
    container = get_container()
    trade_date = _latest_heat_trade_date(container.selection_repository) or date.today()
    themes = container.selection_service.list_heat_snapshots(
        trade_date=trade_date,
        market_code=request.selected_market if request.selected_market != 'ALL' else None,
        theme_type='industry',
    )
    result = container.theme_strategy_agent_service.compose_theme_strategy(
        request=request,
        themes=[ThemeHeatView.model_validate(item.__dict__) for item in themes],
    )
    return ApiSuccess(data=result)


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


@router.post('/data-sources/add', response_model=ApiSuccess[DataSourceAgentResponseView])
def add_data_source(request: DataSourceAgentRequestView) -> ApiSuccess[DataSourceAgentResponseView]:
    container = get_container()
    result = container.data_source_agent_service.add_source_from_dialog(request)
    get_container.cache_clear()
    return ApiSuccess(data=result)
