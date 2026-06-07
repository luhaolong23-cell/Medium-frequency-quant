import unittest
from datetime import date

from packages.shared.settings import MarketsConfig, MarketSettings, ProxySettings
from services.selection_service.app.infra.provider import YFinanceBullSeedProvider


class _FakeTicker:
    def __init__(self, info: dict) -> None:
        self.info = info


class _UnexpectedProfileLookup:
    def __call__(self, symbol: str):
        raise AssertionError(f'profile lookup should not be used for {symbol}')


class DynamicSeedProviderTests(unittest.TestCase):
    def _provider(self, *, quotes: list[dict] | None = None, screener=None, profile_map: dict[str, dict], **discovery_overrides):
        config = {
            'enabled': True,
            'max_candidates_per_market': 10,
            'max_selected_per_market': 5,
            'min_market_cap': 3_000_000_000,
            'max_market_cap': 10_000_000_000,
            'max_price_position_ratio': 0.35,
            'heat_top_industries': 1,
            'heat_top_sectors': 1,
            'heat_min_constituents': 2,
        }
        config.update(discovery_overrides)
        return YFinanceBullSeedProvider(
            markets_config=MarketsConfig(markets=[
                MarketSettings(
                    market_code='US_EQ',
                    market_name='US Equities',
                    country_code='US',
                    region='NORTH_AMERICA',
                    proxies=[ProxySettings(symbol='SPY', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1)],
                )
            ]),
            discovery_config=config,
            screener=screener or (lambda query, size, sortField, sortAsc, offset=None, count=None: {'quotes': quotes or []}),
            ticker_factory=lambda symbol: _FakeTicker(profile_map[symbol]),
        )

    def test_yfinance_bull_seed_provider_learns_hot_industry_and_selects_low_position_small_mid_caps(self) -> None:
        provider = self._provider(
            quotes=[
                {
                    'symbol': 'RGTI',
                    'longName': 'Rigetti Computing, Inc.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 8_057_347_072,
                    'regularMarketPrice': 24.24,
                    'fiftyTwoWeekLow': 10.3,
                    'fiftyTwoWeekHigh': 58.15,
                    'regularMarketChangePercent': 8.2,
                    'regularMarketVolume': 9_600_000,
                    'averageDailyVolume3Month': 4_200_000,
                },
                {
                    'symbol': 'QUBT',
                    'longName': 'Quantum Computing Inc.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 4_100_000_000,
                    'regularMarketPrice': 11.4,
                    'fiftyTwoWeekLow': 8.8,
                    'fiftyTwoWeekHigh': 25.0,
                    'regularMarketChangePercent': 6.5,
                    'regularMarketVolume': 8_200_000,
                    'averageDailyVolume3Month': 3_600_000,
                },
                {
                    'symbol': 'OLDM',
                    'longName': 'Old Manufacturing Ltd.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 6_200_000_000,
                    'regularMarketPrice': 21.0,
                    'fiftyTwoWeekLow': 15.0,
                    'fiftyTwoWeekHigh': 40.0,
                    'regularMarketChangePercent': 1.1,
                    'regularMarketVolume': 2_000_000,
                    'averageDailyVolume3Month': 2_400_000,
                },
            ],
            profile_map={
                'RGTI': {'sector': 'Technology', 'industry': 'Semiconductors'},
                'QUBT': {'sector': 'Technology', 'industry': 'Semiconductors'},
                'OLDM': {'sector': 'Industrials', 'industry': 'Conglomerates'},
            },
        )

        seeds = provider.resolve_seeds(['US_EQ'], date(2026, 5, 25))

        self.assertEqual([seed.ticker for seed in seeds], ['QUBT', 'RGTI'])
        self.assertTrue(all(seed.seed_type == 'bull_heat_screen' for seed in seeds))
        self.assertTrue(all(seed.industry == 'Semiconductors' for seed in seeds))
        self.assertGreaterEqual(seeds[0].theme_score, 75)
        self.assertGreater(seeds[0].valuation_score, 60)

    def test_yfinance_bull_seed_provider_returns_empty_when_no_stock_matches(self) -> None:
        provider = self._provider(
            quotes=[
                {
                    'symbol': 'HIGH',
                    'longName': 'High Position Tech',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 5_000_000_000,
                    'regularMarketPrice': 48.0,
                    'fiftyTwoWeekLow': 10.0,
                    'fiftyTwoWeekHigh': 50.0,
                    'regularMarketChangePercent': 8.5,
                    'regularMarketVolume': 7_000_000,
                    'averageDailyVolume3Month': 3_200_000,
                },
                {
                    'symbol': 'SMAL',
                    'longName': 'Too Small Corp',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 1_000_000_000,
                    'regularMarketPrice': 9.0,
                    'fiftyTwoWeekLow': 6.0,
                    'fiftyTwoWeekHigh': 14.0,
                    'regularMarketChangePercent': 7.0,
                    'regularMarketVolume': 8_000_000,
                    'averageDailyVolume3Month': 2_000_000,
                },
            ],
            profile_map={
                'HIGH': {'sector': 'Technology', 'industry': 'Semiconductors'},
                'SMAL': {'sector': 'Technology', 'industry': 'Semiconductors'},
            },
        )

        seeds = provider.resolve_seeds(['US_EQ'], date(2026, 5, 25))

        self.assertEqual(seeds, [])


    def test_yfinance_bull_seed_provider_pages_entire_market_and_keeps_all_matching_stocks(self) -> None:
        pages = {
            0: [
                {
                    'symbol': 'QUBT',
                    'longName': 'Quantum Computing Inc.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 4_100_000_000,
                    'regularMarketPrice': 11.4,
                    'fiftyTwoWeekLow': 8.8,
                    'fiftyTwoWeekHigh': 25.0,
                    'regularMarketChangePercent': 6.5,
                    'regularMarketVolume': 8_200_000,
                    'averageDailyVolume3Month': 3_600_000,
                },
                {
                    'symbol': 'RGTI',
                    'longName': 'Rigetti Computing, Inc.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 8_057_347_072,
                    'regularMarketPrice': 24.24,
                    'fiftyTwoWeekLow': 10.3,
                    'fiftyTwoWeekHigh': 58.15,
                    'regularMarketChangePercent': 8.2,
                    'regularMarketVolume': 9_600_000,
                    'averageDailyVolume3Month': 4_200_000,
                },
            ],
            2: [
                {
                    'symbol': 'IONQ',
                    'longName': 'IonQ, Inc.',
                    'exchange': 'NYS',
                    'currency': 'USD',
                    'marketCap': 9_100_000_000,
                    'regularMarketPrice': 31.2,
                    'fiftyTwoWeekLow': 15.0,
                    'fiftyTwoWeekHigh': 65.0,
                    'regularMarketChangePercent': 7.8,
                    'regularMarketVolume': 10_400_000,
                    'averageDailyVolume3Month': 4_600_000,
                },
                {
                    'symbol': 'OLDM',
                    'longName': 'Old Manufacturing Ltd.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 6_200_000_000,
                    'regularMarketPrice': 21.0,
                    'fiftyTwoWeekLow': 15.0,
                    'fiftyTwoWeekHigh': 40.0,
                    'regularMarketChangePercent': 1.1,
                    'regularMarketVolume': 2_000_000,
                    'averageDailyVolume3Month': 2_400_000,
                },
            ],
            4: [],
        }

        def screener(query, size, sortField, sortAsc, offset=None, count=None):
            return {'quotes': pages.get(offset or 0, [])}

        provider = self._provider(
            screener=screener,
            profile_map={
                'QUBT': {'sector': 'Technology', 'industry': 'Semiconductors'},
                'RGTI': {'sector': 'Technology', 'industry': 'Semiconductors'},
                'IONQ': {'sector': 'Technology', 'industry': 'Semiconductors'},
                'OLDM': {'sector': 'Industrials', 'industry': 'Conglomerates'},
            },
            max_candidates_per_market=2,
            max_selected_per_market=1,
        )

        seeds = provider.resolve_seeds(['US_EQ'], date(2026, 5, 25))

        self.assertEqual([seed.ticker for seed in seeds], ['QUBT', 'RGTI', 'IONQ'])
        self.assertTrue(all(seed.industry == 'Semiconductors' for seed in seeds))

    def test_yfinance_bull_seed_provider_uses_quote_industry_without_profile_lookup(self) -> None:
        provider = YFinanceBullSeedProvider(
            markets_config=MarketsConfig(markets=[
                MarketSettings(
                    market_code='US_EQ',
                    market_name='US Equities',
                    country_code='US',
                    region='NORTH_AMERICA',
                    proxies=[ProxySettings(symbol='SPY', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1)],
                )
            ]),
            discovery_config={
                'enabled': True,
                'max_candidates_per_market': 10,
                'max_selected_per_market': 5,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'fixed_hot_theme_names': ['半导体'],
            },
            screener=lambda query, size, sortField, sortAsc, offset=None, count=None: {
                'quotes': [
                    {
                        'symbol': 'QUBT',
                        'longName': 'Quantum Computing Inc.',
                        'exchange': 'NCM',
                        'currency': 'USD',
                        'marketCap': 4_100_000_000,
                        'regularMarketPrice': 11.4,
                        'fiftyTwoWeekLow': 8.8,
                        'fiftyTwoWeekHigh': 25.0,
                        'regularMarketChangePercent': 6.5,
                        'regularMarketVolume': 8_200_000,
                        'averageDailyVolume3Month': 3_600_000,
                        'sector': 'Technology',
                        'industry': 'Semiconductors',
                    }
                ] if (offset or 0) == 0 else []
            },
            ticker_factory=_UnexpectedProfileLookup(),
        )

        seeds = provider.resolve_seeds(['US_EQ'], date(2026, 5, 25))

        self.assertEqual([seed.ticker for seed in seeds], ['QUBT'])
        self.assertEqual(seeds[0].industry, 'Semiconductors')

    def test_yfinance_bull_seed_provider_uses_fixed_hot_theme_names(self) -> None:
        provider = self._provider(
            quotes=[
                {
                    'symbol': 'QUBT',
                    'longName': 'Quantum Computing Inc.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 4_100_000_000,
                    'regularMarketPrice': 11.4,
                    'fiftyTwoWeekLow': 8.8,
                    'fiftyTwoWeekHigh': 25.0,
                    'regularMarketChangePercent': 6.5,
                    'regularMarketVolume': 8_200_000,
                    'averageDailyVolume3Month': 3_600_000,
                },
                {
                    'symbol': 'RGTI',
                    'longName': 'Rigetti Computing, Inc.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 8_057_347_072,
                    'regularMarketPrice': 24.24,
                    'fiftyTwoWeekLow': 10.3,
                    'fiftyTwoWeekHigh': 58.15,
                    'regularMarketChangePercent': 8.2,
                    'regularMarketVolume': 9_600_000,
                    'averageDailyVolume3Month': 4_200_000,
                },
                {
                    'symbol': 'ASTR',
                    'longName': 'Astra Space, Inc.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 3_800_000_000,
                    'regularMarketPrice': 14.0,
                    'fiftyTwoWeekLow': 12.5,
                    'fiftyTwoWeekHigh': 31.0,
                    'regularMarketChangePercent': 2.2,
                    'regularMarketVolume': 4_200_000,
                    'averageDailyVolume3Month': 3_800_000,
                },
            ],
            profile_map={
                'QUBT': {'sector': 'Technology', 'industry': 'Semiconductors'},
                'RGTI': {'sector': 'Technology', 'industry': 'Semiconductors'},
                'ASTR': {'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
            },
            fixed_hot_theme_names=['航天'],
        )

        snapshots = provider.build_hot_theme_list(['US_EQ'], date(2026, 5, 25))
        seeds = provider.resolve_seeds(['US_EQ'], date(2026, 5, 25))

        self.assertTrue(any(snapshot.theme_type == 'industry' and snapshot.theme_name == 'Semiconductors' for snapshot in snapshots))
        self.assertTrue(any(snapshot.theme_type == 'global_theme' and snapshot.theme_name == '航天' for snapshot in snapshots))
        self.assertCountEqual([seed.ticker for seed in seeds], ['ASTR', 'QUBT', 'RGTI'])
        self.assertIn('Aerospace & Defense', {seed.industry for seed in seeds})

    def test_yfinance_bull_seed_provider_matches_broader_upstream_and_downstream_industries(self) -> None:
        provider = self._provider(
            quotes=[
                {
                    'symbol': 'SATC',
                    'longName': 'Satellite Comm Holdings',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 4_500_000_000,
                    'regularMarketPrice': 15.5,
                    'fiftyTwoWeekLow': 12.0,
                    'fiftyTwoWeekHigh': 32.0,
                    'regularMarketChangePercent': 3.2,
                    'regularMarketVolume': 2_800_000,
                    'averageDailyVolume3Month': 2_100_000,
                },
                {
                    'symbol': 'PCBX',
                    'longName': 'Printed Circuit Board Systems',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 3_900_000_000,
                    'regularMarketPrice': 18.0,
                    'fiftyTwoWeekLow': 14.0,
                    'fiftyTwoWeekHigh': 34.0,
                    'regularMarketChangePercent': 2.8,
                    'regularMarketVolume': 3_100_000,
                    'averageDailyVolume3Month': 2_000_000,
                },
                {
                    'symbol': 'BTRY',
                    'longName': 'Battery Power Components',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 5_200_000_000,
                    'regularMarketPrice': 22.0,
                    'fiftyTwoWeekLow': 18.0,
                    'fiftyTwoWeekHigh': 40.0,
                    'regularMarketChangePercent': 2.1,
                    'regularMarketVolume': 3_600_000,
                    'averageDailyVolume3Month': 2_400_000,
                },
            ],
            profile_map={
                'SATC': {'sector': 'Industrials', 'industry': 'Satellite & Space Communications'},
                'PCBX': {'sector': 'Technology', 'industry': 'Printed Circuit Boards'},
                'BTRY': {'sector': 'Industrials', 'industry': 'Batteries'},
            },
            fixed_hot_theme_names=['航天', '半导体', '电力'],
        )

        provider.build_hot_theme_list(['US_EQ'], date(2026, 5, 25))
        seeds = provider.resolve_seeds(['US_EQ'], date(2026, 5, 25))

        self.assertCountEqual([seed.ticker for seed in seeds], ['SATC', 'PCBX', 'BTRY'])

    def test_yfinance_bull_seed_provider_does_not_match_entire_sector_as_theme(self) -> None:
        provider = self._provider(
            quotes=[
                {
                    'symbol': 'NEMX',
                    'longName': 'Software App Platform',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 7_300_000_000,
                    'regularMarketPrice': 14.5,
                    'fiftyTwoWeekLow': 12.0,
                    'fiftyTwoWeekHigh': 37.0,
                    'regularMarketChangePercent': 2.5,
                    'regularMarketVolume': 3_000_000,
                    'averageDailyVolume3Month': 2_000_000,
                },
                {
                    'symbol': 'KGXX',
                    'longName': 'Heavy Machinery Holdings',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 5_800_000_000,
                    'regularMarketPrice': 16.0,
                    'fiftyTwoWeekLow': 13.0,
                    'fiftyTwoWeekHigh': 34.0,
                    'regularMarketChangePercent': 2.0,
                    'regularMarketVolume': 2_600_000,
                    'averageDailyVolume3Month': 1_900_000,
                },
                {
                    'symbol': 'SATC',
                    'longName': 'Satellite Comm Holdings',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 4_500_000_000,
                    'regularMarketPrice': 15.5,
                    'fiftyTwoWeekLow': 12.0,
                    'fiftyTwoWeekHigh': 32.0,
                    'regularMarketChangePercent': 3.2,
                    'regularMarketVolume': 2_800_000,
                    'averageDailyVolume3Month': 2_100_000,
                },
            ],
            profile_map={
                'NEMX': {'sector': 'Technology', 'industry': 'Software - Application'},
                'KGXX': {'sector': 'Industrials', 'industry': 'Farm & Heavy Construction Machinery'},
                'SATC': {'sector': 'Industrials', 'industry': 'Satellite & Space Communications'},
            },
            fixed_hot_theme_names=['半导体', '航天'],
        )

        provider.build_hot_theme_list(['US_EQ'], date(2026, 5, 25))
        seeds = provider.resolve_seeds(['US_EQ'], date(2026, 5, 25))

        self.assertIn('SATC', [seed.ticker for seed in seeds])

    def test_yfinance_bull_seed_provider_pushes_fixed_industries_into_remote_query(self) -> None:
        provider = self._provider(
            quotes=[],
            profile_map={},
            fixed_hot_theme_names=['半导体', '航天'],
        )

        query = provider._build_query('us')
        query_dict = query.to_dict()

        self.assertEqual(query_dict['operator'], 'EQ')
        self.assertEqual(query_dict['operands'][0], 'region')
        self.assertEqual(query_dict['operands'][1], 'us')


    def test_yfinance_bull_seed_provider_stops_paging_after_enough_fixed_theme_matches(self) -> None:
        calls: list[int] = []
        pages = {
            0: [
                {
                    'symbol': 'SATC',
                    'longName': 'Satellite Comm Holdings',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 4_500_000_000,
                    'regularMarketPrice': 15.5,
                    'fiftyTwoWeekLow': 12.0,
                    'fiftyTwoWeekHigh': 32.0,
                    'regularMarketChangePercent': 3.2,
                    'regularMarketVolume': 2_800_000,
                    'averageDailyVolume3Month': 2_100_000,
                },
                {
                    'symbol': 'KGXX',
                    'longName': 'Heavy Machinery Holdings',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 5_800_000_000,
                    'regularMarketPrice': 16.0,
                    'fiftyTwoWeekLow': 13.0,
                    'fiftyTwoWeekHigh': 34.0,
                    'regularMarketChangePercent': 2.0,
                    'regularMarketVolume': 2_600_000,
                    'averageDailyVolume3Month': 1_900_000,
                },
            ],
            2: [
                {
                    'symbol': 'ASTR',
                    'longName': 'Astra Space, Inc.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 3_800_000_000,
                    'regularMarketPrice': 14.0,
                    'fiftyTwoWeekLow': 12.5,
                    'fiftyTwoWeekHigh': 31.0,
                    'regularMarketChangePercent': 2.2,
                    'regularMarketVolume': 4_200_000,
                    'averageDailyVolume3Month': 3_800_000,
                },
            ],
        }

        def screener(query, size, sortField, sortAsc, offset=None, count=None):
            calls.append(offset or 0)
            return {'quotes': pages.get(offset or 0, [])}

        provider = self._provider(
            screener=screener,
            profile_map={
                'SATC': {'sector': 'Industrials', 'industry': 'Satellite & Space Communications'},
                'KGXX': {'sector': 'Industrials', 'industry': 'Farm & Heavy Construction Machinery'},
                'ASTR': {'sector': 'Industrials', 'industry': 'Aerospace & Defense'},
            },
            fixed_hot_theme_names=['航天'],
            max_candidates_per_market=2,
            max_selected_per_market=1,
        )

        seeds = provider.resolve_seeds(['US_EQ'], date(2026, 5, 25))

        self.assertEqual(calls, [0, 2])
        self.assertIn('SATC', [seed.ticker for seed in seeds])
        self.assertIn('ASTR', [seed.ticker for seed in seeds])

if __name__ == '__main__':
    unittest.main()
