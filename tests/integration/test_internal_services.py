import os
import unittest
from datetime import date

from fastapi.testclient import TestClient

from packages.shared.container import get_container, reset_container
from services.market_data_service.main import app as market_data_app
from services.refdata_service.main import app as refdata_app
from services.regime_service.main import app as regime_app
from services.selection_service.main import app as selection_app


class InternalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_provider = os.environ.get('QUANT_MARKET_DATA_PROVIDER')
        os.environ['QUANT_MARKET_DATA_PROVIDER'] = 'mock'
        reset_container()
        self.refdata_client = TestClient(refdata_app)
        self.market_data_client = TestClient(market_data_app)
        self.regime_client = TestClient(regime_app)
        self.selection_client = TestClient(selection_app)

    def tearDown(self) -> None:
        if self._original_provider is None:
            os.environ.pop('QUANT_MARKET_DATA_PROVIDER', None)
        else:
            os.environ['QUANT_MARKET_DATA_PROVIDER'] = self._original_provider
        reset_container()

    def test_refdata_and_regime_service_flow(self) -> None:
        expected_market_count = len(get_container().markets_config.markets)

        sync_response = self.refdata_client.post('/v1/refdata/sync/markets')
        self.assertEqual(sync_response.status_code, 200)
        self.assertEqual(sync_response.json()['data']['synced_count'], expected_market_count)

        ingest_response = self.market_data_client.post(
            '/v1/market-data/ingest/daily',
            json={'trade_date': date(2026, 5, 25).isoformat(), 'market_codes': ['ALL']},
        )
        self.assertEqual(ingest_response.status_code, 200)
        self.assertEqual(ingest_response.json()['data']['processed'], expected_market_count)

        run_response = self.regime_client.post(
            '/v1/regime/run/daily',
            json={'trade_date': date(2026, 5, 25).isoformat(), 'market_codes': ['ALL']},
        )
        self.assertEqual(run_response.status_code, 200)
        self.assertEqual(len(run_response.json()['data']), expected_market_count)

        explain_response = self.regime_client.get(
            '/v1/regime/markets/US_EQ/explain',
            params={'trade_date': date(2026, 5, 25).isoformat()},
        )
        self.assertEqual(explain_response.status_code, 200)
        self.assertEqual(explain_response.json()['data']['market_code'], 'US_EQ')

    def test_selection_service_flow(self) -> None:
        response = self.selection_client.post(
            '/v1/selection/run-daily',
            json={'trade_date': date(2026, 5, 25).isoformat(), 'market_codes': ['US_EQ']},
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()['data']['processed_candidates'], 0)
        self.assertIn('watchlist_count', response.json()['data'])

        seeds_response = self.selection_client.get(
            '/v1/selection/seeds',
            params={'trade_date': date(2026, 5, 25).isoformat(), 'market_code': 'US_EQ'},
        )
        self.assertEqual(seeds_response.status_code, 200)
        self.assertEqual(seeds_response.json()['status'], 'success')
        self.assertGreater(len(seeds_response.json()['data']), 0)

        candidates_response = self.selection_client.get(
            '/v1/selection/candidates',
            params={'trade_date': date(2026, 5, 25).isoformat(), 'market_code': 'US_EQ'},
        )
        self.assertEqual(candidates_response.status_code, 200)
        self.assertEqual(candidates_response.json()['status'], 'success')

        watchlist_response = self.selection_client.get(
            '/v1/selection/watchlist',
            params={'trade_date': date(2026, 5, 25).isoformat(), 'market_code': 'US_EQ'},
        )
        self.assertEqual(watchlist_response.status_code, 200)
        self.assertEqual(watchlist_response.json()['status'], 'success')


if __name__ == '__main__':
    unittest.main()
