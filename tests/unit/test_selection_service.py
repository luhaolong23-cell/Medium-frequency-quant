import unittest
from datetime import date

from packages.domain_core.selection.entities import StockSeed, ThemeHeatSnapshot, StockScreenObservation, StockUniverseSnapshot
from packages.shared.settings import (
    DailyRankingConfig,
    DailyRankingWeightsConfig,
    MarketSettings,
    MarketsConfig,
    ProxySettings,
    SeedDiscoveryConfig,
    SelectionRulesConfig,
)
from services.selection_service.app.application.use_cases import SelectionService
from services.selection_service.app.infra.provider import MockSelectionDataProvider
from services.selection_service.app.infra.repository import InMemorySelectionRepository




class _UniverseSeedProvider:
    def __init__(self) -> None:
        self._universes = {}

    def build_hot_theme_list(self, market_codes: list[str], trade_date: date):
        for market_code in market_codes:
            self._universes[(trade_date, market_code)] = [
                {
                    'trade_date': trade_date,
                    'market_code': market_code,
                    'ticker': f'{market_code}_A',
                    'company_name': f'{market_code} Alpha',
                    'sector': 'Technology',
                    'industry': 'Semiconductors',
                    'exchange': 'TEST',
                    'currency': 'USD',
                    'country_code': market_code[:2],
                    'market_cap': 5_000_000_000,
                    'price': 12.0,
                    'price_position': 0.24,
                    'momentum_pct': 6.0,
                    'volume_ratio': 1.4,
                    'theme_tags': ['semiconductors', 'technology', 'global_semiconductor'],
                    'source': 'test',
                }
            ]
        return [
            ThemeHeatSnapshot(
                trade_date=trade_date,
                market_code=market_code,
                theme_type='industry',
                theme_name='Semiconductors',
                raw_heat_score=88.0,
                smoothed_heat_score=88.0,
                constituent_count=1,
                source='test',
            )
            for market_code in market_codes
        ]

    def resolve_seeds(self, market_codes: list[str], trade_date: date):
        return [
            StockSeed(
                market_code=market_code,
                ticker=f'{market_code}_000',
                company_name=f'{market_code} Alpha 000',
                sector='Technology',
                industry='Semiconductors',
                exchange='TEST',
                currency='USD',
                country_code=market_code[:2],
                seed_type='bull_heat_screen',
                theme_tags=['semiconductors', 'technology', 'global_semiconductor'],
                theme_score=88.0,
                valuation_score=76.0,
                size_score=72.0,
                valuation_band='fair',
                market_cap_bucket='mid_cap',
            )
            for market_code in market_codes
        ]

    def sync_market_universe(self, market_codes: list[str], trade_date: date):
        self.build_hot_theme_list(market_codes, trade_date)
        return self.list_market_universe(trade_date, market_codes)

    def list_market_universe(self, trade_date: date, market_codes: list[str]):
        rows = []
        for market_code in market_codes:
            rows.extend(self._universes.get((trade_date, market_code), []))
        return rows



class _LocalUniverseOnlySeedProvider(_UniverseSeedProvider):
    def resolve_seeds(self, market_codes: list[str], trade_date: date):
        raise AssertionError('run_daily_selection should resolve seeds from local universe, not provider.resolve_seeds')

    def resolve_seeds_from_universe(self, rows, trade_date: date):
        return [
            StockSeed(
                market_code=row.market_code,
                ticker=row.ticker,
                company_name=row.company_name,
                sector=row.sector,
                industry=row.industry,
                exchange=row.exchange,
                currency=row.currency,
                country_code=row.country_code,
                seed_type='bull_heat_screen',
                theme_tags=row.theme_tags,
                theme_score=88.0,
                valuation_score=76.0,
                size_score=72.0,
                valuation_band='fair',
                market_cap_bucket='mid_cap',
            )
            for row in rows
        ]


class _EnrichingLocalUniverseSeedProvider(_LocalUniverseOnlySeedProvider):
    def enrich_market_universe_rows(self, rows):
        return [
            StockUniverseSnapshot(
                trade_date=row.trade_date,
                market_code=row.market_code,
                ticker=row.ticker,
                company_name=row.company_name,
                sector='Technology' if row.sector == 'Unknown' else row.sector,
                industry='Semiconductors' if row.industry == 'Unknown' else row.industry,
                exchange=row.exchange,
                currency=row.currency,
                country_code=row.country_code,
                market_cap=row.market_cap,
                price=row.price,
                price_position=row.price_position,
                momentum_pct=row.momentum_pct,
                volume_ratio=row.volume_ratio,
                theme_tags=['semiconductors', 'technology', 'global_semiconductor'],
                source=row.source,
            )
            for row in rows
        ]


class _RecordingEnrichingLocalUniverseSeedProvider(_EnrichingLocalUniverseSeedProvider):
    def __init__(self) -> None:
        self.enriched_batches: list[list[str]] = []

    def enrich_market_universe_rows(self, rows):
        self.enriched_batches.append([row.ticker for row in rows])
        return super().enrich_market_universe_rows(rows)


