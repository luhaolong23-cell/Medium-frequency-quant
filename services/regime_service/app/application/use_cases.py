from datetime import date

from packages.domain_core.market.entities import RegimeSnapshot
from packages.domain_core.market.rules import build_regime_snapshot
from packages.shared.contracts import MarketFeatureRepository, RegimeSnapshotRepository
from packages.shared.logging import get_logger, log_event
from packages.shared.settings import RegimeRulesConfig


logger = get_logger(__name__)


class RegimeService:
    def __init__(
        self,
        rules: RegimeRulesConfig,
        feature_repository: MarketFeatureRepository,
        snapshot_repository: RegimeSnapshotRepository,
    ) -> None:
        self._rules = rules
        self._feature_repository = feature_repository
        self._snapshot_repository = snapshot_repository

    def run_daily(self, trade_date: date, market_codes: list[str]) -> list[RegimeSnapshot]:
        features = self._feature_repository.list_features(trade_date)
        if market_codes != ["ALL"]:
            wanted = set(market_codes)
            features = [feature for feature in features if feature.market_code in wanted]
        snapshots = [
            self._apply_incremental_bull_policy(
                build_regime_snapshot(
                    feature=feature,
                    weights=self._rules.weights.model_dump(),
                    thresholds=self._rules.thresholds.model_dump(),
                    indicators=self._rules.indicators.model_dump(),
                    rule_version=self._rules.rule_version,
                )
            )
            for feature in features
        ]
        self._snapshot_repository.upsert_snapshots(snapshots)
        bull_markets = [snapshot.market_code for snapshot in snapshots if snapshot.regime_status == 'BULL']
        log_event(
            logger,
            'regime.run_daily.completed',
            trade_date=trade_date.isoformat(),
            requested_market_codes=market_codes,
            processed_count=len(snapshots),
            bull_count=len(bull_markets),
            bull_market_codes=bull_markets,
            snapshots=[
                {
                    'market_code': snapshot.market_code,
                    'regime_status': snapshot.regime_status,
                    'bull_score': snapshot.bull_score,
                    'trigger_flags': snapshot.trigger_flags,
                }
                for snapshot in snapshots
            ],
        )
        return snapshots

    def _apply_incremental_bull_policy(self, snapshot: RegimeSnapshot) -> RegimeSnapshot:
        latest = self._snapshot_repository.get_latest_snapshot(snapshot.market_code)
        current_rule_version = self._rules.rule_version
        latest_rule_version = latest.source_used.get('rule_version') if latest is not None else None
        if latest is None or latest.regime_status != 'BULL' or latest_rule_version != current_rule_version or snapshot.regime_status == 'BULL':
            return snapshot
        source_used = dict(latest.source_used)
        source_used.update(snapshot.source_used)
        source_used['incremental_bull_lock'] = 'true'
        source_used['previous_bull_trade_date'] = latest.trade_date.isoformat()
        source_used['incremental_bull_lock_reason'] = 'existing_bull_markets_do_not_downgrade'
        return RegimeSnapshot(
            market_code=snapshot.market_code,
            trade_date=snapshot.trade_date,
            regime_status='BULL',
            bull_score=snapshot.bull_score,
            trend_score=snapshot.trend_score,
            relative_strength_score=snapshot.relative_strength_score,
            risk_penalty_score=snapshot.risk_penalty_score,
            trigger_flags=snapshot.trigger_flags,
            source_used=source_used,
        )

    def list_by_date(self, trade_date: date) -> list[RegimeSnapshot]:
        return self._snapshot_repository.list_by_date(trade_date)

    def list_latest(self) -> list[RegimeSnapshot]:
        return self._snapshot_repository.list_latest()

    def get_latest_snapshot(self, market_code: str) -> RegimeSnapshot | None:
        return self._snapshot_repository.get_latest_snapshot(market_code=market_code)

    def list_tracked_bull(self) -> list[RegimeSnapshot]:
        snapshots = [
            snapshot
            for snapshot in self._snapshot_repository.list_tracked_bull()
            if snapshot.source_used.get('rule_version') == self._rules.rule_version
        ]
        log_event(
            logger,
            'regime.list_tracked_bull.completed',
            tracked_count=len(snapshots),
            tracked_markets=[
                {
                    'market_code': snapshot.market_code,
                    'entered_bull_trade_date': snapshot.trade_date.isoformat(),
                    'bull_score': snapshot.bull_score,
                }
                for snapshot in snapshots
            ],
        )
        return snapshots

    def get_snapshot(self, market_code: str, trade_date: date) -> RegimeSnapshot | None:
        return self._snapshot_repository.get_snapshot(
            market_code=market_code,
            trade_date=trade_date,
        )
