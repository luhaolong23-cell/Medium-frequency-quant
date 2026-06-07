import os
from functools import lru_cache
from pathlib import Path

from packages.shared.contracts import FeatureBuilder, MarketDataProvider, PositionDataProvider, SelectionDataProvider
from packages.shared.orchestrator import DailyRunOrchestrator
from packages.shared.data_source_agent import DataSourceAgentService
from packages.shared.runtime import project_root
from packages.shared.theme_agent import ThemeStrategyAgentService
from packages.shared.settings import (
    RuntimeConfig,
    load_data_sources_config,
    load_local_industry_indices_config,
    load_markets_config,
    load_regime_rules_config,
    load_runtime_config,
    load_selection_rules_config,
    load_trading_rules_config,
)
from services.market_data_service.app.application.use_cases import MarketDataService
from services.market_data_service.app.infra.provider import (
    CompositeMarketDataProvider,
    MockMarketDataProvider,
    ObservationFeatureBuilder,
    YFinanceMarketDataProvider,
    YahooFinanceMarketDataProvider,
)
from services.market_data_service.app.infra.repository import (
    InMemoryMarketDataRepository,
    SqliteMarketDataRepository,
)
from services.refdata_service.app.application.use_cases import RefdataService
from services.refdata_service.app.infra.repository import (
    InMemoryRefdataRepository,
    SqliteRefdataRepository,
)
from services.regime_service.app.application.use_cases import RegimeService
from services.regime_service.app.infra.repository import (
    InMemoryRegimeRepository,
    SqliteRegimeRepository,
)
from services.selection_service.app.application.use_cases import SelectionService
from services.selection_service.app.infra.provider import (
    CompositeSelectionDataProvider,
    MockSelectionDataProvider,
    MockSelectionSeedProvider,
    YFinanceBullSeedProvider,
    YFinanceSelectionDataProvider,
    YahooSelectionDataProvider,
)
from services.selection_service.app.infra.repository import InMemorySelectionRepository, SqliteSelectionRepository
from services.trading_service.app.application.use_cases import TradingService
from services.trading_service.app.infra.provider import (
    CompositePositionDataProvider,
    MockPositionDataProvider,
    YFinancePositionDataProvider,
    YahooPositionDataProvider,
)
from services.trading_service.app.infra.repository import InMemoryTradingRepository, SqliteTradingRepository


