from dataclasses import asdict
from datetime import date

from packages.domain_core.market.entities import MarketFeature, RegimeSnapshot


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _coerce_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    return None


def _drawdown_abs(value: float) -> float:
    return abs(float(value))


def _event_window_score(feature: MarketFeature, indicators: dict[str, float | int | dict]) -> tuple[int, int | None]:
    policy_events = indicators.get("policy_events", {}) or {}
    raw_dates = policy_events.get(feature.market_code, [])
    event_dates = [_coerce_date(item) for item in raw_dates]
    event_dates = [item for item in event_dates if item is not None]
    if not event_dates:
        return 0, None

    strongest_window = int(indicators["policy_window_days_strong"])
    medium_window = int(indicators["policy_window_days_medium"])
    basic_window = int(indicators["policy_window_days_basic"])

    for event_date in sorted(event_dates, reverse=True):
        days_since = (feature.trade_date - event_date).days
        if days_since < 0:
            continue
        if days_since <= strongest_window:
            return 100, days_since
        if days_since <= medium_window:
            return 80, days_since
        if days_since <= basic_window:
            return 60, days_since
        return 0, days_since
    return 0, None


def _single_day_breakout_pass(feature: MarketFeature, indicators: dict[str, float | int | dict]) -> bool:
    ratio = float(feature.turnover_ratio_20d)
    ret_1d = float(feature.ret_1d)
    return (
        ratio >= float(indicators["single_day_turnover_ratio_medium"])
        and ret_1d >= float(indicators["single_day_return_medium"])
    ) or (
        ratio >= float(indicators["single_day_turnover_ratio_strong"])
        and ret_1d >= float(indicators["single_day_return_strong"])
    )


def _consecutive_volume_pass(feature: MarketFeature, indicators: dict[str, float | int | dict]) -> bool:
    return (
        int(feature.volume_up_days_3d) >= int(indicators["consecutive_volume_days_medium"])
        and float(feature.avg_turnover_ratio_3d) >= float(indicators["consecutive_volume_avg_ratio_medium"])
    )


def _score_policy_breakout(feature: MarketFeature, indicators: dict[str, float | int | dict]) -> tuple[float, bool]:
    event_score, _ = _event_window_score(feature, indicators)
    structure_ok = feature.close > feature.ma_20 and feature.ma_5 > feature.ma_10
    score = 0.0
    if event_score:
        score += 40.0
    if _single_day_breakout_pass(feature, indicators):
        score += 20.0
    if _consecutive_volume_pass(feature, indicators):
        score += 20.0
    if structure_ok:
        score += 20.0
    return score, bool(event_score and score >= 70.0)


def _score_trend_persistence(feature: MarketFeature, indicators: dict[str, float | int | dict]) -> tuple[float, bool]:
    score = 0.0
    if feature.close > feature.ma_60:
        score += 20.0
    if feature.close > feature.ma_120:
        score += 20.0
    if feature.ma_20 > feature.ma_60:
        score += 15.0
    if float(feature.ret_60d) >= float(indicators["trend_persistence_min_ret_60d"]):
        score += 15.0
    if float(feature.ret_120d) >= float(indicators["trend_persistence_min_ret_120d"]):
        score += 15.0
    if float(feature.relative_strength_world) >= float(indicators["trend_persistence_min_relative_strength"]):
        score += 15.0
    return score, score >= 70.0


def _score_recovery_reversal(feature: MarketFeature, indicators: dict[str, float | int | dict]) -> tuple[float, bool]:
    score = 0.0
    if feature.close > feature.ma_20:
        score += 20.0
    if feature.close > feature.ma_60:
        score += 20.0
    if float(feature.ret_5d) >= float(indicators["recovery_reversal_min_ret_5d"]):
        score += 20.0
    if int(feature.consecutive_up_weeks) >= int(indicators["recovery_reversal_min_consecutive_up_weeks"]):
        score += 20.0
    if (
        float(feature.turnover_ratio_20d) >= float(indicators["recovery_reversal_min_turnover_ratio_20d"])
        or float(feature.avg_turnover_ratio_3d) >= float(indicators["recovery_reversal_min_avg_turnover_ratio_3d"])
    ):
        score += 20.0
    return score, score >= 70.0