class _FallbackToProviderSeeds(_LocalUniverseOnlySeedProvider):
    def __init__(self, row_count: int = 1) -> None:
        super().__init__()
        self.row_count = row_count
        self.resolve_calls = 0
        self.enrich_calls = 0

    def build_hot_theme_list(self, market_codes: list[str], trade_date: date):
        for market_code in market_codes:
            self._universes[(trade_date, market_code)] = [
                {
                    'trade_date': trade_date,
                    'market_code': market_code,
                    'ticker': f'{market_code}_{index:03d}',
                    'company_name': f'{market_code} Alpha {index:03d}',
                    'sector': 'Unknown',
                    'industry': 'Unknown',
                    'exchange': 'TEST',
                    'currency': 'USD',
                    'country_code': market_code[:2],
                    'market_cap': 5_000_000_000 - (index * 1_000_000),
                    'price': 22.0,
                    'price_position': 0.24,
                    'momentum_pct': 6.0,
                    'volume_ratio': 1.4,
                    'theme_tags': ['auto_heat'],
                    'source': 'test',
                }
                for index in range(self.row_count)
            ]
        return [
            ThemeHeatSnapshot(
                trade_date=trade_date,
                market_code=market_code,
                theme_type='global_theme',
                theme_name='半导体',
                raw_heat_score=88.0,
                smoothed_heat_score=88.0,
                constituent_count=1,
                source='test',
            )
            for market_code in market_codes
        ]

    def resolve_seeds_from_universe(self, rows, trade_date: date):
        return []

    def enrich_market_universe_rows(self, rows):
        self.enrich_calls += 1
        return rows

    def resolve_seeds(self, market_codes: list[str], trade_date: date):
        self.resolve_calls += 1
        return [
            StockSeed(
                market_code=market_code,
                ticker=f'{market_code}_A',
                company_name=f'{market_code} Alpha',
                sector='Technology',
                industry='Semiconductors',
                exchange='TEST',
                currency='USD',
                country_code=market_code[:2],
                seed_type='bull_heat_screen',
                theme_tags=['semiconductors', 'technology', 'global_semiconductor'],
                theme_score=88.0,
                valuation_score=76.0,
                size_score=72.0,
                valuation_band='fair',
                market_cap_bucket='mid_cap',
            )
            for market_code in market_codes
        ]


class _LimitedEnrichmentSeedProvider(_LocalUniverseOnlySeedProvider):
    def __init__(self, row_count: int) -> None:
        super().__init__()
        self.row_count = row_count
        self.enriched_batches: list[list[str]] = []

    def build_hot_theme_list(self, market_codes: list[str], trade_date: date):
        for market_code in market_codes:
            self._universes[(trade_date, market_code)] = [
                {
                    'trade_date': trade_date,
                    'market_code': market_code,
                    'ticker': f'{market_code}_{index:03d}',
                    'company_name': f'{market_code} Candidate {index:03d}',
                    'sector': 'Unknown',
                    'industry': 'Unknown',
                    'exchange': 'TEST',
                    'currency': 'USD',
                    'country_code': market_code[:2],
                    'market_cap': 10_000_000_000 - (index * 10_000_000),
                    'price': 22.0,
                    'price_position': 0.24,
                    'momentum_pct': 9.0 - (index * 0.1),
                    'volume_ratio': 1.5 - (index * 0.01),
                    'theme_tags': ['auto_heat'],
                    'source': 'test',
                }
                for index in range(self.row_count)
            ]
        return [
            ThemeHeatSnapshot(
                trade_date=trade_date,
                market_code=market_code,
                theme_type='global_theme',
                theme_name='半导体',
                raw_heat_score=88.0,
                smoothed_heat_score=88.0,
                constituent_count=1,
                source='test',
            )
            for market_code in market_codes
        ]

    def resolve_seeds(self, market_codes: list[str], trade_date: date):
        raise AssertionError('run_daily_selection should resolve seeds from limited local enrichment, not provider.resolve_seeds')

    def resolve_seeds_from_universe(self, rows, trade_date: date):
        return [
            StockSeed(
                market_code=row.market_code,
                ticker=row.ticker,
                company_name=row.company_name,
                sector=row.sector,
                industry=row.industry,
                exchange=row.exchange,
                currency=row.currency,
                country_code=row.country_code,
                seed_type='bull_heat_screen',
                theme_tags=['semiconductors', 'technology', 'global_semiconductor'],
                theme_score=88.0,
                valuation_score=76.0,
                size_score=72.0,
                valuation_band='fair',
                market_cap_bucket='mid_cap',
            )
            for row in rows
            if row.sector != 'Unknown' and row.industry != 'Unknown'
        ]

    def enrich_market_universe_rows(self, rows):
        self.enriched_batches.append([row.ticker for row in rows])
        return [
            StockUniverseSnapshot(
                trade_date=row.trade_date,
                market_code=row.market_code,
                ticker=row.ticker,
                company_name=row.company_name,
                sector='Technology',
                industry='Semiconductors',
                exchange=row.exchange,
                currency=row.currency,
                country_code=row.country_code,
                market_cap=row.market_cap,
                price=row.price,
                price_position=row.price_position,
                momentum_pct=row.momentum_pct,
                volume_ratio=row.volume_ratio,
                theme_tags=['semiconductors', 'technology', 'global_semiconductor'],
                source=row.source,
            )
            for row in rows
        ]


