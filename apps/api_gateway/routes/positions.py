from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.shared.api_models import ApiSuccess, PaperPositionView, PositionSellRunView
from packages.shared.container import get_container

router = APIRouter(prefix='/positions', tags=['positions'])


class PositionSellItemRequest(BaseModel):
    market_code: str
    ticker: str


class PositionSellRequest(BaseModel):
    trade_date: date | None = None
    positions: list[PositionSellItemRequest] = Field(default_factory=list)


@router.get('', response_model=ApiSuccess[list[PaperPositionView]])
def positions(status: str | None = 'OPEN', market_code: str | None = None) -> ApiSuccess[list[PaperPositionView]]:
    positions = get_container().trading_service.list_positions(status=status, market_code=market_code)
    return ApiSuccess(data=[PaperPositionView.model_validate(position.__dict__) for position in positions])


@router.post('/sell', response_model=ApiSuccess[PositionSellRunView])
def sell_positions(request: PositionSellRequest) -> ApiSuccess[PositionSellRunView]:
    run_date = request.trade_date or date.today()
    selected = [(item.market_code, item.ticker) for item in request.positions]
    container = get_container()
    _, orders, sold_positions = container.trading_service.manual_sell_positions(run_date, selected)
    return ApiSuccess(
        data=PositionSellRunView(
            trade_date=run_date,
            requested_count=len(selected),
            sold_count=len(sold_positions),
            sold_positions=[f'{position.market_code}:{position.ticker}' for position in sold_positions],
            source_mode=container.trading_service.source_mode,
        )
    )
