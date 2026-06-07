import os
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from apps.api_gateway.main import app
from packages.domain_core.market.entities import MarketFeature, RegimeSnapshot
from packages.domain_core.selection.entities import ThemeHeatSnapshot
from packages.shared.config import load_yaml
from packages.shared.container import get_container, reset_container
from packages.shared.runtime import project_root


class ApiGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_provider = os.environ.get('QUANT_MARKET_DATA_PROVIDER')
        self._original_data_sources_path = os.environ.get('QUANT_DATA_SOURCES_PATH')
        self._original_scheduler_log_path = os.environ.get('QUANT_SCHEDULER_LOG_PATH')
        self._temp_dir = TemporaryDirectory()
        self._data_sources_path = Path(self._temp_dir.name) / 'data_sources.yaml'
        self._scheduler_log_path = Path(self._temp_dir.name) / 'scheduler-job-logs.jsonl'
        self._data_sources_path.write_text((project_root() / 'configs' / 'data_sources.yaml').read_text(encoding='utf-8'), encoding='utf-8')
        os.environ['QUANT_MARKET_DATA_PROVIDER'] = 'mock'
        os.environ['QUANT_DATA_SOURCES_PATH'] = str(self._data_sources_path)
        os.environ['QUANT_SCHEDULER_LOG_PATH'] = str(self._scheduler_log_path)
        reset_container()
        get_container().regime_repository.upsert_snapshots([
            RegimeSnapshot(
                market_code='US_EQ',
                trade_date=date(2026, 5, 18),
                regime_status='BULL',
                bull_score=68.0,
                trend_score=50.0,
                relative_strength_score=50.0,
                risk_penalty_score=0.0,
                trigger_flags={'policy_breakout': True, 'trend_persistence': True, 'recovery_reversal': True, 'global_leader': True},
                source_used={'rule_version': 'regime_v4_parallel_entries'},
            )
        ])
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self._original_provider is None:
            os.environ.pop('QUANT_MARKET_DATA_PROVIDER', None)
        else:
            os.environ['QUANT_MARKET_DATA_PROVIDER'] = self._original_provider
        if self._original_data_sources_path is None:
            os.environ.pop('QUANT_DATA_SOURCES_PATH', None)
        else:
            os.environ['QUANT_DATA_SOURCES_PATH'] = self._original_data_sources_path
        if self._original_scheduler_log_path is None:
            os.environ.pop('QUANT_SCHEDULER_LOG_PATH', None)
        else:
            os.environ['QUANT_SCHEDULER_LOG_PATH'] = self._original_scheduler_log_path
        self._temp_dir.cleanup()
        reset_container()

    def test_health(self) -> None:
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['data']['status'], 'ok')
        self.assertIn('selection_service', payload['data']['services'])
        self.assertIn('trading_service', payload['data']['services'])
        self.assertGreaterEqual(payload['data']['market_count'], 30)

    def test_run_daily_and_read_market_results(self) -> None:
        response = self.client.post(
            '/admin/run-daily',
            json={'trade_date': date(2026, 5, 25).isoformat(), 'market_codes': ['ALL']},
        )
        self.assertEqual(response.status_code, 200)
        run_payload = response.json()
        self.assertEqual(run_payload['data']['computed_regimes'], len(get_container().markets_config.markets))
        self.assertIn('selected_candidates', run_payload['data'])
        self.assertIn('watchlist_count', run_payload['data'])
        self.assertIn('generated_signals', run_payload['data'])
        self.assertIn('executed_orders', run_payload['data'])

        candidates_response = self.client.get('/candidates/today')
        self.assertEqual(candidates_response.status_code, 200)
        self.assertEqual(candidates_response.json()['status'], 'success')
        self.assertGreater(len(candidates_response.json()['data']), 0)
        self.assertEqual(candidates_response.json()['data'][0]['trade_date'], '2026-05-25')

        watchlist_response = self.client.get('/watchlist/today')
        self.assertEqual(watchlist_response.status_code, 200)
        self.assertEqual(watchlist_response.json()['status'], 'success')

        heat_response = self.client.get('/themes/hot/today')
        self.assertEqual(heat_response.status_code, 200)
        self.assertEqual(heat_response.json()['status'], 'success')
        self.assertGreater(len(heat_response.json()['data']), 0)

        seeds_response = self.client.get('/seeds/today')
        self.assertEqual(seeds_response.status_code, 200)
        self.assertEqual(seeds_response.json()['status'], 'success')
        self.assertGreater(len(seeds_response.json()['data']), 0)

        signals_response = self.client.get('/signals/today')
        self.assertEqual(signals_response.status_code, 200)
        self.assertEqual(signals_response.json()['status'], 'success')
        self.assertGreater(len(signals_response.json()['data']), 0)
        self.assertEqual(signals_response.json()['data'][0]['trade_date'], '2026-05-25')

        orders_response = self.client.get('/orders/today')
        self.assertEqual(orders_response.status_code, 200)
        self.assertEqual(orders_response.json()['status'], 'success')

        positions_response = self.client.get('/positions')
        self.assertEqual(positions_response.status_code, 200)
        self.assertEqual(positions_response.json()['status'], 'success')

        bull_response = self.client.get('/markets/bull/today')
        self.assertEqual(bull_response.status_code, 200)
        self.assertEqual(bull_response.json()['status'], 'success')
        self.assertGreaterEqual(len(bull_response.json()['data']), 1)

        workflow_response = self.client.get('/workflow/logs/latest-summary')
        self.assertEqual(workflow_response.status_code, 200)
        self.assertEqual(workflow_response.json()['status'], 'success')
        self.assertIn('tracked_bull_markets', workflow_response.json()['data'])
        self.assertIn('latest_watchlist', workflow_response.json()['data'])

        scheduler_logs_response = self.client.get('/workflow/logs/scheduler')
        self.assertEqual(scheduler_logs_response.status_code, 200)
        scheduler_logs_payload = scheduler_logs_response.json()
        self.assertEqual(scheduler_logs_payload['status'], 'success')
        self.assertGreater(len(scheduler_logs_payload['data']), 0)
        self.assertEqual(scheduler_logs_payload['data'][0]['job_name'], 'run_daily_workflow')
        self.assertEqual(scheduler_logs_payload['data'][0]['trigger_mode'], 'manual')
        self.assertEqual(scheduler_logs_payload['data'][0]['status'], 'completed')
        self.assertEqual(scheduler_logs_payload['data'][0]['trade_date'], '2026-05-25')

        bull_process_response = self.client.get('/markets/bull-search/process?trade_date=2026-05-25')
        self.assertEqual(bull_process_response.status_code, 200)
        self.assertEqual(bull_process_response.json()['status'], 'success')
        self.assertEqual(bull_process_response.json()['data']['trade_date'], '2026-05-25')
        self.assertEqual(len(bull_process_response.json()['data']['markets']), len(get_container().markets_config.markets))
        self.assertIn('non_bull_market_codes', bull_process_response.json()['data'])
        self.assertIn('decision_reason', bull_process_response.json()['data']['markets'][0])
        self.assertIn('failed_criteria', bull_process_response.json()['data']['markets'][0])

    def test_run_bull_search_executes_market_screen_once(self) -> None:
        response = self.client.post(
            '/markets/bull-search/run',
            json={'trade_date': date(2026, 5, 25).isoformat(), 'market_codes': ['ALL']},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['data']['trade_date'], '2026-05-25')
        self.assertEqual(payload['data']['processed_markets'], len(get_container().markets_config.markets))
        self.assertIn('bull_market_count', payload['data'])
        self.assertIn('source_mode', payload['data'])

        overview_response = self.client.get('/markets/overview')
        self.assertEqual(overview_response.status_code, 200)
        overview_rows = overview_response.json()['data']
        self.assertEqual(len(overview_rows), len(get_container().markets_config.markets))
        self.assertIn('criteria', overview_rows[0])
        self.assertIn('is_bull', overview_rows[0])


    def test_universe_today_returns_latest_market_universe(self) -> None:
        run_response = self.client.post(
            '/candidates/run',
            json={'trade_date': date(2026, 5, 25).isoformat(), 'market_codes': ['ALL']},
        )
        self.assertEqual(run_response.status_code, 200)

        response = self.client.get('/universe/today')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertGreater(len(payload['data']), 0)
        self.assertEqual(payload['data'][0]['trade_date'], '2026-05-25')
        self.assertIn('market_code', payload['data'][0])
        self.assertIn('ticker', payload['data'][0])
        self.assertIn('industry', payload['data'][0])

        ticker = payload['data'][0]['ticker']
        filtered_response = self.client.get(f'/universe/today?market_code=US_EQ&ticker={ticker}')
        self.assertEqual(filtered_response.status_code, 200)
        filtered_payload = filtered_response.json()
        self.assertEqual(filtered_payload['status'], 'success')
        self.assertEqual(len(filtered_payload['data']), 1)
        self.assertEqual(filtered_payload['data'][0]['ticker'], ticker)

    def test_universe_today_does_not_repair_on_read(self) -> None:
        run_response = self.client.post(
            '/candidates/run',
            json={'trade_date': date(2026, 5, 25).isoformat(), 'market_codes': ['ALL']},
        )
        self.assertEqual(run_response.status_code, 200)

        original_repair = get_container().selection_service.repair_market_universe
        try:
            def _fail_repair(*args, **kwargs):
                raise AssertionError('repair_market_universe should not be called on read')

            get_container().selection_service.repair_market_universe = _fail_repair
            response = self.client.get('/universe/today?market_code=JP_EQ')
        finally:
            get_container().selection_service.repair_market_universe = original_repair

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertIsInstance(payload['data'], list)

    def test_universe_enrich_runs_explicit_metadata_repair_task(self) -> None:
        run_response = self.client.post(
            '/candidates/run',
            json={'trade_date': date(2026, 5, 25).isoformat(), 'market_codes': ['ALL']},
        )
        self.assertEqual(run_response.status_code, 200)

        original_repair = get_container().selection_service.repair_market_universe
        captured = {}
        try:
            def _record_repair(trade_date, market_codes, *, limit=None, offset=0):
                captured['trade_date'] = trade_date
                captured['market_codes'] = market_codes
                captured['limit'] = limit
                captured['offset'] = offset
                return original_repair(trade_date, market_codes, limit=limit, offset=offset)

            get_container().selection_service.repair_market_universe = _record_repair
            response = self.client.post(
                '/universe/enrich',
                json={'trade_date': '2026-05-25', 'market_codes': ['US_EQ'], 'batch_limit': 2, 'batch_offset': 1},
            )
        finally:
            get_container().selection_service.repair_market_universe = original_repair

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['data']['trade_date'], '2026-05-25')
        self.assertEqual(payload['data']['market_codes'], ['US_EQ'])
        self.assertIn('processed_rows', payload['data'])
        self.assertIn('enriched_rows', payload['data'])
        self.assertIn('remaining_unknown_rows', payload['data'])
        self.assertEqual(payload['data']['batch_limit'], 2)
        self.assertEqual(payload['data']['batch_offset'], 1)
        self.assertEqual(captured['market_codes'], ['US_EQ'])
        self.assertEqual(captured['trade_date'], date(2026, 5, 25))
        self.assertEqual(captured['limit'], 2)
        self.assertEqual(captured['offset'], 1)

    def test_run_stock_screen_executes_selection_once(self) -> None:
        response = self.client.post(
            '/candidates/run',
            json={'trade_date': date(2026, 5, 25).isoformat(), 'market_codes': ['ALL']},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['data']['trade_date'], '2026-05-25')
        self.assertGreater(payload['data']['processed_candidates'], 0)
        self.assertGreater(payload['data']['seed_count'], 0)
        self.assertIn('tracked_market_count', payload['data'])
        self.assertIn('source_mode', payload['data'])

        candidates_response = self.client.get('/candidates/today')
        self.assertEqual(candidates_response.status_code, 200)
        self.assertEqual(candidates_response.json()['status'], 'success')
        self.assertGreater(len(candidates_response.json()['data']), 0)

    def test_data_source_agent_adds_new_source_and_persists_config(self) -> None:
        list_response = self.client.get('/data-sources')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()['status'], 'success')
        self.assertTrue(any(item['name'] == 'market_bars' for item in list_response.json()['data']['sources']))

        add_response = self.client.post(
            '/agent/data-sources/add',
            json={
                'message': '新增数据源 news_feed，主源 alphavantage，fallback fmp',
                'conversation': [],
            },
        )

        self.assertEqual(add_response.status_code, 200)
        payload = add_response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['data']['saved_source']['name'], 'news_feed')
        self.assertEqual(payload['data']['saved_source']['primary'], 'alphavantage')
        self.assertEqual(payload['data']['saved_source']['fallback'], 'fmp')

        refreshed_response = self.client.get('/data-sources')
        self.assertEqual(refreshed_response.status_code, 200)
        self.assertTrue(any(item['name'] == 'news_feed' for item in refreshed_response.json()['data']['sources']))

        persisted = load_yaml(self._data_sources_path)
        self.assertEqual(persisted['sources']['news_feed']['primary'], 'alphavantage')
        self.assertEqual(persisted['sources']['news_feed']['fallback'], 'fmp')

    def test_local_industry_catalog_returns_jp_official_index_family(self) -> None:
        response = self.client.get('/themes/local-industry-catalog?market_code=JP_EQ')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(len(payload['data']), 1)
        market = payload['data'][0]
        self.assertEqual(market['market_code'], 'JP_EQ')
        self.assertEqual(market['recommended_primary_family'], 'TOPIX_17')
        self.assertEqual(market['families'][0]['family_code'], 'TOPIX_17')
        family_index_names = {item['name'] for item in market['families'][0]['indices']}
        self.assertIn('TOPIX-17 ELECTRIC POWER & GAS', family_index_names)


    def test_hot_themes_today_reclassifies_fixed_theme_as_global_theme(self) -> None:
        container = get_container()
        container.selection_repository.replace_heat_snapshots(
            trade_date=date(2026, 6, 2),
            market_codes=['US_EQ'],
            snapshots=[
                ThemeHeatSnapshot(
                    trade_date=date(2026, 6, 2),
                    market_code='US_EQ',
                    theme_type='industry',
                    theme_name='半导体',
                    raw_heat_score=99.9,
                    smoothed_heat_score=99.9,
                    constituent_count=3,
                    source='fixed_theme',
                )
            ],
        )

        response = self.client.get('/themes/hot/today')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(len(payload['data']), 1)
        self.assertEqual(payload['data'][0]['theme_name'], '半导体')
        self.assertEqual(payload['data'][0]['theme_type'], 'global_theme')

    def test_sell_selected_positions_closes_open_holdings(self) -> None:
        run_response = self.client.post(
            '/admin/run-daily',
            json={'trade_date': date(2026, 5, 25).isoformat(), 'market_codes': ['ALL']},
        )
        self.assertEqual(run_response.status_code, 200)

        open_before = self.client.get('/positions')
        self.assertEqual(open_before.status_code, 200)
        open_rows = open_before.json()['data']
        self.assertGreater(len(open_rows), 0)
        target = open_rows[0]

        sell_response = self.client.post(
            '/positions/sell',
            json={
                'trade_date': '2026-05-26',
                'positions': [
                    {'market_code': target['market_code'], 'ticker': target['ticker']}
                ],
            },
        )

        self.assertEqual(sell_response.status_code, 200)
        payload = sell_response.json()
        self.assertEqual(payload['status'], 'success')
        self.assertEqual(payload['data']['trade_date'], '2026-05-26')
        self.assertEqual(payload['data']['sold_count'], 1)

        open_after = self.client.get('/positions')
        self.assertEqual(open_after.status_code, 200)
        self.assertFalse(any(item['ticker'] == target['ticker'] and item['market_code'] == target['market_code'] for item in open_after.json()['data']))

        closed_after = self.client.get('/positions?status=CLOSED')
        self.assertEqual(closed_after.status_code, 200)
        self.assertTrue(any(item['ticker'] == target['ticker'] and item['market_code'] == target['market_code'] for item in closed_after.json()['data']))

    def test_market_overview_uses_latest_data_per_market(self) -> None:
        container = get_container()
        container.market_data_repository.upsert_features([
            MarketFeature(
                market_code='US_EQ',
                trade_date=date(2026, 5, 26),
                price_proxy='SPY',
                close=500.0,
                ma_120=480.0,
                ma_200=470.0,
                ret_60d=0.12,
                ret_120d=0.18,
                vol_20d=0.2,
                drawdown_60d=0.05,
                relative_strength_world=0.15,
                fx_ret_60d=0.0,
                avg_volume_recent=120.0,
                avg_volume_prior=100.0,
                volume_ratio_5d=1.2,
                consecutive_up_weeks=6,
                ret_1d=0.023,
                ret_5d=0.068,
                turnover_ratio_20d=1.62,
                avg_turnover_ratio_3d=1.41,
                volume_up_days_2d=2,
                volume_up_days_3d=3,
                consecutive_up_days=4,
                ma_5=503.0,
                ma_10=497.0,
                ma_20=489.0,
                ma_60=475.0,
                source='test',
            ),
            MarketFeature(
                market_code='JP_EQ',
                trade_date=date(2026, 5, 25),
                price_proxy='^N225',
                close=38000.0,
                ma_120=36000.0,
                ma_200=34000.0,
                ret_60d=0.09,
                ret_120d=0.14,
                vol_20d=0.22,
                drawdown_60d=0.06,
                relative_strength_world=0.11,
                fx_ret_60d=0.01,
                avg_volume_recent=118.0,
                avg_volume_prior=100.0,
                volume_ratio_5d=1.18,
                consecutive_up_weeks=1,
                ret_1d=0.021,
                ret_5d=0.057,
                turnover_ratio_20d=1.54,
                avg_turnover_ratio_3d=1.34,
                volume_up_days_2d=2,
                volume_up_days_3d=2,
                consecutive_up_days=3,
                ma_5=38250.0,
                ma_10=37980.0,
                ma_20=37450.0,
                ma_60=36100.0,
                source='test',
            ),
        ])
        container.regime_repository.upsert_snapshots([
            RegimeSnapshot(
                market_code='US_EQ',
                trade_date=date(2026, 5, 26),
                regime_status='BULL',
                bull_score=68.0,
                trend_score=50.0,
                relative_strength_score=50.0,
                risk_penalty_score=0.0,
                trigger_flags={'policy_breakout': True, 'trend_persistence': True, 'recovery_reversal': True, 'global_leader': True},
                source_used={'rule_version': 'regime_v4_parallel_entries'},
            ),
            RegimeSnapshot(
                market_code='JP_EQ',
                trade_date=date(2026, 5, 25),
                regime_status='BULL',
                bull_score=68.0,
                trend_score=50.0,
                relative_strength_score=50.0,
                risk_penalty_score=0.0,
                trigger_flags={'policy_breakout': True, 'trend_persistence': True, 'recovery_reversal': True, 'global_leader': True},
                source_used={'rule_version': 'regime_v4_parallel_entries'},
            ),
        ])

        response = self.client.get('/markets/overview')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'success')
        rows = {item['market_code']: item for item in payload['data']}
        self.assertEqual(rows['US_EQ']['trade_date'], '2026-05-26')
        self.assertEqual(rows['JP_EQ']['trade_date'], '2026-05-25')
        self.assertEqual(rows['JP_EQ']['regime_status'], 'BULL')
        self.assertIsNotNone(rows['JP_EQ']['close'])
        self.assertGreater(len(rows['JP_EQ']['criteria']), 0)
        criteria = {item['name']: item for item in rows['JP_EQ']['criteria']}
        self.assertIn('policy_breakout', criteria)
        self.assertIn('trend_persistence', criteria)
        self.assertIn('recovery_reversal', criteria)
        self.assertIn('global_leader', criteria)
        self.assertEqual(rows['JP_EQ']['volume_up_days_2d'], 2)
        self.assertEqual(rows['JP_EQ']['volume_up_days_3d'], 2)
        self.assertEqual(rows['JP_EQ']['consecutive_up_weeks'], 1)
        self.assertEqual(criteria['trend_persistence']['score'], 100.0)
        self.assertEqual(criteria['recovery_reversal']['score'], 80.0)
        self.assertEqual(criteria['global_leader']['score'], 100.0)
        self.assertIn('Bull Score=', rows['JP_EQ']['decision_reason'])
        self.assertIn('趋势慢牛型', rows['JP_EQ']['decision_reason'])

    def test_market_overview_keeps_bull_status_but_uses_current_score_for_incremental_lock(self) -> None:
        container = get_container()
        container.regime_repository.upsert_snapshots([
            RegimeSnapshot(
                market_code='US_EQ',
                trade_date=date(2026, 5, 18),
                regime_status='BULL',
                bull_score=68.0,
                trend_score=44.0,
                relative_strength_score=24.0,
                risk_penalty_score=0.0,
                trigger_flags={
                    'policy_breakout': True,
                    'trend_persistence': True,
                    'recovery_reversal': True,
                    'global_leader': True,
                },
                source_used={'rule_version': 'regime_v4_parallel_entries'},
            )
        ])
        container.market_data_repository.upsert_features([
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
        container.regime_service.run_daily(date(2026, 5, 26), ['US_EQ'])

        response = self.client.get('/markets/overview')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        row = next(item for item in payload['data'] if item['market_code'] == 'US_EQ')
        criteria = {item['name']: item for item in row['criteria']}
        self.assertEqual(row['regime_status'], 'BULL')
        self.assertEqual(row['bull_score'], 0.0)
        self.assertEqual(criteria['trend_persistence']['score'], 0.0)
        self.assertEqual(criteria['global_leader']['score'], 0.0)

    def test_market_overview_ignores_legacy_bull_snapshot_for_current_scoring(self) -> None:
        container = get_container()
        container.regime_repository.upsert_snapshots([
            RegimeSnapshot(
                market_code='US_EQ',
                trade_date=date(2026, 5, 18),
                regime_status='BULL',
                bull_score=68.0,
                trend_score=44.0,
                relative_strength_score=24.0,
                risk_penalty_score=0.0,
                trigger_flags={
                    'policy_breakout': True,
                    'trend_persistence': True,
                    'recovery_reversal': True,
                    'global_leader': True,
                },
                source_used={'rule_version': 'legacy_v1'},
            )
        ])
        container.market_data_repository.upsert_features([
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
        container.regime_service.run_daily(date(2026, 5, 26), ['US_EQ'])

        response = self.client.get('/markets/overview')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        row = next(item for item in payload['data'] if item['market_code'] == 'US_EQ')
        self.assertEqual(row['regime_status'], 'BEAR')
        self.assertEqual(row['bull_score'], 0.0)
        self.assertIn('Bull Score=0.0', row['decision_reason'])


if __name__ == '__main__':
    unittest.main()
