from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
import importlib
import math
import random
import time as time_module
from statistics import fmean, median, pstdev
import re
from urllib.parse import quote

import httpx
import pandas as pd

from packages.domain_core.selection.entities import StockDailyBar, StockScreenObservation, StockSeed, StockUniverseSnapshot, ThemeHeatSnapshot
from packages.shared.settings import DataSourcesConfig, LocalIndustryIndicesConfig, MarketsConfig


@dataclass(frozen=True)
class _ScreenedQuote:
    market_code: str
    country_code: str
    symbol: str
    company_name: str
    sector: str
    industry: str
    exchange: str
    currency: str
    market_cap: float
    price: float
    price_position: float | None
    momentum_pct: float
    volume_ratio: float


_FIXED_THEME_ALIAS_MAP = {
    '光伏': {
        'industry': {'solar', 'solarenergy', 'solarequipmentparts', 'renewableutilities', 'cleanenergy'},
    },
    'solar': {
        'industry': {'solar', 'solarenergy', 'solarequipmentparts', 'renewableutilities', 'cleanenergy'},
    },
    '半导体': {
        'industry': {'semiconductors', 'semiconductorequipmentmaterials', 'printedcircuitboards', 'electroniccomponents', 'integratedcircuits'},
    },
    'semiconductors': {
        'industry': {'semiconductors', 'semiconductorequipmentmaterials', 'printedcircuitboards', 'electroniccomponents', 'integratedcircuits'},
    },
    '芯片': {
        'industry': {'semiconductors', 'semiconductorequipmentmaterials', 'printedcircuitboards', 'electroniccomponents', 'integratedcircuits'},
    },
    'chip': {
        'industry': {'semiconductors', 'semiconductorequipmentmaterials', 'printedcircuitboards', 'electroniccomponents', 'integratedcircuits'},
    },
    '电力': {
        'industry': {'regulatedelectric', 'utilitiesregulatedelectric', 'independentpowerproducers', 'renewableutilities', 'batteries', 'electricalequipmentparts', 'electricalequipment'},
    },
    'power': {
        'industry': {'regulatedelectric', 'utilitiesregulatedelectric', 'independentpowerproducers', 'renewableutilities', 'batteries', 'electricalequipmentparts', 'electricalequipment'},
    },
    '航天': {
        'industry': {'aerospacedefense', 'satellitespacecommunications', 'defenseaerospace'},
    },
    'aerospace': {
        'industry': {'aerospacedefense', 'satellitespacecommunications', 'defenseaerospace'},
    },
}

_FIXED_THEME_REMOTE_QUERY_MAP = {
    '光伏': {'industry': ['Solar']},
    'solar': {'industry': ['Solar']},
    '半导体': {'industry': ['Semiconductors', 'Semiconductor Equipment Materials', 'Electronic Components']},
    'semiconductors': {'industry': ['Semiconductors', 'Semiconductor Equipment Materials', 'Electronic Components']},
    '芯片': {'industry': ['Semiconductors', 'Semiconductor Equipment Materials', 'Electronic Components']},
    'chip': {'industry': ['Semiconductors', 'Semiconductor Equipment Materials', 'Electronic Components']},
    '电力': {'industry': ['Utilities Regulated Electric', 'Utilities Independent Power Producers', 'Electrical Equipment Parts']},
    'power': {'industry': ['Utilities Regulated Electric', 'Utilities Independent Power Producers', 'Electrical Equipment Parts']},
    '航天': {'industry': ['Aerospace Defense']},
    'aerospace': {'industry': ['Aerospace Defense']},
}
_FIXED_THEME_PROXY_SYMBOL_MAP = {
    '光伏': 'TAN',
    'solar': 'TAN',
    '半导体': 'SOXX',
    'semiconductors': 'SOXX',
    '芯片': 'SOXX',
    'chip': 'SOXX',
    '电力': 'XLU',
    'power': 'XLU',
    '航天': 'ITA',
    'aerospace': 'ITA',
}



class MockSelectionSeedProvider:
    source_mode = 'mock_seed'

    def __init__(self, markets_config: MarketsConfig) -> None:
        self._markets_config = markets_config
        self._last_heat_snapshots: dict[tuple[date, str], list[ThemeHeatSnapshot]] = {}
        self._market_universe_cache: dict[tuple[date, str], list[StockUniverseSnapshot]] = {}

    def build_hot_theme_list(self, market_codes: list[str], trade_date: date) -> list[ThemeHeatSnapshot]:
        wanted = set(market_codes)
        snapshots: list[ThemeHeatSnapshot] = []
        for market in self._markets_config.markets:
            if market.market_code not in wanted:
                continue
            market_seeds = self._build_market_seeds(market.market_code, market.country_code)
            market_snapshots = self._build_heat_snapshots(trade_date, market.market_code, market_seeds)
            self._last_heat_snapshots[(trade_date, market.market_code)] = market_snapshots
            self._market_universe_cache[(trade_date, market.market_code)] = [
                StockUniverseSnapshot(
                    trade_date=trade_date,
                    market_code=seed.market_code,
                    ticker=seed.ticker,
                    company_name=seed.company_name,
                    sector=seed.sector,
                    industry=seed.industry,
                    exchange=seed.exchange,
                    currency=seed.currency,
                    country_code=seed.country_code,
                    market_cap=5_000_000_000,
                    price=20.0,
                    price_position=0.2,
                    momentum_pct=6.0,
                    volume_ratio=1.2,
                    ret_5d=0.03,
                    ret_20d=0.08,
                    ret_60d=0.18,
                    ma_20=19.0,
                    ma_60=18.5,
                    avg_dollar_volume_3d=15_000_000,
                    avg_dollar_volume_20d=12_000_000,
                    volume_ratio_3d=1.25,
                    volume_up_days_5d=3,
                    distance_to_60d_high=0.08,
                    momentum_acceleration=0.01,
                    vol_20d=0.24,
                    theme_tags=seed.theme_tags,
                    source='mock_seed',
                )
                for seed in market_seeds
            ]
            snapshots.extend(market_snapshots)
        return snapshots

    def resolve_seeds(self, market_codes: list[str], trade_date: date) -> list[StockSeed]:
        wanted = set(market_codes)
        seeds: list[StockSeed] = []
        for market in self._markets_config.markets:
            if market.market_code not in wanted:
                continue
            if (trade_date, market.market_code) not in self._last_heat_snapshots:
                self.build_hot_theme_list([market.market_code], trade_date)
            seeds.extend(self._build_market_seeds(market.market_code, market.country_code))
        return seeds

    def list_heat_snapshots(self, trade_date: date, market_codes: list[str]) -> list[ThemeHeatSnapshot]:
        snapshots: list[ThemeHeatSnapshot] = []
        for market_code in market_codes:
            snapshots.extend(self._last_heat_snapshots.get((trade_date, market_code), []))
        return snapshots

    def list_market_universe(self, trade_date: date, market_codes: list[str]) -> list[StockUniverseSnapshot]:
        rows: list[StockUniverseSnapshot] = []
        for market_code in market_codes:
            rows.extend(self._market_universe_cache.get((trade_date, market_code), []))
        return rows

    def _build_market_seeds(self, market_code: str, country_code: str) -> list[StockSeed]:
        templates = [
            ('QNTM', 'Quantum Compute Holdings', 'Technology', 'Semiconductors', 94.0, 88.0, 86.0, 'attractive', 'small_cap'),
            ('AISO', 'Applied Intelligence Software', 'Technology', 'Software Infrastructure', 91.0, 84.0, 81.0, 'fair', 'mid_cap'),
            ('BIOX', 'BioNext Therapeutics', 'Healthcare', 'Biotechnology', 89.0, 82.0, 79.0, 'fair', 'small_cap'),
            ('ROBT', 'Robotics Motion Systems', 'Industrials', 'Scientific Technical Instruments', 86.0, 78.0, 76.0, 'fair', 'mid_cap'),
            ('NETX', 'Network Edge Platforms', 'Communication Services', 'Internet Content & Information', 84.0, 80.0, 73.0, 'attractive', 'mid_cap'),
            ('SOLR', 'Solar Grid Dynamics', 'Industrials', 'Solar', 82.0, 76.0, 71.0, 'fair', 'small_cap'),
        ]
        seeds: list[StockSeed] = []
        prefix = country_code.upper()[:2]
        for index, template in enumerate(templates, start=1):
            suffix, company_name, sector, industry, theme_score, valuation_score, size_score, valuation_band, market_cap_bucket = template
            ticker = f'{prefix}{suffix}{index}'
            seeds.append(
                StockSeed(
                    market_code=market_code,
                    ticker=ticker,
                    company_name=f'{company_name} {market_code}',
                    sector=sector,
                    industry=industry,
                    exchange='MOCK',
                    currency='USD',
                    country_code=country_code,
                    seed_type='mock_bull_seed',
                    theme_tags=[_slugify(industry), _slugify(sector), 'mock_seed'],
                    theme_score=theme_score,
                    valuation_score=valuation_score,
                    size_score=size_score,
                    valuation_band=valuation_band,
                    market_cap_bucket=market_cap_bucket,
                )
            )
        return seeds

    def _build_heat_snapshots(self, trade_date: date, market_code: str, seeds: list[StockSeed]) -> list[ThemeHeatSnapshot]:
        grouped: dict[tuple[str, str], list[float]] = {}
        for seed in seeds:
            grouped.setdefault(('industry', seed.industry), []).append(seed.theme_score)
            grouped.setdefault(('sector', seed.sector), []).append(seed.theme_score)
        snapshots: list[ThemeHeatSnapshot] = []
        for (theme_type, theme_name), scores in grouped.items():
            raw_score = round(sum(scores) / len(scores), 4)
            snapshots.append(
                ThemeHeatSnapshot(
                    trade_date=trade_date,
                    market_code=market_code,
                    theme_type=theme_type,
                    theme_name=theme_name,
                    raw_heat_score=raw_score,
                    smoothed_heat_score=raw_score,
                    constituent_count=len(scores),
                    source='mock_heat',
                )
            )
        return sorted(snapshots, key=lambda item: (-item.raw_heat_score, item.theme_type, item.theme_name))


