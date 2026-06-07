import unittest
from datetime import date

import pandas as pd

from packages.domain_core.market.entities import Market, MarketProxy
from packages.domain_core.selection.entities import StockSeed
from packages.shared.container import AppContainer
from packages.shared.settings import DataSourcesConfig, RetrySettings, SourceSettings, TimeoutsSettings
from services.market_data_service.app.infra.provider import YFinanceMarketDataProvider
from services.selection_service.app.infra.provider import YFinanceSelectionDataProvider


class _FakeTicker:
    def __init__(self, history_frame: pd.DataFrame) -> None:
        self._history_frame = history_frame

    def history(self, *, period: str, interval: str, auto_adjust: bool):
        del period, interval, auto_adjust
        return self._history_frame.copy()


class _UnexpectedTicker:
    def history(self, *, period: str, interval: str, auto_adjust: bool):
        del period, interval, auto_adjust
        raise AssertionError('per-ticker history should not be used when batch download is available')


def _ticker_factory(frames: dict[str, pd.DataFrame]):
    def factory(symbol: str):
        return _FakeTicker(frames.get(symbol, pd.DataFrame()))

    return factory


def _history_frame(*, start_close: float, daily_step: float, start_volume: float, volume_step: float) -> pd.DataFrame:
    periods = 240
    dates = pd.date_range('2025-01-01', periods=periods, freq='D')
    closes = [round(start_close + daily_step * offset, 4) for offset in range(periods)]
    volumes = [round(start_volume + volume_step * offset, 2) for offset in range(periods)]
    return pd.DataFrame({'Close': closes, 'Volume': volumes}, index=dates)


def _data_sources_config() -> DataSourcesConfig:
    return DataSourcesConfig(
        sources={
            'market_bars': SourceSettings(primary='yfinance'),
            'market_reference': SourceSettings(primary='config'),
            'fx_rates': SourceSettings(primary='none'),
        },
        timeouts=TimeoutsSettings(connect_seconds=5, read_seconds=5),
        retry=RetrySettings(max_attempts=1, backoff_seconds=0),
    )


class YFinanceProviderTests(unittest.TestCase):
    def test_market_provider_falls_back_to_next_proxy_when_first_proxy_has_no_history(self) -> None:
        trade_date = date(2026, 5, 25)
        provider = YFinanceMarketDataProvider(
            data_sources_config=_data_sources_config(),
            world_benchmark_symbol='ACWI',
            ticker_factory=_ticker_factory({
                'BROKEN': pd.DataFrame(),
                'WORKS': _history_frame(start_close=100.0, daily_step=0.3, start_volume=10_000_000, volume_step=50_000),
                'ACWI': _history_frame(start_close=90.0, daily_step=0.2, start_volume=8_000_000, volume_step=25_000),
            }),
        )
        market = Market(
            market_code='TEST_EQ',
            market_name='Test Equities',
            country_code='US',
            region='TEST',
            proxies=(
                MarketProxy(symbol='BROKEN', proxy_type='ETF', exchange_code='TEST', currency='USD', priority=1),
                MarketProxy(symbol='WORKS', proxy_type='ETF', exchange_code='TEST', currency='USD', priority=2),
            ),
        )

        observations = provider.fetch_daily([market], trade_date)

        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].price_proxy, 'WORKS')
        self.assertEqual(observations[0].source, 'yfinance')
        self.assertGreater(observations[0].close, 0)

    def test_selection_provider_builds_screen_observation(self) -> None:
        trade_date = date(2026, 5, 25)
        provider = YFinanceSelectionDataProvider(
            data_sources_config=_data_sources_config(),
            ticker_factory=_ticker_factory({
                'AAPL': _history_frame(start_close=150.0, daily_step=0.4, start_volume=20_000_000, volume_step=75_000),
            }),
            download=lambda tickers, **kwargs: _history_frame(
                start_close=150.0,
                daily_step=0.4,
                start_volume=20_000_000,
                volume_step=75_000,
            ),
        )
        seed = StockSeed(
            market_code='US_EQ',
            ticker='AAPL',
            company_name='Apple Inc.',
            sector='Information Technology',
            industry='Consumer Electronics',
            exchange='NASDAQ',
            currency='USD',
            country_code='US',
        )

        observations = provider.fetch_daily([seed], trade_date)

        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].source, 'yfinance')
        self.assertGreater(observations[0].avg_dollar_volume_20d, 0)
        self.assertGreater(observations[0].close, 0)

    def test_selection_provider_batches_history_requests(self) -> None:
        trade_date = date(2026, 5, 25)
        frames = {
            'AAPL': _history_frame(start_close=150.0, daily_step=0.4, start_volume=20_000_000, volume_step=75_000),
            'MSFT': _history_frame(start_close=200.0, daily_step=0.3, start_volume=18_000_000, volume_step=50_000),
        }
        download_calls: list[tuple[str, ...]] = []

        def download(tickers, **kwargs):
            download_calls.append(tuple(tickers.split()))
            return pd.concat(
                {symbol: frame[['Close', 'Volume']] for symbol, frame in frames.items()},
                axis=1,
            )

        provider = YFinanceSelectionDataProvider(
            data_sources_config=_data_sources_config(),
            ticker_factory=lambda symbol: _UnexpectedTicker(),
            download=download,
        )
        seeds = [
            StockSeed(
                market_code='US_EQ',
                ticker='AAPL',
                company_name='Apple Inc.',
                sector='Information Technology',
                industry='Consumer Electronics',
                exchange='NASDAQ',
                currency='USD',
                country_code='US',
            ),
            StockSeed(
                market_code='US_EQ',
                ticker='MSFT',
                company_name='Microsoft Corporation',
                sector='Information Technology',
                industry='Software Infrastructure',
                exchange='NASDAQ',
                currency='USD',
                country_code='US',
            ),
        ]

        observations = provider.fetch_daily(seeds, trade_date)

        self.assertEqual(len(observations), 2)
        self.assertEqual(download_calls, [('AAPL', 'MSFT')])
        self.assertEqual({item.ticker for item in observations}, {'AAPL', 'MSFT'})

    def test_container_wires_yfinance_mode(self) -> None:
        container = AppContainer(provider_mode='yfinance', storage_backend='memory')

        self.assertEqual(container.market_data_service.source_mode, 'yfinance')
        self.assertEqual(container.selection_service.source_mode, 'yfinance')


if __name__ == '__main__':
    unittest.main()
