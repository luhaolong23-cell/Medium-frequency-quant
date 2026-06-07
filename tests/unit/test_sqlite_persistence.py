import tempfile
import unittest
import sqlite3
from datetime import date
from pathlib import Path

from packages.domain_core.market.entities import RegimeSnapshot
from packages.shared.container import AppContainer
from packages.shared.sqlite import initialize_sqlite


class SqlitePersistenceTests(unittest.TestCase):
    def test_sqlite_selection_run_supports_legacy_watchlist_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / 'quant.sqlite3'
            initialize_sqlite(db_path)
            with sqlite3.connect(db_path) as connection:
                connection.execute("DROP TABLE stock_watchlist_daily")
                connection.execute(
                    """
                    CREATE TABLE stock_watchlist_daily (
                        trade_date TEXT NOT NULL,
                        market_code TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        regime_trade_date TEXT,
                        watch_rank INTEGER NOT NULL,
                        company_name TEXT NOT NULL,
                        sector TEXT NOT NULL,
                        industry TEXT NOT NULL,
                        close REAL NOT NULL,
                        ret_60d REAL NOT NULL,
                        avg_dollar_volume_5d REAL NOT NULL,
                        avg_dollar_volume_20d REAL NOT NULL,
                        volume_ratio_5d REAL NOT NULL,
                        vol_20d REAL NOT NULL,
                        composite_score REAL NOT NULL,
                        theme_score REAL NOT NULL,
                        volume_score REAL NOT NULL,
                        valuation_score REAL NOT NULL,
                        size_score REAL NOT NULL,
                        valuation_band TEXT NOT NULL,
                        market_cap_bucket TEXT NOT NULL,
                        theme_tags_json TEXT NOT NULL,
                        source TEXT NOT NULL,
                        watch_reason TEXT NOT NULL,
                        computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        ret_5d REAL NOT NULL DEFAULT 0,
                        ret_20d REAL NOT NULL DEFAULT 0,
                        ma_20 REAL NOT NULL DEFAULT 0,
                        ma_60 REAL NOT NULL DEFAULT 0,
                        avg_dollar_volume_3d REAL NOT NULL DEFAULT 0,
                        volume_ratio_3d REAL NOT NULL DEFAULT 0,
                        volume_up_days_5d INTEGER NOT NULL DEFAULT 0,
                        distance_to_60d_high REAL NOT NULL DEFAULT 0,
                        momentum_acceleration REAL NOT NULL DEFAULT 0,
                        lagging_score REAL NOT NULL DEFAULT 0,
                        trend_recovery_score REAL NOT NULL DEFAULT 0,
                        momentum_acceleration_score REAL NOT NULL DEFAULT 0,
                        volume_probe_score REAL NOT NULL DEFAULT 0,
                        risk_control_score REAL NOT NULL DEFAULT 0,
                        PRIMARY KEY (trade_date, ticker)
                    )
                    """
                )
            writer = AppContainer(storage_backend='sqlite', sqlite_path=db_path, provider_mode='mock')
            writer.regime_repository.upsert_snapshots([
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

            result = writer.orchestrator.run(date(2026, 5, 25), ['ALL'])

            self.assertGreater(result.watchlist_count, 0)
            reader = AppContainer(storage_backend='sqlite', sqlite_path=db_path, provider_mode='mock')
            watchlist = reader.selection_service.list_watchlist(date(2026, 5, 25))
            self.assertEqual(len(watchlist), result.watchlist_count)

    def test_sqlite_repositories_persist_across_container_restarts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / 'quant.sqlite3'
            writer = AppContainer(storage_backend='sqlite', sqlite_path=db_path, provider_mode='mock')
            writer.regime_repository.upsert_snapshots([
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
            result = writer.orchestrator.run(date(2026, 5, 25), ['ALL'])
            self.assertEqual(result.computed_regimes, len(writer.markets_config.markets))

            reader = AppContainer(storage_backend='sqlite', sqlite_path=db_path, provider_mode='mock')
            markets = reader.refdata_service.list_markets()
            snapshots = reader.regime_service.list_by_date(date(2026, 5, 25))
            feature = reader.market_data_service.get_feature('US_EQ', date(2026, 5, 25))
            seeds = reader.selection_service.list_seed_pool(date(2026, 5, 25))
            candidates = reader.selection_service.list_candidates(date(2026, 5, 25))
            watchlist = reader.selection_service.list_watchlist(date(2026, 5, 25))
            heat = reader.selection_service.list_heat_snapshots(date(2026, 5, 25))
            signals = reader.trading_service.list_signals(date(2026, 5, 25))
            orders = reader.trading_service.list_orders(date(2026, 5, 25))
            positions = reader.trading_service.list_positions()

            self.assertEqual(len(markets), len(reader.markets_config.markets))
            self.assertEqual(len(snapshots), len(reader.markets_config.markets))
            self.assertIsNotNone(feature)
            self.assertEqual(feature.market_code, 'US_EQ')
            self.assertGreater(len(seeds), 0)
            self.assertIn('theme=', seeds[0].seed_reason)
            self.assertEqual(len(candidates), result.selected_candidates)
            self.assertEqual(len(watchlist), result.watchlist_count)
            self.assertGreater(len(heat), 0)
            self.assertEqual(len(signals), result.generated_signals)
            self.assertEqual(len(orders), result.executed_orders)
            self.assertEqual(len(positions), result.open_positions)
            if candidates:
                metadata = reader.selection_repository.get_metadata(candidates[0].market_code, candidates[0].ticker)
                self.assertIsNotNone(metadata)
                self.assertGreaterEqual(metadata.theme_score, 0)
            if positions:
                self.assertGreaterEqual(positions[0].peak_price, positions[0].avg_price)
                self.assertEqual(positions[0].entry_signal_type, 'BUY_VOLUME_SURGE')
            if orders:
                self.assertEqual(orders[0].position_effect, 'OPEN')
                self.assertEqual(orders[0].position_status_after, 'OPEN')
            if signals:
                self.assertEqual(signals[0].side, 'BUY')

    def test_sqlite_tracked_bull_markets_keep_last_bull_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / 'quant.sqlite3'
            writer = AppContainer(storage_backend='sqlite', sqlite_path=db_path, provider_mode='mock')
            writer.regime_repository.upsert_snapshots([
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
                ),
                RegimeSnapshot(
                    market_code='US_EQ',
                    trade_date=date(2026, 5, 25),
                    regime_status='BEAR',
                    bull_score=0.0,
                    trend_score=0.0,
                    relative_strength_score=0.0,
                    risk_penalty_score=0.0,
                    trigger_flags={'policy_breakout': False, 'trend_persistence': False, 'recovery_reversal': False, 'global_leader': False},
                    source_used={'rule_version': 'regime_v4_parallel_entries'},
                ),
            ])

            reader = AppContainer(storage_backend='sqlite', sqlite_path=db_path, provider_mode='mock')
            tracked = reader.regime_service.list_tracked_bull()
            self.assertEqual([snapshot.market_code for snapshot in tracked], ['US_EQ'])
            self.assertEqual(tracked[0].trade_date, date(2026, 5, 18))


if __name__ == '__main__':
    unittest.main()
