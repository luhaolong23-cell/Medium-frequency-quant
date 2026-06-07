from __future__ import annotations
from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar('T')


class ErrorDetail(BaseModel):
    code: str
    message: str


class ApiSuccess(BaseModel, Generic[T]):
    status: Literal['success'] = 'success'
    data: T


class ApiError(BaseModel):
    status: Literal['error'] = 'error'
    error: ErrorDetail


class HealthView(BaseModel):
    status: str
    services: dict[str, str]
    market_count: int


class JobStepResult(BaseModel):
    name: str
    processed_count: int = 0
    source_mode: str | None = None


class JobRunResult(BaseModel):
    trade_date: date
    market_codes: list[str]
    synced_markets: int
    computed_features: int
    computed_regimes: int
    selected_candidates: int = 0
    watchlist_count: int = 0
    generated_signals: int = 0
    executed_orders: int = 0
    open_positions: int = 0
    status: Literal['running', 'completed', 'failed'] = 'completed'
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    steps: list[JobStepResult] = Field(default_factory=list)


class MarketRegimeView(BaseModel):
    market_code: str
    trade_date: date
    regime_status: str
    bull_score: float


class MarketOverviewView(BaseModel):
    market_code: str
    market_name: str
    country_code: str
    region: str
    trade_date: date | None = None
    regime_status: str | None = None
    bull_score: float | None = None
    is_bull: bool = False
    price_proxy: str | None = None
    close: float | None = None
    ret_1d: float | None = None
    ret_5d: float | None = None
    ret_60d: float | None = None
    ret_120d: float | None = None
    turnover_ratio_20d: float | None = None
    avg_turnover_ratio_3d: float | None = None
    volume_up_days_2d: int | None = None
    volume_up_days_3d: int | None = None
    consecutive_up_days: int | None = None
    consecutive_up_weeks: int | None = None
    relative_strength_world: float | None = None
    drawdown_60d: float | None = None
    ma_5: float | None = None
    ma_10: float | None = None
    ma_20: float | None = None
    ma_60: float | None = None
    ma_120: float | None = None
    ma_200: float | None = None
    feature_source: str | None = None
    criteria: list[MarketBullCriterionView] = Field(default_factory=list)
    passed_criteria: list[str] = Field(default_factory=list)
    failed_criteria: list[str] = Field(default_factory=list)
    decision_reason: str = ''


class MarketBullSearchRunView(BaseModel):
    trade_date: date
    processed_markets: int
    bull_market_count: int
    bull_market_codes: list[str] = Field(default_factory=list)
    source_mode: str


class StockScreenRunView(BaseModel):
    trade_date: date
    tracked_market_count: int
    tracked_market_codes: list[str] = Field(default_factory=list)
    seed_count: int
    processed_candidates: int
    watchlist_count: int
    source_mode: str


class TrackedBullMarketView(BaseModel):
    market_code: str
    entered_bull_trade_date: date
    bull_score: float
    regime_status: str


class MarketBullCriterionView(BaseModel):
    name: str
    label: str = ''
    passed: bool
    score: float = 0.0
    max_score: float = 0.0
    actual_value: float | int | bool | str | None = None
    threshold_value: float | int | bool | str | None = None
    detail: str


class MarketBullSearchItemView(BaseModel):
    market_code: str
    trade_date: date
    regime_status: str
    bull_score: float
    is_bull: bool
    included_in_tracked_bull: bool
    tracked_entry_trade_date: date | None = None
    price_proxy: str | None = None
    close: float | None = None
    avg_volume_recent: float | None = None
    avg_volume_prior: float | None = None
    ret_1d: float | None = None
    ret_5d: float | None = None
    ret_60d: float | None = None
    ret_120d: float | None = None
    turnover_ratio_20d: float | None = None
    avg_turnover_ratio_3d: float | None = None
    volume_up_days_2d: int | None = None
    volume_up_days_3d: int | None = None
    consecutive_up_days: int | None = None
    consecutive_up_weeks: int | None = None
    relative_strength_world: float | None = None
    drawdown_60d: float | None = None
    ma_5: float | None = None
    ma_10: float | None = None
    ma_20: float | None = None
    ma_60: float | None = None
    ma_120: float | None = None
    ma_200: float | None = None
    feature_source: str | None = None
    criteria: list[MarketBullCriterionView] = Field(default_factory=list)
    passed_criteria: list[str] = Field(default_factory=list)
    failed_criteria: list[str] = Field(default_factory=list)
    decision_reason: str


class MarketBullSearchProcessView(BaseModel):
    trade_date: date | None = None
    bull_market_codes: list[str] = Field(default_factory=list)
    non_bull_market_codes: list[str] = Field(default_factory=list)
    tracked_bull_market_codes: list[str] = Field(default_factory=list)
    markets: list[MarketBullSearchItemView] = Field(default_factory=list)