class _FailingSelectionDataProvider:
    source_mode = 'should_not_fetch'

    def fetch_daily(self, seeds: list[StockSeed], trade_date: date):
        raise AssertionError('run_daily_selection should use local universe metrics when they are already available')


class _MetricRichUniverseSeedProvider(_LocalUniverseOnlySeedProvider):
    def build_hot_theme_list(self, market_codes: list[str], trade_date: date):
        for market_code in market_codes:
            self._universes[(trade_date, market_code)] = [
                {
                    'trade_date': trade_date,
                    'market_code': market_code,
                    'ticker': f'{market_code}_A',
                    'company_name': f'{market_code} Alpha',
                    'sector': 'Technology',
                    'industry': 'Semiconductors',
                    'exchange': 'TEST',
                    'currency': 'USD',
                    'country_code': market_code[:2],
                    'market_cap': 5_000_000_000,
                    'price': 22.0,
                    'price_position': 0.24,
                    'momentum_pct': 6.0,
                    'volume_ratio': 1.4,
                    'ret_5d': 0.035,
                    'ret_20d': 0.08,
                    'ret_60d': 0.18,
                    'ma_20': 20.0,
                    'ma_60': 19.5,
                    'avg_dollar_volume_3d': 15_600_000,
                    'avg_dollar_volume_20d': 12_000_000,
                    'volume_ratio_3d': 1.3,
                    'volume_up_days_5d': 3,
                    'distance_to_60d_high': 0.09,
                    'momentum_acceleration': 0.015,
                    'vol_20d': 0.25,
                    'theme_tags': ['semiconductors', 'technology', 'global_semiconductor'],
                    'source': 'test',
                }
            ]
        return [
            ThemeHeatSnapshot(
                trade_date=trade_date,
                market_code=market_code,
                theme_type='industry',
                theme_name='Semiconductors',
                raw_heat_score=88.0,
                smoothed_heat_score=88.0,
                constituent_count=1,
                source='test',
            )
            for market_code in market_codes
        ]


class _LocalUniverseDataProvider:
    source_mode = 'test'

    def fetch_daily(self, seeds: list[StockSeed], trade_date: date):
        return [
            StockScreenObservation(
                market_code=seed.market_code,
                ticker=seed.ticker,
                trade_date=trade_date,
                close=22.0,
                ma_20=20.0,
                ma_60=19.5,
                ma_120=18.0,
                ma_200=17.0,
                ret_5d=0.035,
                ret_20d=0.08,
                ret_60d=0.18,
                avg_dollar_volume_3d=15_600_000,
                avg_dollar_volume_5d=18_000_000,
                avg_dollar_volume_20d=12_000_000,
                volume_ratio_3d=1.3,
                volume_ratio_5d=1.5,
                volume_up_days_5d=3,
                distance_to_60d_high=0.09,
                momentum_acceleration=0.015,
                vol_20d=0.25,
                source='test',
            )
            for seed in seeds
        ]


class _RecordingLocalUniverseDataProvider(_LocalUniverseDataProvider):
    def __init__(self) -> None:
        self.fetch_calls = 0

    def fetch_daily(self, seeds: list[StockSeed], trade_date: date):
        self.fetch_calls += 1
        return super().fetch_daily(seeds, trade_date)


class _InventoryAndBarsSeedProvider(_LocalUniverseOnlySeedProvider):
    def __init__(self) -> None:
        super().__init__()
        self.latest_bar_dates: dict[tuple[str, str], date | None] = {}
        self.bar_sync_calls = 0

    def build_hot_theme_list(self, market_codes: list[str], trade_date: date):
        for market_code in market_codes:
            self._universes[(trade_date, market_code)] = [
                {
                    'trade_date': trade_date,
                    'market_code': market_code,
                    'ticker': f'{market_code}_A',
                    'company_name': f'{market_code} Alpha',
                    'sector': 'Technology',
                    'industry': 'Semiconductors',
                    'exchange': 'TEST',
                    'currency': 'USD',
                    'country_code': market_code[:2],
                    'market_cap': 5_000_000_000,
                    'price': 22.0,
                    'price_position': 0.24,
                    'momentum_pct': 6.0,
                    'volume_ratio': 1.4,
                    'theme_tags': ['semiconductors', 'technology', 'global_semiconductor'],
                    'source': 'test',
                }
            ]
        return [
            ThemeHeatSnapshot(
                trade_date=trade_date,
                market_code=market_code,
                theme_type='industry',
                theme_name='Semiconductors',
                raw_heat_score=88.0,
                smoothed_heat_score=88.0,
                constituent_count=1,
                source='test',
            )
            for market_code in market_codes
        ]

    def sync_market_universe_bars(self, rows, *, trade_date: date, latest_bar_dates: dict[tuple[str, str], date | None]):
        self.bar_sync_calls += 1
        self.latest_bar_dates = dict(latest_bar_dates)
        history_rows = []
        for row in rows:
            for index in range(80):
                history_rows.append({
                    'market_code': row.market_code,
                    'ticker': row.ticker,
                    'trade_date': date(2026, 2, 2).fromordinal(date(2026, 2, 2).toordinal() + index),
                    'close': 20.0 + (index * 0.12),
                    'volume': 600_000 + (index * 1200),
                })
        return history_rows


