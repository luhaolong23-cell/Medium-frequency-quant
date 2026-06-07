from fastapi import APIRouter

from packages.shared.api_models import ApiSuccess
from packages.shared.container import get_container
from services.refdata_service.app.api.schemas import (
    ListMarketsResponse,
    MarketProxySchema,
    MarketSchema,
    SyncMarketsResponse,
    SyncMarketsResult,
)

router = APIRouter(prefix="/v1/refdata", tags=["refdata"])


@router.post("/sync/markets", response_model=SyncMarketsResponse)
def sync_markets() -> SyncMarketsResponse:
    synced = get_container().refdata_service.sync_markets()
    return ApiSuccess(
        data=SyncMarketsResult(
            synced_count=len(synced),
            market_codes=[market.market_code for market in synced],
        )
    )


@router.get("/markets", response_model=ListMarketsResponse)
def list_markets() -> ListMarketsResponse:
    markets = get_container().refdata_service.list_markets()
    return ApiSuccess(
        data=[
            MarketSchema(
                market_code=market.market_code,
                market_name=market.market_name,
                country_code=market.country_code,
                region=market.region,
                proxies=[
                    MarketProxySchema(
                        symbol=proxy.symbol,
                        proxy_type=proxy.proxy_type,
                        exchange_code=proxy.exchange_code,
                        currency=proxy.currency,
                        priority=proxy.priority,
                    )
                    for proxy in market.proxies
                ],
            )
            for market in markets
        ]
    )
