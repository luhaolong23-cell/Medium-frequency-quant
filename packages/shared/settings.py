import os
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from packages.shared.config import load_yaml


class ProxySettings(BaseModel):
    symbol: str
    proxy_type: str
    exchange_code: str
    currency: str
    priority: int


class MarketSettings(BaseModel):
    market_code: str
    market_name: str
    country_code: str
    region: str
    proxies: list[ProxySettings]


class MarketsConfig(BaseModel):
    markets: list[MarketSettings]


class LocalIndustryIndexSettings(BaseModel):
    local_code: str
    name: str
    level: str
    official_code: str | None = None
    proxy_symbol: str | None = None
    match_industries: list[str] = Field(default_factory=list)
    match_sectors: list[str] = Field(default_factory=list)
    notes: str | None = None


class LocalIndustryIndexFamilySettings(BaseModel):
    family_code: str
    family_name: str
    provider_name: str
    provider_type: str
    source_url: str
    coverage: str
    classification_standard: str
    granularity: str
    implementation_priority: str = 'medium'
    notes: str | None = None
    indices: list[LocalIndustryIndexSettings] = Field(default_factory=list)


class MarketLocalIndustryCatalogSettings(BaseModel):
    market_code: str
    market_name: str
    status: Literal['ready', 'partial', 'researching']
    recommended_primary_family: str
    benchmark_name: str
    benchmark_symbol: str | None = None
    source_notes: str | None = None
    families: list[LocalIndustryIndexFamilySettings] = Field(default_factory=list)


class LocalIndustryIndicesConfig(BaseModel):
    markets: list[MarketLocalIndustryCatalogSettings]


class SourceSettings(BaseModel):
    primary: str
    fallback: str | None = None
    backup: str | None = None


class TimeoutsSettings(BaseModel):
    connect_seconds: int
    read_seconds: int


class RetrySettings(BaseModel):
    max_attempts: int
    backoff_seconds: int


class DataSourcesConfig(BaseModel):
    sources: dict[str, SourceSettings]
    timeouts: TimeoutsSettings
    retry: RetrySettings


class ThresholdsConfig(BaseModel):
    bull_min_score: float
    neutral_min_score: float


class WeightsConfig(BaseModel):
    policy_breakout: float
    trend_persistence: float
    recovery_reversal: float
    global_leader: float


class TrendConfig(BaseModel):
    ma_fast: int = 5
    ma_medium: int = 10
    ma_base: int = 20
    ma_long: int = 60


class RiskConfig(BaseModel):
    vol_window: int = 20
    drawdown_window: int = 60


class MarketIndicatorConfig(BaseModel):
    single_day_turnover_ratio_strong: float
    single_day_return_strong: float
    single_day_turnover_ratio_medium: float
    single_day_return_medium: float
    single_day_turnover_ratio_basic: float
    consecutive_volume_days_strong: int
    consecutive_volume_avg_ratio_strong: float
    consecutive_volume_days_medium: int
    consecutive_volume_avg_ratio_medium: float
    consecutive_volume_days_basic: int
    policy_window_days_strong: int
    policy_window_days_medium: int
    policy_window_days_basic: int
    trend_persistence_min_ret_60d: float
    trend_persistence_min_ret_120d: float
    trend_persistence_min_relative_strength: float
    recovery_reversal_min_ret_5d: float
    recovery_reversal_min_turnover_ratio_20d: float
    recovery_reversal_min_avg_turnover_ratio_3d: float
    recovery_reversal_min_consecutive_up_weeks: int
    global_leader_min_ret_120d: float
    global_leader_min_relative_strength: float
    global_leader_max_drawdown_60d: float
    policy_events: dict[str, list[date]] = Field(default_factory=dict)


class ExplanationsConfig(BaseModel):
    include_flags: bool = True


class RegimeRulesConfig(BaseModel):
    rule_version: str
    thresholds: ThresholdsConfig
    weights: WeightsConfig
    trend: TrendConfig
    risk: RiskConfig
    indicators: MarketIndicatorConfig
    explanations: ExplanationsConfig


class AppSettings(BaseModel):
    name: str
    env: str
    timezone: str


class ApiGatewaySettings(BaseModel):
    host: str
    port: int


class SchedulerJobsSettings(BaseModel):
    sync_refdata_hour: int
    ingest_market_bars_hour: int
    run_regime_hour: int
    run_regime_day_of_week: str = 'mon'
    sync_stock_universe_inventory_hour: int
    sync_stock_universe_inventory_day_of_week: str = 'mon'
    prepare_hot_themes_hour: int
    prepare_hot_themes_interval_days: int = 3
    sync_stock_universe_bars_hour: int
    compute_stock_universe_metrics_hour: int
    run_stock_selection_hour: int
    run_position_monitor_hour: int
    sync_background_universe_inventory_hour: int


class SchedulerSettings(BaseModel):
    timezone: str
    jobs: SchedulerJobsSettings


