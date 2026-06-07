import unittest
from dataclasses import replace
from datetime import date

from packages.domain_core.market.entities import Market, MarketObservation, MarketProxy
from packages.domain_core.selection.entities import StockScreenObservation, StockSeed
from services.market_data_service.app.infra.provider import CompositeMarketDataProvider
from services.selection_service.app.infra.provider import CompositeSelectionDataProvider


class CompositeProviderTests(unittest.TestCase):
    def test_market_composite_prefers_consensus_observation(self) -> None:
        trade_date = date(2026, 5, 25)
        market = Market(
            market_code='US_EQ',
            market_name='US Equity',
            country_code='US',
            region='NA',
            proxies=(MarketProxy(symbol='SPY', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1),),
        )
        provider = CompositeMarketDataProvider([
            _MarketProvider('source_a', [_market_observation(trade_date, 101.0, 1.10)]),
            _MarketProvider('source_b', [_market_observation(trade_date, 100.0, 1.08)]),
            _MarketProvider('source_c', [_market_observation(trade_date, 150.0, 2.10)]),
        ])

        observations = provider.fetch_daily([market], trade_date)

        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].source, 'source_a')
        self.assertEqual(observations[0].close, 101.0)

    def test_selection_composite_prefers_consensus_observation(self) -> None:
        trade_date = date(2026, 5, 25)
        seed = StockSeed(
            market_code='US_EQ',
            ticker='AAPL',
            company_name='Apple Inc.',
            sector='Technology',
            industry='Consumer Electronics',
            exchange='NASDAQ',
            currency='USD',
            country_code='US',
        )
        provider = CompositeSelectionDataProvider([
            _SelectionProvider('source_a', [_selection_observation(trade_date, 181.0, 1.20)]),
            _SelectionProvider('source_b', [_selection_observation(trade_date, 180.0, 1.18)]),
            _SelectionProvider('source_c', [_selection_observation(trade_date, 220.0, 2.00)]),
        ])

        observations = provider.fetch_daily([seed], trade_date)

        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].source, 'source_a')
        self.assertEqual(observations[0].close, 181.0)


class _MarketProvider:
    def __init__(self, source_mode: str, observations: list[MarketObservation]) -> None:
        self.source_mode = source_mode
        self._observations = observations

    def fetch_daily(self, markets, trade_date: date) -> list[MarketObservation]:
        return [replace(observation, source=self.source_mode) for observation in self._observations]


class _SelectionProvider:
    def __init__(self, source_mode: str, observations: list[StockScreenObservation]) -> None:
        self.source_mode = source_mode
        self._observations = observations

    def fetch_daily(self, seeds, trade_date: date) -> list[StockScreenObservation]:
        return [replace(observation, source=self.source_mode) for observation in self._observations]


def _market_observation(trade_date: date, close: float, volume_ratio_5d: float) -> MarketObservation:
    return MarketObservation(
        market_code='US_EQ',
        trade_date=trade_date,
        price_proxy='SPY',
        close=close,
        ma_120=close - 1,
        ma_200=close - 2,
        ret_60d=0.10,
        ret_120d=0.20,
        vol_20d=0.18,
        drawdown_60d=-0.05,
        relative_strength_world=0.03,
        fx_ret_60d=0.0,
        avg_volume_recent=110000000.0,
        avg_volume_prior=100000000.0,
        volume_ratio_5d=volume_ratio_5d,
        consecutive_up_weeks=3,
        source='placeholder',
    )


def _selection_observation(trade_date: date, close: float, volume_ratio_5d: float) -> StockScreenObservation:
    return StockScreenObservation(
        market_code='US_EQ',
        ticker='AAPL',
        trade_date=trade_date,
        close=close,
        ma_20=close - 0.5,
        ma_60=close - 1.0,
        ma_120=close - 1.5,
        ma_200=close - 2.0,
        ret_5d=0.03,
        ret_20d=0.08,
        ret_60d=0.12,
        avg_dollar_volume_3d=130000000.0,
        avg_dollar_volume_5d=120000000.0,
        avg_dollar_volume_20d=100000000.0,
        volume_ratio_3d=1.3,
        volume_ratio_5d=volume_ratio_5d,
        volume_up_days_5d=3,
        distance_to_60d_high=0.08,
        momentum_acceleration=0.012,
        vol_20d=0.22,
        source='placeholder',
    )


if __name__ == '__main__':
    unittest.main()
