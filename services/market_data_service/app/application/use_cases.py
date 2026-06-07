from __future__ import annotations

from datetime import date

from packages.domain_core.market.entities import MarketFeature
from packages.shared.contracts import (
    FeatureBuilder,
    MarketDataProvider,
    MarketFeatureRepository,
    MarketRepository,
)
from packages.shared.logging import get_logger, log_event


logger = get_logger(__name__)


class MarketDataService:
    def __init__(
        self,
        market_repository: MarketRepository,
        market_data_provider: MarketDataProvider,
        feature_builder: FeatureBuilder,
        feature_repository: MarketFeatureRepository,
    ) -> None:
        self._market_repository = market_repository
        self._market_data_provider = market_data_provider
        self._feature_builder = feature_builder
        self._feature_repository = feature_repository

    @property
    def source_mode(self) -> str:
        return getattr(self._market_data_provider, "source_mode", "unknown")

    def ingest_daily(self, trade_date: date, market_codes: list[str]) -> list[MarketFeature]:
        markets = self._resolve_markets(market_codes)
        observations, failed_market_codes = self._fetch_observations_with_tolerance(markets=markets, trade_date=trade_date)
        features = [self._feature_builder.build(observation) for observation in observations]
        self._feature_repository.upsert_features(features)
        log_event(
            logger,
            'market_data.ingest_daily.completed',
            trade_date=trade_date.isoformat(),
            requested_market_codes=market_codes,
            resolved_market_codes=[market.market_code for market in markets],
            failed_market_codes=failed_market_codes,
            source_mode=self.source_mode,
            processed_count=len(features),
            features=[
                {
                    'market_code': feature.market_code,
                    'price_proxy': feature.price_proxy,
                    'close': round(feature.close, 4),
                    'volume_ratio_5d': round(feature.volume_ratio_5d, 4),
                    'consecutive_up_weeks': feature.consecutive_up_weeks,
                    'source': feature.source,
                }
                for feature in features
            ],
        )
        return features

    def get_feature(self, market_code: str, trade_date: date) -> MarketFeature | None:
        return self._feature_repository.get_feature(
            market_code=market_code,
            trade_date=trade_date,
        )

    def get_latest_feature(self, market_code: str) -> MarketFeature | None:
        return self._feature_repository.get_latest_feature(market_code=market_code)

    def _resolve_markets(self, market_codes: list[str]):
        markets = self._market_repository.list_markets()
        if market_codes == ["ALL"]:
            return markets
        wanted = set(market_codes)
        return [market for market in markets if market.market_code in wanted]

    def _fetch_observations_with_tolerance(self, *, markets, trade_date: date):
        try:
            return self._market_data_provider.fetch_daily(markets=markets, trade_date=trade_date), []
        except Exception:
            if len(markets) <= 1:
                raise

        observations = []
        failed_market_codes: list[str] = []
        for market in markets:
            try:
                market_observations = self._market_data_provider.fetch_daily(markets=[market], trade_date=trade_date)
                observations.extend(market_observations)
            except Exception as exc:  # noqa: BLE001
                failed_market_codes.append(market.market_code)
                log_event(
                    logger,
                    'market_data.ingest_daily.market_failed',
                    trade_date=trade_date.isoformat(),
                    market_code=market.market_code,
                    source_mode=self.source_mode,
                    error=str(exc),
                )
        return observations, failed_market_codes