class YFinanceHotThemeListBuilder:
    def __init__(self, config) -> None:
        self._config = config.model_dump() if hasattr(config, 'model_dump') else dict(config)

    def build(
        self,
        *,
        trade_date: date,
        market_code: str,
        quotes: list[_ScreenedQuote],
    ) -> tuple[dict, list[ThemeHeatSnapshot]]:
        hot_theme_list = self._learn_hot_theme_list(quotes)
        snapshots = self._build_heat_snapshots(trade_date, market_code, hot_theme_list)
        return hot_theme_list, snapshots

    def _learn_hot_theme_list(self, quotes: list[_ScreenedQuote]) -> dict:
        industry_scores, industry_counts, industry_labels = self._group_heat_scores(quotes, label_attr='industry')
        sector_scores, sector_counts, sector_labels = self._group_heat_scores(quotes, label_attr='sector')
        hot_industries = {
            key
            for key, _ in sorted(industry_scores.items(), key=lambda item: (-item[1], item[0]))[: max(0, int(self._config.get('heat_top_industries', 5)))]
        }
        hot_sectors = {
            key
            for key, _ in sorted(sector_scores.items(), key=lambda item: (-item[1], item[0]))[: max(0, int(self._config.get('heat_top_sectors', 3)))]
        }
        return {
            'industry_scores': industry_scores,
            'sector_scores': sector_scores,
            'industry_counts': industry_counts,
            'sector_counts': sector_counts,
            'industry_labels': industry_labels,
            'sector_labels': sector_labels,
            'hot_industries': hot_industries,
            'hot_sectors': hot_sectors,
        }

    def _build_heat_snapshots(self, trade_date: date, market_code: str, hot_theme_list: dict) -> list[ThemeHeatSnapshot]:
        snapshots: list[ThemeHeatSnapshot] = []
        for theme_type, score_key, count_key, label_key in (
            ('industry', 'industry_scores', 'industry_counts', 'industry_labels'),
            ('sector', 'sector_scores', 'sector_counts', 'sector_labels'),
        ):
            for normalized_name, raw_score in hot_theme_list[score_key].items():
                snapshots.append(
                    ThemeHeatSnapshot(
                        trade_date=trade_date,
                        market_code=market_code,
                        theme_type=theme_type,
                        theme_name=hot_theme_list[label_key].get(normalized_name, normalized_name),
                        raw_heat_score=raw_score,
                        smoothed_heat_score=raw_score,
                        constituent_count=hot_theme_list[count_key].get(normalized_name, 0),
                        source='yfinance_heat',
                    )
                )
        return sorted(snapshots, key=lambda item: (-item.raw_heat_score, item.theme_type, item.theme_name))

    def _group_heat_scores(self, quotes: list[_ScreenedQuote], *, label_attr: str) -> tuple[dict[str, float], dict[str, int], dict[str, str]]:
        grouped: dict[str, list[_ScreenedQuote]] = {}
        labels: dict[str, str] = {}
        for quote in quotes:
            label = getattr(quote, label_attr)
            key = _normalize_label(label)
            if not key or key == 'unknown':
                continue
            grouped.setdefault(key, []).append(quote)
            labels.setdefault(key, label)
        scores, counts = self._build_group_scores(grouped, minimum=max(1, int(self._config.get('heat_min_constituents', 2))))
        if scores:
            return scores, counts, labels
        scores, counts = self._build_group_scores(grouped, minimum=1)
        return scores, counts, labels

    def _build_group_scores(self, grouped: dict[str, list[_ScreenedQuote]], *, minimum: int) -> tuple[dict[str, float], dict[str, int]]:
        scores: dict[str, float] = {}
        counts: dict[str, int] = {}
        for key, group in grouped.items():
            if len(group) < minimum:
                continue
            momentum_score = _bounded_linear_score(median([quote.momentum_pct for quote in group]), lower=0.0, upper=12.0)
            volume_score = _bounded_linear_score(median([quote.volume_ratio for quote in group]), lower=1.0, upper=2.5)
            breadth_score = min(1.0, len(group) / max(minimum, 1)) * 100.0
            scores[key] = round(momentum_score * 0.45 + volume_score * 0.35 + breadth_score * 0.20, 4)
            counts[key] = len(group)
        return scores, counts