def _score_global_leader(feature: MarketFeature, indicators: dict[str, float | int | dict]) -> tuple[float, bool]:
    score = 0.0
    if float(feature.relative_strength_world) >= float(indicators["global_leader_min_relative_strength"]):
        score += 25.0
    if float(feature.ret_120d) >= float(indicators["global_leader_min_ret_120d"]):
        score += 20.0
    if feature.close > feature.ma_200:
        score += 20.0
    if feature.ma_60 > feature.ma_120:
        score += 15.0
    if _drawdown_abs(feature.drawdown_60d) <= float(indicators["global_leader_max_drawdown_60d"]):
        score += 20.0
    return score, score >= 70.0


def score_market_entries(
    feature: MarketFeature,
    weights: dict[str, float],
    indicators: dict[str, float | int | dict],
) -> dict[str, dict[str, float | bool]]:
    policy_breakout_score, policy_breakout_passed = _score_policy_breakout(feature, indicators)
    trend_persistence_score, trend_persistence_passed = _score_trend_persistence(feature, indicators)
    recovery_reversal_score, recovery_reversal_passed = _score_recovery_reversal(feature, indicators)
    global_leader_score, global_leader_passed = _score_global_leader(feature, indicators)

    return {
        "policy_breakout": {
            "score": round(min(policy_breakout_score, float(weights["policy_breakout"])), 4),
            "max_score": float(weights["policy_breakout"]),
            "passed": policy_breakout_passed,
        },
        "trend_persistence": {
            "score": round(min(trend_persistence_score, float(weights["trend_persistence"])), 4),
            "max_score": float(weights["trend_persistence"]),
            "passed": trend_persistence_passed,
        },
        "recovery_reversal": {
            "score": round(min(recovery_reversal_score, float(weights["recovery_reversal"])), 4),
            "max_score": float(weights["recovery_reversal"]),
            "passed": recovery_reversal_passed,
        },
        "global_leader": {
            "score": round(min(global_leader_score, float(weights["global_leader"])), 4),
            "max_score": float(weights["global_leader"]),
            "passed": global_leader_passed,
        },
    }


def classify_regime(score: float, bull_min: float, neutral_min: float) -> str:
    if score >= bull_min:
        return "BULL"
    if score >= neutral_min:
        return "NEUTRAL"
    return "BEAR"


def build_regime_snapshot(
    feature: MarketFeature,
    weights: dict[str, float],
    thresholds: dict[str, float],
    indicators: dict[str, float | int | dict],
    rule_version: str,
) -> RegimeSnapshot:
    score_by_entry = score_market_entries(feature, weights, indicators)

    bull_score = round(_clamp(max(float(item["score"]) for item in score_by_entry.values())), 4)
    regime_status = classify_regime(
        score=bull_score,
        bull_min=thresholds["bull_min_score"],
        neutral_min=thresholds["neutral_min_score"],
    )
    return RegimeSnapshot(
        market_code=feature.market_code,
        trade_date=feature.trade_date,
        regime_status=regime_status,
        bull_score=bull_score,
        trend_score=round(max(float(score_by_entry["trend_persistence"]["score"]), float(score_by_entry["global_leader"]["score"])), 4),
        relative_strength_score=round(max(float(score_by_entry["policy_breakout"]["score"]), float(score_by_entry["recovery_reversal"]["score"])), 4),
        risk_penalty_score=0.0,
        trigger_flags={
            name: bool(payload["passed"])
            for name, payload in score_by_entry.items()
        },
        source_used={"market_feature_source": feature.source, "rule_version": rule_version},
    )


def snapshot_to_dict(snapshot: RegimeSnapshot) -> dict:
    return asdict(snapshot)
