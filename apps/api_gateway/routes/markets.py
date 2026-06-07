from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.domain_core.market.rules import score_market_entries
from packages.shared.api_models import (
    ApiSuccess,
    MarketBullCriterionView,
    MarketBullSearchItemView,
    MarketBullSearchProcessView,
    MarketBullSearchRunView,
    MarketOverviewView,
    MarketRegimeView,
    TrackedBullMarketView,
)
from packages.shared.container import get_container

router = APIRouter(prefix="/markets", tags=["markets"])


class MarketBullSearchRunRequest(BaseModel):
    trade_date: date | None = None
    market_codes: list[str] = Field(default_factory=lambda: ['ALL'])


CRITERION_LABELS = {
    'policy_breakout': '政策点火型',
    'trend_persistence': '趋势慢牛型',
    'recovery_reversal': '超跌反转型',
    'global_leader': '全球强势型',
}


@router.get("/today", response_model=ApiSuccess[list[MarketRegimeView]])
def markets_today() -> ApiSuccess[list[MarketRegimeView]]:
    snapshots = get_container().regime_service.list_by_date(date.today())
    return ApiSuccess(
        data=[
            MarketRegimeView(
                market_code=snapshot.market_code,
                trade_date=snapshot.trade_date,
                regime_status=snapshot.regime_status,
                bull_score=snapshot.bull_score,
            )
            for snapshot in snapshots
        ]
    )


@router.get("/bull/today", response_model=ApiSuccess[list[TrackedBullMarketView]])
def bull_markets_today() -> ApiSuccess[list[TrackedBullMarketView]]:
    snapshots = get_container().regime_service.list_tracked_bull()
    return ApiSuccess(
        data=[
            TrackedBullMarketView(
                market_code=snapshot.market_code,
                entered_bull_trade_date=snapshot.trade_date,
                bull_score=snapshot.bull_score,
                regime_status=snapshot.regime_status,
            )
            for snapshot in snapshots
        ]
    )


@router.post('/bull-search/run', response_model=ApiSuccess[MarketBullSearchRunView])
def run_bull_search(request: MarketBullSearchRunRequest) -> ApiSuccess[MarketBullSearchRunView]:
    run_date = request.trade_date or date.today()
    container = get_container()
    container.refdata_service.list_markets()
    features = container.market_data_service.ingest_daily(
        trade_date=run_date,
        market_codes=request.market_codes,
    )
    snapshots = container.regime_service.run_daily(
        trade_date=run_date,
        market_codes=request.market_codes,
    )
    bull_market_codes = [snapshot.market_code for snapshot in snapshots if snapshot.regime_status == 'BULL']
    return ApiSuccess(
        data=MarketBullSearchRunView(
            trade_date=run_date,
            processed_markets=len(features),
            bull_market_count=len(bull_market_codes),
            bull_market_codes=bull_market_codes,
            source_mode=container.market_data_service.source_mode,
        )
    )


@router.get('/overview', response_model=ApiSuccess[list[MarketOverviewView]])
def market_overview() -> ApiSuccess[list[MarketOverviewView]]:
    container = get_container()
    markets = container.refdata_service.list_markets()
    indicators = container.regime_rules_config.indicators
    weights = container.regime_rules_config.weights

    rows = []
    for market in markets:
        snapshot = container.regime_service.get_latest_snapshot(market.market_code)
        trade_date = snapshot.trade_date if snapshot is not None else None
        feature = (
            container.market_data_service.get_feature(market.market_code, trade_date)
            if trade_date is not None
            else container.market_data_service.get_latest_feature(market.market_code)
        )
        effective_trade_date = trade_date or (feature.trade_date if feature is not None else None)
        criteria = _build_criteria(feature=feature, indicators=indicators, weights=weights) if effective_trade_date is not None else _missing_criteria(weights)
        passed_criteria = [criterion.name for criterion in criteria if criterion.passed]
        failed_criteria = [criterion.name for criterion in criteria if not criterion.passed]
        decision_reason = (
            _build_decision_reason(snapshot.regime_status, criteria, snapshot.bull_score)
            if snapshot is not None and criteria
            else ''
        )
        rows.append(
            MarketOverviewView(
                market_code=market.market_code,
                market_name=market.market_name,
                country_code=market.country_code,
                region=market.region,
                trade_date=effective_trade_date,
                regime_status=snapshot.regime_status if snapshot is not None else None,
                bull_score=snapshot.bull_score if snapshot is not None else None,
                is_bull=snapshot.regime_status == 'BULL' if snapshot is not None else False,
                price_proxy=feature.price_proxy if feature is not None else None,
                close=feature.close if feature is not None else None,
                ret_1d=feature.ret_1d if feature is not None else None,
                ret_5d=feature.ret_5d if feature is not None else None,
                ret_60d=feature.ret_60d if feature is not None else None,
                ret_120d=feature.ret_120d if feature is not None else None,
                turnover_ratio_20d=feature.turnover_ratio_20d if feature is not None else None,
                avg_turnover_ratio_3d=feature.avg_turnover_ratio_3d if feature is not None else None,
                volume_up_days_2d=feature.volume_up_days_2d if feature is not None else None,
                volume_up_days_3d=feature.volume_up_days_3d if feature is not None else None,
                consecutive_up_days=feature.consecutive_up_days if feature is not None else None,
                consecutive_up_weeks=feature.consecutive_up_weeks if feature is not None else None,
                relative_strength_world=feature.relative_strength_world if feature is not None else None,
                drawdown_60d=feature.drawdown_60d if feature is not None else None,
                ma_5=feature.ma_5 if feature is not None else None,
                ma_10=feature.ma_10 if feature is not None else None,
                ma_20=feature.ma_20 if feature is not None else None,
                ma_60=feature.ma_60 if feature is not None else None,
                ma_120=feature.ma_120 if feature is not None else None,
                ma_200=feature.ma_200 if feature is not None else None,
                feature_source=feature.source if feature is not None else None,
                criteria=criteria,
                passed_criteria=passed_criteria,
                failed_criteria=failed_criteria,
                decision_reason=decision_reason,
            )
        )
    return ApiSuccess(data=rows)