class WorkflowLogsSummaryView(BaseModel):
    regime_latest_trade_date: date | None = None
    latest_candidates_trade_date: date | None = None
    latest_watchlist_trade_date: date | None = None
    latest_signals_trade_date: date | None = None
    latest_orders_trade_date: date | None = None
    tracked_bull_count: int
    open_position_count: int
    latest_market_regimes: list[MarketRegimeView] = Field(default_factory=list)
    tracked_bull_markets: list[TrackedBullMarketView] = Field(default_factory=list)
    latest_candidates: list[SelectedStockView] = Field(default_factory=list)
    latest_watchlist: list[WatchlistStockView] = Field(default_factory=list)
    latest_signals: list[TradeSignalView] = Field(default_factory=list)
    latest_orders: list[PaperOrderView] = Field(default_factory=list)
    open_positions: list[PaperPositionView] = Field(default_factory=list)


class SchedulerExecutionLogView(BaseModel):
    job_name: str
    trigger_mode: Literal['manual', 'scheduled', 'startup']
    status: Literal['running', 'completed', 'failed']
    trade_date: date | None = None
    market_codes: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class SelectedStockView(BaseModel):
    market_code: str
    ticker: str
    trade_date: date
    regime_trade_date: date | None = None
    company_name: str
    sector: str
    industry: str
    close: float
    ret_5d: float
    ret_20d: float
    ret_60d: float
    ma_20: float
    ma_60: float
    avg_dollar_volume_3d: float
    avg_dollar_volume_5d: float
    avg_dollar_volume_20d: float
    volume_ratio_3d: float
    volume_ratio_5d: float
    volume_up_days_5d: int
    distance_to_60d_high: float
    momentum_acceleration: float
    vol_20d: float
    rank: int
    composite_score: float
    coarse_score: float
    theme_score: float
    lagging_score: float
    trend_recovery_score: float
    momentum_acceleration_score: float
    volume_probe_score: float
    risk_control_score: float
    valuation_band: str
    market_cap_bucket: str
    theme_tags: list[str]
    source: str


class StockUniverseView(BaseModel):
    trade_date: date
    market_code: str
    ticker: str
    company_name: str
    sector: str
    industry: str
    exchange: str
    currency: str
    country_code: str
    market_cap: float
    price: float
    price_position: float | None = None
    momentum_pct: float
    volume_ratio: float
    ret_5d: float | None = None
    ret_20d: float | None = None
    ret_60d: float | None = None
    ma_20: float | None = None
    ma_60: float | None = None
    avg_dollar_volume_3d: float | None = None
    avg_dollar_volume_20d: float | None = None
    volume_ratio_3d: float | None = None
    volume_up_days_5d: int | None = None
    distance_to_60d_high: float | None = None
    momentum_acceleration: float | None = None
    vol_20d: float | None = None
    theme_tags: list[str] = Field(default_factory=list)
    source: str


class UniverseEnrichmentRunView(BaseModel):
    trade_date: date
    market_codes: list[str] = Field(default_factory=list)
    processed_rows: int
    enriched_rows: int
    remaining_unknown_rows: int
    batch_limit: int | None = None
    batch_offset: int = 0
    source_mode: str


class WatchlistStockView(BaseModel):
    market_code: str
    ticker: str
    trade_date: date
    regime_trade_date: date | None = None
    watch_rank: int
    company_name: str
    sector: str
    industry: str
    close: float
    ret_5d: float
    ret_20d: float
    ret_60d: float
    ma_20: float
    ma_60: float
    avg_dollar_volume_3d: float
    avg_dollar_volume_5d: float
    avg_dollar_volume_20d: float
    volume_ratio_3d: float
    volume_ratio_5d: float
    volume_up_days_5d: int
    distance_to_60d_high: float
    momentum_acceleration: float
    vol_20d: float
    composite_score: float
    theme_score: float
    lagging_score: float
    trend_recovery_score: float
    momentum_acceleration_score: float
    volume_probe_score: float
    risk_control_score: float
    valuation_band: str
    market_cap_bucket: str
    theme_tags: list[str]
    source: str
    watch_reason: str


class ThemeHeatView(BaseModel):
    trade_date: date
    market_code: str
    theme_type: str
    theme_name: str
    raw_heat_score: float
    smoothed_heat_score: float
    constituent_count: int
    source: str


class LocalIndustryIndexView(BaseModel):
    local_code: str
    name: str
    level: str
    official_code: str | None = None
    proxy_symbol: str | None = None
    match_industries: list[str] = Field(default_factory=list)
    match_sectors: list[str] = Field(default_factory=list)
    notes: str | None = None