def _selection_rules_config(*, max_selected_per_market: int = 10) -> SelectionRulesConfig:
    return SelectionRulesConfig(
        daily_ranking=DailyRankingConfig(
            min_price=10.0,
            min_avg_dollar_volume_20d=10_000_000,
            min_volume_ratio_3d=1.1,
            max_distance_to_60d_high=0.18,
            max_vol_20d=0.7,
            min_composite_score=60.0,
            watchlist_size=5,
            weights=DailyRankingWeightsConfig(
                theme=20,
                lagging=25,
                trend_recovery=20,
                momentum_acceleration=20,
                volume_probe=10,
                risk_control=5,
            ),
        ),
        seed_discovery=SeedDiscoveryConfig(
            enabled=True,
            max_selected_per_market=max_selected_per_market,
        ),
    )


def _markets_config() -> MarketsConfig:
    return MarketsConfig(
        markets=[
            MarketSettings(
                market_code='US_EQ',
                market_name='United States Equities',
                country_code='US',
                region='NORTH_AMERICA',
                proxies=[ProxySettings(symbol='SPY', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1)],
            )
        ]
    )


def _multi_markets_config() -> MarketsConfig:
    return MarketsConfig(
        markets=[
            MarketSettings(
                market_code='US_EQ',
                market_name='United States Equities',
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
            MarketSettings(
                market_code='SG_EQ',
                market_name='Singapore Equities',
                country_code='SG',
                region='ASIA',
                proxies=[ProxySettings(symbol='EWS', proxy_type='ETF', exchange_code='ARCA', currency='USD', priority=1)],
            ),
        ]
    )


class _RecordingThemeSeedProvider(_UniverseSeedProvider):
    def __init__(self) -> None:
        super().__init__()
        self.build_calls: list[list[str]] = []

    def build_hot_theme_list(self, market_codes: list[str], trade_date: date):
        self.build_calls.append(list(market_codes))
        return super().build_hot_theme_list(market_codes, trade_date)


class _RecordingUniverseInventorySeedProvider(_LocalUniverseOnlySeedProvider):
    def __init__(self) -> None:
        super().__init__()
        self.inventory_calls: list[list[str]] = []
        self.theme_calls: list[list[str]] = []

    def build_hot_theme_list(self, market_codes: list[str], trade_date: date):
        self.theme_calls.append(list(market_codes))
        return super().build_hot_theme_list(market_codes, trade_date)

    def sync_market_universe_inventory(self, market_codes: list[str], trade_date: date):
        self.inventory_calls.append(list(market_codes))
        return super().sync_market_universe(market_codes, trade_date)


class _PartiallyFailingUniverseInventorySeedProvider(_RecordingUniverseInventorySeedProvider):
    def __init__(self, failing_market_code: str) -> None:
        super().__init__()
        self.failing_market_code = failing_market_code

    def sync_market_universe_inventory(self, market_codes: list[str], trade_date: date):
        self.inventory_calls.append(list(market_codes))
        if market_codes == [self.failing_market_code]:
            raise RuntimeError(f'{self.failing_market_code} inventory failed')
        return _UniverseSeedProvider.sync_market_universe(self, market_codes, trade_date)


class SelectionServiceTests(unittest.TestCase):
    def test_prepare_hot_themes_builds_missing_markets_only_for_same_day_full_snapshot(self) -> None:
        repository = InMemorySelectionRepository()
        seed_provider = _RecordingThemeSeedProvider()
        service = SelectionService(
            markets_config=_multi_markets_config(),
            seed_provider=seed_provider,
            rules_config=_selection_rules_config(),
            data_provider=MockSelectionDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        trade_date = date(2026, 6, 6)
        initial = service.prepare_hot_themes(trade_date=trade_date, market_codes=['US_EQ'])
        full_snapshot = service.prepare_hot_themes(trade_date=trade_date, market_codes=['ALL'])
        rerun_snapshot = service.prepare_hot_themes(trade_date=trade_date, market_codes=['ALL'])

        self.assertEqual(len(initial), 1)
        self.assertEqual(seed_provider.build_calls[0], ['US_EQ'])
        self.assertEqual(set(seed_provider.build_calls[1]), {'JP_EQ', 'SG_EQ'})
        self.assertEqual(len(seed_provider.build_calls), 2)
        self.assertEqual({item.market_code for item in full_snapshot}, {'US_EQ', 'JP_EQ', 'SG_EQ'})
        self.assertEqual({item.market_code for item in rerun_snapshot}, {'US_EQ', 'JP_EQ', 'SG_EQ'})
        stored = service.list_heat_snapshots(trade_date=trade_date)
        self.assertEqual({item.market_code for item in stored}, {'US_EQ', 'JP_EQ', 'SG_EQ'})

    def test_prepare_hot_themes_carries_forward_previous_full_snapshot_before_incremental_update(self) -> None:
        repository = InMemorySelectionRepository()
        seed_provider = _RecordingThemeSeedProvider()
        service = SelectionService(
            markets_config=_multi_markets_config(),
            seed_provider=seed_provider,
            rules_config=_selection_rules_config(),
            data_provider=MockSelectionDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        base_date = date(2026, 6, 6)
        next_date = date(2026, 6, 7)
        service.prepare_hot_themes(trade_date=base_date, market_codes=['ALL'])
        next_day = service.prepare_hot_themes(trade_date=next_date, market_codes=['US_EQ'])

        self.assertEqual(seed_provider.build_calls[0], ['US_EQ', 'JP_EQ', 'SG_EQ'])
        self.assertEqual(seed_provider.build_calls[1], ['US_EQ'])
        self.assertEqual({item.market_code for item in next_day}, {'US_EQ'})
        stored = service.list_heat_snapshots(trade_date=next_date)
        self.assertEqual({item.market_code for item in stored}, {'US_EQ', 'JP_EQ', 'SG_EQ'})

    def test_sync_market_universe_inventory_builds_missing_markets_only_for_same_day_full_snapshot(self) -> None:
        repository = InMemorySelectionRepository()
        seed_provider = _RecordingUniverseInventorySeedProvider()
        service = SelectionService(
            markets_config=_multi_markets_config(),
            seed_provider=seed_provider,
            rules_config=_selection_rules_config(),
            data_provider=MockSelectionDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        trade_date = date(2026, 6, 6)
        initial = service.sync_market_universe_inventory(trade_date=trade_date, market_codes=['US_EQ'])
        full_snapshot = service.sync_market_universe_inventory(trade_date=trade_date, market_codes=['ALL'])
        rerun_snapshot = service.sync_market_universe_inventory(trade_date=trade_date, market_codes=['ALL'])

        self.assertEqual(len(initial), 1)
        self.assertEqual(seed_provider.inventory_calls[0], ['US_EQ'])
        self.assertEqual(seed_provider.inventory_calls[1], ['JP_EQ'])
        self.assertEqual(seed_provider.inventory_calls[2], ['SG_EQ'])
        self.assertEqual(len(seed_provider.inventory_calls), 3)
        self.assertEqual({item.market_code for item in full_snapshot}, {'US_EQ', 'JP_EQ', 'SG_EQ'})
        self.assertEqual({item.market_code for item in rerun_snapshot}, {'US_EQ', 'JP_EQ', 'SG_EQ'})
        stored = service.list_market_universe(trade_date=trade_date)
        self.assertEqual({item.market_code for item in stored}, {'US_EQ', 'JP_EQ', 'SG_EQ'})

    def test_run_daily_selection_falls_back_to_provider_seeds_when_local_universe_has_no_classification(self) -> None:
        repository = InMemorySelectionRepository()
        seed_provider = _FallbackToProviderSeeds(row_count=1201)
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=seed_provider,
            rules_config=_selection_rules_config(),
            data_provider=_LocalUniverseDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        trade_date = date(2026, 6, 6)
        service.prepare_hot_themes(trade_date=trade_date, market_codes=['US_EQ'])
        service.sync_market_universe_inventory(trade_date=trade_date, market_codes=['US_EQ'])

        candidates, watchlist = service.run_daily_selection(trade_date=trade_date, market_codes=['US_EQ'])

        self.assertEqual(seed_provider.resolve_calls, 1)
        self.assertEqual(seed_provider.enrich_calls, 0)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(watchlist), 1)

    def test_run_daily_selection_limits_local_universe_enrichment_to_seed_subset(self) -> None:
        repository = InMemorySelectionRepository()
        seed_provider = _LimitedEnrichmentSeedProvider(row_count=6)
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=seed_provider,
            rules_config=_selection_rules_config(max_selected_per_market=2),
            data_provider=_LocalUniverseDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        trade_date = date(2026, 6, 6)
        service.prepare_hot_themes(trade_date=trade_date, market_codes=['US_EQ'])
        service.sync_market_universe_inventory(trade_date=trade_date, market_codes=['US_EQ'])

        candidates, watchlist = service.run_daily_selection(trade_date=trade_date, market_codes=['US_EQ'])

        self.assertEqual(len(seed_provider.enriched_batches), 1)
        self.assertEqual(seed_provider.enriched_batches[0], ['US_EQ_000', 'US_EQ_001'])
        self.assertEqual(len(service.list_seed_pool(trade_date=trade_date, market_code='US_EQ')), 2)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(len(watchlist), 2)

    def test_sync_market_universe_inventory_carries_forward_previous_full_snapshot_before_incremental_update(self) -> None:
        repository = InMemorySelectionRepository()
        seed_provider = _RecordingUniverseInventorySeedProvider()
        service = SelectionService(
            markets_config=_multi_markets_config(),
            seed_provider=seed_provider,
            rules_config=_selection_rules_config(),
            data_provider=MockSelectionDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        base_date = date(2026, 6, 6)
        next_date = date(2026, 6, 7)
        service.sync_market_universe_inventory(trade_date=base_date, market_codes=['ALL'])
        next_day = service.sync_market_universe_inventory(trade_date=next_date, market_codes=['US_EQ'])

        self.assertEqual(seed_provider.inventory_calls[0], ['US_EQ'])
        self.assertEqual(seed_provider.inventory_calls[1], ['JP_EQ'])
        self.assertEqual(seed_provider.inventory_calls[2], ['SG_EQ'])
        self.assertEqual(seed_provider.inventory_calls[3], ['US_EQ'])
        self.assertEqual({item.market_code for item in next_day}, {'US_EQ'})
        stored = service.list_market_universe(trade_date=next_date)
        self.assertEqual({item.market_code for item in stored}, {'US_EQ', 'JP_EQ', 'SG_EQ'})

    def test_sync_market_universe_inventory_continues_when_one_market_fails_during_full_snapshot(self) -> None:
        repository = InMemorySelectionRepository()
        seed_provider = _PartiallyFailingUniverseInventorySeedProvider('JP_EQ')
        service = SelectionService(
            markets_config=_multi_markets_config(),
            seed_provider=seed_provider,
            rules_config=_selection_rules_config(),
            data_provider=MockSelectionDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        trade_date = date(2026, 6, 6)
        rows = service.sync_market_universe_inventory(trade_date=trade_date, market_codes=['ALL'])

        self.assertEqual(seed_provider.inventory_calls, [['US_EQ'], ['JP_EQ'], ['SG_EQ']])
        self.assertEqual({item.market_code for item in rows}, {'US_EQ', 'SG_EQ'})
        stored = service.list_market_universe(trade_date=trade_date)
        self.assertEqual({item.market_code for item in stored}, {'US_EQ', 'SG_EQ'})

    def test_run_daily_selection_reuses_latest_incremental_snapshots_without_daily_rebuild(self) -> None:
        repository = InMemorySelectionRepository()
        seed_provider = _RecordingUniverseInventorySeedProvider()
        data_provider = _RecordingLocalUniverseDataProvider()
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=seed_provider,
            rules_config=_selection_rules_config(),
            data_provider=data_provider,
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        base_date = date(2026, 6, 6)
        next_date = date(2026, 6, 7)
        service.prepare_hot_themes(trade_date=base_date, market_codes=['US_EQ'])
        service.sync_market_universe_inventory(trade_date=base_date, market_codes=['US_EQ'])
        base_theme_calls = list(seed_provider.theme_calls)
        base_inventory_calls = list(seed_provider.inventory_calls)

        candidates, watchlist = service.run_daily_selection(
            trade_date=next_date,
            market_codes=['US_EQ'],
        )

        self.assertEqual(seed_provider.theme_calls, base_theme_calls)
        self.assertEqual(seed_provider.inventory_calls, base_inventory_calls)
        self.assertEqual(data_provider.fetch_calls, 1)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(watchlist), 1)
        self.assertEqual(service.list_heat_snapshots(trade_date=base_date, market_code='US_EQ')[0].market_code, 'US_EQ')

    def test_prepare_hot_themes_does_not_persist_market_universe_rows(self) -> None:
        repository = InMemorySelectionRepository()
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=_UniverseSeedProvider(),
            rules_config=_selection_rules_config(),
            data_provider=MockSelectionDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        service.prepare_hot_themes(trade_date=date(2026, 6, 2), market_codes=['US_EQ'])

        universe = service.list_market_universe(trade_date=date(2026, 6, 2), market_code='US_EQ')
        self.assertEqual(universe, [])

    def test_sync_market_universe_persists_market_universe_rows_when_seed_provider_exposes_them(self) -> None:
        repository = InMemorySelectionRepository()
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=_UniverseSeedProvider(),
            rules_config=_selection_rules_config(),
            data_provider=MockSelectionDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
        )

        service.sync_market_universe(trade_date=date(2026, 6, 2), market_codes=['US_EQ'])

        universe = service.list_market_universe(trade_date=date(2026, 6, 2), market_code='US_EQ')
        self.assertEqual(len(universe), 1)
        self.assertEqual(universe[0].ticker, 'US_EQ_A')
        self.assertEqual(universe[0].industry, 'Semiconductors')

    def test_run_daily_selection_prefers_local_market_universe_seed_resolution(self) -> None:
        repository = InMemorySelectionRepository()
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=_LocalUniverseOnlySeedProvider(),
            rules_config=_selection_rules_config(),
            data_provider=_LocalUniverseDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
        )

        trade_date = date(2026, 6, 2)
        prepared = service.prepare_hot_themes(trade_date=trade_date, market_codes=['US_EQ'])
        service.sync_market_universe(trade_date=trade_date, market_codes=['US_EQ'])
        candidates, watchlist = service.run_daily_selection(
            trade_date=trade_date,
            market_codes=['US_EQ'],
            prepared_heat_snapshots=prepared,
        )

        self.assertEqual(len(repository.list_seed_pool(trade_date, market_code='US_EQ')), 1)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].ticker, 'US_EQ_A')
        self.assertEqual(len(watchlist), 1)
        self.assertEqual(watchlist[0].ticker, 'US_EQ_A')


    def test_run_daily_selection_prefers_local_universe_metrics_when_available(self) -> None:
        repository = InMemorySelectionRepository()
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=_MetricRichUniverseSeedProvider(),
            rules_config=_selection_rules_config(),
            data_provider=_FailingSelectionDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        candidates, watchlist = service.run_daily_selection(
            trade_date=date(2026, 6, 2),
            market_codes=['US_EQ'],
            replace_market_codes=['US_EQ'],
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(watchlist), 1)
        self.assertEqual(candidates[0].source, 'local_universe')
        self.assertEqual(candidates[0].ret_5d, 0.035)
        self.assertEqual(candidates[0].volume_ratio_3d, 1.3)
        self.assertEqual(candidates[0].distance_to_60d_high, 0.09)

    def test_run_daily_selection_syncs_inventory_only_then_fetches_selected_observations(self) -> None:
        repository = InMemorySelectionRepository()
        provider = _InventoryAndBarsSeedProvider()
        data_provider = _RecordingLocalUniverseDataProvider()
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=provider,
            rules_config=_selection_rules_config(),
            data_provider=data_provider,
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
            bar_repository=repository,
        )

        candidates, watchlist = service.run_daily_selection(
            trade_date=date(2026, 6, 2),
            market_codes=['US_EQ'],
            replace_market_codes=['US_EQ'],
        )

        self.assertEqual(provider.bar_sync_calls, 0)
        self.assertEqual(data_provider.fetch_calls, 1)
        self.assertEqual(len(service.list_market_universe(trade_date=date(2026, 6, 2), market_code='US_EQ')), 1)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(watchlist), 1)
        self.assertEqual(candidates[0].source, 'test')
        self.assertGreater(candidates[0].ret_20d, 0)

    def test_run_daily_selection_uses_new_lagging_strategy_fields(self) -> None:
        repository = InMemorySelectionRepository()
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=_LocalUniverseOnlySeedProvider(),
            rules_config=_selection_rules_config(),
            data_provider=_LocalUniverseDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
        )

        trade_date = date(2026, 6, 2)
        prepared = service.prepare_hot_themes(trade_date=trade_date, market_codes=['US_EQ'])
        service.sync_market_universe(trade_date=trade_date, market_codes=['US_EQ'])
        candidates, watchlist = service.run_daily_selection(
            trade_date=trade_date,
            market_codes=['US_EQ'],
            prepared_heat_snapshots=prepared,
        )

        self.assertEqual(len(candidates), 1)
        self.assertGreater(candidates[0].lagging_score, 0)
        self.assertGreater(candidates[0].trend_recovery_score, 0)
        self.assertGreater(candidates[0].momentum_acceleration_score, 0)
        self.assertGreater(candidates[0].volume_probe_score, 0)
        self.assertGreater(candidates[0].risk_control_score, 0)
        self.assertAlmostEqual(candidates[0].ret_5d, 0.035)
        self.assertAlmostEqual(candidates[0].ret_20d, 0.08)
        self.assertAlmostEqual(candidates[0].volume_ratio_3d, 1.3)
        self.assertEqual(candidates[0].volume_up_days_5d, 3)
        self.assertAlmostEqual(candidates[0].distance_to_60d_high, 0.09)
        self.assertAlmostEqual(candidates[0].momentum_acceleration, 0.015)
        self.assertEqual(len(watchlist), 1)
        self.assertIn('lagging=', watchlist[0].watch_reason)
        self.assertIn('trend=', watchlist[0].watch_reason)
        self.assertIn('volume_probe=', watchlist[0].watch_reason)

    def test_run_daily_selection_enriches_unknown_universe_rows_before_local_theme_filtering(self) -> None:
        repository = InMemorySelectionRepository()
        trade_date = date(2026, 6, 2)
        repository.replace_market_universe(
            trade_date=trade_date,
            market_codes=['US_EQ'],
            rows=[
                StockUniverseSnapshot(
                    trade_date=trade_date,
                    market_code='US_EQ',
                    ticker='US_EQ_A',
                    company_name='US_EQ Alpha',
                    sector='Unknown',
                    industry='Unknown',
                    exchange='TEST',
                    currency='USD',
                    country_code='US',
                    market_cap=5_000_000_000,
                    price=12.0,
                    price_position=0.24,
                    momentum_pct=6.0,
                    volume_ratio=1.4,
                    theme_tags=['unknown', 'auto_heat'],
                    source='test',
                )
            ],
        )
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=_EnrichingLocalUniverseSeedProvider(),
            rules_config=_selection_rules_config(),
            data_provider=_LocalUniverseDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
        )

        prepared = service.prepare_hot_themes(trade_date=trade_date, market_codes=['US_EQ'])
        candidates, watchlist = service.run_daily_selection(
            trade_date=trade_date,
            market_codes=['US_EQ'],
            prepared_heat_snapshots=prepared,
        )

        universe = service.list_market_universe(trade_date=trade_date, market_code='US_EQ')
        self.assertEqual(universe[0].sector, 'Technology')
        self.assertEqual(universe[0].industry, 'Semiconductors')
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].industry, 'Semiconductors')
        self.assertEqual(len(watchlist), 1)
        self.assertEqual(watchlist[0].industry, 'Semiconductors')

    def test_repair_market_universe_persists_enriched_rows(self) -> None:
        repository = InMemorySelectionRepository()
        trade_date = date(2026, 6, 2)
        repository.replace_market_universe(
            trade_date=trade_date,
            market_codes=['US_EQ'],
            rows=[
                StockUniverseSnapshot(
                    trade_date=trade_date,
                    market_code='US_EQ',
                    ticker='US_EQ_A',
                    company_name='US_EQ Alpha',
                    sector='Unknown',
                    industry='Unknown',
                    exchange='TEST',
                    currency='USD',
                    country_code='US',
                    market_cap=5_000_000_000,
                    price=12.0,
                    price_position=0.24,
                    momentum_pct=6.0,
                    volume_ratio=1.4,
                    theme_tags=['unknown', 'auto_heat'],
                    source='test',
                )
            ],
        )
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=_EnrichingLocalUniverseSeedProvider(),
            rules_config=_selection_rules_config(),
            data_provider=_LocalUniverseDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
        )

        rows = service.repair_market_universe(trade_date=trade_date, market_codes=['US_EQ'])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].industry, 'Semiconductors')
        stored = service.list_market_universe(trade_date=trade_date, market_code='US_EQ')
        self.assertEqual(stored[0].sector, 'Technology')
        self.assertEqual(stored[0].industry, 'Semiconductors')

    def test_repair_market_universe_can_process_unknown_rows_in_batches(self) -> None:
        repository = InMemorySelectionRepository()
        trade_date = date(2026, 6, 2)
        repository.replace_market_universe(
            trade_date=trade_date,
            market_codes=['US_EQ'],
            rows=[
                StockUniverseSnapshot(
                    trade_date=trade_date,
                    market_code='US_EQ',
                    ticker='US_EQ_A',
                    company_name='US_EQ Alpha',
                    sector='Unknown',
                    industry='Unknown',
                    exchange='TEST',
                    currency='USD',
                    country_code='US',
                    market_cap=5_000_000_000,
                    price=12.0,
                    price_position=0.24,
                    momentum_pct=6.0,
                    volume_ratio=1.4,
                    theme_tags=['unknown', 'auto_heat'],
                    source='test',
                ),
                StockUniverseSnapshot(
                    trade_date=trade_date,
                    market_code='US_EQ',
                    ticker='US_EQ_B',
                    company_name='US_EQ Beta',
                    sector='Unknown',
                    industry='Unknown',
                    exchange='TEST',
                    currency='USD',
                    country_code='US',
                    market_cap=5_500_000_000,
                    price=13.0,
                    price_position=0.21,
                    momentum_pct=5.0,
                    volume_ratio=1.2,
                    theme_tags=['unknown', 'auto_heat'],
                    source='test',
                ),
            ],
        )
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=_EnrichingLocalUniverseSeedProvider(),
            rules_config=_selection_rules_config(),
            data_provider=_LocalUniverseDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
        )

        service.repair_market_universe(trade_date=trade_date, market_codes=['US_EQ'], limit=1)

        stored = service.list_market_universe(trade_date=trade_date, market_code='US_EQ')
        self.assertEqual(stored[0].industry, 'Unknown')
        self.assertEqual(stored[1].industry, 'Semiconductors')

        service.repair_market_universe(trade_date=trade_date, market_codes=['US_EQ'], limit=1, offset=0)

        stored = service.list_market_universe(trade_date=trade_date, market_code='US_EQ')
        self.assertEqual(stored[0].industry, 'Semiconductors')
        self.assertEqual(stored[1].industry, 'Semiconductors')

    def test_repair_market_universe_prioritizes_higher_value_unknown_rows_first(self) -> None:
        repository = InMemorySelectionRepository()
        trade_date = date(2026, 6, 2)
        repository.replace_market_universe(
            trade_date=trade_date,
            market_codes=['US_EQ'],
            rows=[
                StockUniverseSnapshot(
                    trade_date=trade_date,
                    market_code='US_EQ',
                    ticker='US_EQ_A',
                    company_name='US_EQ Alpha',
                    sector='Unknown',
                    industry='Unknown',
                    exchange='TEST',
                    currency='USD',
                    country_code='US',
                    market_cap=5_000_000_000,
                    price=12.0,
                    price_position=0.24,
                    momentum_pct=4.0,
                    volume_ratio=1.1,
                    theme_tags=['unknown', 'auto_heat'],
                    source='test',
                ),
                StockUniverseSnapshot(
                    trade_date=trade_date,
                    market_code='US_EQ',
                    ticker='US_EQ_B',
                    company_name='US_EQ Beta',
                    sector='Unknown',
                    industry='Unknown',
                    exchange='TEST',
                    currency='USD',
                    country_code='US',
                    market_cap=9_000_000_000,
                    price=13.0,
                    price_position=0.21,
                    momentum_pct=7.0,
                    volume_ratio=1.6,
                    theme_tags=['unknown', 'auto_heat'],
                    source='test',
                ),
            ],
        )
        seed_provider = _RecordingEnrichingLocalUniverseSeedProvider()
        service = SelectionService(
            markets_config=_markets_config(),
            seed_provider=seed_provider,
            rules_config=_selection_rules_config(),
            data_provider=_LocalUniverseDataProvider(),
            metadata_repository=repository,
            seed_pool_repository=repository,
            candidate_repository=repository,
            watchlist_repository=repository,
            heat_repository=repository,
            universe_repository=repository,
        )

        service.repair_market_universe(trade_date=trade_date, market_codes=['US_EQ'], limit=1)

        self.assertEqual(seed_provider.enriched_batches, [['US_EQ_B']])


if __name__ == '__main__':
    unittest.main()
