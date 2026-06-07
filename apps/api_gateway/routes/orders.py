from datetime import date

from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess, PaperOrderView
from packages.shared.container import get_container

router = APIRouter(prefix='/orders', tags=['orders'])


@router.get('/today', response_model=ApiSuccess[list[PaperOrderView]])
def orders_today(market_code: str | None = None) -> ApiSuccess[list[PaperOrderView]]:
    orders = get_container().trading_service.list_orders(date.today(), market_code=market_code)
    return ApiSuccess(data=[PaperOrderView.model_validate(order.__dict__) for order in orders])
