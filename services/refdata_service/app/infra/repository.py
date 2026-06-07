from pathlib import Path

from packages.domain_core.market.entities import Market, MarketProxy
from packages.shared.contracts import MarketRepository
from packages.shared.sqlite import initialize_sqlite, sqlite_session


class InMemoryRefdataRepository(MarketRepository):
    backend_name = "memory"

    def __init__(self) -> None:
        self._markets: dict[str, Market] = {}

    def upsert_markets(self, markets: list[Market]) -> None:
        self._markets.update({market.market_code: market for market in markets})

    def list_markets(self) -> list[Market]:
        return sorted(self._markets.values(), key=lambda item: item.market_code)

    def get_market(self, market_code: str) -> Market | None:
        return self._markets.get(market_code)


class SqliteRefdataRepository(MarketRepository):
    backend_name = "sqlite"

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        initialize_sqlite(self._db_path)

    def upsert_markets(self, markets: list[Market]) -> None:
        with sqlite_session(self._db_path) as connection:
            for market in markets:
                connection.execute(
                    """
                    INSERT INTO markets (market_code, market_name, country_code, region)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(market_code) DO UPDATE SET
                        market_name = excluded.market_name,
                        country_code = excluded.country_code,
                        region = excluded.region
                    """,
                    (market.market_code, market.market_name, market.country_code, market.region),
                )
                connection.execute(
                    "DELETE FROM market_proxies WHERE market_code = ?",
                    (market.market_code,),
                )
                connection.executemany(
                    """
                    INSERT INTO market_proxies (market_code, symbol, proxy_type, exchange_code, currency, priority)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            market.market_code,
                            proxy.symbol,
                            proxy.proxy_type,
                            proxy.exchange_code,
                            proxy.currency,
                            proxy.priority,
                        )
                        for proxy in market.proxies
                    ],
                )

    def list_markets(self) -> list[Market]:
        with sqlite_session(self._db_path) as connection:
            market_rows = connection.execute(
                "SELECT market_code, market_name, country_code, region FROM markets ORDER BY market_code"
            ).fetchall()
            proxy_rows = connection.execute(
                """
                SELECT market_code, symbol, proxy_type, exchange_code, currency, priority
                FROM market_proxies
                ORDER BY market_code, priority, symbol
                """
            ).fetchall()
        proxies_by_market: dict[str, list[MarketProxy]] = {}
        for row in proxy_rows:
            proxies_by_market.setdefault(row["market_code"], []).append(
                MarketProxy(
                    symbol=row["symbol"],
                    proxy_type=row["proxy_type"],
                    exchange_code=row["exchange_code"],
                    currency=row["currency"],
                    priority=row["priority"],
                )
            )
        return [
            Market(
                market_code=row["market_code"],
                market_name=row["market_name"],
                country_code=row["country_code"],
                region=row["region"],
                proxies=tuple(proxies_by_market.get(row["market_code"], [])),
            )
            for row in market_rows
        ]

    def get_market(self, market_code: str) -> Market | None:
        markets = [market for market in self.list_markets() if market.market_code == market_code]
        return markets[0] if markets else None
