from collections.abc import Callable
from datetime import date

from packages.shared.api_models import JobRunResult, JobStepResult
from packages.shared.logging import get_logger, log_event


logger = get_logger(__name__)


class DailyRunOrchestrator:
    def __init__(self, refdata_service, market_data_service, regime_service, selection_service, trading_service) -> None:
        self._refdata_service = refdata_service
        self._market_data_service = market_data_service
        self._regime_service = regime_service
        self._selection_service = selection_service
        self._trading_service = trading_service

    def run(
        self,
        trade_date: date,
        market_codes: list[str] | None = None,
        *,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> JobRunResult:
        requested_codes = market_codes or ['ALL']
        log_event(
            logger,
            'orchestrator.run.started',
            trade_date=trade_date.isoformat(),
            market_codes=requested_codes,
        )
        markets = self._refdata_service.sync_markets()
        self._emit_progress(
            progress_callback,
            trade_date=trade_date,
            market_codes=requested_codes,
            current_step='sync_refdata',
            synced_markets=len(markets),
        )
        resolved_market_codes = self._resolve_market_codes(markets, requested_codes)
        features = self._load_existing_features(trade_date, resolved_market_codes)
        if len(features) != len(resolved_market_codes):
            features = self._market_data_service.ingest_daily(
                trade_date=trade_date,
                market_codes=requested_codes,
            )
        self._emit_progress(
            progress_callback,
            trade_date=trade_date,
            market_codes=requested_codes,
            current_step='ingest_market_bars',
            synced_markets=len(markets),
            computed_features=len(features),
        )
        snapshots = self._load_existing_snapshots(trade_date, resolved_market_codes)
        if len(snapshots) != len(resolved_market_codes):
            snapshots = self._regime_service.run_daily(
                trade_date=trade_date,
                market_codes=requested_codes,
            )
        self._emit_progress(
            progress_callback,
            trade_date=trade_date,
            market_codes=requested_codes,
            current_step='run_regime',
            synced_markets=len(markets),
            computed_features=len(features),
            computed_regimes=len(snapshots),
        )
        tracked_bull_snapshots = self._regime_service.list_tracked_bull()
        tracked_market_codes = [snapshot.market_code for snapshot in tracked_bull_snapshots if snapshot.market_code in resolved_market_codes]
        background_market_codes = [market_code for market_code in resolved_market_codes if market_code not in set(tracked_market_codes)]
        regime_trade_date = max((snapshot.trade_date for snapshot in tracked_bull_snapshots if snapshot.market_code in resolved_market_codes), default=trade_date)
        inventory_rows = self._selection_service.sync_market_universe_inventory(
            trade_date=trade_date,
            market_codes=resolved_market_codes,
            replace_market_codes=resolved_market_codes,
        )
        self._emit_progress(
            progress_callback,
            trade_date=trade_date,
            market_codes=requested_codes,
            current_step='sync_stock_universe_inventory',
            synced_markets=len(markets),
            computed_features=len(features),
            computed_regimes=len(snapshots),
            tracked_market_count=len(tracked_market_codes),
            universe_count=len(inventory_rows),
        )
        prepared_hot_themes = self._selection_service.prepare_hot_themes(
            trade_date=trade_date,
            market_codes=tracked_market_codes,
            replace_market_codes=tracked_market_codes,
        )
        self._emit_progress(
            progress_callback,
            trade_date=trade_date,
            market_codes=requested_codes,
            current_step='prepare_hot_themes',
            synced_markets=len(markets),
            computed_features=len(features),
            computed_regimes=len(snapshots),
            tracked_market_count=len(tracked_market_codes),
            universe_count=len(inventory_rows),
            heat_snapshot_count=len(prepared_hot_themes),
        )
        candidates, watchlist = self._selection_service.run_daily_selection(
            trade_date=trade_date,
            market_codes=tracked_market_codes,
            replace_market_codes=tracked_market_codes,
            regime_trade_date=regime_trade_date,
            prepared_heat_snapshots=prepared_hot_themes,
        )
        self._emit_progress(
            progress_callback,
            trade_date=trade_date,
            market_codes=requested_codes,
            current_step='run_daily_selection',
            synced_markets=len(markets),
            computed_features=len(features),
            computed_regimes=len(snapshots),
            tracked_market_count=len(tracked_market_codes),
            universe_count=len(inventory_rows),
            heat_snapshot_count=len(prepared_hot_themes),
            selected_candidates=len(candidates),
            watchlist_count=len(watchlist),
        )
        signals, orders, positions = self._trading_service.run_daily(
            trade_date=trade_date,
            watchlist=watchlist,
        )
        self._emit_progress(
            progress_callback,
            trade_date=trade_date,
            market_codes=requested_codes,
            current_step='run_paper_trading',
            synced_markets=len(markets),
            computed_features=len(features),
            computed_regimes=len(snapshots),
            tracked_market_count=len(tracked_market_codes),
            universe_count=len(inventory_rows),
            heat_snapshot_count=len(prepared_hot_themes),
            selected_candidates=len(candidates),
            watchlist_count=len(watchlist),
            generated_signals=len(signals),
            executed_orders=len(orders),
            open_positions=len(positions),
        )
        result = JobRunResult(
            trade_date=trade_date,
            market_codes=requested_codes,
            synced_markets=len(markets),
            computed_features=len(features),
            computed_regimes=len(snapshots),
            selected_candidates=len(candidates),
            watchlist_count=len(watchlist),
            generated_signals=len(signals),
            executed_orders=len(orders),
            open_positions=len(positions),
            steps=[
                JobStepResult(name='sync_refdata', processed_count=len(markets)),
                JobStepResult(
                    name='ingest_market_bars',
                    processed_count=len(features),
                    source_mode=self._market_data_service.source_mode,
                ),
                JobStepResult(name='run_regime', processed_count=len(snapshots)),
                JobStepResult(
                    name='sync_stock_universe_inventory',
                    processed_count=len(inventory_rows),
                    source_mode=self._selection_service.source_mode,
                ),
                JobStepResult(
                    name='prepare_hot_themes',
                    processed_count=len(prepared_hot_themes),
                    source_mode=self._selection_service.source_mode,
                ),
                JobStepResult(
                    name='run_daily_selection',
                    processed_count=len(candidates),
                    source_mode=self._selection_service.source_mode,
                ),
                JobStepResult(
                    name='run_paper_trading',
                    processed_count=len(orders),
                    source_mode=self._trading_service.source_mode,
                ),
            ],
        )
        log_event(
            logger,
            'orchestrator.run.completed',
            trade_date=trade_date.isoformat(),
            market_codes=requested_codes,
            tracked_market_codes=tracked_market_codes,
            background_market_codes=background_market_codes,
            tracked_regime_trade_date=regime_trade_date.isoformat(),
            synced_markets=result.synced_markets,
            computed_features=result.computed_features,
            computed_regimes=result.computed_regimes,
            selected_candidates=result.selected_candidates,
            watchlist_count=result.watchlist_count,
            generated_signals=result.generated_signals,
            executed_orders=result.executed_orders,
            open_positions=result.open_positions,
        )
        return result

    @staticmethod
    def _resolve_market_codes(markets, requested_codes: list[str]) -> list[str]:
        if requested_codes == ['ALL']:
            return [market.market_code for market in markets]
        wanted = set(requested_codes)
        return [market.market_code for market in markets if market.market_code in wanted]

    def _load_existing_features(self, trade_date: date, market_codes: list[str]):
        features = []
        for market_code in market_codes:
            feature = self._market_data_service.get_feature(market_code, trade_date)
            if feature is None:
                return []
            features.append(feature)
        return features

    @staticmethod
    def _emit_progress(
        progress_callback: Callable[[dict], None] | None,
        **payload,
    ) -> None:
        if progress_callback is None:
            return
        progress_callback(payload)

    def _load_existing_snapshots(self, trade_date: date, market_codes: list[str]):
        snapshots = []
        for market_code in market_codes:
            snapshot = self._regime_service.get_snapshot(market_code, trade_date)
            if snapshot is None:
                return []
            snapshots.append(snapshot)
        return snapshots
