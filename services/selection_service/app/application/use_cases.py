from dataclasses import replace
from datetime import date, timedelta
from statistics import fmean, pstdev
import math

from packages.domain_core.selection.entities import (
    StockCandidate,
    StockSeedSnapshot,
    StockMetadata,
    StockDailyBar,
    StockScreenObservation,
    StockSeed,
    StockUniverseSnapshot,
    StockWatchItem,
    ThemeHeatSnapshot,
)
from packages.domain_core.selection.rules import evaluate_daily_candidate
from packages.shared.contracts import (
    SelectionDataProvider,
    StockCandidateRepository,
    StockSeedPoolRepository,
    StockMetadataRepository,
    StockUniverseRepository,
    StockBarRepository,
    StockWatchlistRepository,
    ThemeHeatRepository,
)
from packages.shared.logging import get_logger, log_event
from packages.shared.settings import MarketsConfig, SelectionRulesConfig
from packages.shared.sqlite import sqlite_session


logger = get_logger(__name__)


class SelectionService:
    def __init__(
        self,
        markets_config: MarketsConfig,
        seed_provider,
        rules_config: SelectionRulesConfig,
        data_provider: SelectionDataProvider,
        metadata_repository: StockMetadataRepository,
        seed_pool_repository: StockSeedPoolRepository,
        candidate_repository: StockCandidateRepository,
        watchlist_repository: StockWatchlistRepository,
        heat_repository: ThemeHeatRepository,
        universe_repository: StockUniverseRepository | None = None,
        bar_repository: StockBarRepository | None = None,
    ) -> None:
        self._markets_config = markets_config
        self._seed_provider = seed_provider
        self._rules_config = rules_config
        self._data_provider = data_provider
        self._metadata_repository = metadata_repository
        self._seed_pool_repository = seed_pool_repository
        self._candidate_repository = candidate_repository
        self._watchlist_repository = watchlist_repository
        self._heat_repository = heat_repository
        self._universe_repository = universe_repository
        self._bar_repository = bar_repository

    @property
    def source_mode(self) -> str:
        return getattr(self._data_provider, 'source_mode', 'unknown')

    def prepare_hot_themes(
        self,
        trade_date: date,
        market_codes: list[str],
        *,
        replace_market_codes: list[str] | None = None,
    ) -> list[ThemeHeatSnapshot]:
        resolved_market_codes = self._resolve_market_codes(market_codes)
        replace_codes = self._resolve_market_codes(replace_market_codes or market_codes)
        if not resolved_market_codes:
            return []

        self._bootstrap_incremental_heat_snapshot(trade_date, resolved_market_codes)
        existing_snapshots = self._list_heat_snapshots_for_markets(trade_date, resolved_market_codes)
        existing_market_codes = {item.market_code for item in existing_snapshots}
        missing_market_codes = [market_code for market_code in resolved_market_codes if market_code not in existing_market_codes]

        builder = getattr(self._seed_provider, 'build_hot_theme_list', None)
        if missing_market_codes and builder is not None:
            raw_heat_snapshots = builder(missing_market_codes, trade_date)
            smoothed_heat_snapshots = self._smooth_heat_snapshots(trade_date, raw_heat_snapshots)
            if smoothed_heat_snapshots:
                self._heat_repository.replace_heat_snapshots(
                    trade_date=trade_date,
                    market_codes=missing_market_codes,
                    snapshots=smoothed_heat_snapshots,
                )

        snapshots = self._list_heat_snapshots_for_markets(trade_date, resolved_market_codes)
        log_event(
            logger,
            'selection.prepare_hot_themes.completed',
            trade_date=trade_date.isoformat(),
            requested_market_codes=market_codes,
            resolved_market_codes=resolved_market_codes,
            replace_market_codes=replace_codes,
            built_market_codes=missing_market_codes,
            heat_snapshot_count=len(snapshots),
            source_mode=self.source_mode,
        )
        return snapshots

    def sync_market_universe_inventory(
        self,
        trade_date: date,
        market_codes: list[str],
        *,
        replace_market_codes: list[str] | None = None,
    ) -> list[StockUniverseSnapshot]:
        resolved_market_codes = self._resolve_market_codes(market_codes)
        replace_codes = self._resolve_market_codes(replace_market_codes or market_codes)
        if not resolved_market_codes or self._universe_repository is None:
            return []
        self._bootstrap_incremental_market_universe(trade_date, resolved_market_codes)
        existing_rows = self._list_market_universe_rows_for_markets(trade_date, resolved_market_codes)
        existing_market_codes = {row.market_code for row in existing_rows}
        missing_market_codes = [market_code for market_code in resolved_market_codes if market_code not in existing_market_codes]
        builder = getattr(self._seed_provider, 'sync_market_universe_inventory', None)
        if missing_market_codes and builder is not None:
            for market_code in missing_market_codes:
                try:
                    rows = builder([market_code], trade_date)
                except Exception as exc:
                    if len(resolved_market_codes) == 1:
                        raise
                    log_event(
                        logger,
                        'selection.sync_market_universe_inventory.market_failed',
                        trade_date=trade_date.isoformat(),
                        market_code=market_code,
                        source_mode=self.source_mode,
                        error=str(exc),
                    )
                    continue
                self._replace_market_universe_rows(trade_date, [market_code], rows)
        elif missing_market_codes:
            legacy_builder = getattr(self._seed_provider, 'sync_market_universe', None)
            if legacy_builder is not None:
                for market_code in missing_market_codes:
                    try:
                        legacy_builder([market_code], trade_date)
                    except Exception as exc:
                        if len(resolved_market_codes) == 1:
                            raise
                        log_event(
                            logger,
                            'selection.sync_market_universe_inventory.market_failed',
                            trade_date=trade_date.isoformat(),
                            market_code=market_code,
                            source_mode=self.source_mode,
                            error=str(exc),
                        )
                        continue
                    self._persist_market_universe(trade_date, [market_code])
            else:
                self._persist_market_universe(trade_date, missing_market_codes)
        rows = self._list_market_universe_rows_for_markets(trade_date, resolved_market_codes)
        log_event(
            logger,
            'selection.sync_market_universe_inventory.completed',
            trade_date=trade_date.isoformat(),
            requested_market_codes=market_codes,
            resolved_market_codes=resolved_market_codes,
            replace_market_codes=replace_codes,
            built_market_codes=missing_market_codes,
            universe_count=len(rows),
            source_mode=self.source_mode,
        )
        return rows

    def sync_market_universe_bars(
        self,
        trade_date: date,
        market_codes: list[str],
    ) -> list[StockDailyBar]:
        resolved_market_codes = self._resolve_market_codes(market_codes)
        if not resolved_market_codes or self._universe_repository is None or self._bar_repository is None:
            return []
        rows = self._load_local_universe_rows(resolved_market_codes, trade_date)
        if not rows:
            rows = self.sync_market_universe_inventory(trade_date=trade_date, market_codes=resolved_market_codes)
        builder = getattr(self._seed_provider, 'sync_market_universe_bars', None)
        if builder is None or not rows:
            return []
        latest_bar_dates = {
            (row.market_code, row.ticker): self._bar_repository.get_latest_stock_bar_date(row.market_code, row.ticker)
            for row in rows
        }
        raw_bars = builder(rows, trade_date=trade_date, latest_bar_dates=latest_bar_dates)
        bars = self._normalize_stock_bars(raw_bars)
        if bars:
            self._bar_repository.upsert_stock_bars(bars)
        log_event(
            logger,
            'selection.sync_market_universe_bars.completed',
            trade_date=trade_date.isoformat(),
            market_codes=resolved_market_codes,
            bar_count=len(bars),
            source_mode=self.source_mode,
        )
        return bars

    def compute_market_universe_metrics(
        self,
        trade_date: date,
        market_codes: list[str],
        *,
        replace_market_codes: list[str] | None = None,
    ) -> list[StockUniverseSnapshot]:
        resolved_market_codes = self._resolve_market_codes(market_codes)
        replace_codes = self._resolve_market_codes(replace_market_codes or market_codes)
        if not resolved_market_codes or self._universe_repository is None or self._bar_repository is None:
            return []
        rows = self._load_local_universe_rows(resolved_market_codes, trade_date)
        if not rows:
            return []
        updated_rows: list[StockUniverseSnapshot] = []
        for row in rows:
            bars = self._bar_repository.list_stock_bars(row.market_code, row.ticker, trade_date=trade_date)
            updated_rows.append(self._apply_local_metrics_to_universe_row(row, bars))
        self._universe_repository.replace_market_universe(trade_date=trade_date, market_codes=replace_codes, rows=updated_rows)
        log_event(
            logger,
            'selection.compute_market_universe_metrics.completed',
            trade_date=trade_date.isoformat(),
            requested_market_codes=market_codes,
            resolved_market_codes=resolved_market_codes,
            replace_market_codes=replace_codes,
            universe_count=len(updated_rows),
            source_mode=self.source_mode,
        )
        return updated_rows

    def sync_market_universe(
        self,
        trade_date: date,
        market_codes: list[str],
        *,
        replace_market_codes: list[str] | None = None,
    ) -> list[StockUniverseSnapshot]:
        inventory_rows = self.sync_market_universe_inventory(
            trade_date=trade_date,
            market_codes=market_codes,
            replace_market_codes=replace_market_codes,
        )
        if inventory_rows and self._bar_repository is not None:
            self.sync_market_universe_bars(trade_date=trade_date, market_codes=market_codes)
            return self.compute_market_universe_metrics(
                trade_date=trade_date,
                market_codes=market_codes,
                replace_market_codes=replace_market_codes,
            )
        return inventory_rows

    def run_daily_selection(
        self,
        trade_date: date,
        market_codes: list[str],
        *,
        replace_market_codes: list[str] | None = None,
        regime_trade_date: date | None = None,
        prepared_heat_snapshots: list[ThemeHeatSnapshot] | None = None,
    ) -> tuple[list[StockCandidate], list[StockWatchItem]]:
        resolved_market_codes = self._resolve_market_codes(market_codes)
        replace_codes = self._resolve_market_codes(replace_market_codes or market_codes)
        if not resolved_market_codes:
            self._seed_pool_repository.replace_seed_pool(trade_date=trade_date, market_codes=replace_codes, seeds=[])
            self._candidate_repository.replace_candidates(trade_date=trade_date, market_codes=replace_codes, candidates=[])
            self._watchlist_repository.replace_watchlist(trade_date=trade_date, watchlist=[])
            self._heat_repository.replace_heat_snapshots(trade_date=trade_date, market_codes=replace_codes, snapshots=[])
            log_event(
                logger,
                'selection.run_daily_selection.skipped',
                trade_date=trade_date.isoformat(),
                requested_market_codes=market_codes,
                replace_market_codes=replace_codes,
                source_mode=self.source_mode,
                reason='no_tracked_bull_markets',
            )
            return [], []

        smoothed_heat_snapshots, should_persist_heat_snapshots = self._resolve_incremental_heat_snapshots(
            trade_date=trade_date,
            market_codes=resolved_market_codes,
            replace_market_codes=replace_codes,
            prepared_heat_snapshots=prepared_heat_snapshots,
        )
        local_rows = self._load_local_universe_rows(resolved_market_codes, trade_date)
        if not local_rows:
            local_rows = self._load_latest_local_universe_rows(resolved_market_codes, trade_date)
        if not local_rows and self._universe_repository is not None:
            local_rows = self.sync_market_universe_inventory(
                trade_date=trade_date,
                market_codes=resolved_market_codes,
                replace_market_codes=replace_codes,
            )
        seeds = self._resolve_seeds(resolved_market_codes, trade_date, local_rows=local_rows)
        seed_snapshots = [self._seed_to_snapshot(trade_date, seed) for seed in seeds]
        self._seed_pool_repository.replace_seed_pool(trade_date=trade_date, market_codes=replace_codes, seeds=seed_snapshots)
        observations = self._resolve_observations(seeds=seeds, trade_date=trade_date, local_rows=local_rows)
        weights = self._rules_config.daily_ranking.weights.model_dump()
        thresholds = self._rules_config.daily_ranking.model_dump(exclude={'weights', 'watchlist_size'})
        seeds_by_key = {(seed.market_code, seed.ticker): seed for seed in seeds}
        metadata_rows: dict[tuple[str, str], StockMetadata] = {}
        ranked_candidates: list[StockCandidate] = []

        for observation in observations:
            seed = seeds_by_key[(observation.market_code, observation.ticker)]
            passed, composite_score, component_scores, flags = evaluate_daily_candidate(
                seed=seed,
                observation=observation,
                weights=weights,
                thresholds=thresholds,
            )
            if not passed:
                continue
            metadata_rows[(seed.market_code, seed.ticker)] = StockMetadata(
                market_code=seed.market_code,
                ticker=seed.ticker,
                company_name=seed.company_name,
                sector=seed.sector,
                industry=seed.industry,
                exchange=seed.exchange,
                currency=seed.currency,
                country_code=seed.country_code,
                theme_tags=seed.theme_tags,
                theme_score=seed.theme_score,
                valuation_score=seed.valuation_score,
                size_score=seed.size_score,
                valuation_band=seed.valuation_band,
                market_cap_bucket=seed.market_cap_bucket,
                updated_at=trade_date,
            )
            ranked_candidates.append(
                StockCandidate(
                    market_code=seed.market_code,
                    ticker=seed.ticker,
                    trade_date=trade_date,
                    regime_trade_date=regime_trade_date or trade_date,
                    company_name=seed.company_name,
                    sector=seed.sector,
                    industry=seed.industry,
                    seed_type=seed.seed_type,
                    rank=0,
                    close=observation.close,
                    ret_5d=observation.ret_5d,
                    ret_20d=observation.ret_20d,
                    ret_60d=observation.ret_60d,
                    ma_20=observation.ma_20,
                    ma_60=observation.ma_60,
                    avg_dollar_volume_3d=observation.avg_dollar_volume_3d,
                    avg_dollar_volume_5d=observation.avg_dollar_volume_5d,
                    avg_dollar_volume_20d=observation.avg_dollar_volume_20d,
                    volume_ratio_3d=observation.volume_ratio_3d,
                    volume_ratio_5d=observation.volume_ratio_5d,
                    volume_up_days_5d=observation.volume_up_days_5d,
                    distance_to_60d_high=observation.distance_to_60d_high,
                    momentum_acceleration=observation.momentum_acceleration,
                    vol_20d=observation.vol_20d,
                    coarse_score=composite_score,
                    composite_score=composite_score,
                    theme_score=component_scores['theme_score'],
                    lagging_score=component_scores['lagging_score'],
                    trend_recovery_score=component_scores['trend_recovery_score'],
                    momentum_acceleration_score=component_scores['momentum_acceleration_score'],
                    volume_probe_score=component_scores['volume_probe_score'],
                    risk_control_score=component_scores['risk_control_score'],
                    valuation_band=seed.valuation_band,
                    market_cap_bucket=seed.market_cap_bucket,
                    theme_tags=seed.theme_tags,
                    source=observation.source,
                    screen_flags=flags,
                )
            )

        ordered_candidates = sorted(
            ranked_candidates,
            key=lambda item: (
                -item.composite_score,
                -item.trend_recovery_score,
                -item.lagging_score,
                -item.volume_probe_score,
                -item.theme_score,
                item.ticker,
            ),
        )
        candidates = [replace(candidate, rank=index) for index, candidate in enumerate(ordered_candidates, start=1)]
        watchlist = [
            StockWatchItem(
                market_code=candidate.market_code,
                ticker=candidate.ticker,
                trade_date=candidate.trade_date,
                regime_trade_date=candidate.regime_trade_date,
                watch_rank=candidate.rank,
                company_name=candidate.company_name,
                sector=candidate.sector,
                industry=candidate.industry,
                close=candidate.close,
                ret_5d=candidate.ret_5d,
                ret_20d=candidate.ret_20d,
                ret_60d=candidate.ret_60d,
                ma_20=candidate.ma_20,
                ma_60=candidate.ma_60,
                avg_dollar_volume_3d=candidate.avg_dollar_volume_3d,
                avg_dollar_volume_5d=candidate.avg_dollar_volume_5d,
                avg_dollar_volume_20d=candidate.avg_dollar_volume_20d,
                volume_ratio_3d=candidate.volume_ratio_3d,
                volume_ratio_5d=candidate.volume_ratio_5d,
                volume_up_days_5d=candidate.volume_up_days_5d,
                distance_to_60d_high=candidate.distance_to_60d_high,
                momentum_acceleration=candidate.momentum_acceleration,
                vol_20d=candidate.vol_20d,
                composite_score=candidate.composite_score,
                theme_score=candidate.theme_score,
                lagging_score=candidate.lagging_score,
                trend_recovery_score=candidate.trend_recovery_score,
                momentum_acceleration_score=candidate.momentum_acceleration_score,
                volume_probe_score=candidate.volume_probe_score,
                risk_control_score=candidate.risk_control_score,
                valuation_band=candidate.valuation_band,
                market_cap_bucket=candidate.market_cap_bucket,
                theme_tags=candidate.theme_tags,
                source=candidate.source,
                watch_reason=self._build_watch_reason(candidate),
            )
            for candidate in candidates[: self._rules_config.daily_ranking.watchlist_size]
        ]

        self._metadata_repository.upsert_metadata(list(metadata_rows.values()))
        self._candidate_repository.replace_candidates(
            trade_date=trade_date,
            market_codes=replace_codes,
            candidates=candidates,
        )
        self._watchlist_repository.replace_watchlist(trade_date=trade_date, watchlist=watchlist)
        if should_persist_heat_snapshots:
            self._heat_repository.replace_heat_snapshots(trade_date=trade_date, market_codes=replace_codes, snapshots=smoothed_heat_snapshots)
        log_event(
            logger,
            'selection.run_daily_selection.completed',
            trade_date=trade_date.isoformat(),
            regime_trade_date=(regime_trade_date or trade_date).isoformat(),
            requested_market_codes=market_codes,
            resolved_market_codes=resolved_market_codes,
            replace_market_codes=replace_codes,
            seed_count=len(seeds),
            observation_count=len(observations),
            candidate_count=len(candidates),
            watchlist_count=len(watchlist),
            heat_snapshot_count=len(smoothed_heat_snapshots),
            source_mode=self.source_mode,
            top_candidates=[
                {
                    'market_code': candidate.market_code,
                    'ticker': candidate.ticker,
                    'rank': candidate.rank,
                    'composite_score': round(candidate.composite_score, 4),
                    'lagging_score': round(candidate.lagging_score, 4),
                    'trend_recovery_score': round(candidate.trend_recovery_score, 4),
                    'theme_score': candidate.theme_score,
                }
                for candidate in candidates[:5]
            ],
            hot_themes=[
                {
                    'market_code': item.market_code,
                    'theme_type': item.theme_type,
                    'theme_name': item.theme_name,
                    'raw_heat_score': round(item.raw_heat_score, 4),
                    'smoothed_heat_score': round(item.smoothed_heat_score, 4),
                }
                for item in smoothed_heat_snapshots[:5]
            ],
            watchlist=[
                {
                    'market_code': item.market_code,
                    'ticker': item.ticker,
                    'watch_rank': item.watch_rank,
                    'composite_score': round(item.composite_score, 4),
                    'watch_reason': item.watch_reason,
                }
                for item in watchlist
            ],
        )
        return candidates, watchlist

    def run_coarse_screen(
        self,
        trade_date: date,
        market_codes: list[str],
        *,
        replace_market_codes: list[str] | None = None,
        regime_trade_date: date | None = None,
    ) -> list[StockCandidate]:
        candidates, _ = self.run_daily_selection(
            trade_date=trade_date,
            market_codes=market_codes,
            replace_market_codes=replace_market_codes,
            regime_trade_date=regime_trade_date,
        )
        return candidates

    def list_seed_pool(self, trade_date: date, market_code: str | None = None) -> list[StockSeedSnapshot]:
        return self._seed_pool_repository.list_seed_pool(trade_date=trade_date, market_code=market_code)

    def list_candidates(self, trade_date: date, market_code: str | None = None) -> list[StockCandidate]:
        return self._candidate_repository.list_candidates(trade_date=trade_date, market_code=market_code)

    def list_market_universe(self, trade_date: date, market_code: str | None = None) -> list[StockUniverseSnapshot]:
        if self._universe_repository is None:
            return []
        return self._universe_repository.list_market_universe(trade_date=trade_date, market_code=market_code)

    def repair_market_universe(
        self,
        trade_date: date,
        market_codes: list[str],
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[StockUniverseSnapshot]:
        if self._universe_repository is None:
            return []
        resolved_market_codes = self._resolve_market_codes(market_codes)
        rows: list[StockUniverseSnapshot] = []
        for market_code in resolved_market_codes:
            rows.extend(self._universe_repository.list_market_universe(trade_date=trade_date, market_code=market_code))
        if not rows:
            return []
        enricher = getattr(self._seed_provider, 'enrich_market_universe_rows', None)
        if enricher is None:
            return rows
        target_rows = [row for row in rows if row.sector == 'Unknown' or row.industry == 'Unknown']
        target_rows.sort(
            key=lambda row: (
                -row.market_cap,
                -row.momentum_pct,
                -row.volume_ratio,
                row.market_code,
                row.ticker,
            )
        )
        if offset > 0:
            target_rows = target_rows[offset:]
        if limit is not None:
            target_rows = target_rows[: max(limit, 0)]
        if not target_rows:
            return rows

        enriched_subset = enricher(target_rows)
        if enriched_subset == target_rows:
            return rows

        rows_by_key = {(row.market_code, row.ticker): row for row in rows}
        for row in enriched_subset:
            rows_by_key[(row.market_code, row.ticker)] = row
        enriched_rows = sorted(rows_by_key.values(), key=lambda item: (item.market_code, item.ticker))
        if enriched_rows != rows:
            self._universe_repository.replace_market_universe(
                trade_date=trade_date,
                market_codes=resolved_market_codes,
                rows=enriched_rows,
            )
        return enriched_rows

    def list_watchlist(self, trade_date: date, market_code: str | None = None) -> list[StockWatchItem]:
        return self._watchlist_repository.list_watchlist(trade_date=trade_date, market_code=market_code)

    def list_heat_snapshots(
        self,
        trade_date: date,
        market_code: str | None = None,
        theme_type: str | None = None,
    ) -> list[ThemeHeatSnapshot]:
        return self._heat_repository.list_heat_snapshots(
            trade_date=trade_date,
            market_code=market_code,
            theme_type=theme_type,
        )

    def _load_local_universe_rows(self, market_codes: list[str], trade_date: date) -> list[StockUniverseSnapshot]:
        return self._list_market_universe_rows_for_markets(trade_date, market_codes)

    def _load_latest_local_universe_rows(self, market_codes: list[str], trade_date: date) -> list[StockUniverseSnapshot]:
        latest_trade_date = self._latest_market_universe_trade_date(before_or_on_trade_date=trade_date, market_codes=market_codes)
        if latest_trade_date is None:
            return []
        return self._list_market_universe_rows_for_markets(latest_trade_date, market_codes)

    def _resolve_observations(
        self,
        *,
        seeds: list[StockSeed],
        trade_date: date,
        local_rows: list[StockUniverseSnapshot],
    ) -> list[StockScreenObservation]:
        local_rows_by_key = {(row.market_code, row.ticker): row for row in local_rows}
        resolved: list[StockScreenObservation] = []
        missing: list[StockSeed] = []
        for seed in seeds:
            row = local_rows_by_key.get((seed.market_code, seed.ticker))
            observation = self._local_universe_to_observation(row, trade_date) if row is not None else None
            if observation is None:
                missing.append(seed)
                continue
            resolved.append(observation)
        if missing:
            resolved.extend(self._data_provider.fetch_daily(seeds=missing, trade_date=trade_date))
        return resolved

    @staticmethod
    def _local_universe_to_observation(
        row: StockUniverseSnapshot | None,
        trade_date: date,
    ) -> StockScreenObservation | None:
        if row is None:
            return None
        required = (
            row.ret_5d,
            row.ret_20d,
            row.ret_60d,
            row.ma_20,
            row.ma_60,
            row.avg_dollar_volume_3d,
            row.avg_dollar_volume_20d,
            row.volume_ratio_3d,
            row.volume_up_days_5d,
            row.distance_to_60d_high,
            row.momentum_acceleration,
            row.vol_20d,
        )
        if any(value is None for value in required):
            return None
        avg_dollar_volume_3d = float(row.avg_dollar_volume_3d)
        avg_dollar_volume_20d = float(row.avg_dollar_volume_20d)
        volume_ratio_3d = float(row.volume_ratio_3d)
        return StockScreenObservation(
            market_code=row.market_code,
            ticker=row.ticker,
            trade_date=trade_date,
            close=float(row.price),
            ma_20=float(row.ma_20),
            ma_60=float(row.ma_60),
            ma_120=float(row.ma_60),
            ma_200=float(row.ma_60),
            ret_5d=float(row.ret_5d),
            ret_20d=float(row.ret_20d),
            ret_60d=float(row.ret_60d),
            avg_dollar_volume_3d=avg_dollar_volume_3d,
            avg_dollar_volume_5d=avg_dollar_volume_3d,
            avg_dollar_volume_20d=avg_dollar_volume_20d,
            volume_ratio_3d=volume_ratio_3d,
            volume_ratio_5d=volume_ratio_3d,
            volume_up_days_5d=int(row.volume_up_days_5d),
            distance_to_60d_high=float(row.distance_to_60d_high),
            momentum_acceleration=float(row.momentum_acceleration),
            vol_20d=float(row.vol_20d),
            source='local_universe',
        )

    def _resolve_market_codes(self, market_codes: list[str]) -> list[str]:
        if market_codes == ['ALL']:
            return [item.market_code for item in self._markets_config.markets]
        wanted = set(market_codes)
        return [item.market_code for item in self._markets_config.markets if item.market_code in wanted]

    def _resolve_seeds(
        self,
        market_codes: list[str],
        trade_date: date,
        *,
        local_rows: list[StockUniverseSnapshot] | None = None,
    ) -> list[StockSeed]:
        local_resolver = getattr(self._seed_provider, 'resolve_seeds_from_universe', None)
        if self._universe_repository is not None and local_resolver is not None:
            rows = list(local_rows or [])
            if not rows:
                rows = self._load_local_universe_rows(market_codes, trade_date)
            if not rows:
                rows = self._load_latest_local_universe_rows(market_codes, trade_date)
            if not rows:
                rows = self.sync_market_universe_inventory(trade_date=trade_date, market_codes=market_codes)
            has_classified_rows = any(row.sector != 'Unknown' or row.industry != 'Unknown' for row in rows)
            local_enrichment_threshold = max(
                500,
                len(market_codes) * self._rules_config.seed_discovery.max_selected_per_market * 20,
            )
            if rows and not has_classified_rows and len(rows) > local_enrichment_threshold:
                return self._seed_provider.resolve_seeds(market_codes, trade_date)
            enricher = getattr(self._seed_provider, 'enrich_market_universe_rows', None)
            if rows and enricher is not None:
                enrichment_rows = self._select_rows_for_seed_enrichment(rows)
                if enrichment_rows:
                    enriched_subset = enricher(enrichment_rows)
                    if enriched_subset and enriched_subset != enrichment_rows:
                        rows_by_key = {(row.market_code, row.ticker): row for row in rows}
                        for row in enriched_subset:
                            rows_by_key[(row.market_code, row.ticker)] = row
                        rows = list(rows_by_key.values())
                        target_trade_date = enriched_subset[0].trade_date
                        self._universe_repository.replace_market_universe(
                            trade_date=target_trade_date,
                            market_codes=market_codes,
                            rows=rows,
                        )
                else:
                    rows = list(rows)
            if rows:
                local_seeds = local_resolver(rows, trade_date)
                if local_seeds:
                    return local_seeds
                if not any(row.sector != 'Unknown' or row.industry != 'Unknown' for row in rows):
                    return self._seed_provider.resolve_seeds(market_codes, trade_date)
        return self._seed_provider.resolve_seeds(market_codes, trade_date)

    def _select_rows_for_seed_enrichment(
        self,
        rows: list[StockUniverseSnapshot],
    ) -> list[StockUniverseSnapshot]:
        per_market_limit = min(
            max(1, self._rules_config.seed_discovery.max_selected_per_market),
            max(5, self._rules_config.daily_ranking.watchlist_size * 2),
        )
        grouped: dict[str, list[StockUniverseSnapshot]] = {}
        for row in rows:
            if row.sector != 'Unknown' and row.industry != 'Unknown':
                continue
            grouped.setdefault(row.market_code, []).append(row)
        selected: list[StockUniverseSnapshot] = []
        for market_code, market_rows in grouped.items():
            prioritized = sorted(
                market_rows,
                key=lambda item: (
                    -item.market_cap,
                    -item.momentum_pct,
                    -item.volume_ratio,
                    item.ticker,
                ),
            )
            selected.extend(prioritized[:per_market_limit])
        return selected

    def _persist_market_universe(self, trade_date: date, market_codes: list[str]) -> None:
        if self._universe_repository is None:
            return
        resolver = getattr(self._seed_provider, 'list_market_universe', None)
        if resolver is None:
            return
        rows = resolver(trade_date, market_codes)
        self._replace_market_universe_rows(trade_date=trade_date, market_codes=market_codes, rows=rows)

    @staticmethod
    def _normalize_stock_bars(raw_rows) -> list[StockDailyBar]:
        normalized: list[StockDailyBar] = []
        for row in raw_rows or []:
            if isinstance(row, StockDailyBar):
                normalized.append(row)
                continue
            if isinstance(row, dict):
                normalized.append(StockDailyBar(**row))
        return normalized

    def _replace_market_universe_rows(self, trade_date: date, market_codes: list[str], rows) -> None:
        if self._universe_repository is None:
            return
        normalized_rows: list[StockUniverseSnapshot] = []
        for row in rows or []:
            if isinstance(row, StockUniverseSnapshot):
                normalized_rows.append(row)
                continue
            if isinstance(row, dict):
                normalized_rows.append(StockUniverseSnapshot(**row))
        self._universe_repository.replace_market_universe(trade_date=trade_date, market_codes=market_codes, rows=normalized_rows)

    def _apply_local_metrics_to_universe_row(
        self,
        row: StockUniverseSnapshot,
        bars: list[StockDailyBar],
    ) -> StockUniverseSnapshot:
        if not bars:
            return row
        history = [(bar.trade_date, bar.close, bar.volume) for bar in bars]
        try:
            metrics = _selection_metrics_from_bars(history)
        except RuntimeError:
            latest_bar = bars[-1]
            return replace(row, price=latest_bar.close)
        latest_bar = bars[-1]
        return replace(
            row,
            price=latest_bar.close,
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
            source='local_universe',
        )

    def _list_heat_snapshots_for_markets(self, trade_date: date, market_codes: list[str]) -> list[ThemeHeatSnapshot]:
        rows: list[ThemeHeatSnapshot] = []
        for market_code in market_codes:
            rows.extend(self._heat_repository.list_heat_snapshots(trade_date=trade_date, market_code=market_code))
        return sorted(rows, key=lambda item: (-item.smoothed_heat_score, -item.raw_heat_score, item.theme_type, item.theme_name))

    def _list_market_universe_rows_for_markets(self, trade_date: date, market_codes: list[str]) -> list[StockUniverseSnapshot]:
        if self._universe_repository is None:
            return []
        rows: list[StockUniverseSnapshot] = []
        for market_code in market_codes:
            rows.extend(self._universe_repository.list_market_universe(trade_date=trade_date, market_code=market_code))
        return rows

    def _resolve_incremental_heat_snapshots(
        self,
        *,
        trade_date: date,
        market_codes: list[str],
        replace_market_codes: list[str],
        prepared_heat_snapshots: list[ThemeHeatSnapshot] | None,
    ) -> tuple[list[ThemeHeatSnapshot], bool]:
        if prepared_heat_snapshots is not None:
            persist = all(item.trade_date == trade_date for item in prepared_heat_snapshots)
            return prepared_heat_snapshots, persist
        current_rows = self._list_heat_snapshots_for_markets(trade_date, market_codes)
        if current_rows:
            return current_rows, True
        latest_trade_date = self._latest_heat_snapshot_trade_date(before_trade_date=trade_date, market_codes=market_codes)
        if latest_trade_date is not None:
            latest_rows = self._list_heat_snapshots_for_markets(latest_trade_date, market_codes)
            if latest_rows:
                return latest_rows, False
        built_rows = self.prepare_hot_themes(
            trade_date=trade_date,
            market_codes=market_codes,
            replace_market_codes=replace_market_codes,
        )
        return built_rows, True

    def _bootstrap_incremental_heat_snapshot(self, trade_date: date, market_codes: list[str]) -> None:
        if self._heat_repository.list_heat_snapshots(trade_date=trade_date):
            return
        previous_trade_date = self._latest_heat_snapshot_trade_date(before_trade_date=trade_date)
        if previous_trade_date is None:
            return
        previous_rows = self._heat_repository.list_heat_snapshots(trade_date=previous_trade_date)
        if not previous_rows:
            return
        requested = set(market_codes)
        carried_rows = [replace(item, trade_date=trade_date) for item in previous_rows if item.market_code not in requested]
        if not carried_rows:
            return
        carried_market_codes = sorted({item.market_code for item in carried_rows})
        self._heat_repository.replace_heat_snapshots(
            trade_date=trade_date,
            market_codes=carried_market_codes,
            snapshots=carried_rows,
        )

    def _bootstrap_incremental_market_universe(self, trade_date: date, market_codes: list[str]) -> None:
        if self._universe_repository is None or self._list_market_universe_rows_for_markets(trade_date, market_codes):
            return
        previous_trade_date = self._latest_market_universe_trade_date(before_trade_date=trade_date)
        if previous_trade_date is None:
            return
        previous_rows = self._list_market_universe_rows_for_markets(previous_trade_date, self._resolve_market_codes(['ALL']))
        if not previous_rows:
            return
        requested = set(market_codes)
        carried_rows = [replace(item, trade_date=trade_date) for item in previous_rows if item.market_code not in requested]
        if not carried_rows:
            return
        carried_market_codes = sorted({item.market_code for item in carried_rows})
        self._universe_repository.replace_market_universe(
            trade_date=trade_date,
            market_codes=carried_market_codes,
            rows=carried_rows,
        )

    def _latest_heat_snapshot_trade_date(
        self,
        *,
        before_trade_date: date | None = None,
        market_codes: list[str] | None = None,
    ) -> date | None:
        backend_name = getattr(self._heat_repository, 'backend_name', 'unknown')
        if backend_name == 'memory':
            store = getattr(self._heat_repository, '_heat_snapshots', {})
            dates = {
                current_date
                for current_date, current_market_code, _, _ in store.keys()
                if market_codes is None or current_market_code in set(market_codes)
            }
            if before_trade_date is not None:
                dates = {current_date for current_date in dates if current_date < before_trade_date}
            return max(dates) if dates else None

        db_path = getattr(self._heat_repository, '_db_path', None)
        if db_path is None:
            return None
        query = 'SELECT MAX(trade_date) AS trade_date FROM selection_heat_daily'
        clauses: list[str] = []
        parameters: list[str] = []
        if before_trade_date is not None:
            clauses.append('trade_date < ?')
            parameters.append(before_trade_date.isoformat())
        if market_codes:
            placeholders = ', '.join('?' for _ in market_codes)
            clauses.append(f"market_code IN ({placeholders})")
            parameters.extend(market_codes)
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        with sqlite_session(db_path) as connection:
            row = connection.execute(query, parameters).fetchone()
        if row is None or row['trade_date'] is None:
            return None
        return date.fromisoformat(row['trade_date'])

    def _latest_market_universe_trade_date(
        self,
        *,
        before_trade_date: date | None = None,
        before_or_on_trade_date: date | None = None,
        market_codes: list[str] | None = None,
    ) -> date | None:
        if self._universe_repository is None:
            return None
        backend_name = getattr(self._universe_repository, 'backend_name', 'unknown')
        market_code_filter = set(market_codes or [])
        if backend_name == 'memory':
            store = getattr(self._universe_repository, '_market_universe', {})
            dates = {
                current_date
                for current_date, current_market_code, _ in store.keys()
                if not market_code_filter or current_market_code in market_code_filter
            }
            if before_trade_date is not None:
                dates = {current_date for current_date in dates if current_date < before_trade_date}
            if before_or_on_trade_date is not None:
                dates = {current_date for current_date in dates if current_date <= before_or_on_trade_date}
            return max(dates) if dates else None

        db_path = getattr(self._universe_repository, '_db_path', None)
        if db_path is None:
            return None
        query = 'SELECT MAX(trade_date) AS trade_date FROM stock_universe_daily'
        clauses: list[str] = []
        parameters: list[str] = []
        if before_trade_date is not None:
            clauses.append('trade_date < ?')
            parameters.append(before_trade_date.isoformat())
        if before_or_on_trade_date is not None:
            clauses.append('trade_date <= ?')
            parameters.append(before_or_on_trade_date.isoformat())
        if market_codes:
            placeholders = ', '.join('?' for _ in market_codes)
            clauses.append(f"market_code IN ({placeholders})")
            parameters.extend(market_codes)
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        with sqlite_session(db_path) as connection:
            row = connection.execute(query, parameters).fetchone()
        if row is None or row['trade_date'] is None:
            return None
        return date.fromisoformat(row['trade_date'])

    def _resolve_heat_snapshots(self, trade_date: date, market_codes: list[str]) -> list[ThemeHeatSnapshot]:
        resolver = getattr(self._seed_provider, 'list_heat_snapshots', None)
        if resolver is None:
            return []
        snapshots = resolver(trade_date, market_codes)
        return sorted(snapshots, key=lambda item: (-item.raw_heat_score, item.theme_type, item.theme_name))

    def _smooth_heat_snapshots(self, trade_date: date, snapshots: list[ThemeHeatSnapshot]) -> list[ThemeHeatSnapshot]:
        lookback_days = max(1, int(getattr(self._rules_config.seed_discovery, 'heat_lookback_days', 3)))
        smoothed: list[ThemeHeatSnapshot] = []
        for snapshot in snapshots:
            history_scores = [snapshot.raw_heat_score]
            for offset in range(1, lookback_days):
                previous_date = trade_date - timedelta(days=offset)
                previous_rows = self._heat_repository.list_heat_snapshots(
                    trade_date=previous_date,
                    market_code=snapshot.market_code,
                    theme_type=snapshot.theme_type,
                )
                matched = next((row for row in previous_rows if row.theme_name == snapshot.theme_name), None)
                if matched is not None:
                    history_scores.append(matched.raw_heat_score)
            averaged = sum(history_scores) / len(history_scores)
            smoothed_score = round(max(snapshot.raw_heat_score, averaged), 4)
            smoothed.append(replace(snapshot, smoothed_heat_score=smoothed_score))
        return sorted(smoothed, key=lambda item: (-item.smoothed_heat_score, -item.raw_heat_score, item.theme_type, item.theme_name))

    @staticmethod
    def _seed_to_snapshot(trade_date: date, seed: StockSeed) -> StockSeedSnapshot:
        primary_theme = seed.theme_tags[0] if seed.theme_tags else 'core_theme'
        return StockSeedSnapshot(
            trade_date=trade_date,
            market_code=seed.market_code,
            ticker=seed.ticker,
            company_name=seed.company_name,
            sector=seed.sector,
            industry=seed.industry,
            exchange=seed.exchange,
            currency=seed.currency,
            country_code=seed.country_code,
            seed_type=seed.seed_type,
            theme_tags=seed.theme_tags,
            theme_score=seed.theme_score,
            valuation_score=seed.valuation_score,
            size_score=seed.size_score,
            valuation_band=seed.valuation_band,
            market_cap_bucket=seed.market_cap_bucket,
            seed_reason=f'theme={primary_theme} valuation={seed.valuation_band} size={seed.market_cap_bucket}',
        )

    @staticmethod
    def _build_watch_reason(candidate: StockCandidate) -> str:
        primary_theme = candidate.theme_tags[0] if candidate.theme_tags else 'core_theme'
        return (
            f'rank#{candidate.rank} theme={primary_theme} '
            f'lagging={candidate.lagging_score:.1f} '
            f'trend={candidate.trend_recovery_score:.1f} '
            f'momentum={candidate.momentum_acceleration_score:.1f} '
            f'volume_probe={candidate.volume_probe_score:.1f} '
            f'risk={candidate.risk_control_score:.1f}'
        )


def _selection_metrics_from_bars(history: list[tuple[date, float, float]]) -> dict[str, float | int]:
    closes = [close for _, close, _ in history]
    if len(closes) < 61:
        raise RuntimeError(f'Not enough history for selection metrics: need 61 closes, got {len(closes)}')
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
