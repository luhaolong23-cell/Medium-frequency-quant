from packages.domain_core.selection.entities import StockScreenObservation, StockSeed


def evaluate_daily_candidate(
    seed: StockSeed,
    observation: StockScreenObservation,
    weights: dict[str, float],
    thresholds: dict[str, float],
) -> tuple[bool, float, dict[str, float], dict[str, bool]]:
    theme_component = max(0.0, min(100.0, float(seed.theme_score)))
    lagging_score = _lagging_score(observation, thresholds)
    trend_recovery_score = _trend_recovery_score(observation, thresholds)
    momentum_acceleration_score = _momentum_acceleration_score(observation, thresholds)
    volume_probe_score = _volume_probe_score(observation, thresholds)
    risk_control_score = _risk_control_score(observation, thresholds)

    weight_total = max(sum(float(value) for value in weights.values()), 1.0)
    weighted_total = (
        theme_component * float(weights.get('theme', 0.0))
        + lagging_score * float(weights.get('lagging', 0.0))
        + trend_recovery_score * float(weights.get('trend_recovery', 0.0))
        + momentum_acceleration_score * float(weights.get('momentum_acceleration', 0.0))
        + volume_probe_score * float(weights.get('volume_probe', 0.0))
        + risk_control_score * float(weights.get('risk_control', 0.0))
    )
    composite_score = round(weighted_total / weight_total, 4)

    flags = {
        'theme_ok': theme_component > 0,
        'min_price_ok': float(observation.close) >= float(thresholds['min_price']),
        'liquidity_ok': float(observation.avg_dollar_volume_20d) >= float(thresholds['min_avg_dollar_volume_20d']),
        'lagging_ok': lagging_score >= 60.0,
        'trend_recovery_ok': trend_recovery_score >= 70.0,
        'momentum_acceleration_ok': momentum_acceleration_score >= 60.0,
        'volume_probe_ok': volume_probe_score >= 60.0,
        'risk_control_ok': risk_control_score >= 50.0,
    }
    flags['composite_score_ok'] = composite_score >= float(thresholds['min_composite_score'])

    passed = flags['min_price_ok'] and flags['liquidity_ok'] and flags['composite_score_ok']

    component_scores = {
        'theme_score': round(theme_component, 4),
        'lagging_score': lagging_score,
        'trend_recovery_score': trend_recovery_score,
        'momentum_acceleration_score': momentum_acceleration_score,
        'volume_probe_score': volume_probe_score,
        'risk_control_score': risk_control_score,
    }
    return passed, composite_score, component_scores, flags


def _lagging_score(observation: StockScreenObservation, thresholds: dict[str, float]) -> float:
    score = 0.0
    if 0.0 < float(observation.ret_5d) <= float(thresholds['max_ret_5d']):
        score += 30.0
    if 0.0 < float(observation.ret_20d) <= float(thresholds['max_ret_20d']):
        score += 30.0
    distance = float(observation.distance_to_60d_high)
    if 0.03 <= distance <= float(thresholds['max_distance_to_60d_high']):
        score += 40.0
    return round(score, 4)


def _trend_recovery_score(observation: StockScreenObservation, thresholds: dict[str, float]) -> float:
    score = 0.0
    close = float(observation.close)
    ma_20 = float(observation.ma_20)
    ma_60 = float(observation.ma_60)
    if close > ma_20:
        score += 30.0
    if close > ma_60:
        score += 30.0
    if ma_60 > 0 and (ma_20 / ma_60) >= float(thresholds['min_ma20_to_ma60_ratio']):
        score += 20.0
    if float(observation.ret_20d) > 0:
        score += 20.0
    return round(score, 4)


def _momentum_acceleration_score(observation: StockScreenObservation, thresholds: dict[str, float]) -> float:
    score = 0.0
    if float(observation.ret_5d) >= float(thresholds['min_ret_5d']):
        score += 40.0
    if float(observation.momentum_acceleration) >= float(thresholds['min_momentum_acceleration']):
        score += 35.0
    if float(observation.ret_5d) <= float(thresholds['max_ret_5d']):
        score += 25.0
    return round(score, 4)


def _volume_probe_score(observation: StockScreenObservation, thresholds: dict[str, float]) -> float:
    score = 0.0
    if float(observation.volume_ratio_3d) >= float(thresholds['min_volume_ratio_3d']):
        score += 60.0
    if int(observation.volume_up_days_5d) >= int(thresholds['min_volume_up_days_5d']):
        score += 40.0
    return round(score, 4)


def _risk_control_score(observation: StockScreenObservation, thresholds: dict[str, float]) -> float:
    score = 0.0
    if float(observation.vol_20d) <= float(thresholds['max_vol_20d']):
        score += 50.0
    ma_20 = float(observation.ma_20)
    if ma_20 > 0:
        extension = (float(observation.close) / ma_20) - 1.0
        if 0.0 <= extension <= float(thresholds['max_close_to_ma20_extension']):
            score += 50.0
    return round(score, 4)