@router.get("/bull-search/process", response_model=ApiSuccess[MarketBullSearchProcessView])
def bull_search_process(trade_date: date | None = None) -> ApiSuccess[MarketBullSearchProcessView]:
    container = get_container()
    snapshots = container.regime_service.list_by_date(trade_date) if trade_date is not None else container.regime_service.list_latest()
    if not snapshots:
        return ApiSuccess(data=MarketBullSearchProcessView())

    effective_trade_date = snapshots[0].trade_date
    tracked = {snapshot.market_code: snapshot for snapshot in container.regime_service.list_tracked_bull()}
    indicators = container.regime_rules_config.indicators
    weights = container.regime_rules_config.weights
    items: list[MarketBullSearchItemView] = []

    for snapshot in snapshots:
        feature = container.market_data_service.get_feature(snapshot.market_code, effective_trade_date)
        criteria = _build_criteria(feature=feature, indicators=indicators, weights=weights)
        passed_criteria = [criterion.name for criterion in criteria if criterion.passed]
        failed_criteria = [criterion.name for criterion in criteria if not criterion.passed]
        tracked_snapshot = tracked.get(snapshot.market_code)
        items.append(
            MarketBullSearchItemView(
                market_code=snapshot.market_code,
                trade_date=snapshot.trade_date,
                regime_status=snapshot.regime_status,
                bull_score=snapshot.bull_score,
                is_bull=snapshot.regime_status == 'BULL',
                included_in_tracked_bull=tracked_snapshot is not None,
                tracked_entry_trade_date=tracked_snapshot.trade_date if tracked_snapshot is not None else None,
                price_proxy=feature.price_proxy if feature is not None else None,
                close=feature.close if feature is not None else None,
                avg_volume_recent=feature.avg_volume_recent if feature is not None else None,
                avg_volume_prior=feature.avg_volume_prior if feature is not None else None,
                ret_1d=feature.ret_1d if feature is not None else None,
                ret_5d=feature.ret_5d if feature is not None else None,
                ret_60d=feature.ret_60d if feature is not None else None,
                ret_120d=feature.ret_120d if feature is not None else None,
                turnover_ratio_20d=feature.turnover_ratio_20d if feature is not None else None,
                avg_turnover_ratio_3d=feature.avg_turnover_ratio_3d if feature is not None else None,
                volume_up_days_2d=feature.volume_up_days_2d if feature is not None else None,
                volume_up_days_3d=feature.volume_up_days_3d if feature is not None else None,
                consecutive_up_days=feature.consecutive_up_days if feature is not None else None,
                consecutive_up_weeks=feature.consecutive_up_weeks if feature is not None else None,
                relative_strength_world=feature.relative_strength_world if feature is not None else None,
                drawdown_60d=feature.drawdown_60d if feature is not None else None,
                ma_5=feature.ma_5 if feature is not None else None,
                ma_10=feature.ma_10 if feature is not None else None,
                ma_20=feature.ma_20 if feature is not None else None,
                ma_60=feature.ma_60 if feature is not None else None,
                ma_120=feature.ma_120 if feature is not None else None,
                ma_200=feature.ma_200 if feature is not None else None,
                feature_source=feature.source if feature is not None else None,
                criteria=criteria,
                passed_criteria=passed_criteria,
                failed_criteria=failed_criteria,
                decision_reason=_build_decision_reason(snapshot.regime_status, criteria, snapshot.bull_score),
            )
        )

    bull_market_codes = [item.market_code for item in items if item.is_bull]
    non_bull_market_codes = [item.market_code for item in items if not item.is_bull]
    tracked_bull_market_codes = [item.market_code for item in items if item.included_in_tracked_bull]
    return ApiSuccess(
        data=MarketBullSearchProcessView(
            trade_date=effective_trade_date,
            bull_market_codes=bull_market_codes,
            non_bull_market_codes=non_bull_market_codes,
            tracked_bull_market_codes=tracked_bull_market_codes,
            markets=items,
        )
    )


