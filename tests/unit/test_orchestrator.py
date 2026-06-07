import unittest
from datetime import date

from packages.domain_core.market.entities import Market, MarketFeature, MarketProxy, RegimeSnapshot
from packages.shared.container import AppContainer
from packages.shared.orchestrator import DailyRunOrchestrator




class _StubRefdataService:
    def __init__(self, markets):
        self._markets = markets

    def sync_markets(self):
        return self._markets


class _StubMarketDataService:
    source_mode = 'yfinance'

    def __init__(self, features_by_code):
        self._features_by_code = features_by_code
        self.ingest_calls = 0

    def get_feature(self, market_code, trade_date):
        feature = self._features_by_code.get(market_code)
        if feature is not None and feature.trade_date == trade_date:
            return feature
        return None

    def ingest_daily(self, trade_date, market_codes):
        self.ingest_calls += 1
        raise AssertionError('ingest_daily should not run when same-day features already exist')


class _StubRegimeService:
    def __init__(self, snapshots_by_code):
        self._snapshots_by_code = snapshots_by_code
        self.run_calls = 0

    def get_snapshot(self, market_code, trade_date):
        snapshot = self._snapshots_by_code.get(market_code)
        if snapshot is not None and snapshot.trade_date == trade_date:
            return snapshot
        return None

    def run_daily(self, trade_date, market_codes):
        self.run_calls += 1
        raise AssertionError('run_daily should not run when same-day snapshots already exist')

    def list_tracked_bull(self):
        return list(self._snapshots_by_code.values())


class _StubSelectionService:
    source_mode = 'yfinance'

    def __init__(self) -> None:
        self.inventory_calls = 0
        self.bar_calls = 0
        self.metric_calls = 0

    def sync_market_universe_inventory(self, trade_date, market_codes, replace_market_codes=None):
        self.inventory_calls += 1
        return []

    def sync_market_universe_bars(self, trade_date, market_codes):
        self.bar_calls += 1
        return []

    def compute_market_universe_metrics(self, trade_date, market_codes, replace_market_codes=None):
        self.metric_calls += 1
        return []

    def prepare_hot_themes(self, trade_date, market_codes, replace_market_codes=None):
        return []

    def run_daily_selection(self, trade_date, market_codes, replace_market_codes=None, regime_trade_date=None, prepared_heat_snapshots=None):
        return [], []


class _StubTradingService:
    source_mode = 'paper'

    def run_daily(self, trade_date, watchlist):
        return [], [], []


