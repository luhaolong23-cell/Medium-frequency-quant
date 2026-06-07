from packages.shared.api_models import ApiSuccess
from packages.shared.settings import MarketSettings
from pydantic import BaseModel


class MarketProxySchema(BaseModel):
    symbol: str
    proxy_type: str
    exchange_code: str
    currency: str
    priority: int


class MarketSchema(BaseModel):
    market_code: str
    market_name: str
    country_code: str
    region: str
    proxies: list[MarketProxySchema]


class SyncMarketsResult(BaseModel):
    synced_count: int
    market_codes: list[str]


SyncMarketsResponse = ApiSuccess[SyncMarketsResult]
ListMarketsResponse = ApiSuccess[list[MarketSchema]]

_ = MarketSettings
