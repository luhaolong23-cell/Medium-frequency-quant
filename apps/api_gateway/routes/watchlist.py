from datetime import date

from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess, WatchlistStockView
from packages.shared.container import get_container

router = APIRouter(prefix='/watchlist', tags=['watchlist'])


@router.get('/today', response_model=ApiSuccess[list[WatchlistStockView]])
def watchlist_today(market_code: str | None = None) -> ApiSuccess[list[WatchlistStockView]]:
    watchlist = get_container().selection_service.list_watchlist(date.today(), market_code=market_code)
    return ApiSuccess(data=[WatchlistStockView.model_validate(item.__dict__) for item in watchlist])
