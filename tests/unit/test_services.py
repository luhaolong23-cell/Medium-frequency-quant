import unittest
from datetime import date, timedelta

from packages.domain_core.market.entities import MarketFeature, RegimeSnapshot
from packages.shared.container import AppContainer


class FailingSingleMarketDataProvider:
    source_mode = 'test'

    def __init__(self, delegate, failing_market_code: str) -> None:
        self._delegate = delegate
        self._failing_market_code = failing_market_code

    def fetch_daily(self, markets, trade_date: date):
        if any(market.market_code == self._failing_market_code for market in markets):
            raise RuntimeError(f'boom {self._failing_market_code}')
        return self._delegate.fetch_daily(markets, trade_date)


class FakePositionDataProvider:
    source_mode = 'test'

    def __init__(self, drawdown_ticker: str) -> None:
        self._drawdown_ticker = drawdown_ticker

    def fetch_history(self, ticker: str, trade_date: date) -> list[tuple[date, float, float]]:
        base = trade_date - timedelta(days=5)
        if ticker == self._drawdown_ticker:
            return [
                (base, 100.0, 1_000_000.0),
                (base + timedelta(days=1), 110.0, 1_200_000.0),
                (base + timedelta(days=2), 115.0, 1_100_000.0),
                (base + timedelta(days=3), 118.0, 1_050_000.0),
                (base + timedelta(days=4), 120.0, 1_000_000.0),
                (trade_date, 80.0, 850_000.0),
            ]
        return [
            (base, 100.0, 1_000_000.0),
            (base + timedelta(days=1), 105.0, 1_050_000.0),
            (base + timedelta(days=2), 108.0, 1_030_000.0),
            (base + timedelta(days=3), 107.0, 1_020_000.0),
            (base + timedelta(days=4), 109.0, 1_040_000.0),
            (trade_date, 110.0, 1_060_000.0),
        ]


class ServiceFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = AppContainer(provider_mode='mock')

    def test_refdata_sync_loads_markets(self) -> None:
        markets = self.container.refdata_service.sync_markets()
        self.assertEqual(len(markets), len(self.container.markets_config.markets))
        self.assertEqual(markets[0].market_code, 'US_EQ')

    def test_market_data_ingest_all_markets(self) -> None:
        self.container.refdata_service.sync_markets()
        features = self.container.market_data_service.ingest_daily(date(2026, 5, 25), ['ALL'])
        self.assertEqual(len(features), len(self.container.markets_config.markets))

    def test_market_data_ingest_subset(self) -> None:
        self.container.refdata_service.sync_markets()
        features = self.container.market_data_service.ingest_daily(date(2026, 5, 25), ['US_EQ'])
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0].market_code, 'US_EQ')

    def test_market_data_ingest_all_markets_skips_single_failed_market(self) -> None:
        self.container.refdata_service.sync_markets()
        original_provider = self.container.market_data_service._market_data_provider
        self.container.market_data_service._market_data_provider = FailingSingleMarketDataProvider(original_provider, 'EG_EQ')
        try:
            features = self.container.market_data_service.ingest_daily(date(2026, 5, 25), ['ALL'])
        finally:
            self.container.market_data_service._market_data_provider = original_provider

        self.assertEqual(len(features), len(self.container.markets_config.markets) - 1)
        self.assertNotIn('EG_EQ', {feature.market_code for feature in features})

    def test_market_data_ingest_single_failed_market_still_raises(self) -> None:
        self.container.refdata_service.sync_markets()
        original_provider = self.container.market_data_service._market_data_provider
        self.container.market_data_service._market_data_provider = FailingSingleMarketDataProvider(original_provider, 'EG_EQ')
        try:
            with self.assertRaisesRegex(RuntimeError, 'boom EG_EQ'):
                self.container.market_data_service.ingest_daily(date(2026, 5, 25), ['EG_EQ'])
        finally:
            self.container.market_data_service._market_data_provider = original_provider

    def test_regime_run_generates_snapshots(self) -> None:
        self.container.refdata_service.sync_markets()
        self.container.market_data_service.ingest_daily(date(2026, 5, 25), ['ALL'])
        snapshots = self.container.regime_service.run_daily(date(2026, 5, 25), ['ALL'])
        self.assertEqual(len(snapshots), len(self.container.markets_config.markets))
        self.assertIn(snapshots[0].regime_status, {'BULL', 'NEUTRAL', 'BEAR'})

    def test_selection_daily_ranking_stores_candidates_and_watchlist(self) -> None:
        candidates, watchlist = self.container.selection_service.run_daily_selection(
            trade_date=date(2026, 5, 25),
            market_codes=['US_EQ'],
        )
        self.assertGreater(len(candidates), 0)
        self.assertLessEqual(len(watchlist), 5)
        stored_seeds = self.container.selection_service.list_seed_pool(date(2026, 5, 25), market_code='US_EQ')
        stored_candidates = self.container.selection_service.list_candidates(date(2026, 5, 25), market_code='US_EQ')
        stored_watchlist = self.container.selection_service.list_watchlist(date(2026, 5, 25), market_code='US_EQ')
        self.assertGreater(len(stored_seeds), 0)
        self.assertEqual(stored_seeds[0].trade_date, date(2026, 5, 25))
        self.assertIn('theme=', stored_seeds[0].seed_reason)
        self.assertEqual(len(candidates), len(stored_candidates))
        self.assertEqual(len(watchlist), len(stored_watchlist))
        if candidates:
            self.assertGreaterEqual(candidates[0].composite_score, candidates[-1].composite_score)
            self.assertGreaterEqual(candidates[0].volume_ratio_5d, 0)
            self.assertGreater(candidates[0].rank, 0)
        if watchlist:
            self.assertEqual(watchlist[0].watch_rank, 1)
            self.assertIn('volume_probe=', watchlist[0].watch_reason)

    def test_selection_daily_ranking_persists_heat_snapshots(self) -> None:
        self.container.selection_service.run_daily_selection(
            trade_date=date(2026, 5, 25),
            market_codes=['US_EQ'],
        )

        heat = self.container.selection_service.list_heat_snapshots(date(2026, 5, 25), market_code='US_EQ')

        self.assertGreater(len(heat), 0)
        self.assertEqual(heat[0].trade_date, date(2026, 5, 25))
        self.assertIn(heat[0].theme_type, {'industry', 'sector'})
        self.assertGreaterEqual(heat[0].smoothed_heat_score, heat[0].raw_heat_score)
        self.assertGreaterEqual(heat[0].constituent_count, 1)

    def test_trading_service_generates_paper_orders_once_per_position(self) -> None:
        _, watchlist = self.container.selection_service.run_daily_selection(
            trade_date=date(2026, 5, 25),
            market_codes=['US_EQ'],
        )
        signals, orders, positions = self.container.trading_service.run_daily(date(2026, 5, 25), watchlist)
        self.assertEqual(len(signals), len(watchlist))
        self.assertGreater(len(orders), 0)
        self.assertEqual(len(orders), len(positions))
        self.assertEqual(orders[0].requested_notional, 10000)
        self.assertEqual(orders[0].status, 'FILLED')
        self.assertEqual(orders[0].position_effect, 'OPEN')
        self.assertEqual(orders[0].position_status_after, 'OPEN')
        self.assertEqual(signals[0].side, 'BUY')
        repeated_signals, repeated_orders, repeated_positions = self.container.trading_service.run_daily(date(2026, 5, 26), watchlist)
        self.assertEqual(len(repeated_signals), len(watchlist))
        self.assertEqual(len(repeated_orders), 0)
        self.assertEqual(len(repeated_positions), len(positions))

    def test_position_monitor_closes_position_on_30pct_drawdown(self) -> None:
        buy_trade_date = date(2026, 5, 25)
        base_container = AppContainer(provider_mode='mock')
        _, watchlist = base_container.selection_service.run_daily_selection(
            trade_date=buy_trade_date,
            market_codes=['US_EQ'],
        )
        watch_item = watchlist[0]

        container = AppContainer(provider_mode='mock', position_data_provider=FakePositionDataProvider(watch_item.ticker))
        container.selection_service.run_daily_selection(
            trade_date=buy_trade_date,
            market_codes=['US_EQ'],
        )
        container.trading_service.run_daily(buy_trade_date, [watch_item])

        signals, orders, positions = container.trading_service.run_position_monitor(date(2026, 5, 26))

        sell_signal = next(signal for signal in signals if signal.ticker == watch_item.ticker)
        self.assertTrue(sell_signal.triggered)
        self.assertEqual(sell_signal.side, 'SELL')
        self.assertEqual(sell_signal.signal_type, 'SELL_TRAILING_DRAWDOWN')
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side, 'SELL')
        self.assertEqual(orders[0].position_effect, 'CLOSE')
        self.assertEqual(orders[0].position_status_after, 'CLOSED')
        closed_position = next(position for position in positions if position.ticker == watch_item.ticker)
        self.assertEqual(closed_position.status, 'CLOSED')
        self.assertEqual(closed_position.closed_trade_date, date(2026, 5, 26))
        self.assertLessEqual(closed_position.closed_price or 0.0, closed_position.peak_price * 0.7)


    def test_existing_bull_market_is_only_incrementally_updated(self) -> None:
        self.container.regime_repository.upsert_snapshots([
            RegimeSnapshot(
                market_code='US_EQ',
                trade_date=date(2026, 5, 18),
                regime_status='BULL',
                bull_score=68.0,
                trend_score=44.0,
                relative_strength_score=24.0,
                risk_penalty_score=0.0,
                trigger_flags={'policy_breakout': True, 'trend_persistence': True, 'recovery_reversal': True, 'global_leader': True},
                source_used={'rule_version': 'regime_v4_parallel_entries'},
            ),
        ])
        self.container.market_data_repository.upsert_features([
            MarketFeature(
                market_code='US_EQ',
                trade_date=date(2026, 5, 26),
                price_proxy='SPY',
                close=400.0,
                ma_120=480.0,
                ma_200=470.0,
                ret_60d=-0.12,
                ret_120d=-0.18,
                vol_20d=0.3,
                drawdown_60d=0.25,
                relative_strength_world=-0.2,
                fx_ret_60d=0.0,
                avg_volume_recent=80.0,
                avg_volume_prior=100.0,
                volume_ratio_5d=0.8,
                consecutive_up_weeks=0,
                ma_5=395.0,
                ma_10=405.0,
                ma_20=415.0,
                ma_60=430.0,
                ret_1d=-0.03,
                ret_5d=-0.08,
                turnover_ratio_20d=0.9,
                avg_turnover_ratio_3d=0.85,
                volume_up_days_2d=0,
                volume_up_days_3d=0,
                consecutive_up_days=0,
                source='test',
            ),
        ])

        snapshots = self.container.regime_service.run_daily(date(2026, 5, 26), ['US_EQ'])

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].regime_status, 'BULL')
        self.assertEqual(snapshots[0].trade_date, date(2026, 5, 26))
        self.assertEqual(snapshots[0].bull_score, 0.0)
        self.assertEqual(snapshots[0].trend_score, 0.0)
        self.assertEqual(snapshots[0].relative_strength_score, 0.0)
        self.assertEqual(
            snapshots[0].trigger_flags,
            {
                'policy_breakout': False,
                'trend_persistence': False,
                'recovery_reversal': False,
                'global_leader': False,
            },
        )
        self.assertEqual(snapshots[0].source_used.get('incremental_bull_lock'), 'true')
        latest = self.container.regime_service.get_latest_snapshot('US_EQ')
        self.assertIsNotNone(latest)
        self.assertEqual(latest.regime_status, 'BULL')
        self.assertEqual(latest.trade_date, date(2026, 5, 26))


    def test_legacy_bull_snapshot_does_not_lock_new_scoring(self) -> None:
        self.container.regime_repository.upsert_snapshots([
            RegimeSnapshot(
                market_code='US_EQ',
                trade_date=date(2026, 5, 18),
                regime_status='BULL',
                bull_score=68.0,
                trend_score=44.0,
                relative_strength_score=24.0,
                risk_penalty_score=0.0,
                trigger_flags={'policy_breakout': True, 'trend_persistence': True, 'recovery_reversal': True, 'global_leader': True},
                source_used={'rule_version': 'legacy_v1'},
            ),
        ])
        self.container.market_data_repository.upsert_features([
            MarketFeature(
                market_code='US_EQ',
                trade_date=date(2026, 5, 26),
                price_proxy='SPY',
                close=400.0,
                ma_120=480.0,
                ma_200=470.0,
                ret_60d=-0.12,
                ret_120d=-0.18,
                vol_20d=0.3,
                drawdown_60d=0.25,
                relative_strength_world=-0.2,
                fx_ret_60d=0.0,
                avg_volume_recent=80.0,
                avg_volume_prior=100.0,
                volume_ratio_5d=0.8,
                consecutive_up_weeks=0,
                ma_5=395.0,
                ma_10=405.0,
                ma_20=415.0,
                ma_60=430.0,
                ret_1d=-0.03,
                ret_5d=-0.08,
                turnover_ratio_20d=0.9,
                avg_turnover_ratio_3d=0.85,
                volume_up_days_2d=0,
                volume_up_days_3d=0,
                consecutive_up_days=0,
                source='test',
            ),
        ])

        snapshots = self.container.regime_service.run_daily(date(2026, 5, 26), ['US_EQ'])

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].regime_status, 'BEAR')
        self.assertEqual(snapshots[0].bull_score, 0.0)
        self.assertNotIn('incremental_bull_lock', snapshots[0].source_used)

    def test_tracked_bull_markets_persist_until_cancel_logic_exists(self) -> None:
        self.container.regime_repository.upsert_snapshots([
            RegimeSnapshot(
                market_code='US_EQ',
                trade_date=date(2026, 5, 18),
                regime_status='BULL',
                bull_score=100.0,
                trend_score=50.0,
                relative_strength_score=50.0,
                risk_penalty_score=0.0,
                trigger_flags={
                    'policy_breakout': True,
                    'trend_persistence': True,
                    'recovery_reversal': True,
                    'global_leader': True,
                },
                source_used={'rule_version': 'regime_v4_parallel_entries'},
            ),
            RegimeSnapshot(
                market_code='US_EQ',
                trade_date=date(2026, 5, 25),
                regime_status='NEUTRAL',
                bull_score=50.0,
                trend_score=50.0,
                relative_strength_score=0.0,
                risk_penalty_score=0.0,
                trigger_flags={
                    'policy_breakout': False,
                    'trend_persistence': True,
                    'recovery_reversal': True,
                    'global_leader': False,
                },
                source_used={'rule_version': 'regime_v4_parallel_entries'},
            ),
        ])
        tracked = self.container.regime_service.list_tracked_bull()
        self.assertEqual([snapshot.market_code for snapshot in tracked], ['US_EQ'])
        self.assertEqual(tracked[0].trade_date, date(2026, 5, 18))


if __name__ == '__main__':
    unittest.main()