class OrchestratorTests(unittest.TestCase):
    def test_run_returns_expected_counts(self) -> None:
        container = AppContainer(provider_mode='mock')
        container.regime_repository.upsert_snapshots([
            RegimeSnapshot(
                market_code='US_EQ',
                trade_date=date(2026, 5, 18),
                regime_status='BULL',
                bull_score=100.0,
                trend_score=50.0,
                relative_strength_score=50.0,
                risk_penalty_score=0.0,
                trigger_flags={'policy_breakout': True, 'trend_persistence': True, 'recovery_reversal': True, 'global_leader': True},
                source_used={'rule_version': 'regime_v4_parallel_entries'},
            )
        ])
        result = container.orchestrator.run(date(2026, 5, 25), ['ALL'])
        expected_market_count = len(container.markets_config.markets)
        self.assertEqual(result.synced_markets, expected_market_count)
        self.assertEqual(result.computed_features, expected_market_count)
        self.assertEqual(result.computed_regimes, expected_market_count)
        self.assertGreaterEqual(result.selected_candidates, 0)
        self.assertGreaterEqual(result.watchlist_count, 0)
        self.assertGreaterEqual(result.generated_signals, 0)
        self.assertGreaterEqual(result.executed_orders, 0)
        self.assertGreaterEqual(result.open_positions, 0)
        self.assertEqual([step.name for step in result.steps], [
            'sync_refdata',
            'ingest_market_bars',
            'run_regime',
            'sync_stock_universe_inventory',
            'prepare_hot_themes',
            'run_daily_selection',
            'run_paper_trading',
        ])


    def test_run_reports_progress_after_each_step(self) -> None:
        trade_date = date(2026, 5, 25)
        markets = [
            Market(
                market_code='US_EQ',
                market_name='US Equities',
                country_code='US',
                region='NORTH_AMERICA',
                proxies=(MarketProxy(symbol='SPY', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1),),
            )
        ]
        feature = MarketFeature(
            market_code='US_EQ',
            trade_date=trade_date,
            price_proxy='SPY',
            close=100.0,
            ma_120=95.0,
            ma_200=90.0,
            ret_60d=0.1,
            ret_120d=0.2,
            vol_20d=0.15,
            drawdown_60d=-0.05,
            relative_strength_world=0.03,
            fx_ret_60d=0.0,
            avg_volume_recent=1000.0,
            avg_volume_prior=900.0,
            volume_ratio_5d=1.1111,
            consecutive_up_weeks=3,
            source='yfinance',
        )
        snapshot = RegimeSnapshot(
            market_code='US_EQ',
            trade_date=trade_date,
            regime_status='BULL',
            bull_score=100.0,
            trend_score=50.0,
            relative_strength_score=50.0,
            risk_penalty_score=0.0,
            trigger_flags={'policy_breakout': True, 'trend_persistence': True, 'recovery_reversal': True, 'global_leader': True},
            source_used={'rule_version': 'regime_v4_parallel_entries'},
        )
        market_data_service = _StubMarketDataService({'US_EQ': feature})
        regime_service = _StubRegimeService({'US_EQ': snapshot})
        selection_service = _StubSelectionService()
        orchestrator = DailyRunOrchestrator(
            refdata_service=_StubRefdataService(markets),
            market_data_service=market_data_service,
            regime_service=regime_service,
            selection_service=selection_service,
            trading_service=_StubTradingService(),
        )
        progress_updates = []

        orchestrator.run(
            trade_date,
            ['US_EQ'],
            progress_callback=progress_updates.append,
        )

        self.assertEqual(
            [item['current_step'] for item in progress_updates],
            [
                'sync_refdata',
                'ingest_market_bars',
                'run_regime',
                'sync_stock_universe_inventory',
                'prepare_hot_themes',
                'run_daily_selection',
                'run_paper_trading',
            ],
        )
        self.assertEqual(progress_updates[-1]['computed_regimes'], 1)
        self.assertEqual(progress_updates[-1]['selected_candidates'], 0)

    def test_run_reuses_existing_same_day_market_and_regime_results(self) -> None:
        trade_date = date(2026, 5, 25)
        markets = [
            Market(
                market_code='US_EQ',
                market_name='US Equities',
                country_code='US',
                region='NORTH_AMERICA',
                proxies=(MarketProxy(symbol='SPY', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1),),
            )
        ]
        feature = MarketFeature(
            market_code='US_EQ',
            trade_date=trade_date,
            price_proxy='SPY',
            close=100.0,
            ma_120=95.0,
            ma_200=90.0,
            ret_60d=0.1,
            ret_120d=0.2,
            vol_20d=0.15,
            drawdown_60d=-0.05,
            relative_strength_world=0.03,
            fx_ret_60d=0.0,
            avg_volume_recent=1000.0,
            avg_volume_prior=900.0,
            volume_ratio_5d=1.1111,
            consecutive_up_weeks=3,
            source='yfinance',
        )
        snapshot = RegimeSnapshot(
            market_code='US_EQ',
            trade_date=trade_date,
            regime_status='BULL',
            bull_score=100.0,
            trend_score=50.0,
            relative_strength_score=50.0,
            risk_penalty_score=0.0,
            trigger_flags={'policy_breakout': True, 'trend_persistence': True, 'recovery_reversal': True, 'global_leader': True},
            source_used={'rule_version': 'regime_v4_parallel_entries'},
        )
        market_data_service = _StubMarketDataService({'US_EQ': feature})
        regime_service = _StubRegimeService({'US_EQ': snapshot})
        selection_service = _StubSelectionService()
        orchestrator = DailyRunOrchestrator(
            refdata_service=_StubRefdataService(markets),
            market_data_service=market_data_service,
            regime_service=regime_service,
            selection_service=selection_service,
            trading_service=_StubTradingService(),
        )

        result = orchestrator.run(trade_date, ['US_EQ'])

        self.assertEqual(result.computed_features, 1)
        self.assertEqual(result.computed_regimes, 1)
        self.assertEqual(market_data_service.ingest_calls, 0)
        self.assertEqual(regime_service.run_calls, 0)
        self.assertEqual(selection_service.inventory_calls, 1)
        self.assertEqual(selection_service.bar_calls, 0)
        self.assertEqual(selection_service.metric_calls, 0)


if __name__ == '__main__':
    unittest.main()
