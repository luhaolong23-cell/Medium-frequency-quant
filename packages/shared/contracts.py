from datetime import date
from typing import Protocol, runtime_checkable

from packages.domain_core.market.entities import (
    Market,
    MarketFeature,
    MarketObservation,
    RegimeSnapshot,
)
from packages.domain_core.selection.entities import (
    StockCandidate,
    StockSeedSnapshot,
    StockMetadata,
    StockUniverseSnapshot,
    StockScreenObservation,
    StockSeed,
    StockWatchItem,
    ThemeHeatSnapshot,
    StockDailyBar,
)
from packages.domain_core.trading.entities import PaperOrder, PaperPosition, TradeSignal


@runtime_checkable
class MarketRepository(Protocol):
    def upsert_markets(self, markets: list[Market]) -> None: ...
    def list_markets(self) -> list[Market]: ...
    def get_market(self, market_code: str) -> Market | None: ...


@runtime_checkable
class MarketFeatureRepository(Protocol):
    def upsert_features(self, features: list[MarketFeature]) -> None: ...
    def get_feature(self, market_code: str, trade_date: date) -> MarketFeature | None: ...
    def get_latest_feature(self, market_code: str) -> MarketFeature | None: ...
    def list_features(self, trade_date: date) -> list[MarketFeature]: ...


@runtime_checkable
class RegimeSnapshotRepository(Protocol):
    def upsert_snapshots(self, snapshots: list[RegimeSnapshot]) -> None: ...
    def get_snapshot(self, market_code: str, trade_date: date) -> RegimeSnapshot | None: ...
    def get_latest_snapshot(self, market_code: str) -> RegimeSnapshot | None: ...
    def list_by_date(self, trade_date: date) -> list[RegimeSnapshot]: ...
    def list_latest(self) -> list[RegimeSnapshot]: ...
    def list_tracked_bull(self) -> list[RegimeSnapshot]: ...




@runtime_checkable
class StockSeedPoolRepository(Protocol):
    def replace_seed_pool(self, trade_date: date, market_codes: list[str], seeds: list[StockSeedSnapshot]) -> None: ...
    def list_seed_pool(self, trade_date: date, market_code: str | None = None) -> list[StockSeedSnapshot]: ...

@runtime_checkable
class StockMetadataRepository(Protocol):
    def upsert_metadata(self, metadata_rows: list[StockMetadata]) -> None: ...
    def get_metadata(self, market_code: str, ticker: str) -> StockMetadata | None: ...


@runtime_checkable
class StockUniverseRepository(Protocol):
    def replace_market_universe(self, trade_date: date, market_codes: list[str], rows: list[StockUniverseSnapshot]) -> None: ...
    def list_market_universe(self, trade_date: date, market_code: str | None = None) -> list[StockUniverseSnapshot]: ...


@runtime_checkable
class StockBarRepository(Protocol):
    def upsert_stock_bars(self, bars: list[StockDailyBar]) -> None: ...
    def list_stock_bars(self, market_code: str, ticker: str, trade_date: date | None = None) -> list[StockDailyBar]: ...
    def get_latest_stock_bar_date(self, market_code: str, ticker: str) -> date | None: ...


@runtime_checkable
class StockCandidateRepository(Protocol):
    def replace_candidates(self, trade_date: date, market_codes: list[str], candidates: list[StockCandidate]) -> None: ...
    def list_candidates(self, trade_date: date, market_code: str | None = None) -> list[StockCandidate]: ...


@runtime_checkable
class StockWatchlistRepository(Protocol):
    def replace_watchlist(self, trade_date: date, watchlist: list[StockWatchItem]) -> None: ...
    def list_watchlist(self, trade_date: date, market_code: str | None = None) -> list[StockWatchItem]: ...


@runtime_checkable
class ThemeHeatRepository(Protocol):
    def replace_heat_snapshots(self, trade_date: date, market_codes: list[str], snapshots: list[ThemeHeatSnapshot]) -> None: ...
    def list_heat_snapshots(
        self,
        trade_date: date,
        market_code: str | None = None,
        theme_type: str | None = None,
    ) -> list[ThemeHeatSnapshot]: ...


@runtime_checkable
class TradeSignalRepository(Protocol):
    def replace_signals(self, trade_date: date, signals: list[TradeSignal]) -> None: ...
    def list_signals(self, trade_date: date, market_code: str | None = None) -> list[TradeSignal]: ...


@runtime_checkable
class PaperOrderRepository(Protocol):
    def append_orders(self, orders: list[PaperOrder]) -> None: ...
    def list_orders(self, trade_date: date, market_code: str | None = None) -> list[PaperOrder]: ...


@runtime_checkable
class PaperPositionRepository(Protocol):
    def upsert_positions(self, positions: list[PaperPosition]) -> None: ...
    def list_positions(self, status: str | None = None, market_code: str | None = None) -> list[PaperPosition]: ...
    def get_position(self, market_code: str, ticker: str) -> PaperPosition | None: ...


@runtime_checkable
class MarketDataProvider(Protocol):
    def fetch_daily(self, markets: list[Market], trade_date: date) -> list[MarketObservation]: ...


@runtime_checkable
class SelectionDataProvider(Protocol):
    def fetch_daily(self, seeds: list[StockSeed], trade_date: date) -> list[StockScreenObservation]: ...


@runtime_checkable
class PositionDataProvider(Protocol):
    def fetch_history(self, ticker: str, trade_date: date) -> list[tuple[date, float, float]]: ...


@runtime_checkable
class FeatureBuilder(Protocol):
    def build(self, observation: MarketObservation) -> MarketFeature: ...