class LocalIndustryIndexFamilyView(BaseModel):
    family_code: str
    family_name: str
    provider_name: str
    provider_type: str
    source_url: str
    coverage: str
    classification_standard: str
    granularity: str
    implementation_priority: str
    notes: str | None = None
    indices: list[LocalIndustryIndexView] = Field(default_factory=list)


class MarketLocalIndustryCatalogView(BaseModel):
    market_code: str
    market_name: str
    status: str
    recommended_primary_family: str
    benchmark_name: str
    benchmark_symbol: str | None = None
    source_notes: str | None = None
    families: list[LocalIndustryIndexFamilyView] = Field(default_factory=list)


class SeedPoolView(BaseModel):
    trade_date: date
    market_code: str
    ticker: str
    company_name: str
    sector: str
    industry: str
    exchange: str
    currency: str
    country_code: str
    seed_type: str
    theme_tags: list[str]
    theme_score: float
    valuation_score: float
    size_score: float
    valuation_band: str
    market_cap_bucket: str
    seed_reason: str


class TradeSignalView(BaseModel):
    market_code: str
    ticker: str
    trade_date: date
    side: str
    signal_type: str
    triggered: bool
    signal_reason: str
    close: float
    volume_ratio_5d: float
    threshold_volume_ratio: float
    order_notional: float
    source: str


class PaperOrderView(BaseModel):
    order_id: str
    market_code: str
    ticker: str
    trade_date: date
    side: str
    order_type: str
    status: str
    signal_type: str
    signal_reason: str
    position_effect: str
    position_status_before: str
    position_status_after: str
    requested_notional: float
    quantity: float
    limit_price: float
    filled_price: float
    filled_at: datetime
    source: str


class PaperPositionView(BaseModel):
    market_code: str
    ticker: str
    opened_trade_date: date
    last_trade_date: date
    quantity: float
    avg_price: float
    invested_notional: float
    peak_price: float
    last_close: float
    last_volume_ratio_5d: float
    consecutive_decline_days: int
    unrealized_pnl: float
    unrealized_return: float
    entry_signal_type: str
    last_signal_type: str
    last_signal_reason: str
    closed_trade_date: date | None = None
    closed_price: float | None = None
    status: str


class PositionSellRunView(BaseModel):
    trade_date: date
    requested_count: int
    sold_count: int
    sold_positions: list[str] = Field(default_factory=list)
    source_mode: str


class AgentDialogueMessageView(BaseModel):
    role: Literal['user', 'assistant']
    content: str


class AgentToolSpecView(BaseModel):
    name: str
    description: str
    kind: str | None = None


class AgentSkillSpecView(BaseModel):
    name: str
    description: str
    category: str | None = None


class AgentToolRecommendationView(BaseModel):
    name: str
    reason: str


class AgentSkillRecommendationView(BaseModel):
    name: str
    reason: str


class ThemeStrategyPatchView(BaseModel):
    additions: list[str] = Field(default_factory=list)
    boosts: list[str] = Field(default_factory=list)
    suppressions: list[str] = Field(default_factory=list)


class ThemeMarketTargetView(BaseModel):
    market_code: str
    country_code: str
    reason: str


class DataSourceEntryView(BaseModel):
    name: str
    primary: str
    fallback: str | None = None
    backup: str | None = None


class DataSourceTimeoutsView(BaseModel):
    connect_seconds: int
    read_seconds: int


class DataSourceRetryView(BaseModel):
    max_attempts: int
    backoff_seconds: int


class DataSourceCatalogView(BaseModel):
    sources: list[DataSourceEntryView] = Field(default_factory=list)
    timeouts: DataSourceTimeoutsView
    retry: DataSourceRetryView


class DataSourceAgentRequestView(BaseModel):
    message: str
    conversation: list[AgentDialogueMessageView] = Field(default_factory=list)


class DataSourceAgentResponseView(BaseModel):
    assistant_message: str
    saved_source: DataSourceEntryView
    source_count: int
    follow_up_questions: list[str] = Field(default_factory=list)
    model: str


class ThemeStrategyAgentRequestView(BaseModel):
    selected_market: str = 'ALL'
    message: str
    conversation: list[AgentDialogueMessageView] = Field(default_factory=list)


class ThemeStrategyAgentResponseView(BaseModel):
    assistant_message: str
    strategy_name: str
    strategy_description: str
    patch: ThemeStrategyPatchView
    market_targets: list[ThemeMarketTargetView] = Field(default_factory=list)
    recommended_tools: list[AgentToolRecommendationView] = Field(default_factory=list)
    recommended_skills: list[AgentSkillRecommendationView] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    model: str
    theme_snapshot_count: int
