from packages.domain_core.market.entities import Market, MarketProxy
from packages.shared.contracts import MarketRepository
from packages.shared.logging import get_logger, log_event
from packages.shared.settings import MarketsConfig


logger = get_logger(__name__)


class RefdataService:
    def __init__(self, config: MarketsConfig, repository: MarketRepository) -> None:
        self._config = config
        self._repository = repository

    def sync_markets(self) -> list[Market]:
        markets = [self._to_entity(item) for item in self._config.markets]
        self._repository.upsert_markets(markets)
        log_event(
            logger,
            'refdata.sync_markets.completed',
            synced_count=len(markets),
            market_codes=[market.market_code for market in markets],
        )
        return markets

    def list_markets(self) -> list[Market]:
        markets = self._repository.list_markets()
        if markets:
            return markets
        return self.sync_markets()

    @staticmethod
    def _to_entity(settings) -> Market:
        proxies = tuple(
            MarketProxy(
                symbol=proxy.symbol,
                proxy_type=proxy.proxy_type,
                exchange_code=proxy.exchange_code,
                currency=proxy.currency,
                priority=proxy.priority,
            )
            for proxy in settings.proxies
        )
        return Market(
            market_code=settings.market_code,
            market_name=settings.market_name,
            country_code=settings.country_code,
            region=settings.region,
            proxies=proxies,
        )