def _weights_dict(weights) -> dict[str, float]:
    return weights.model_dump() if hasattr(weights, 'model_dump') else dict(weights)


def _indicators_dict(indicators) -> dict[str, float | int | dict]:
    return indicators.model_dump() if hasattr(indicators, 'model_dump') else dict(indicators)


def _missing_criteria(weights) -> list[MarketBullCriterionView]:
    values = _weights_dict(weights)
    return [
        MarketBullCriterionView(
            name='policy_breakout',
            label=CRITERION_LABELS['policy_breakout'],
            passed=False,
            score=0.0,
            max_score=float(values['policy_breakout']),
            actual_value=None,
            threshold_value='政策窗口 + 放量上涨 + 连续放量 + 站稳短均线',
            detail='政策点火型要求近期有宽松事件，同时出现单日放量上涨、连续放量和短期结构转强。当前缺少市场特征数据。',
        ),
        MarketBullCriterionView(
            name='trend_persistence',
            label=CRITERION_LABELS['trend_persistence'],
            passed=False,
            score=0.0,
            max_score=float(values['trend_persistence']),
            actual_value=None,
            threshold_value='站上 MA60/MA120 + 中期收益为正 + 相对强弱为正',
            detail='趋势慢牛型要求中长期均线和中期收益同时转强。当前缺少市场特征数据。',
        ),
        MarketBullCriterionView(
            name='recovery_reversal',
            label=CRITERION_LABELS['recovery_reversal'],
            passed=False,
            score=0.0,
            max_score=float(values['recovery_reversal']),
            actual_value=None,
            threshold_value='重新站稳 MA20/MA60 + 周线连涨 + 量能修复',
            detail='超跌反转型要求价格重新站稳关键均线，并出现周线修复与量能回暖。当前缺少市场特征数据。',
        ),
        MarketBullCriterionView(
            name='global_leader',
            label=CRITERION_LABELS['global_leader'],
            passed=False,
            score=0.0,
            max_score=float(values['global_leader']),
            actual_value=None,
            threshold_value='相对全球强 + 长期收益强 + 回撤可控',
            detail='全球强势型要求长期收益、相对强弱和回撤控制同时优秀。当前缺少市场特征数据。',
        ),
    ]