class YFinanceBullSeedProvider:
    source_mode = 'yfinance_screen'

    def __init__(
        self,
        *,
        markets_config: MarketsConfig,
        discovery_config,
        local_industry_indices_config: LocalIndustryIndicesConfig | None = None,
        screener=None,
        ticker_factory=None,
        download=None,
    ) -> None:
        self._markets_config = markets_config
        self._config = discovery_config.model_dump() if hasattr(discovery_config, 'model_dump') else dict(discovery_config)
        self._screener = screener or _resolve_yfinance_screen()
        self._ticker_factory = ticker_factory or _resolve_yfinance_ticker_factory()
        self._download = download or _resolve_yfinance_download()
        self._local_industry_catalogs = {
            item.market_code: item for item in (local_industry_indices_config.markets if local_industry_indices_config is not None else [])
        }
        self._profile_cache: dict[str, dict] = {}
        self._stock_history_cache: dict[str, list[tuple[date, float, float]]] = {}
        self._local_index_history_cache: dict[str, list[tuple[date, float, float]]] = {}
        self._last_heat_snapshots: dict[tuple[date, str], list[ThemeHeatSnapshot]] = {}
        self._screened_quotes_cache: dict[tuple[date, str], list[_ScreenedQuote]] = {}
        self._market_universe_cache: dict[tuple[date, str], list[StockUniverseSnapshot]] = {}
        self._hot_theme_lists: dict[tuple[date, str], dict] = {}
        self._hot_theme_builder = YFinanceHotThemeListBuilder(self._config)

    def build_hot_theme_list(self, market_codes: list[str], trade_date: date) -> list[ThemeHeatSnapshot]:
        if not self._config.get('enabled', False):
            return []
        wanted = set(market_codes)
        snapshots: list[ThemeHeatSnapshot] = []
        for market in self._markets_config.markets:
            if market.market_code not in wanted:
                continue
            try:
                snapshots.extend(self._prepare_market_heat_context(trade_date, market.market_code))
            except Exception:
                self._hot_theme_lists[(trade_date, market.market_code)] = {}
                self._last_heat_snapshots[(trade_date, market.market_code)] = []
        return snapshots

    def sync_market_universe(self, market_codes: list[str], trade_date: date) -> list[StockUniverseSnapshot]:
        inventory_rows = self.sync_market_universe_inventory(market_codes, trade_date)
        if not inventory_rows:
            return []
        bars = self.sync_market_universe_bars(inventory_rows, trade_date=trade_date, latest_bar_dates={})
        bars_by_key: dict[tuple[str, str], list[StockDailyBar]] = {}
        for bar in bars:
            bars_by_key.setdefault((bar.market_code, bar.ticker), []).append(bar)
        enriched_rows: list[StockUniverseSnapshot] = []
        for row in inventory_rows:
            history = bars_by_key.get((row.market_code, row.ticker), [])
            if not history:
                enriched_rows.append(row)
                continue
            try:
                metrics = _selection_metrics_from_history([(item.trade_date, item.close, item.volume) for item in history])
            except Exception:
                enriched_rows.append(replace(row, price=history[-1].close))
                continue
            enriched_rows.append(
                replace(
                    row,
                    price=history[-1].close,
                    ret_5d=round(float(metrics['ret_5d']), 4),
                    ret_20d=round(float(metrics['ret_20d']), 4),
                    ret_60d=round(float(metrics['ret_60d']), 4),
                    ma_20=round(float(metrics['ma_20']), 4),
                    ma_60=round(float(metrics['ma_60']), 4),
                    avg_dollar_volume_3d=round(float(metrics['avg_dollar_volume_3d']), 2),
                    avg_dollar_volume_20d=round(float(metrics['avg_dollar_volume_20d']), 2),
                    volume_ratio_3d=round(float(metrics['volume_ratio_3d']), 4),
                    volume_up_days_5d=int(metrics['volume_up_days_5d']),
                    distance_to_60d_high=round(float(metrics['distance_to_60d_high']), 4),
                    momentum_acceleration=round(float(metrics['momentum_acceleration']), 4),
                    vol_20d=round(float(metrics['vol_20d']), 4),
                    source='yfinance_screen',
                )
            )
        for market_code in {row.market_code for row in enriched_rows}:
            self._market_universe_cache[(trade_date, market_code)] = [row for row in enriched_rows if row.market_code == market_code]
        return enriched_rows

    def sync_market_universe_inventory(self, market_codes: list[str], trade_date: date) -> list[StockUniverseSnapshot]:
        if not self._config.get('enabled', False):
            return []
        wanted = set(market_codes)
        rows: list[StockUniverseSnapshot] = []
        for market in self._markets_config.markets:
            if market.market_code not in wanted:
                continue
            try:
                rows.extend(self._sync_market_universe_for_market(trade_date, market.market_code, market.country_code))
            except Exception:
                self._screened_quotes_cache[(trade_date, market.market_code)] = []
                self._market_universe_cache[(trade_date, market.market_code)] = []
        return rows

    def sync_market_universe_bars(
        self,
        inventory_rows: list[StockUniverseSnapshot],
        *,
        trade_date: date,
        latest_bar_dates: dict[tuple[str, str], date | None],
    ) -> list[StockDailyBar]:
        if not inventory_rows:
            return []
        full_period = str(self._config.get('history_full_period', '30mo'))
        incremental_period = str(self._config.get('history_incremental_period', '3mo'))
        batch_size = max(1, int(self._config.get('history_batch_size', 50)))
        full_rows = [row for row in inventory_rows if latest_bar_dates.get((row.market_code, row.ticker)) is None]
        incremental_rows = [
            row for row in inventory_rows
            if latest_bar_dates.get((row.market_code, row.ticker)) is not None
            and latest_bar_dates.get((row.market_code, row.ticker)) < trade_date
        ]
        bars: list[StockDailyBar] = []
        bars.extend(self._download_stock_bar_batches(full_rows, full_period, latest_bar_dates, trade_date=trade_date))
        bars.extend(self._download_stock_bar_batches(incremental_rows, incremental_period, latest_bar_dates, trade_date=trade_date))
        return bars

    def resolve_seeds(self, market_codes: list[str], trade_date: date) -> list[StockSeed]:
        if not self._config.get('enabled', False):
            return []
        wanted = set(market_codes)
        discovered: list[StockSeed] = []
        for market in self._markets_config.markets:
            if market.market_code not in wanted:
                continue
            try:
                discovered.extend(self._discover_market_seeds(trade_date, market.market_code, market.country_code))
            except Exception:
                continue
        return discovered

    def list_heat_snapshots(self, trade_date: date, market_codes: list[str]) -> list[ThemeHeatSnapshot]:
        snapshots: list[ThemeHeatSnapshot] = []
        for market_code in market_codes:
            snapshots.extend(self._last_heat_snapshots.get((trade_date, market_code), []))
        return snapshots

    def list_market_universe(self, trade_date: date, market_codes: list[str]) -> list[StockUniverseSnapshot]:
        rows: list[StockUniverseSnapshot] = []
        for market_code in market_codes:
            rows.extend(self._market_universe_cache.get((trade_date, market_code), []))
        return rows

    def enrich_market_universe_rows(self, rows: list[StockUniverseSnapshot]) -> list[StockUniverseSnapshot]:
        enriched_rows: list[StockUniverseSnapshot] = []
        for row in rows:
            if row.sector != 'Unknown' and row.industry != 'Unknown':
                enriched_rows.append(row)
                continue
            try:
                profile = self._load_profile(row.ticker)
            except Exception:
                enriched_rows.append(row)
                continue
            sector = str(profile.get('sector') or '').strip() or row.sector
            industry = str(profile.get('industry') or '').strip() or row.industry
            if sector == row.sector and industry == row.industry:
                enriched_rows.append(row)
                continue
            screened_quote = self._universe_snapshot_to_screened_quote(
                replace(row, sector=sector or 'Unknown', industry=industry or sector or 'Unknown')
            )
            enriched_rows.append(
                replace(
                    row,
                    sector=screened_quote.sector,
                    industry=screened_quote.industry,
                    theme_tags=self._theme_tags_for_quote(screened_quote),
                )
            )
        return enriched_rows

    def resolve_seeds_from_universe(self, rows: list[StockUniverseSnapshot], trade_date: date) -> list[StockSeed]:
        grouped: dict[str, list[_ScreenedQuote]] = {}
        for row in rows:
            grouped.setdefault(row.market_code, []).append(self._universe_snapshot_to_screened_quote(row))
        discovered: list[StockSeed] = []
        for market_code, quotes in grouped.items():
            hot_theme_list = self._hot_theme_lists.get((trade_date, market_code), {})
            if not hot_theme_list:
                continue
            discovered.extend(self._select_seed_quotes(quotes, hot_theme_list))
        return discovered

    def _prepare_market_heat_context(self, trade_date: date, market_code: str) -> list[ThemeHeatSnapshot]:
        local_hot_theme_list = self._empty_hot_theme_list()
        local_snapshots: list[ThemeHeatSnapshot] = []
        global_hot_theme_list, global_snapshots = self._build_fixed_hot_theme_list(trade_date, market_code)
        official_local_hot_theme_list, official_local_snapshots = self._build_official_local_industry_snapshots(trade_date, market_code)
        hot_theme_list = self._merge_hot_theme_lists(local_hot_theme_list, global_hot_theme_list, official_local_hot_theme_list)
        snapshots = sorted([*local_snapshots, *official_local_snapshots, *global_snapshots], key=lambda item: (-item.raw_heat_score, item.theme_type, item.theme_name))
        self._hot_theme_lists[(trade_date, market_code)] = hot_theme_list
        self._last_heat_snapshots[(trade_date, market_code)] = snapshots
        return snapshots

    def _sync_market_universe_for_market(self, trade_date: date, market_code: str, country_code: str) -> list[StockUniverseSnapshot]:
        screened_quotes = self._screen_market_quotes(
            market_code,
            country_code,
            enrich_missing_profile=False,
            page_size_override=int(self._config.get('universe_page_size', 100)),
            page_limit_override=int(self._config.get('max_universe_pages_per_market', 20)),
        )
        self._screened_quotes_cache[(trade_date, market_code)] = screened_quotes
        rows = [self._screened_quote_to_universe_snapshot(trade_date, quote, include_metrics=False) for quote in screened_quotes]
        self._market_universe_cache[(trade_date, market_code)] = rows
        return rows

    def _discover_market_seeds(self, trade_date: date, market_code: str, country_code: str) -> list[StockSeed]:
        cache_key = (trade_date, market_code)
        if cache_key not in self._hot_theme_lists:
            self._prepare_market_heat_context(trade_date, market_code)
        hot_theme_list = self._hot_theme_lists.get(cache_key, {})
        if not hot_theme_list:
            return []
        screened_quotes = self._screened_quotes_cache.get(cache_key)
        selected_limit = None
        if self._fixed_hot_theme_names():
            selected_limit = max(1, int(self._config.get('max_selected_per_market', 10)))
        needs_enriched_rescan = screened_quotes is None or any(
            quote.sector == 'Unknown' or quote.industry == 'Unknown'
            for quote in screened_quotes
        )
        candidate_quotes = screened_quotes
        if candidate_quotes is None:
            self._sync_market_universe_for_market(trade_date, market_code, country_code)
            candidate_quotes = self._screened_quotes_cache.get(cache_key, [])
        if needs_enriched_rescan:
            candidate_quotes = self._screen_market_quotes(
                market_code,
                country_code,
                hot_theme_list=hot_theme_list,
                selected_limit=selected_limit,
                enrich_missing_profile=True,
            )
            if screened_quotes is None:
                self._screened_quotes_cache[cache_key] = candidate_quotes
        if not candidate_quotes:
            return []
        return self._select_seed_quotes(candidate_quotes, hot_theme_list)

    def _select_seed_quotes(self, quotes: list[_ScreenedQuote], hot_theme_list: dict) -> list[StockSeed]:
        selected_quotes = [
            quote
            for quote in quotes
            if self._matches_seed_filters(quote, hot_theme_list)
        ]
        selected_quotes.sort(
            key=lambda quote: (
                -self._theme_score_for_quote(quote, hot_theme_list),
                quote.price_position if quote.price_position is not None else 1.0,
                -quote.volume_ratio,
                -quote.momentum_pct,
                quote.symbol,
            )
        )
        return [self._screened_quote_to_seed(quote, hot_theme_list) for quote in selected_quotes]

    def _screen_market_quotes(
        self,
        market_code: str,
        country_code: str,
        *,
        hot_theme_list: dict | None = None,
        selected_limit: int | None = None,
        enrich_missing_profile: bool = True,
        page_size_override: int | None = None,
        page_limit_override: int | None = None,
    ) -> list[_ScreenedQuote]:
        page_size = max(1, int(page_size_override or self._config.get('max_candidates_per_market', 25)))
        page_limit = max(1, int(page_limit_override or self._config.get('max_scan_pages_per_market', 8)))
        page_count = 0
        offset = 0
        seen_symbols: set[str] = set()
        screened_quotes: list[_ScreenedQuote] = []
        matched_count = 0
        while True:
            payload = self._screener(
                self._build_query(country_code.lower()),
                size=page_size,
                offset=offset,
                sortField='dayvolume',
                sortAsc=False,
            )
            quotes = payload.get('quotes') or []
            if not quotes:
                break
            for quote in quotes:
                screened = self._screen_quote(
                    market_code,
                    country_code,
                    quote,
                    enrich_missing_profile=enrich_missing_profile,
                )
                if screened is None or screened.symbol in seen_symbols:
                    continue
                seen_symbols.add(screened.symbol)
                screened_quotes.append(screened)
                if hot_theme_list and self._matches_seed_filters(screened, hot_theme_list):
                    matched_count += 1
            page_count += 1
            if selected_limit is not None and matched_count >= selected_limit:
                break
            if len(quotes) < page_size:
                break
            if page_count >= page_limit:
                break
            offset += page_size
        return screened_quotes

    def _build_query(self, region: str):
        equity_query = _resolve_yfinance_equity_query()
        return equity_query('eq', ['region', region])

    def _screen_quote(
        self,
        market_code: str,
        country_code: str,
        quote: dict,
        *,
        enrich_missing_profile: bool = True,
    ) -> _ScreenedQuote | None:
        symbol = str(quote.get('symbol') or '').strip()
        if not symbol:
            return None
        market_cap = _coerce_number(quote.get('marketCap') or quote.get('intradaymarketcap'))
        price = _coerce_number(quote.get('regularMarketPrice') or quote.get('intradayprice') or quote.get('eodprice'))
        low = _coerce_number(quote.get('fiftyTwoWeekLow') or quote.get('lastclose52weeklow.lasttwelvemonths'))
        high = _coerce_number(quote.get('fiftyTwoWeekHigh') or quote.get('lastclose52weekhigh.lasttwelvemonths'))
        sector = str(quote.get('sector') or '').strip()
        industry = str(quote.get('industry') or '').strip()
        company_name = str(quote.get('longName') or quote.get('shortName') or symbol)
        exchange = str(quote.get('exchange') or '')
        currency = str(quote.get('currency') or '')
        if enrich_missing_profile and (not sector or not industry):
            profile = self._load_profile(symbol)
            sector = sector or str(profile.get('sector') or '').strip()
            industry = industry or str(profile.get('industry') or '').strip()
            company_name = str(quote.get('longName') or quote.get('shortName') or profile.get('longName') or profile.get('shortName') or symbol)
            exchange = exchange or str(profile.get('exchange') or '')
            currency = currency or str(profile.get('currency') or '')
        return _ScreenedQuote(
            market_code=market_code,
            country_code=country_code,
            symbol=symbol,
            company_name=company_name,
            sector=sector or 'Unknown',
            industry=industry or sector or 'Unknown',
            exchange=exchange,
            currency=currency,
            market_cap=market_cap,
            price=price,
            price_position=_price_position_ratio(price=price, low=low, high=high),
            momentum_pct=self._momentum_pct(quote),
            volume_ratio=self._screen_volume_ratio(quote),
        )

    def _screened_quote_to_universe_snapshot(self, trade_date: date, quote: _ScreenedQuote, *, include_metrics: bool = True) -> StockUniverseSnapshot:
        try:
            metrics = self._stock_history_metrics(quote.symbol) if include_metrics else {}
        except Exception:
            metrics = {}
        return StockUniverseSnapshot(
            trade_date=trade_date,
            market_code=quote.market_code,
            ticker=quote.symbol,
            company_name=quote.company_name,
            sector=quote.sector,
            industry=quote.industry,
            exchange=quote.exchange,
            currency=quote.currency,
            country_code=quote.country_code,
            market_cap=quote.market_cap,
            price=quote.price,
            price_position=quote.price_position,
            momentum_pct=quote.momentum_pct,
            volume_ratio=quote.volume_ratio,
            ret_5d=metrics.get('ret_5d'),
            ret_20d=metrics.get('ret_20d'),
            ret_60d=metrics.get('ret_60d'),
            ma_20=metrics.get('ma_20'),
            ma_60=metrics.get('ma_60'),
            avg_dollar_volume_3d=metrics.get('avg_dollar_volume_3d'),
            avg_dollar_volume_20d=metrics.get('avg_dollar_volume_20d'),
            volume_ratio_3d=metrics.get('volume_ratio_3d'),
            volume_up_days_5d=metrics.get('volume_up_days_5d'),
            distance_to_60d_high=metrics.get('distance_to_60d_high'),
            momentum_acceleration=metrics.get('momentum_acceleration'),
            vol_20d=metrics.get('vol_20d'),
            theme_tags=self._theme_tags_for_quote(quote),
            source='yfinance_screen',
        )

    def _stock_history_metrics(self, symbol: str) -> dict[str, float | int | None]:
        rows = self._fetch_stock_history(symbol)
        return _selection_metrics_from_history(rows)

    def _fetch_stock_history(self, symbol: str) -> list[tuple[date, float, float]]:
        if symbol in self._stock_history_cache:
            return self._stock_history_cache[symbol]
        history_frame = self._download(
            symbol,
            period=str(self._config.get('history_full_period', '30mo')),
            interval='1d',
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        rows = _history_rows_from_frame(_extract_symbol_history_frame(history_frame, symbol, 1))
        self._stock_history_cache[symbol] = rows
        return rows

    def _download_stock_bar_batches(
        self,
        rows: list[StockUniverseSnapshot],
        period: str,
        latest_bar_dates: dict[tuple[str, str], date | None],
        *,
        trade_date: date,
    ) -> list[StockDailyBar]:
        if not rows:
            return []
        batch_size = max(1, int(self._config.get('history_batch_size', 50)))
        bars: list[StockDailyBar] = []
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            symbols = [row.ticker for row in batch]
            history_frame = self._download(
                ' '.join(symbols),
                period=period,
                interval='1d',
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if history_frame is None or getattr(history_frame, 'empty', False):
                continue
            for row in batch:
                symbol_frame = _extract_symbol_history_frame(history_frame, row.ticker, len(symbols))
                history_rows = _history_rows_from_frame(symbol_frame)
                if not history_rows:
                    continue
                latest_date = latest_bar_dates.get((row.market_code, row.ticker))
                filtered_rows = [item for item in history_rows if latest_date is None or item[0] > latest_date]
                if not filtered_rows:
                    continue
                combined_rows = list(self._stock_history_cache.get(row.ticker, []))
                combined_rows.extend(filtered_rows)
                deduped = {trade_day: (trade_day, close, volume) for trade_day, close, volume in combined_rows}
                merged = [deduped[key] for key in sorted(deduped)]
                self._stock_history_cache[row.ticker] = merged
                bars.extend([
                    StockDailyBar(
                        market_code=row.market_code,
                        ticker=row.ticker,
                        trade_date=trade_day,
                        close=close,
                        volume=volume,
                        source='yfinance_history_batch',
                    )
                    for trade_day, close, volume in filtered_rows
                    if trade_day <= trade_date
                ])
        return bars

    def _universe_snapshot_to_screened_quote(self, row: StockUniverseSnapshot) -> _ScreenedQuote:
        return _ScreenedQuote(
            market_code=row.market_code,
            country_code=row.country_code,
            symbol=row.ticker,
            company_name=row.company_name,
            sector=row.sector,
            industry=row.industry,
            exchange=row.exchange,
            currency=row.currency,
            market_cap=row.market_cap,
            price=row.price,
            price_position=row.price_position,
            momentum_pct=row.momentum_pct,
            volume_ratio=row.volume_ratio,
        )

    def _screened_quote_to_seed(self, quote: _ScreenedQuote, hot_theme_list: dict) -> StockSeed:
        theme_score = self._theme_score_for_quote(quote, hot_theme_list)
        price_position = quote.price_position if quote.price_position is not None else 1.0
        return StockSeed(
            market_code=quote.market_code,
            ticker=quote.symbol,
            company_name=quote.company_name,
            sector=quote.sector,
            industry=quote.industry,
            exchange=quote.exchange,
            currency=quote.currency,
            country_code=quote.country_code,
            seed_type='bull_heat_screen',
            theme_tags=self._theme_tags_for_quote(quote),
            theme_score=round(max(60.0, min(99.0, theme_score)), 4),
            valuation_score=self._valuation_score(price_position),
            size_score=self._size_score(quote.market_cap),
            valuation_band=self._valuation_band(price_position),
            market_cap_bucket=self._market_cap_bucket(quote.market_cap),
        )

    def _theme_tags_for_quote(self, quote: _ScreenedQuote) -> list[str]:
        tags: list[str] = []
        for theme_name in self._global_theme_tags_for_quote(quote):
            tag = _slugify(theme_name)
            if tag and tag not in tags:
                tags.append(tag)
        for raw_tag in (_slugify(quote.industry), _slugify(quote.sector), 'auto_heat'):
            if raw_tag and raw_tag not in tags:
                tags.append(raw_tag)
        return tags

    def _matches_hot_theme(self, quote: _ScreenedQuote, hot_theme_list: dict) -> bool:
        industry_key = _normalize_label(quote.industry)
        sector_key = _normalize_label(quote.sector)
        if industry_key in hot_theme_list.get('hot_industries', set()) or sector_key in hot_theme_list.get('hot_sectors', set()):
            return True
        if self._matching_official_local_industries(quote, hot_theme_list):
            return True
        return bool(self._global_theme_tags_for_quote(quote))

    def _fixed_hot_theme_names(self) -> list[str]:
        return [str(name).strip() for name in self._config.get('fixed_hot_theme_names', []) if str(name).strip()]

    def _fixed_remote_query_industries(self) -> list[str]:
        industries: list[str] = []
        seen: set[str] = set()
        for theme_name in self._fixed_hot_theme_names():
            aliases = _FIXED_THEME_REMOTE_QUERY_MAP.get(theme_name.strip().lower(), {})
            for industry_name in aliases.get('industry', []):
                if industry_name in seen:
                    continue
                seen.add(industry_name)
                industries.append(industry_name)
        return industries

    def _empty_hot_theme_list(self) -> dict:
        return {
            'industry_scores': {},
            'sector_scores': {},
            'industry_counts': {},
            'sector_counts': {},
            'industry_labels': {},
            'sector_labels': {},
            'hot_industries': set(),
            'hot_sectors': set(),
            'global_theme_scores': {},
            'global_theme_matches': {},
            'official_local_scores': {},
            'official_local_rules': {},
        }

    def _merge_hot_theme_lists(self, local_hot_theme_list: dict, global_hot_theme_list: dict, official_local_hot_theme_list: dict | None = None) -> dict:
        merged = self._empty_hot_theme_list()
        official_local_hot_theme_list = official_local_hot_theme_list or self._empty_hot_theme_list()
        for key in ('industry_scores', 'sector_scores', 'industry_counts', 'sector_counts', 'industry_labels', 'sector_labels', 'global_theme_scores', 'global_theme_matches', 'official_local_scores', 'official_local_rules'):
            merged[key] = {**local_hot_theme_list.get(key, {}), **global_hot_theme_list.get(key, {}), **official_local_hot_theme_list.get(key, {})}
        merged['hot_industries'] = set(local_hot_theme_list.get('hot_industries', set())) | set(global_hot_theme_list.get('hot_industries', set())) | set(official_local_hot_theme_list.get('hot_industries', set()))
        merged['hot_sectors'] = set(local_hot_theme_list.get('hot_sectors', set())) | set(global_hot_theme_list.get('hot_sectors', set())) | set(official_local_hot_theme_list.get('hot_sectors', set()))
        return merged

    def _build_official_local_industry_snapshots(self, trade_date: date, market_code: str) -> tuple[dict, list[ThemeHeatSnapshot]]:
        catalog = self._local_industry_catalogs.get(market_code)
        if catalog is None:
            return self._empty_hot_theme_list(), []
        snapshots: list[ThemeHeatSnapshot] = []
        hot_theme_list = self._empty_hot_theme_list()
        families = sorted(
            catalog.families,
            key=lambda item: (0 if item.family_code == catalog.recommended_primary_family else 1, item.family_code),
        )
        for family in families:
            for index in family.indices:
                if not index.proxy_symbol:
                    continue
                rows = self._fetch_local_index_history(index.proxy_symbol)
                if len(rows) < 21:
                    continue
                heat_score = self._heat_score_for_index_history(rows)
                hot_theme_list['official_local_scores'][index.local_code] = heat_score
                hot_theme_list['official_local_rules'][index.local_code] = {
                    'name': index.name,
                    'match_industries': {_normalize_label(value) for value in index.match_industries if _normalize_label(value)},
                    'match_sectors': {_normalize_label(value) for value in index.match_sectors if _normalize_label(value)},
                }
                snapshots.append(
                    ThemeHeatSnapshot(
                        trade_date=trade_date,
                        market_code=market_code,
                        theme_type='official_local_industry',
                        theme_name=index.name,
                        raw_heat_score=heat_score,
                        smoothed_heat_score=heat_score,
                        constituent_count=1,
                        source='yfinance_official_local_index_proxy',
                    )
                )
        return hot_theme_list, snapshots

    def _fetch_local_index_history(self, symbol: str) -> list[tuple[date, float, float]]:
        if symbol in self._local_index_history_cache:
            return self._local_index_history_cache[symbol]
        history_frame = self._download(
            symbol,
            period='12mo',
            interval='1d',
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        rows = _history_rows_from_frame(_extract_symbol_history_frame(history_frame, symbol, 1))
        self._local_index_history_cache[symbol] = rows
        return rows

    def _heat_score_for_index_history(self, rows: list[tuple[date, float, float]]) -> float:
        closes = [close for _, close, _ in rows]
        recent_volumes = [volume for _, _, volume in rows[-5:] if volume > 0]
        baseline_volumes = [volume for _, _, volume in rows[-20:] if volume > 0]
        ret_20d = _period_return(closes, 20)
        momentum_score = _bounded_linear_score(ret_20d, lower=-0.05, upper=0.20)
        if recent_volumes and baseline_volumes:
            volume_ratio = (fmean(recent_volumes) / fmean(baseline_volumes)) if fmean(baseline_volumes) > 0 else 1.0
        else:
            volume_ratio = 1.0
        volume_score = _bounded_linear_score(volume_ratio, lower=0.9, upper=1.8)
        return round(momentum_score * 0.65 + volume_score * 0.35, 4)

    def _build_fixed_hot_theme_list(self, trade_date: date, market_code: str) -> tuple[dict, list[ThemeHeatSnapshot]]:
        hot_theme_list = self._empty_hot_theme_list()
        snapshots: list[ThemeHeatSnapshot] = []
        for theme_name in self._fixed_hot_theme_names():
            proxy_symbol = _FIXED_THEME_PROXY_SYMBOL_MAP.get(theme_name.strip().lower())
            if not proxy_symbol:
                continue
            rows = self._fetch_local_index_history(proxy_symbol)
            if len(rows) < 21:
                continue
            score = self._heat_score_for_index_history(rows)
            hot_theme_list['global_theme_scores'][theme_name] = score
            snapshots.append(
                ThemeHeatSnapshot(
                    trade_date=trade_date,
                    market_code=market_code,
                    theme_type='global_theme',
                    theme_name=theme_name,
                    raw_heat_score=score,
                    smoothed_heat_score=score,
                    constituent_count=1,
                    source='yfinance_global_theme',
                )
            )
        return hot_theme_list, snapshots

    def _matching_official_local_industries(self, quote: _ScreenedQuote, hot_theme_list: dict) -> list[str]:
        industry_key = _normalize_label(quote.industry)
        sector_key = _normalize_label(quote.sector)
        matched: list[str] = []
        for local_code, rules in hot_theme_list.get('official_local_rules', {}).items():
            industry_rules = rules.get('match_industries', set())
            sector_rules = rules.get('match_sectors', set())
            if industry_key in industry_rules or sector_key in sector_rules:
                matched.append(local_code)
        return matched

    def _global_theme_tags_for_quote(self, quote: _ScreenedQuote) -> list[str]:
        industry_key = _normalize_label(quote.industry)
        sector_key = _normalize_label(quote.sector)
        matched: list[str] = []
        for theme_name in self._fixed_hot_theme_names():
            industry_aliases, sector_aliases = _resolve_fixed_theme_aliases(theme_name)
            if industry_key in industry_aliases or sector_key in sector_aliases:
                matched.append(theme_name)
        return matched

    def _theme_score_for_quote(self, quote: _ScreenedQuote, hot_theme_list: dict) -> float:
        industry_key = _normalize_label(quote.industry)
        sector_key = _normalize_label(quote.sector)
        local_score = max(
            hot_theme_list['industry_scores'].get(industry_key, 0.0),
            hot_theme_list['sector_scores'].get(sector_key, 0.0),
        )
        global_score = max(
            [hot_theme_list.get('global_theme_scores', {}).get(theme_name, 0.0) for theme_name in self._global_theme_tags_for_quote(quote)] or [0.0]
        )
        official_local_score = max(
            [hot_theme_list.get('official_local_scores', {}).get(local_code, 0.0) for local_code in self._matching_official_local_industries(quote, hot_theme_list)] or [0.0]
        )
        return max(local_score, global_score, official_local_score)

    def _matches_seed_filters(self, quote: _ScreenedQuote, hot_theme_list: dict) -> bool:
        return self._within_market_cap(quote.market_cap) and self._matches_hot_theme(quote, hot_theme_list)

    def _is_low_position(self, price_position: float | None) -> bool:
        return price_position is not None and price_position <= float(self._config.get('max_price_position_ratio', 0.35))

    def _momentum_pct(self, quote: dict) -> float:
        return _coerce_percent(
            _first_number(
                quote.get('regularMarketChangePercent'),
                quote.get('fiftyDayAverageChangePercent'),
                quote.get('twoHundredDayAverageChangePercent'),
            )
        )

    def _screen_volume_ratio(self, quote: dict) -> float:
        current_volume = _coerce_number(quote.get('regularMarketVolume') or quote.get('dayvolume'))
        baseline_volume = _coerce_number(
            quote.get('averageDailyVolume3Month')
            or quote.get('averageDailyVolume10Day')
            or quote.get('averageVolume')
        )
        if current_volume <= 0 or baseline_volume <= 0:
            return 1.0
        return round(current_volume / baseline_volume, 4)

    def _heat_score_for_quotes(self, quotes: list[_ScreenedQuote]) -> float:
        if not quotes:
            return 0.0
        momentum_score = _bounded_linear_score(median([quote.momentum_pct for quote in quotes]), lower=0.0, upper=12.0)
        volume_score = _bounded_linear_score(median([quote.volume_ratio for quote in quotes]), lower=1.0, upper=2.5)
        breadth_score = min(1.0, len(quotes) / max(1, int(self._config.get('heat_min_constituents', 2)))) * 100.0
        return round(momentum_score * 0.45 + volume_score * 0.35 + breadth_score * 0.20, 4)

    def _load_profile(self, symbol: str) -> dict:
        if symbol in self._profile_cache:
            return self._profile_cache[symbol]
        ticker = self._ticker_factory(symbol)
        info = getattr(ticker, 'info', None)
        if callable(info):
            info = info()
        if info is None and hasattr(ticker, 'get_info'):
            info = ticker.get_info()
        profile = info if isinstance(info, dict) else {}
        self._profile_cache[symbol] = profile
        return profile

    def _valuation_score(self, price_position: float) -> float:
        threshold = max(float(self._config.get('max_price_position_ratio', 0.35)), 0.01)
        return round(60.0 + 40.0 * max(0.0, 1.0 - (price_position / threshold)), 4)

    def _size_score(self, market_cap: float) -> float:
        minimum = float(self._config.get('min_market_cap', 3_000_000_000))
        maximum = float(self._config.get('max_market_cap', 10_000_000_000))
        if maximum <= minimum:
            return 80.0
        normalized = max(0.0, min(1.0, (market_cap - minimum) / (maximum - minimum)))
        return round(90.0 - 30.0 * normalized, 4)

    def _valuation_band(self, price_position: float) -> str:
        if price_position <= 0.15:
            return 'attractive'
        if price_position <= float(self._config.get('max_price_position_ratio', 0.35)):
            return 'fair'
        return 'expensive'

    def _market_cap_bucket(self, market_cap: float) -> str:
        if market_cap < 5_000_000_000:
            return 'small_cap'
        return 'mid_cap'

    def _within_market_cap(self, market_cap: float) -> bool:
        return float(self._config.get('min_market_cap', 3_000_000_000)) <= market_cap <= float(self._config.get('max_market_cap', 10_000_000_000))


class MockSelectionDataProvider:
    source_mode = "mock"

    def fetch_daily(self, seeds: list[StockSeed], trade_date: date) -> list[StockScreenObservation]:
        return [self._build_observation(seed, trade_date) for seed in seeds]

    @staticmethod
    def _build_observation(seed: StockSeed, trade_date: date) -> StockScreenObservation:
        base_seed = sum(ord(char) for char in f"{seed.market_code}:{seed.ticker}") + trade_date.toordinal()
        rng = random.Random(base_seed)
        quality_bias = rng.uniform(0.25, 0.95)
        close = round(20 + quality_bias * 180, 4)
        ma_20 = round(close * rng.uniform(0.96, 1.01), 4)
        ma_60 = round(close * rng.uniform(0.93, 1.02), 4)
        ma_120 = round(close * rng.uniform(0.88, 1.04), 4)
        ma_200 = round(close * rng.uniform(0.84, 1.08), 4)
        ret_5d = round(rng.uniform(0.01, 0.06), 4)
        ret_20d = round(rng.uniform(0.03, 0.12), 4)
        ret_60d = round(rng.uniform(-0.08, 0.28), 4)
        avg_dollar_volume_20d = round(5_000_000 + quality_bias * 180_000_000, 2)
        volume_ratio_3d = round(rng.uniform(1.0, 1.6), 4)
        volume_ratio_5d = round(max(volume_ratio_3d - 0.05, 0.9), 4)
        avg_dollar_volume_3d = round(avg_dollar_volume_20d * volume_ratio_3d, 2)
        avg_dollar_volume_5d = round(avg_dollar_volume_20d * volume_ratio_5d, 2)
        volume_up_days_5d = rng.randint(2, 4)
        distance_to_60d_high = round(rng.uniform(0.04, 0.16), 4)
        momentum_acceleration = round(ret_5d - (ret_20d / 4), 4)
        vol_20d = round(rng.uniform(0.16, 0.62), 4)
        return StockScreenObservation(
            market_code=seed.market_code,
            ticker=seed.ticker,
            trade_date=trade_date,
            close=close,
            ma_20=ma_20,
            ma_60=ma_60,
            ma_120=ma_120,
            ma_200=ma_200,
            ret_5d=ret_5d,
            ret_20d=ret_20d,
            ret_60d=ret_60d,
            avg_dollar_volume_3d=avg_dollar_volume_3d,
            avg_dollar_volume_5d=avg_dollar_volume_5d,
            avg_dollar_volume_20d=avg_dollar_volume_20d,
            volume_ratio_3d=volume_ratio_3d,
            volume_ratio_5d=volume_ratio_5d,
            volume_up_days_5d=volume_up_days_5d,
            distance_to_60d_high=distance_to_60d_high,
            momentum_acceleration=momentum_acceleration,
            vol_20d=vol_20d,
            source="mock",
        )


class YahooSelectionDataProvider:
    source_mode = "yahoo"

    def __init__(
        self,
        *,
        data_sources_config: DataSourcesConfig,
        chart_base_url: str,
        allow_mock_fallback: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        timeout = httpx.Timeout(
            connect=data_sources_config.timeouts.connect_seconds,
            read=data_sources_config.timeouts.read_seconds,
            write=data_sources_config.timeouts.read_seconds,
            pool=data_sources_config.timeouts.connect_seconds,
        )
        self._client = client or httpx.Client(timeout=timeout)
        self._chart_base_url = chart_base_url.rstrip("/")
        self._allow_mock_fallback = allow_mock_fallback
        self._mock_provider = MockSelectionDataProvider()
        self._history_cache: dict[tuple[str, date], list[tuple[date, float, float]]] = {}
        self._max_attempts = max(1, data_sources_config.retry.max_attempts)
        self._backoff_seconds = max(0, data_sources_config.retry.backoff_seconds)

    def fetch_daily(self, seeds: list[StockSeed], trade_date: date) -> list[StockScreenObservation]:
        observations: list[StockScreenObservation] = []
        for seed in seeds:
            try:
                history = self._fetch_history(seed.ticker, trade_date)
                observations.append(self._history_to_observation(seed, trade_date, history))
            except Exception:  # noqa: BLE001
                if self._allow_mock_fallback:
                    observations.append(self._mock_provider._build_observation(seed, trade_date))
        return observations

    def _history_to_observation(
        self,
        seed: StockSeed,
        trade_date: date,
        history: list[tuple[date, float, float]],
    ) -> StockScreenObservation:
        filtered = [(trade_day, close, volume) for trade_day, close, volume in history if trade_day <= trade_date]
        return _selection_observation_from_history(seed=seed, trade_date=trade_date, history=filtered, source='yahoo')

    def _fetch_history(self, symbol: str, trade_date: date) -> list[tuple[date, float, float]]:
        cache_key = (symbol, trade_date)
        if cache_key in self._history_cache:
            return self._history_cache[cache_key]
        start_date = trade_date - timedelta(days=600)
        period1 = int(datetime.combine(start_date, time.min, tzinfo=timezone.utc).timestamp())
        period2 = int(datetime.combine(trade_date + timedelta(days=1), time.min, tzinfo=timezone.utc).timestamp())
        payload = self._request_chart_payload(
            url=f"{self._chart_base_url}/v8/finance/chart/{quote(symbol, safe='')}",
            params={
                "interval": "1d",
                "period1": period1,
                "period2": period2,
                "includePrePost": "false",
                "events": "div,splits",
            },
        )
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            error = (payload.get("chart") or {}).get("error") or {}
            raise RuntimeError(error.get("description") or f"No chart result returned for {symbol}")
        chart = result[0]
        timestamps = chart.get("timestamp") or []
        quote_rows = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quote_rows.get("close") or []
        adjusted = ((chart.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
        volumes = quote_rows.get("volume") or []
        history: list[tuple[date, float, float]] = []
        for index, timestamp in enumerate(timestamps):
            raw_close = adjusted[index] if index < len(adjusted) and adjusted[index] is not None else closes[index]
            raw_volume = volumes[index] if index < len(volumes) and volumes[index] is not None else 0
            if raw_close is None:
                continue
            trade_day = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
            history.append((trade_day, float(raw_close), float(raw_volume)))
        if not history:
            raise RuntimeError(f"No daily data returned for {symbol}")
        self._history_cache[cache_key] = history
        return history

    def _request_chart_payload(self, *, url: str, params: dict[str, str | int]) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == self._max_attempts:
                    break
                if self._backoff_seconds > 0:
                    time_module.sleep(self._backoff_seconds * attempt)
        assert last_error is not None
        raise last_error


class YFinanceSelectionDataProvider:
    source_mode = "yfinance"

    def __init__(
        self,
        *,
        data_sources_config: DataSourcesConfig,
        allow_mock_fallback: bool = False,
        ticker_factory=None,
        download=None,
    ) -> None:
        self._data_sources_config = data_sources_config
        self._allow_mock_fallback = allow_mock_fallback
        self._mock_provider = MockSelectionDataProvider()
        self._history_cache: dict[str, list[tuple[date, float, float]]] = {}
        self._ticker_factory = ticker_factory or _resolve_yfinance_ticker_factory()
        self._download = download or _resolve_yfinance_download()

    def fetch_daily(self, seeds: list[StockSeed], trade_date: date) -> list[StockScreenObservation]:
        observations: list[StockScreenObservation] = []
        self._prefetch_histories([seed.ticker for seed in seeds])
        for seed in seeds:
            try:
                history = self._fetch_history(seed.ticker)
                observations.append(self._history_to_observation(seed, trade_date, history))
            except Exception:  # noqa: BLE001
                if self._allow_mock_fallback:
                    observations.append(self._mock_provider._build_observation(seed, trade_date))
        return observations

    def _history_to_observation(
        self,
        seed: StockSeed,
        trade_date: date,
        history: list[tuple[date, float, float]],
    ) -> StockScreenObservation:
        filtered = [(trade_day, close, volume) for trade_day, close, volume in history if trade_day <= trade_date]
        return _selection_observation_from_history(seed=seed, trade_date=trade_date, history=filtered, source='yfinance')

    def _fetch_history(self, symbol: str) -> list[tuple[date, float, float]]:
        if symbol in self._history_cache:
            return self._history_cache[symbol]
        ticker = self._ticker_factory(symbol)
        history = ticker.history(period='30mo', interval='1d', auto_adjust=True)
        rows = _history_rows_from_frame(history)
        if not rows:
            raise RuntimeError(f"No daily data returned for {symbol}")
        self._history_cache[symbol] = rows
        return rows

    def _prefetch_histories(self, symbols: list[str]) -> None:
        missing_symbols = [symbol for symbol in dict.fromkeys(symbols) if symbol not in self._history_cache]
        if not missing_symbols:
            return
        history_frame = self._download(
            ' '.join(missing_symbols),
            period='30mo',
            interval='1d',
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        if history_frame is None or getattr(history_frame, 'empty', False):
            return
        for symbol in missing_symbols:
            symbol_frame = _extract_symbol_history_frame(history_frame, symbol, len(missing_symbols))
            rows = _history_rows_from_frame(symbol_frame)
            if rows:
                self._history_cache[symbol] = rows


class CompositeSelectionDataProvider:
    def __init__(self, providers: list) -> None:
        self._providers = providers

    @property
    def source_mode(self) -> str:
        names = [provider.source_mode for provider in self._providers]
        return f"composite[{','.join(names)}]"

    def fetch_daily(self, seeds: list[StockSeed], trade_date: date) -> list[StockScreenObservation]:
        candidates_by_key: dict[tuple[str, str], list[StockScreenObservation]] = {
            (seed.market_code, seed.ticker): [] for seed in seeds
        }
        errors: list[str] = []
        for provider in self._providers:
            try:
                observations = provider.fetch_daily(seeds, trade_date)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider.source_mode}: {exc}")
                continue
            for observation in observations:
                candidates_by_key.setdefault((observation.market_code, observation.ticker), []).append(observation)

        selected: list[StockScreenObservation] = []
        for seed in seeds:
            key = (seed.market_code, seed.ticker)
            candidates = candidates_by_key.get(key, [])
            if not candidates:
                error_detail = '; '.join(errors) if errors else 'no provider returned data'
                raise RuntimeError(f"No selection data candidates for {seed.ticker}: {error_detail}")
            selected.append(_select_best_selection_observation(candidates, self._providers))
        return selected



def _select_best_selection_observation(
    candidates: list[StockScreenObservation],
    providers: list,
) -> StockScreenObservation:
    priority = {provider.source_mode: index for index, provider in enumerate(providers)}
    field_names = [
        'close',
        'ma_20',
        'ma_60',
        'ma_120',
        'ma_200',
        'ret_5d',
        'ret_20d',
        'ret_60d',
        'avg_dollar_volume_3d',
        'avg_dollar_volume_20d',
        'volume_ratio_3d',
        'volume_up_days_5d',
        'distance_to_60d_high',
        'momentum_acceleration',
        'vol_20d',
    ]
    medians = _numeric_medians(candidates, field_names)

    def score(candidate: StockScreenObservation) -> tuple[float, float, float]:
        completeness = sum(1 for field_name in field_names if _is_valid_number(getattr(candidate, field_name)))
        deviation_penalty = 0.0
        for field_name in field_names:
            value = getattr(candidate, field_name)
            pivot = medians.get(field_name)
            if not _is_valid_number(value) or pivot is None:
                continue
            scale = max(abs(pivot), 1.0)
            deviation_penalty += abs(float(value) - pivot) / scale
        priority_rank = priority.get(candidate.source, len(priority))
        source_bonus = 0.1 if candidate.source != 'mock' else 0.0
        return (completeness + source_bonus, -deviation_penalty, -priority_rank)

    return max(candidates, key=score)


def _numeric_medians(candidates: list[StockScreenObservation], field_names: list[str]) -> dict[str, float]:
    medians: dict[str, float] = {}
    for field_name in field_names:
        values = [float(getattr(candidate, field_name)) for candidate in candidates if _is_valid_number(getattr(candidate, field_name))]
        if values:
            medians[field_name] = float(median(values))
    return medians


def _selection_observation_from_history(
    *,
    seed: StockSeed,
    trade_date: date,
    history: list[tuple[date, float, float]],
    source: str,
) -> StockScreenObservation:
    closes = [close for _, close, _ in history]
    if len(closes) < 201:
        raise RuntimeError(f"Not enough history for {seed.ticker}: need 201 closes, got {len(closes)}")
    metrics = _selection_metrics_from_history(history)
    return StockScreenObservation(
        market_code=seed.market_code,
        ticker=seed.ticker,
        trade_date=trade_date,
        close=round(closes[-1], 4),
        ma_20=round(float(metrics['ma_20']), 4),
        ma_60=round(float(metrics['ma_60']), 4),
        ma_120=round(fmean(closes[-120:]), 4),
        ma_200=round(fmean(closes[-200:]), 4),
        ret_5d=round(float(metrics['ret_5d']), 4),
        ret_20d=round(float(metrics['ret_20d']), 4),
        ret_60d=round(float(metrics['ret_60d']), 4),
        avg_dollar_volume_3d=round(float(metrics['avg_dollar_volume_3d']), 2),
        avg_dollar_volume_5d=round(float(metrics['avg_dollar_volume_5d']), 2),
        avg_dollar_volume_20d=round(float(metrics['avg_dollar_volume_20d']), 2),
        volume_ratio_3d=round(float(metrics['volume_ratio_3d']), 4),
        volume_ratio_5d=round(float(metrics['volume_ratio_5d']), 4),
        volume_up_days_5d=int(metrics['volume_up_days_5d']),
        distance_to_60d_high=round(float(metrics['distance_to_60d_high']), 4),
        momentum_acceleration=round(float(metrics['momentum_acceleration']), 4),
        vol_20d=round(float(metrics['vol_20d']), 4),
        source=source,
    )


def _selection_metrics_from_history(history: list[tuple[date, float, float]]) -> dict[str, float | int]:
    closes = [close for _, close, _ in history]
    if len(closes) < 61:
        raise RuntimeError(f"Not enough history for selection metrics: need 61 closes, got {len(closes)}")
    dollar_volumes_20d = [close * volume for _, close, volume in history[-20:] if volume > 0]
    dollar_volumes_5d = [close * volume for _, close, volume in history[-5:] if volume > 0]
    dollar_volumes_3d = [close * volume for _, close, volume in history[-3:] if volume > 0]
    if len(dollar_volumes_20d) < 10 or len(dollar_volumes_3d) < 2:
        raise RuntimeError('Not enough volume history for selection metrics')
    avg_dollar_volume_20d = fmean(dollar_volumes_20d)
    avg_dollar_volume_5d = fmean(dollar_volumes_5d) if dollar_volumes_5d else avg_dollar_volume_20d
    avg_dollar_volume_3d = fmean(dollar_volumes_3d)
    volume_ratio_3d = (avg_dollar_volume_3d / avg_dollar_volume_20d) if avg_dollar_volume_20d > 0 else 0.0
    volume_ratio_5d = (avg_dollar_volume_5d / avg_dollar_volume_20d) if avg_dollar_volume_20d > 0 else 0.0
    recent_high = max(closes[-60:])
    return {
        'ret_5d': _period_return(closes, 5),
        'ret_20d': _period_return(closes, 20),
        'ret_60d': _period_return(closes, 60),
        'ma_20': fmean(closes[-20:]),
        'ma_60': fmean(closes[-60:]),
        'avg_dollar_volume_3d': avg_dollar_volume_3d,
        'avg_dollar_volume_5d': avg_dollar_volume_5d,
        'avg_dollar_volume_20d': avg_dollar_volume_20d,
        'volume_ratio_3d': volume_ratio_3d,
        'volume_ratio_5d': volume_ratio_5d,
        'volume_up_days_5d': _volume_up_days(history, 5),
        'distance_to_60d_high': max(0.0, 1.0 - (closes[-1] / recent_high)) if recent_high > 0 else 0.0,
        'momentum_acceleration': _period_return(closes, 5) - (_period_return(closes, 20) / 4),
        'vol_20d': _annualized_volatility(closes, 20),
    }


def _volume_up_days(history: list[tuple[date, float, float]], lookback: int) -> int:
    recent = history[-(lookback + 1):]
    dollar_volumes = [close * volume for _, close, volume in recent]
    return sum(1 for previous, current in zip(dollar_volumes, dollar_volumes[1:]) if current > previous)


def _period_return(closes: list[float], lookback: int) -> float:
    base_price = closes[-(lookback + 1)]
    return (closes[-1] / base_price) - 1.0


def _annualized_volatility(closes: list[float], lookback: int) -> float:
    window = closes[-(lookback + 1):]
    daily_returns = [(current / previous) - 1.0 for previous, current in zip(window, window[1:])]
    if len(daily_returns) < 2:
        return 0.0
    return pstdev(daily_returns) * math.sqrt(252)


def _resolve_yfinance_screen():
    try:
        module = importlib.import_module('yfinance')
    except ModuleNotFoundError as exc:  # noqa: PERF203
        raise RuntimeError('yfinance is not installed. Add the dependency or switch provider mode.') from exc
    return module.screen


def _resolve_yfinance_equity_query():
    try:
        module = importlib.import_module('yfinance')
    except ModuleNotFoundError as exc:  # noqa: PERF203
        raise RuntimeError('yfinance is not installed. Add the dependency or switch provider mode.') from exc
    return module.EquityQuery


def _extract_symbol_history_frame(history_frame: pd.DataFrame, symbol: str, symbol_count: int) -> pd.DataFrame:
    columns = getattr(history_frame, 'columns', None)
    if isinstance(columns, pd.MultiIndex):
        if symbol in columns.get_level_values(0):
            return history_frame[symbol][['Close', 'Volume']].copy()
        if symbol in columns.get_level_values(-1):
            return history_frame.xs(symbol, axis=1, level=-1)[['Close', 'Volume']].copy()
    if symbol_count == 1:
        return history_frame[['Close', 'Volume']].copy()
    return pd.DataFrame()


def _history_rows_from_frame(history: pd.DataFrame) -> list[tuple[date, float, float]]:
    if history is None or getattr(history, 'empty', True):
        return []
    frame = history[['Close', 'Volume']].copy()
    rows: list[tuple[date, float, float]] = []
    for timestamp, row in frame.iterrows():
        close = row.get('Close')
        if close is None or math.isnan(float(close)):
            continue
        volume = _coerce_number(row.get('Volume'))
        rows.append((timestamp.to_pydatetime().date(), float(close), volume))
    return rows


def _resolve_yfinance_download():
    try:
        module = importlib.import_module('yfinance')
    except ModuleNotFoundError as exc:  # noqa: PERF203
        raise RuntimeError('yfinance is not installed. Add the dependency or switch provider mode.') from exc
    return module.download


def _resolve_yfinance_ticker_factory():
    try:
        module = importlib.import_module('yfinance')
    except ModuleNotFoundError as exc:  # noqa: PERF203
        raise RuntimeError('yfinance is not installed. Add the dependency or switch provider mode.') from exc
    return module.Ticker


def _first_number(*values) -> float:
    for value in values:
        if value is None:
            continue
        number = _coerce_number(value)
        if number != 0.0:
            return number
    return 0.0


def _coerce_percent(value) -> float:
    number = _coerce_number(value)
    if abs(number) <= 1.0:
        return number * 100.0
    return number


def _bounded_linear_score(value: float, *, lower: float, upper: float) -> float:
    if upper <= lower:
        return 0.0
    clamped = max(lower, min(upper, value))
    return ((clamped - lower) / (upper - lower)) * 100.0


def _coerce_number(value) -> float:
    if value is None:
        return 0.0
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        return 0.0
    return number


def _is_valid_number(value) -> bool:
    return isinstance(value, (int, float)) and not math.isnan(value) and not math.isinf(value)


def _resolve_fixed_theme_aliases(theme_name: str) -> tuple[set[str], set[str]]:
    aliases = _FIXED_THEME_ALIAS_MAP.get(theme_name.strip().lower(), {})
    industry_aliases = {_normalize_label(value) for value in aliases.get('industry', set()) if _normalize_label(value)}
    sector_aliases = {_normalize_label(value) for value in aliases.get('sector', set()) if _normalize_label(value)}
    if industry_aliases or sector_aliases:
        return industry_aliases, sector_aliases
    fallback = _normalize_label(theme_name)
    if fallback:
        return {fallback}, set()
    return set(), set()


def _price_position_ratio(*, price: float, low: float, high: float) -> float | None:
    if price <= 0 or low <= 0 or high <= 0 or high <= low:
        return None
    return max(0.0, min(1.0, (price - low) / (high - low)))


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "bull_screen"