class AppContainer:
    def __init__(
        self,
        *,
        market_data_provider: MarketDataProvider | None = None,
        selection_data_provider: SelectionDataProvider | None = None,
        position_data_provider: PositionDataProvider | None = None,
        feature_builder: FeatureBuilder | None = None,
        runtime_config: RuntimeConfig | None = None,
        storage_backend: str | None = None,
        sqlite_path: Path | None = None,
        provider_mode: str | None = None,
    ) -> None:
        root = project_root()
        self.markets_config = load_markets_config(root / 'configs' / 'markets.yaml')
        self.local_industry_indices_config = load_local_industry_indices_config(root / 'configs' / 'local_industry_indices.yaml')
        self.data_sources_path = self._resolve_data_sources_path(root)
        self.data_sources_config = load_data_sources_config(self.data_sources_path)
        self.regime_rules_config = load_regime_rules_config(root / 'configs' / 'regime_rules.yaml')
        self.selection_rules_config = load_selection_rules_config(root / 'configs' / 'selection_rules.yaml')
        self.trading_rules_config = load_trading_rules_config(root / 'configs' / 'trading_rules.yaml')
        self.runtime_config = self._resolve_runtime_config(
            root=root,
            runtime_config=runtime_config,
            storage_backend=storage_backend,
            sqlite_path=sqlite_path,
            provider_mode=provider_mode,
        )

        self.refdata_repository = self._build_refdata_repository()
        self.market_data_repository = self._build_market_data_repository()
        self.regime_repository = self._build_regime_repository()
        self.selection_repository = self._build_selection_repository()
        self.trading_repository = self._build_trading_repository()
        self.market_data_provider = market_data_provider or self._build_market_data_provider()
        self.selection_data_provider = selection_data_provider or self._build_selection_data_provider()
        self.stock_seed_provider = self._build_stock_seed_provider()
        self.position_data_provider = position_data_provider or self._build_position_data_provider()
        self.feature_builder = feature_builder or ObservationFeatureBuilder()
        self.theme_strategy_agent_service = self._build_theme_strategy_agent_service()
        self.data_source_agent_service = self._build_data_source_agent_service()

        self.refdata_service = RefdataService(
            config=self.markets_config,
            repository=self.refdata_repository,
        )
        self.market_data_service = MarketDataService(
            market_repository=self.refdata_repository,
            market_data_provider=self.market_data_provider,
            feature_builder=self.feature_builder,
            feature_repository=self.market_data_repository,
        )
        self.regime_service = RegimeService(
            rules=self.regime_rules_config,
            feature_repository=self.market_data_repository,
            snapshot_repository=self.regime_repository,
        )
        self.selection_service = SelectionService(
            markets_config=self.markets_config,
            seed_provider=self.stock_seed_provider,
            rules_config=self.selection_rules_config,
            data_provider=self.selection_data_provider,
            metadata_repository=self.selection_repository,
            seed_pool_repository=self.selection_repository,
            candidate_repository=self.selection_repository,
            watchlist_repository=self.selection_repository,
            heat_repository=self.selection_repository,
            universe_repository=self.selection_repository,
            bar_repository=self.selection_repository,
        )
        self.trading_service = TradingService(
            rules=self.trading_rules_config,
            signal_repository=self.trading_repository,
            order_repository=self.trading_repository,
            position_repository=self.trading_repository,
            position_data_provider=self.position_data_provider,
        )
        self.orchestrator = DailyRunOrchestrator(
            refdata_service=self.refdata_service,
            market_data_service=self.market_data_service,
            regime_service=self.regime_service,
            selection_service=self.selection_service,
            trading_service=self.trading_service,
        )

    def _resolve_runtime_config(
        self,
        *,
        root: Path,
        runtime_config: RuntimeConfig | None,
        storage_backend: str | None,
        sqlite_path: Path | None,
        provider_mode: str | None,
    ) -> RuntimeConfig:
        resolved = runtime_config or load_runtime_config(root)
        if storage_backend is None and sqlite_path is None and provider_mode is None:
            return resolved
        update_payload = resolved.model_dump()
        if storage_backend is not None:
            update_payload['storage_backend'] = storage_backend
        if sqlite_path is not None:
            update_payload['sqlite_path'] = Path(sqlite_path)
        if provider_mode is not None:
            update_payload['market_data_provider'] = provider_mode
        return RuntimeConfig.model_validate(update_payload)

    def _build_refdata_repository(self):
        if self.runtime_config.storage_backend == 'sqlite':
            return SqliteRefdataRepository(self.runtime_config.sqlite_path)
        return InMemoryRefdataRepository()

    def _build_market_data_repository(self):
        if self.runtime_config.storage_backend == 'sqlite':
            return SqliteMarketDataRepository(self.runtime_config.sqlite_path)
        return InMemoryMarketDataRepository()

    def _build_regime_repository(self):
        if self.runtime_config.storage_backend == 'sqlite':
            return SqliteRegimeRepository(self.runtime_config.sqlite_path)
        return InMemoryRegimeRepository()

    def _build_selection_repository(self):
        if self.runtime_config.storage_backend == 'sqlite':
            return SqliteSelectionRepository(self.runtime_config.sqlite_path)
        return InMemorySelectionRepository()

    def _build_trading_repository(self):
        if self.runtime_config.storage_backend == 'sqlite':
            return SqliteTradingRepository(self.runtime_config.sqlite_path)
        return InMemoryTradingRepository()

    def _build_market_data_provider(self) -> MarketDataProvider:
        if self.runtime_config.market_data_provider == 'composite':
            return CompositeMarketDataProvider(self._build_market_data_provider_sequence())
        if self.runtime_config.market_data_provider == 'yfinance':
            return self._build_yfinance_market_data_provider()
        if self.runtime_config.market_data_provider == 'yahoo':
            return self._build_yahoo_market_data_provider()
        return MockMarketDataProvider()

    def _build_selection_data_provider(self) -> SelectionDataProvider:
        if self.runtime_config.market_data_provider == 'composite':
            return CompositeSelectionDataProvider(self._build_selection_data_provider_sequence())
        if self.runtime_config.market_data_provider == 'yfinance':
            return self._build_yfinance_selection_data_provider()
        if self.runtime_config.market_data_provider == 'yahoo':
            return self._build_yahoo_selection_data_provider()
        return MockSelectionDataProvider()

    def _build_stock_seed_provider(self):
        if self.runtime_config.market_data_provider == 'mock':
            return MockSelectionSeedProvider(self.markets_config)
        return YFinanceBullSeedProvider(
            markets_config=self.markets_config,
            discovery_config=self.selection_rules_config.seed_discovery,
            local_industry_indices_config=self.local_industry_indices_config,
        )

    def _build_theme_strategy_agent_service(self) -> ThemeStrategyAgentService:
        return ThemeStrategyAgentService(markets_config=self.markets_config)

    def _build_data_source_agent_service(self) -> DataSourceAgentService:
        return DataSourceAgentService(config_path=self.data_sources_path)

    def _resolve_data_sources_path(self, root: Path) -> Path:
        raw_path = os.getenv('QUANT_DATA_SOURCES_PATH')
        if not raw_path:
            return root / 'configs' / 'data_sources.yaml'
        candidate = Path(raw_path)
        return candidate if candidate.is_absolute() else root / candidate

    def _build_position_data_provider(self) -> PositionDataProvider:
        if self.runtime_config.market_data_provider == 'composite':
            return CompositePositionDataProvider(self._build_position_data_provider_sequence())
        if self.runtime_config.market_data_provider == 'yfinance':
            return self._build_yfinance_position_data_provider()
        if self.runtime_config.market_data_provider == 'yahoo':
            return self._build_yahoo_position_data_provider()
        return MockPositionDataProvider()

    def _build_market_data_provider_sequence(self) -> list[MarketDataProvider]:
        providers: list[MarketDataProvider] = []
        for source_name in self._resolve_market_bar_sources():
            provider = self._named_market_data_provider(source_name)
            if provider is not None:
                providers.append(provider)
        if not providers:
            providers.append(MockMarketDataProvider())
        return providers

    def _build_selection_data_provider_sequence(self) -> list[SelectionDataProvider]:
        providers: list[SelectionDataProvider] = []
        for source_name in self._resolve_market_bar_sources():
            provider = self._named_selection_data_provider(source_name)
            if provider is not None:
                providers.append(provider)
        if not providers:
            providers.append(MockSelectionDataProvider())
        return providers

    def _build_position_data_provider_sequence(self) -> list[PositionDataProvider]:
        providers: list[PositionDataProvider] = []
        for source_name in self._resolve_market_bar_sources():
            provider = self._named_position_data_provider(source_name)
            if provider is not None:
                providers.append(provider)
        if not providers:
            providers.append(MockPositionDataProvider())
        return providers

    def _resolve_market_bar_sources(self) -> list[str]:
        source_config = self.data_sources_config.sources.get('market_bars')
        if source_config is None:
            return ['mock']
        names = [source_config.primary, source_config.fallback, source_config.backup]
        ordered: list[str] = []
        for name in names:
            if name is None or name in ordered:
                continue
            ordered.append(name)
        return ordered

    def _named_market_data_provider(self, source_name: str) -> MarketDataProvider | None:
        if source_name == 'yfinance':
            return self._build_yfinance_market_data_provider()
        if source_name == 'yahoo':
            return self._build_yahoo_market_data_provider()
        if source_name == 'mock':
            return MockMarketDataProvider()
        return None

    def _named_selection_data_provider(self, source_name: str) -> SelectionDataProvider | None:
        if source_name == 'yfinance':
            return self._build_yfinance_selection_data_provider()
        if source_name == 'yahoo':
            return self._build_yahoo_selection_data_provider()
        if source_name == 'mock':
            return MockSelectionDataProvider()
        return None

    def _named_position_data_provider(self, source_name: str) -> PositionDataProvider | None:
        if source_name == 'yfinance':
            return self._build_yfinance_position_data_provider()
        if source_name == 'yahoo':
            return self._build_yahoo_position_data_provider()
        if source_name == 'mock':
            return MockPositionDataProvider()
        return None

    def _build_yahoo_market_data_provider(self) -> YahooFinanceMarketDataProvider:
        return YahooFinanceMarketDataProvider(
            data_sources_config=self.data_sources_config,
            chart_base_url=self.runtime_config.yahoo_chart_base_url,
            world_benchmark_symbol=self.runtime_config.yahoo_world_benchmark_symbol,
            allow_mock_fallback=self.runtime_config.allow_mock_provider_fallback,
        )

    def _build_yfinance_market_data_provider(self) -> YFinanceMarketDataProvider:
        return YFinanceMarketDataProvider(
            data_sources_config=self.data_sources_config,
            world_benchmark_symbol=self.runtime_config.yahoo_world_benchmark_symbol,
            allow_mock_fallback=self.runtime_config.allow_mock_provider_fallback,
        )

    def _build_yahoo_selection_data_provider(self) -> YahooSelectionDataProvider:
        return YahooSelectionDataProvider(
            data_sources_config=self.data_sources_config,
            chart_base_url=self.runtime_config.yahoo_chart_base_url,
            allow_mock_fallback=self.runtime_config.allow_mock_provider_fallback,
        )

    def _build_yfinance_selection_data_provider(self) -> YFinanceSelectionDataProvider:
        return YFinanceSelectionDataProvider(
            data_sources_config=self.data_sources_config,
            allow_mock_fallback=self.runtime_config.allow_mock_provider_fallback,
        )

    def _build_yahoo_position_data_provider(self) -> YahooPositionDataProvider:
        return YahooPositionDataProvider(
            data_sources_config=self.data_sources_config,
            chart_base_url=self.runtime_config.yahoo_chart_base_url,
            allow_mock_fallback=self.runtime_config.allow_mock_provider_fallback,
        )

    def _build_yfinance_position_data_provider(self) -> YFinancePositionDataProvider:
        return YFinancePositionDataProvider(
            data_sources_config=self.data_sources_config,
            allow_mock_fallback=self.runtime_config.allow_mock_provider_fallback,
        )


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    return AppContainer()


def reset_container() -> None:
    get_container.cache_clear()