def _build_criteria(feature, indicators, weights) -> list[MarketBullCriterionView]:
    if feature is None:
        return _missing_criteria(weights)

    indicator_values = _indicators_dict(indicators)
    weight_values = _weights_dict(weights)
    scores = score_market_entries(feature, weight_values, indicator_values)
    policy_days = _policy_days_since(feature.market_code, feature.trade_date, indicator_values)

    return [
        MarketBullCriterionView(
            name='policy_breakout',
            label=CRITERION_LABELS['policy_breakout'],
            passed=bool(scores['policy_breakout']['passed']),
            score=float(scores['policy_breakout']['score']),
            max_score=float(scores['policy_breakout']['max_score']),
            actual_value=f"{feature.turnover_ratio_20d:.2f}x / {feature.ret_1d:.2%}",
            threshold_value='政策窗口 + 放量上涨 + 连续放量 + 站稳短均线',
            detail=(
                f'条件：最近政策窗口内，并出现单日放量上涨、连续放量、收盘站上 MA20 且 MA5>MA10。'
                f'当前 政策窗口={_policy_window_text(policy_days)}，20日成交额比={feature.turnover_ratio_20d:.2f}，单日涨幅={feature.ret_1d:.2%}，'
                f'3日均额比={feature.avg_turnover_ratio_3d:.2f}，MA5={feature.ma_5:.2f}，MA10={feature.ma_10:.2f}，MA20={feature.ma_20:.2f}。'
            ),
        ),
        MarketBullCriterionView(
            name='trend_persistence',
            label=CRITERION_LABELS['trend_persistence'],
            passed=bool(scores['trend_persistence']['passed']),
            score=float(scores['trend_persistence']['score']),
            max_score=float(scores['trend_persistence']['max_score']),
            actual_value=f"60日={feature.ret_60d:.2%} / 120日={feature.ret_120d:.2%}",
            threshold_value='站上 MA60/MA120 + 中期收益为正 + 相对强弱为正',
            detail=(
                f'条件：close>MA60、close>MA120、MA20>MA60、60日收益>={indicator_values["trend_persistence_min_ret_60d"]:.0%}、'
                f'120日收益>={indicator_values["trend_persistence_min_ret_120d"]:.0%}、相对全球强弱>=0。'
                f'当前 close={feature.close:.2f}，MA60={feature.ma_60:.2f}，MA120={feature.ma_120:.2f}，MA20={feature.ma_20:.2f}，'
                f'60日收益={feature.ret_60d:.2%}，120日收益={feature.ret_120d:.2%}，相对强弱={feature.relative_strength_world:.2%}。'
            ),
        ),
        MarketBullCriterionView(
            name='recovery_reversal',
            label=CRITERION_LABELS['recovery_reversal'],
            passed=bool(scores['recovery_reversal']['passed']),
            score=float(scores['recovery_reversal']['score']),
            max_score=float(scores['recovery_reversal']['max_score']),
            actual_value=f"5日={feature.ret_5d:.2%} / 周连涨={feature.consecutive_up_weeks}",
            threshold_value='重新站稳 MA20/MA60 + 周线连涨 + 量能修复',
            detail=(
                f'条件：close>MA20、close>MA60、5日涨幅>={indicator_values["recovery_reversal_min_ret_5d"]:.0%}、'
                f'连续上涨周数>={indicator_values["recovery_reversal_min_consecutive_up_weeks"]}，并出现量能修复。'
                f'当前 close={feature.close:.2f}，MA20={feature.ma_20:.2f}，MA60={feature.ma_60:.2f}，5日涨幅={feature.ret_5d:.2%}，'
                f'连续上涨周数={feature.consecutive_up_weeks}，20日成交额比={feature.turnover_ratio_20d:.2f}，3日均额比={feature.avg_turnover_ratio_3d:.2f}。'
            ),
        ),
        MarketBullCriterionView(
            name='global_leader',
            label=CRITERION_LABELS['global_leader'],
            passed=bool(scores['global_leader']['passed']),
            score=float(scores['global_leader']['score']),
            max_score=float(scores['global_leader']['max_score']),
            actual_value=f"RS={feature.relative_strength_world:.2%} / 120日={feature.ret_120d:.2%}",
            threshold_value='相对全球强 + 长期收益强 + 回撤可控',
            detail=(
                f'条件：相对全球强弱>={indicator_values["global_leader_min_relative_strength"]:.0%}、120日收益>={indicator_values["global_leader_min_ret_120d"]:.0%}、'
                f'close>MA200、MA60>MA120、60日回撤<={indicator_values["global_leader_max_drawdown_60d"]:.0%}。'
                f'当前 相对强弱={feature.relative_strength_world:.2%}，120日收益={feature.ret_120d:.2%}，close={feature.close:.2f}，'
                f'MA200={feature.ma_200:.2f}，MA60={feature.ma_60:.2f}，MA120={feature.ma_120:.2f}，60日回撤={abs(feature.drawdown_60d):.2%}。'
            ),
        ),
    ]


def _policy_days_since(market_code: str, trade_date: date, indicators: dict[str, float | int | dict]) -> int | None:
    event_dates = indicators.get('policy_events', {}).get(market_code, [])
    if not event_dates:
        return None
    latest_event = max(event_dates)
    days_since = (trade_date - latest_event).days
    if days_since < 0:
        return None
    return days_since


def _policy_window_text(days_since: int | None) -> str:
    if days_since is None:
        return '未命中'
    return f'{days_since} 天前'


def _build_decision_reason(regime_status: str, criteria: list[MarketBullCriterionView], bull_score: float) -> str:
    score_text = '，'.join(
        f'{criterion.label}{criterion.score:.0f}/{criterion.max_score:.0f}'
        for criterion in criteria
    )
    passed_entries = [criterion.label for criterion in criteria if criterion.passed]
    entry_text = '、'.join(passed_entries) if passed_entries else '无'
    if regime_status == 'BULL':
        return f'判定为牛市：Bull Score={bull_score:.1f}（{score_text}）。已命中入口：{entry_text}。'
    if regime_status == 'NEUTRAL':
        return f'判定为观望：Bull Score={bull_score:.1f}（{score_text}）。已命中入口：{entry_text}。'
    return f'判定为熊市：Bull Score={bull_score:.1f}（{score_text}）。已命中入口：{entry_text}。'
