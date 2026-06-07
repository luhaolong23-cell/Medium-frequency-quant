import json
import unittest
from datetime import date, datetime, timedelta, timezone
from urllib.parse import unquote

import httpx

from packages.domain_core.market.entities import Market, MarketProxy
from packages.shared.settings import DataSourcesConfig, RetrySettings, SourceSettings, TimeoutsSettings
from services.market_data_service.app.infra.provider import YahooFinanceMarketDataProvider


class YahooProviderTests(unittest.TestCase):
    def test_provider_falls_back_to_next_proxy_when_first_proxy_fails(self) -> None:
        trade_date = date(2026, 5, 25)
        history_payload = _chart_payload(trade_date, 240, start_price=100.0, daily_step=0.4)

        def handler(request: httpx.Request) -> httpx.Response:
            symbol = unquote(request.url.path.rsplit("/", 1)[-1])
            if symbol == "BROKEN":
                return httpx.Response(404, json={"chart": {"result": None, "error": {"description": "not found"}}})
            if symbol in {"WORKS", "ACWI"}:
                return httpx.Response(200, json=history_payload)
            return httpx.Response(404, json={"chart": {"result": None, "error": {"description": f"unknown symbol {symbol}"}}})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = YahooFinanceMarketDataProvider(
            data_sources_config=_data_sources_config(),
            chart_base_url="https://query1.finance.yahoo.com",
            world_benchmark_symbol="ACWI",
            client=client,
        )
        market = Market(
            market_code="TEST_EQ",
            market_name="Test Equities",
            country_code="US",
            region="TEST",
            proxies=(
                MarketProxy(symbol="BROKEN", proxy_type="ETF", exchange_code="TEST", currency="USD", priority=1),
                MarketProxy(symbol="WORKS", proxy_type="ETF", exchange_code="TEST", currency="USD", priority=2),
            ),
        )

        observations = provider.fetch_daily([market], trade_date)

        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].price_proxy, "WORKS")
        self.assertEqual(observations[0].source, "yahoo")
        self.assertGreater(observations[0].close, 0)


class _JsonEncoder(json.JSONEncoder):
    pass


def _chart_payload(trade_date: date, periods: int, *, start_price: float, daily_step: float) -> dict:
    timestamps: list[int] = []
    closes: list[float] = []
    current = start_price
    start_day = trade_date - timedelta(days=periods - 1)
    for offset in range(periods):
        trade_day = start_day + timedelta(days=offset)
        timestamps.append(int(datetime.combine(trade_day, datetime.min.time(), tzinfo=timezone.utc).timestamp()))
        closes.append(round(current, 4))
        current += daily_step
    return {
        "chart": {
            "result": [
                {
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [{"close": closes}],
                        "adjclose": [{"adjclose": closes}],
                    },
                }
            ],
            "error": None,
        }
    }


def _data_sources_config() -> DataSourcesConfig:
    return DataSourcesConfig(
        sources={
            "market_bars": SourceSettings(primary="yahoo"),
            "market_reference": SourceSettings(primary="config"),
            "fx_rates": SourceSettings(primary="none"),
        },
        timeouts=TimeoutsSettings(connect_seconds=5, read_seconds=5),
        retry=RetrySettings(max_attempts=1, backoff_seconds=0),
    )


if __name__ == "__main__":
    unittest.main()
