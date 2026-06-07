import unittest
from datetime import date

import pandas as pd

from packages.domain_core.selection.entities import StockUniverseSnapshot
from packages.shared.settings import (
    LocalIndustryIndexFamilySettings,
    LocalIndustryIndexSettings,
    LocalIndustryIndicesConfig,
    MarketLocalIndustryCatalogSettings,
    MarketsConfig,
    MarketSettings,
    ProxySettings,
)
from services.selection_service.app.infra.provider import YFinanceBullSeedProvider


class _FakeTicker:
    def __init__(self, info: dict) -> None:
        self.info = info


class YFinanceUniverseProviderTests(unittest.TestCase):

    def test_prepare_hot_themes_does_not_scan_or_persist_universe(self) -> None:
        screener_calls: list[int] = []

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
                'max_candidates_per_market': 2,
                'max_scan_pages_per_market': 1,
                'universe_page_size': 2,
                'max_universe_pages_per_market': 2,
                'max_selected_per_market': 1,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 1,
                'fixed_hot_theme_names': ['半导体'],
            },
            screener=lambda query, size, sortField, sortAsc, offset=None, count=None: screener_calls.append(offset or 0) or {'quotes': []},
            ticker_factory=lambda symbol: _FakeTicker({}),
            download=lambda symbols, period, interval, auto_adjust, progress, threads: pd.DataFrame({
                'Close': [100 + index for index in range(25)],
                'Volume': [1000] * 20 + [1800] * 5,
            }, index=pd.date_range('2026-04-01', periods=25, freq='B')),
        )

        provider.build_hot_theme_list(['US_EQ'], date(2026, 5, 25))
        universe = provider.list_market_universe(date(2026, 5, 25), ['US_EQ'])

        self.assertEqual(screener_calls, [])
        self.assertEqual(universe, [])

    def test_sync_market_universe_populates_local_strategy_metrics(self) -> None:
        provider = self._provider(
            quotes=[
                {
                    'symbol': 'AAA',
                    'longName': 'Alpha',
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
            ],
            profile_map={'AAA': {'sector': 'Technology', 'industry': 'Semiconductors', 'longName': 'Alpha', 'exchange': 'NCM', 'currency': 'USD'}},
        )

        provider.sync_market_universe(['US_EQ'], date(2026, 5, 25))
        universe = provider.list_market_universe(date(2026, 5, 25), ['US_EQ'])

        self.assertEqual(len(universe), 1)
        row = universe[0]
        self.assertIsNotNone(row.ret_5d)
        self.assertIsNotNone(row.ret_20d)
        self.assertIsNotNone(row.ret_60d)
        self.assertIsNotNone(row.ma_20)
        self.assertIsNotNone(row.ma_60)
        self.assertIsNotNone(row.avg_dollar_volume_3d)
        self.assertIsNotNone(row.avg_dollar_volume_20d)
        self.assertIsNotNone(row.volume_ratio_3d)
        self.assertIsNotNone(row.volume_up_days_5d)
        self.assertIsNotNone(row.distance_to_60d_high)
        self.assertIsNotNone(row.momentum_acceleration)
        self.assertIsNotNone(row.vol_20d)

    def test_sync_market_universe_bars_batches_full_and_incremental_history_downloads(self) -> None:
        download_calls: list[tuple[str, str, bool]] = []

        def fake_download(symbols, period, interval, auto_adjust, progress, threads):
            download_calls.append((symbols, period, threads))
            frames = {}
            for symbol in symbols.split():
                dates = pd.date_range('2025-01-01', periods=80, freq='B')
                frames[(symbol, 'Close')] = [50 + (index * 0.12) for index in range(80)]
                frames[(symbol, 'Volume')] = [500000] * 70 + [850000] * 10
            return pd.DataFrame(frames, index=dates)

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
                'max_scan_pages_per_market': 1,
                'universe_page_size': 10,
                'max_universe_pages_per_market': 1,
                'max_selected_per_market': 5,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 1,
                'fixed_hot_theme_names': [],
            },
            screener=lambda query, size, sortField, sortAsc, offset=None, count=None: {
                'quotes': [
                    {
                        'symbol': 'AAA',
                        'longName': 'Alpha',
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
                    },
                    {
                        'symbol': 'BBB',
                        'longName': 'Beta',
                        'exchange': 'NCM',
                        'currency': 'USD',
                        'marketCap': 4_200_000_000,
                        'regularMarketPrice': 12.4,
                        'fiftyTwoWeekLow': 8.8,
                        'fiftyTwoWeekHigh': 25.0,
                        'regularMarketChangePercent': 5.5,
                        'regularMarketVolume': 7_200_000,
                        'averageDailyVolume3Month': 3_300_000,
                        'sector': 'Technology',
                        'industry': 'Semiconductors',
                    },
                    {
                        'symbol': 'CCC',
                        'longName': 'Gamma',
                        'exchange': 'NCM',
                        'currency': 'USD',
                        'marketCap': 4_300_000_000,
                        'regularMarketPrice': 13.4,
                        'fiftyTwoWeekLow': 8.8,
                        'fiftyTwoWeekHigh': 25.0,
                        'regularMarketChangePercent': 4.5,
                        'regularMarketVolume': 6_200_000,
                        'averageDailyVolume3Month': 3_100_000,
                        'sector': 'Technology',
                        'industry': 'Software Infrastructure',
                    },
                ]
            },
            ticker_factory=lambda symbol: _FakeTicker({}),
            download=fake_download,
        )

        inventory = provider.sync_market_universe_inventory(['US_EQ'], date(2026, 5, 25))
        bars = provider.sync_market_universe_bars(
            inventory,
            trade_date=date(2026, 5, 25),
            latest_bar_dates={('US_EQ', 'BBB'): date(2026, 5, 23), ('US_EQ', 'CCC'): date(2026, 5, 24)},
        )

        self.assertGreater(len(bars), 0)
        self.assertEqual(download_calls, [('AAA', '30mo', True), ('BBB CCC', '3mo', True)])


    def test_sync_market_universe_inventory_skips_single_failed_market(self) -> None:
        provider = YFinanceBullSeedProvider(
            markets_config=MarketsConfig(markets=[
                MarketSettings(
                    market_code='US_EQ',
                    market_name='US Equities',
                    country_code='US',
                    region='NORTH_AMERICA',
                    proxies=[ProxySettings(symbol='SPY', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1)],
                ),
                MarketSettings(
                    market_code='JP_EQ',
                    market_name='Japan Equities',
                    country_code='JP',
                    region='ASIA',
                    proxies=[ProxySettings(symbol='EWJ', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1)],
                ),
            ]),
            discovery_config={
                'enabled': True,
                'max_candidates_per_market': 10,
                'max_scan_pages_per_market': 1,
                'universe_page_size': 10,
                'max_universe_pages_per_market': 1,
                'max_selected_per_market': 5,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 1,
                'fixed_hot_theme_names': [],
            },
            screener=lambda *args, **kwargs: {'quotes': []},
            ticker_factory=lambda symbol: _FakeTicker({}),
        )

        def fake_sync_market(trade_date, market_code, country_code):
            if market_code == 'JP_EQ':
                raise RuntimeError('jp screener down')
            return [
                StockUniverseSnapshot(
                    trade_date=trade_date,
                    market_code='US_EQ',
                    ticker='AAA',
                    company_name='Alpha',
                    sector='Unknown',
                    industry='Unknown',
                    exchange='NCM',
                    currency='USD',
                    country_code='US',
                    market_cap=4_100_000_000,
                    price=11.4,
                    price_position=0.2,
                    momentum_pct=6.5,
                    volume_ratio=2.0,
                    theme_tags=['auto_heat'],
                    source='test',
                )
            ]

        provider._sync_market_universe_for_market = fake_sync_market

        rows = provider.sync_market_universe_inventory(['US_EQ', 'JP_EQ'], date(2026, 5, 25))

        self.assertEqual({row.market_code for row in rows}, {'US_EQ'})
        self.assertEqual(provider.list_market_universe(date(2026, 5, 25), ['JP_EQ']), [])

    def test_sync_market_universe_uses_dedicated_universe_scan_limits(self) -> None:
        requested_offsets: list[tuple[int, int]] = []

        def fake_screener(query, size, sortField, sortAsc, offset=None, count=None):
            current_offset = offset or 0
            requested_offsets.append((size, current_offset))
            pages = {
                0: [
                    {
                        'symbol': 'AAA',
                        'longName': 'Alpha',
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
                    },
                    {
                        'symbol': 'BBB',
                        'longName': 'Beta',
                        'exchange': 'NCM',
                        'currency': 'USD',
                        'marketCap': 4_200_000_000,
                        'regularMarketPrice': 12.4,
                        'fiftyTwoWeekLow': 8.8,
                        'fiftyTwoWeekHigh': 25.0,
                        'regularMarketChangePercent': 5.5,
                        'regularMarketVolume': 7.2,
                        'averageDailyVolume3Month': 3.3,
                        'sector': 'Technology',
                        'industry': 'Semiconductors',
                    },
                ],
                2: [
                    {
                        'symbol': 'CCC',
                        'longName': 'Gamma',
                        'exchange': 'NCM',
                        'currency': 'USD',
                        'marketCap': 4_300_000_000,
                        'regularMarketPrice': 13.4,
                        'fiftyTwoWeekLow': 8.8,
                        'fiftyTwoWeekHigh': 25.0,
                        'regularMarketChangePercent': 4.5,
                        'regularMarketVolume': 6_200_000,
                        'averageDailyVolume3Month': 3_100_000,
                        'sector': 'Technology',
                        'industry': 'Software Infrastructure',
                    },
                    {
                        'symbol': 'DDD',
                        'longName': 'Delta',
                        'exchange': 'NCM',
                        'currency': 'USD',
                        'marketCap': 4_400_000_000,
                        'regularMarketPrice': 14.4,
                        'fiftyTwoWeekLow': 8.8,
                        'fiftyTwoWeekHigh': 25.0,
                        'regularMarketChangePercent': 3.5,
                        'regularMarketVolume': 5_200_000,
                        'averageDailyVolume3Month': 2_900_000,
                        'sector': 'Industrials',
                        'industry': 'Electrical Equipment',
                    },
                ],
            }
            return {'quotes': pages.get(current_offset, [])}

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
                'max_candidates_per_market': 1,
                'max_scan_pages_per_market': 1,
                'universe_page_size': 2,
                'max_universe_pages_per_market': 2,
                'max_selected_per_market': 1,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 1,
                'fixed_hot_theme_names': [],
            },
            screener=fake_screener,
            ticker_factory=lambda symbol: _FakeTicker({}),
        )

        provider.sync_market_universe(['US_EQ'], date(2026, 5, 25))
        universe = provider.list_market_universe(date(2026, 5, 25), ['US_EQ'])

        self.assertEqual(requested_offsets, [(2, 0), (2, 2)])
        self.assertEqual({row.ticker for row in universe}, {'AAA', 'BBB', 'CCC', 'DDD'})
    def _provider(self, *, quotes: list[dict], profile_map: dict[str, dict], **discovery_overrides):
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
            'fixed_hot_theme_names': ['半导体', '电力'],
        }
        config.update(discovery_overrides)

        def fake_download(symbols, period, interval, auto_adjust, progress, threads):
            symbol = symbols.strip()
            dates = pd.date_range('2025-01-01', periods=320, freq='B')
            if symbol == 'SOXX':
                close = [100 + (index * 1.0) for index in range(320)]
                volume = [1000] * 300 + [2200] * 20
            elif symbol == 'XLU':
                close = [100 + (index * 0.8) for index in range(320)]
                volume = [1000] * 300 + [1800] * 20
            else:
                close = [50 + (index * 0.12) for index in range(320)]
                volume = [500000] * 300 + [850000] * 20
            return pd.DataFrame({'Close': close, 'Volume': volume}, index=dates)

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
            screener=lambda query, size, sortField, sortAsc, offset=None, count=None: {'quotes': quotes if (offset or 0) == 0 else []},
            ticker_factory=lambda symbol: _FakeTicker(profile_map[symbol]),
            download=fake_download,
        )

    def test_provider_adds_official_local_industry_snapshots_for_jp_market(self) -> None:
        def fake_download(symbols, period, interval, auto_adjust, progress, threads):
            symbol = symbols.strip()
            dates = pd.date_range('2026-04-01', periods=25, freq='B')
            if symbol == '1627.T':
                close = [100 + index for index in range(25)]
                volume = [1000] * 20 + [2200] * 5
            elif symbol == '1625.T':
                close = [100 + (index * 0.2) for index in range(25)]
                volume = [1000] * 25
            else:
                return pd.DataFrame()
            return pd.DataFrame({'Close': close, 'Volume': volume}, index=dates)

        provider = YFinanceBullSeedProvider(
            markets_config=MarketsConfig(markets=[
                MarketSettings(
                    market_code='JP_EQ',
                    market_name='Japan Equities',
                    country_code='JP',
                    region='ASIA',
                    proxies=[ProxySettings(symbol='EWJ', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1)],
                )
            ]),
            local_industry_indices_config=LocalIndustryIndicesConfig(markets=[
                MarketLocalIndustryCatalogSettings(
                    market_code='JP_EQ',
                    market_name='Japan Equities',
                    status='ready',
                    recommended_primary_family='TOPIX_17',
                    benchmark_name='TOPIX',
                    benchmark_symbol='^TOPX',
                    families=[
                        LocalIndustryIndexFamilySettings(
                            family_code='TOPIX_17',
                            family_name='TOPIX-17 Series',
                            provider_name='Japan Exchange Group',
                            provider_type='exchange_index_family',
                            source_url='https://www.jpx.co.jp/english/markets/indices/line-up/files/e_fac_13_sector.pdf',
                            coverage='Tokyo Stock Exchange broad market',
                            classification_standard='JPX TOPIX sector framework',
                            granularity='17_sector',
                            implementation_priority='high',
                            indices=[
                                LocalIndustryIndexSettings(
                                    local_code='TOPIX17_ELECTRIC_POWER_GAS',
                                    name='TOPIX-17 ELECTRIC POWER & GAS',
                                    level='17_sector',
                                    proxy_symbol='1627.T',
                                ),
                                LocalIndustryIndexSettings(
                                    local_code='TOPIX17_ELECTRIC_APPLIANCES_PRECISION',
                                    name='TOPIX-17 ELECTRIC APPLIANCES & PRECISION INSTRUMENTS',
                                    level='17_sector',
                                    proxy_symbol='1625.T',
                                ),
                            ],
                        )
                    ],
                )
            ]),
            discovery_config={
                'enabled': True,
                'max_candidates_per_market': 10,
                'max_selected_per_market': 5,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 1,
                'fixed_hot_theme_names': [],
            },
            screener=lambda query, size, sortField, sortAsc, offset=None, count=None: {
                'quotes': [
                    {
                        'symbol': '6501.T',
                        'longName': 'Hitachi',
                        'exchange': 'TSE',
                        'currency': 'JPY',
                        'marketCap': 5_000_000_000,
                        'regularMarketPrice': 12.0,
                        'fiftyTwoWeekLow': 10.0,
                        'fiftyTwoWeekHigh': 30.0,
                        'regularMarketChangePercent': 4.0,
                        'regularMarketVolume': 8_000_000,
                        'averageDailyVolume3Month': 4_000_000,
                    }
                ] if (offset or 0) == 0 else []
            },
            ticker_factory=lambda symbol: _FakeTicker({'sector': 'Industrials', 'industry': 'Electrical Equipment'}),
            download=fake_download,
        )

        snapshots = provider.build_hot_theme_list(['JP_EQ'], date(2026, 5, 25))

        official_names = {item.theme_name for item in snapshots if item.theme_type == 'official_local_industry'}
        self.assertIn('TOPIX-17 ELECTRIC POWER & GAS', official_names)
        self.assertIn('TOPIX-17 ELECTRIC APPLIANCES & PRECISION INSTRUMENTS', official_names)

    def test_provider_uses_official_local_industry_to_select_cn_seeds(self) -> None:
        def fake_download(symbols, period, interval, auto_adjust, progress, threads):
            dates = pd.date_range('2026-04-01', periods=25, freq='B')
            return pd.DataFrame({
                'Close': [100 + index for index in range(25)],
                'Volume': [1000] * 20 + [1800] * 5,
            }, index=dates)

        provider = YFinanceBullSeedProvider(
            markets_config=MarketsConfig(markets=[
                MarketSettings(
                    market_code='CN_EQ',
                    market_name='China Equities',
                    country_code='CN',
                    region='ASIA',
                    proxies=[ProxySettings(symbol='MCHI', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1)],
                )
            ]),
            local_industry_indices_config=LocalIndustryIndicesConfig(markets=[
                MarketLocalIndustryCatalogSettings(
                    market_code='CN_EQ',
                    market_name='China Equities',
                    status='ready',
                    recommended_primary_family='CSI_ALL_SHARE_INDUSTRY_PRIORITY_L2',
                    benchmark_name='中证全指',
                    benchmark_symbol='000985',
                    families=[
                        LocalIndustryIndexFamilySettings(
                            family_code='CSI_ALL_SHARE_INDUSTRY_PRIORITY_L2',
                            family_name='中证全指行业指数（重点二级/主题行业）',
                            provider_name='中证指数有限公司',
                            provider_type='official_index_company',
                            source_url='https://www.csindex.com.cn/zh-CN/downloads/industry-price-earnings-ratio',
                            coverage='全A股重点行业',
                            classification_standard='中证行业分类',
                            granularity='level_2_industry',
                            implementation_priority='high',
                            indices=[
                                LocalIndustryIndexSettings(
                                    local_code='CSI_ALL_SHARE_SEMICONDUCTOR_EQUIPMENT',
                                    name='中证全指半导体产品与设备指数',
                                    level='level_2_industry',
                                    official_code='H30184',
                                    proxy_symbol='512480.SS',
                                    match_industries=['semiconductors', 'electroniccomponents', 'semiconductorequipmentmaterials'],
                                    match_sectors=['technology'],
                                )
                            ],
                        )
                    ],
                )
            ]),
            discovery_config={
                'enabled': True,
                'max_candidates_per_market': 10,
                'max_selected_per_market': 5,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 2,
                'fixed_hot_theme_names': [],
            },
            screener=lambda query, size, sortField, sortAsc, offset=None, count=None: {
                'quotes': [
                    {
                        'symbol': '688256.SS',
                        'longName': 'Cambricon',
                        'exchange': 'SHH',
                        'currency': 'CNY',
                        'marketCap': 6_000_000_000,
                        'regularMarketPrice': 18.0,
                        'fiftyTwoWeekLow': 15.0,
                        'fiftyTwoWeekHigh': 70.0,
                        'regularMarketChangePercent': 3.5,
                        'regularMarketVolume': 9_000_000,
                        'averageDailyVolume3Month': 4_000_000,
                    }
                ] if (offset or 0) == 0 else []
            },
            ticker_factory=lambda symbol: _FakeTicker({'sector': 'Technology', 'industry': 'Electronic Components'}),
            download=fake_download,
        )

        snapshots = provider.build_hot_theme_list(['CN_EQ'], date(2026, 5, 25))
        seeds = provider.resolve_seeds(['CN_EQ'], date(2026, 5, 25))

        self.assertTrue(any(item.theme_type == 'official_local_industry' and item.theme_name == '中证全指半导体产品与设备指数' for item in snapshots))
        self.assertEqual({seed.ticker for seed in seeds}, {'688256.SS'})
        self.assertGreater(seeds[0].theme_score, 80.0)

    def test_provider_uses_official_local_industry_to_select_us_seeds(self) -> None:
        def fake_download(symbols, period, interval, auto_adjust, progress, threads):
            dates = pd.date_range('2026-04-01', periods=25, freq='B')
            return pd.DataFrame({
                'Close': [100 + index for index in range(25)],
                'Volume': [1000] * 20 + [1800] * 5,
            }, index=dates)

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
            local_industry_indices_config=LocalIndustryIndicesConfig(markets=[
                MarketLocalIndustryCatalogSettings(
                    market_code='US_EQ',
                    market_name='US Equities',
                    status='partial',
                    recommended_primary_family='SP500_SECTORS',
                    benchmark_name='S&P 500',
                    benchmark_symbol='^GSPC',
                    families=[
                        LocalIndustryIndexFamilySettings(
                            family_code='SP500_SECTORS',
                            family_name='S&P 500 Sector Indices',
                            provider_name='S&P Dow Jones Indices',
                            provider_type='index_provider',
                            source_url='https://www.spglobal.com/spdji/en/index-family/equity/us-equity/sp-sectors/',
                            coverage='U.S. large cap equities',
                            classification_standard='GICS',
                            granularity='sector',
                            implementation_priority='high',
                            indices=[
                                LocalIndustryIndexSettings(
                                    local_code='SP500_INFORMATION_TECHNOLOGY',
                                    name='Information Technology Select Sector',
                                    level='sector',
                                    proxy_symbol='XLK',
                                    match_industries=['semiconductors', 'softwareinfrastructure', 'softwareapplication'],
                                    match_sectors=['technology'],
                                )
                            ],
                        )
                    ],
                )
            ]),
            discovery_config={
                'enabled': True,
                'max_candidates_per_market': 10,
                'max_selected_per_market': 5,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 2,
                'fixed_hot_theme_names': [],
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
                    }
                ] if (offset or 0) == 0 else []
            },
            ticker_factory=lambda symbol: _FakeTicker({'sector': 'Technology', 'industry': 'Semiconductors'}),
            download=fake_download,
        )

        snapshots = provider.build_hot_theme_list(['US_EQ'], date(2026, 5, 25))
        seeds = provider.resolve_seeds(['US_EQ'], date(2026, 5, 25))

        self.assertTrue(any(item.theme_type == 'official_local_industry' and item.theme_name == 'Information Technology Select Sector' for item in snapshots))
        self.assertEqual({seed.ticker for seed in seeds}, {'QUBT'})
        self.assertGreater(seeds[0].theme_score, 80.0)

    def test_enrich_market_universe_rows_keeps_request_alive_when_profile_lookup_fails(self) -> None:
        def fake_ticker_factory(symbol: str) -> _FakeTicker:
            if symbol == '6501.T':
                raise RuntimeError('profile lookup failed')
            return _FakeTicker({'sector': 'Technology', 'industry': 'Semiconductors'})

        provider = YFinanceBullSeedProvider(
            markets_config=MarketsConfig(markets=[
                MarketSettings(
                    market_code='JP_EQ',
                    market_name='Japan Equities',
                    country_code='JP',
                    region='ASIA',
                    proxies=[ProxySettings(symbol='EWJ', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1)],
                )
            ]),
            discovery_config={
                'enabled': True,
                'max_candidates_per_market': 2,
                'max_scan_pages_per_market': 1,
                'max_selected_per_market': 1,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 1,
                'fixed_hot_theme_names': [],
            },
            screener=lambda *args, **kwargs: {'quotes': []},
            ticker_factory=fake_ticker_factory,
        )

        rows = provider.enrich_market_universe_rows([
            StockUniverseSnapshot(
                trade_date=date(2026, 6, 2),
                market_code='JP_EQ',
                ticker='6501.T',
                company_name='Hitachi',
                sector='Unknown',
                industry='Unknown',
                exchange='TSE',
                currency='JPY',
                country_code='JP',
                market_cap=5_000_000_000,
                price=12.0,
                price_position=0.24,
                momentum_pct=6.0,
                volume_ratio=1.4,
                theme_tags=['unknown', 'auto_heat'],
                source='test',
            ),
            StockUniverseSnapshot(
                trade_date=date(2026, 6, 2),
                market_code='JP_EQ',
                ticker='6758.T',
                company_name='Sony',
                sector='Unknown',
                industry='Unknown',
                exchange='TSE',
                currency='JPY',
                country_code='JP',
                market_cap=6_000_000_000,
                price=13.0,
                price_position=0.21,
                momentum_pct=5.0,
                volume_ratio=1.2,
                theme_tags=['unknown', 'auto_heat'],
                source='test',
            ),
        ])

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].ticker, '6501.T')
        self.assertEqual(rows[0].industry, 'Unknown')
        self.assertEqual(rows[1].ticker, '6758.T')
        self.assertEqual(rows[1].industry, 'Semiconductors')

    def test_provider_exposes_market_universe_and_combines_local_and_global_themes(self) -> None:
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
                    'sector': 'Technology',
                    'industry': 'Semiconductors',
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
                    'sector': 'Technology',
                    'industry': 'Semiconductors',
                },
                {
                    'symbol': 'UTIL',
                    'longName': 'Grid Utility Co.',
                    'exchange': 'NCM',
                    'currency': 'USD',
                    'marketCap': 5_100_000_000,
                    'regularMarketPrice': 18.2,
                    'fiftyTwoWeekLow': 15.0,
                    'fiftyTwoWeekHigh': 32.0,
                    'regularMarketChangePercent': 5.4,
                    'regularMarketVolume': 7_500_000,
                    'averageDailyVolume3Month': 3_500_000,
                    'sector': 'Utilities',
                    'industry': 'Utilities Regulated Electric',
                },
            ],
            profile_map={
                'QUBT': {'sector': 'Technology', 'industry': 'Semiconductors'},
                'RGTI': {'sector': 'Technology', 'industry': 'Semiconductors'},
                'UTIL': {'sector': 'Utilities', 'industry': 'Utilities Regulated Electric'},
            },
        )

        snapshots = provider.build_hot_theme_list(['US_EQ'], date(2026, 5, 25))
        provider.sync_market_universe(['US_EQ'], date(2026, 5, 25))
        universe = provider.list_market_universe(date(2026, 5, 25), ['US_EQ'])
        seeds = provider.resolve_seeds(['US_EQ'], date(2026, 5, 25))

        self.assertEqual({row.ticker for row in universe}, {'QUBT', 'RGTI', 'UTIL'})
        self.assertFalse(any(item.theme_type == 'industry' and item.theme_name == 'Semiconductors' for item in snapshots))
        self.assertTrue(any(item.theme_type == 'global_theme' and item.theme_name == '半导体' for item in snapshots))
        self.assertTrue(any(item.theme_type == 'global_theme' and item.theme_name == '电力' for item in snapshots))
        self.assertEqual({seed.ticker for seed in seeds}, {'QUBT', 'UTIL', 'RGTI'})

    def test_provider_limits_page_scan_per_market_during_heat_preparation(self) -> None:
        requested_offsets: list[int] = []

        def fake_screener(query, size, sortField, sortAsc, offset=None, count=None):
            current_offset = offset or 0
            requested_offsets.append(current_offset)
            if current_offset >= 6:
                return {'quotes': []}
            page_index = current_offset // size
            return {
                'quotes': [
                    {
                        'symbol': f'PAGE{page_index}_{slot}',
                        'longName': f'Page {page_index} Quote {slot}',
                        'exchange': 'NCM',
                        'currency': 'USD',
                        'marketCap': 4_000_000_000 + (page_index * 10_000_000),
                        'regularMarketPrice': 12.0 + page_index,
                        'fiftyTwoWeekLow': 10.0,
                        'fiftyTwoWeekHigh': 30.0,
                        'regularMarketChangePercent': 4.0 + slot,
                        'regularMarketVolume': 8_000_000,
                        'averageDailyVolume3Month': 4_000_000,
                        'sector': 'Technology',
                        'industry': 'Semiconductors',
                    }
                    for slot in range(size)
                ]
            }

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
                'max_candidates_per_market': 2,
                'max_scan_pages_per_market': 2,
                'universe_page_size': 2,
                'max_universe_pages_per_market': 2,
                'max_selected_per_market': 5,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 2,
                'fixed_hot_theme_names': [],
            },
            screener=fake_screener,
            ticker_factory=lambda symbol: _FakeTicker({}),
        )

        provider.sync_market_universe(['US_EQ'], date(2026, 5, 25))
        universe = provider.list_market_universe(date(2026, 5, 25), ['US_EQ'])

        self.assertEqual(requested_offsets, [0, 2])
        self.assertEqual(len(universe), 4)

    def test_sync_market_universe_inventory_keeps_profile_lookup_out_of_lightweight_stage(self) -> None:
        profile_calls: list[str] = []

        def fake_ticker_factory(symbol: str) -> _FakeTicker:
            profile_calls.append(symbol)
            return _FakeTicker({'sector': 'Technology', 'industry': 'Semiconductors'})

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
                'max_candidates_per_market': 2,
                'max_scan_pages_per_market': 1,
                'max_selected_per_market': 1,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 1,
                'fixed_hot_theme_names': [],
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
                    }
                ] if (offset or 0) == 0 else []
            },
            ticker_factory=fake_ticker_factory,
        )

        provider.sync_market_universe_inventory(['US_EQ'], date(2026, 5, 25))
        universe = provider.list_market_universe(date(2026, 5, 25), ['US_EQ'])

        self.assertEqual(profile_calls, [])
        self.assertEqual(universe[0].sector, 'Unknown')
        self.assertEqual(universe[0].industry, 'Unknown')


    def test_prepare_hot_themes_uses_dedicated_universe_scan_limits(self) -> None:
        requested_offsets: list[tuple[int, int]] = []

        def fake_screener(query, size, sortField, sortAsc, offset=None, count=None):
            current_offset = offset or 0
            requested_offsets.append((size, current_offset))
            pages = {
                0: [
                    {
                        'symbol': 'AAA',
                        'longName': 'Alpha',
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
                    },
                    {
                        'symbol': 'BBB',
                        'longName': 'Beta',
                        'exchange': 'NCM',
                        'currency': 'USD',
                        'marketCap': 4_200_000_000,
                        'regularMarketPrice': 12.4,
                        'fiftyTwoWeekLow': 8.8,
                        'fiftyTwoWeekHigh': 25.0,
                        'regularMarketChangePercent': 5.5,
                        'regularMarketVolume': 7_200_000,
                        'averageDailyVolume3Month': 3_300_000,
                        'sector': 'Technology',
                        'industry': 'Semiconductors',
                    },
                ],
                2: [
                    {
                        'symbol': 'CCC',
                        'longName': 'Gamma',
                        'exchange': 'NCM',
                        'currency': 'USD',
                        'marketCap': 4_300_000_000,
                        'regularMarketPrice': 13.4,
                        'fiftyTwoWeekLow': 8.8,
                        'fiftyTwoWeekHigh': 25.0,
                        'regularMarketChangePercent': 4.5,
                        'regularMarketVolume': 6_200_000,
                        'averageDailyVolume3Month': 3_100_000,
                        'sector': 'Technology',
                        'industry': 'Software Infrastructure',
                    },
                    {
                        'symbol': 'DDD',
                        'longName': 'Delta',
                        'exchange': 'NCM',
                        'currency': 'USD',
                        'marketCap': 4_400_000_000,
                        'regularMarketPrice': 14.4,
                        'fiftyTwoWeekLow': 8.8,
                        'fiftyTwoWeekHigh': 25.0,
                        'regularMarketChangePercent': 3.5,
                        'regularMarketVolume': 5_200_000,
                        'averageDailyVolume3Month': 2_900_000,
                        'sector': 'Industrials',
                        'industry': 'Electrical Equipment',
                    },
                ],
            }
            return {'quotes': pages.get(current_offset, [])}

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
                'max_candidates_per_market': 1,
                'max_scan_pages_per_market': 1,
                'universe_page_size': 2,
                'max_universe_pages_per_market': 2,
                'max_selected_per_market': 1,
                'min_market_cap': 3_000_000_000,
                'max_market_cap': 10_000_000_000,
                'max_price_position_ratio': 0.35,
                'heat_top_industries': 1,
                'heat_top_sectors': 1,
                'heat_min_constituents': 1,
                'fixed_hot_theme_names': [],
            },
            screener=fake_screener,
            ticker_factory=lambda symbol: _FakeTicker({}),
        )

        provider.sync_market_universe(['US_EQ'], date(2026, 5, 25))
        universe = provider.list_market_universe(date(2026, 5, 25), ['US_EQ'])

        self.assertEqual(requested_offsets, [(2, 0), (2, 2)])
        self.assertEqual({row.ticker for row in universe}, {'AAA', 'BBB', 'CCC', 'DDD'})


if __name__ == '__main__':
    unittest.main()