class AppConfig(BaseModel):
    app: AppSettings
    api_gateway: ApiGatewaySettings
    scheduler: SchedulerSettings


class DailyRankingWeightsConfig(BaseModel):
    theme: float
    lagging: float
    trend_recovery: float
    momentum_acceleration: float
    volume_probe: float
    risk_control: float


class DailyRankingConfig(BaseModel):
    min_price: float
    min_avg_dollar_volume_20d: float
    min_volume_ratio_3d: float
    max_distance_to_60d_high: float
    max_vol_20d: float
    min_composite_score: float
    min_ret_5d: float = 0.01
    max_ret_5d: float = 0.08
    max_ret_20d: float = 0.15
    min_ma20_to_ma60_ratio: float = 0.98
    min_momentum_acceleration: float = 0.0
    min_volume_up_days_5d: int = 2
    max_close_to_ma20_extension: float = 0.12
    watchlist_size: int = 5
    weights: DailyRankingWeightsConfig


class SeedDiscoveryConfig(BaseModel):
    enabled: bool = False
    max_candidates_per_market: int = 25
    max_scan_pages_per_market: int = 8
    universe_page_size: int = 100
    max_universe_pages_per_market: int = 20
    max_selected_per_market: int = 10
    history_batch_size: int = 50
    history_full_period: str = '30mo'
    history_incremental_period: str = '3mo'
    min_market_cap: float = 3_000_000_000
    max_market_cap: float = 10_000_000_000
    max_price_position_ratio: float = 0.35
    heat_top_industries: int = 5
    heat_top_sectors: int = 3
    heat_min_constituents: int = 2
    heat_lookback_days: int = 3
    fixed_hot_theme_names: list[str] = Field(default_factory=lambda: ['光伏', '半导体', '电力', '芯片', '航天'])


class SelectionRulesConfig(BaseModel):
    daily_ranking: DailyRankingConfig
    seed_discovery: SeedDiscoveryConfig = Field(default_factory=SeedDiscoveryConfig)


class TradingSignalConfig(BaseModel):
    min_volume_ratio_5d: float


class TradingExitConfig(BaseModel):
    max_drawdown_from_peak_pct: float
    consecutive_shrink_down_days: int


class TradingExecutionConfig(BaseModel):
    fixed_order_amount: float
    quantity_precision: int = 4


class TradingRulesConfig(BaseModel):
    signal: TradingSignalConfig
    exit: TradingExitConfig
    execution: TradingExecutionConfig


class RuntimeConfig(BaseModel):
    storage_backend: Literal["memory", "sqlite"] = "memory"
    sqlite_path: Path
    market_data_provider: Literal["mock", "yahoo", "yfinance", "composite"] = "yfinance"
    yahoo_chart_base_url: str = "https://query1.finance.yahoo.com"
    yahoo_world_benchmark_symbol: str = "ACWI"
    allow_mock_provider_fallback: bool = False


def load_markets_config(path: Path) -> MarketsConfig:
    return MarketsConfig.model_validate(load_yaml(path))


def load_local_industry_indices_config(path: Path) -> LocalIndustryIndicesConfig:
    return LocalIndustryIndicesConfig.model_validate(load_yaml(path))


def load_data_sources_config(path: Path) -> DataSourcesConfig:
    return DataSourcesConfig.model_validate(load_yaml(path))


def load_regime_rules_config(path: Path) -> RegimeRulesConfig:
    return RegimeRulesConfig.model_validate(load_yaml(path))


def load_app_config(path: Path) -> AppConfig:
    return AppConfig.model_validate(load_yaml(path))


def load_selection_rules_config(path: Path) -> SelectionRulesConfig:
    return SelectionRulesConfig.model_validate(load_yaml(path))


def load_trading_rules_config(path: Path) -> TradingRulesConfig:
    return TradingRulesConfig.model_validate(load_yaml(path))


def load_runtime_config(project_root: Path) -> RuntimeConfig:
    raw_sqlite_path = Path(os.getenv("QUANT_SQLITE_PATH", "data/quant-platform.sqlite3"))
    sqlite_path = raw_sqlite_path if raw_sqlite_path.is_absolute() else project_root / raw_sqlite_path
    return RuntimeConfig(
        storage_backend=os.getenv("QUANT_STORAGE_BACKEND", "memory"),
        sqlite_path=sqlite_path,
        market_data_provider=os.getenv("QUANT_MARKET_DATA_PROVIDER", "yfinance"),
        yahoo_chart_base_url=os.getenv("QUANT_YAHOO_CHART_BASE_URL", "https://query1.finance.yahoo.com"),
        yahoo_world_benchmark_symbol=os.getenv("QUANT_WORLD_BENCHMARK_SYMBOL", "ACWI"),
        allow_mock_provider_fallback=_parse_bool(os.getenv("QUANT_ALLOW_MOCK_PROVIDER_FALLBACK"), default=False),
    )


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
