import unittest
from datetime import date

from packages.domain_core.market.entities import MarketFeature
from packages.domain_core.market.rules import build_regime_snapshot, classify_regime


DEFAULT_WEIGHTS = {
    "policy_breakout": 100,
    "trend_persistence": 100,
    "recovery_reversal": 100,
    "global_leader": 100,
}

DEFAULT_THRESHOLDS = {
    "bull_min_score": 70,
    "neutral_min_score": 45,
}

DEFAULT_INDICATORS = {
    "single_day_turnover_ratio_strong": 2.0,
    "single_day_return_strong": 0.03,
    "single_day_turnover_ratio_medium": 1.5,
    "single_day_return_medium": 0.02,
    "single_day_turnover_ratio_basic": 1.2,
    "consecutive_volume_days_strong": 3,
    "consecutive_volume_avg_ratio_strong": 1.5,
    "consecutive_volume_days_medium": 2,
    "consecutive_volume_avg_ratio_medium": 1.3,
    "consecutive_volume_days_basic": 2,
    "policy_window_days_strong": 3,
    "policy_window_days_medium": 7,
    "policy_window_days_basic": 10,
    "trend_persistence_min_ret_60d": 0.03,
    "trend_persistence_min_ret_120d": 0.08,
    "trend_persistence_min_relative_strength": 0.0,
    "recovery_reversal_min_ret_5d": 0.03,
    "recovery_reversal_min_turnover_ratio_20d": 1.1,
    "recovery_reversal_min_avg_turnover_ratio_3d": 1.2,
    "recovery_reversal_min_consecutive_up_weeks": 2,
    "global_leader_min_ret_120d": 0.12,
    "global_leader_min_relative_strength": 0.05,
    "global_leader_max_drawdown_60d": 0.12,
    "policy_events": {
        "CN_EQ": ["2026-05-23"],
    },
}


class RegimeRuleTests(unittest.TestCase):
    def test_classify_regime_thresholds(self) -> None:
        self.assertEqual(classify_regime(80, bull_min=70, neutral_min=45), "BULL")
        self.assertEqual(classify_regime(50, bull_min=70, neutral_min=45), "NEUTRAL")
        self.assertEqual(classify_regime(10, bull_min=70, neutral_min=45), "BEAR")

    def test_policy_breakout_entry_can_trigger_bull(self) -> None:
        feature = MarketFeature(
            market_code="CN_EQ",
            trade_date=date(2026, 5, 25),
            price_proxy="MCHI",
            close=108.0,
            ma_120=101.0,
            ma_200=98.0,
            ret_60d=0.10,
            ret_120d=0.18,
            vol_20d=0.16,
            drawdown_60d=-0.04,
            relative_strength_world=0.06,
            fx_ret_60d=0.0,
            avg_volume_recent=150_000_000.0,
            avg_volume_prior=100_000_000.0,
            volume_ratio_5d=1.5,
            consecutive_up_weeks=2,
            ma_5=107.0,
            ma_10=105.0,
            ma_20=103.0,
            ma_60=100.0,
            ret_1d=0.021,
            ret_5d=0.052,
            turnover_ratio_20d=1.55,
            avg_turnover_ratio_3d=1.32,
            volume_up_days_2d=2,
            volume_up_days_3d=2,
            consecutive_up_days=3,
            source="test",
        )

        snapshot = build_regime_snapshot(
            feature=feature,
            weights=DEFAULT_WEIGHTS,
            thresholds=DEFAULT_THRESHOLDS,
            indicators=DEFAULT_INDICATORS,
            rule_version='regime_v4_parallel_entries',
        )

        self.assertEqual(snapshot.regime_status, "BULL")
        self.assertTrue(snapshot.trigger_flags["policy_breakout"])

    def test_long_trend_bull_can_enter_without_short_term_breakout(self) -> None:
        feature = MarketFeature(
            market_code="US_EQ",
            trade_date=date(2026, 5, 25),
            price_proxy="SPY",
            close=110.0,
            ma_120=104.0,
            ma_200=100.0,
            ret_60d=0.14,
            ret_120d=0.24,
            vol_20d=0.16,
            drawdown_60d=-0.06,
            relative_strength_world=0.07,
            fx_ret_60d=0.0,
            avg_volume_recent=100_000_000.0,
            avg_volume_prior=98_000_000.0,
            volume_ratio_5d=1.02,
            consecutive_up_weeks=3,
            ma_5=109.8,
            ma_10=109.1,
            ma_20=107.2,
            ma_60=103.5,
            ret_1d=0.003,
            ret_5d=0.011,
            turnover_ratio_20d=0.94,
            avg_turnover_ratio_3d=0.88,
            volume_up_days_2d=1,
            volume_up_days_3d=1,
            consecutive_up_days=1,
            source="test",
        )

        snapshot = build_regime_snapshot(
            feature=feature,
            weights=DEFAULT_WEIGHTS,
            thresholds=DEFAULT_THRESHOLDS,
            indicators=DEFAULT_INDICATORS,
            rule_version='regime_v4_parallel_entries',
        )

        self.assertEqual(snapshot.regime_status, "BULL")
        self.assertTrue(snapshot.trigger_flags["trend_persistence"])
        self.assertGreaterEqual(snapshot.bull_score, 70)

    def test_global_leader_entry_requires_relative_strength_and_long_term_trend(self) -> None:
        feature = MarketFeature(
            market_code="JP_EQ",
            trade_date=date(2026, 5, 25),
            price_proxy="EWJ",
            close=95.0,
            ma_120=88.0,
            ma_200=84.0,
            ret_60d=0.09,
            ret_120d=0.18,
            vol_20d=0.14,
            drawdown_60d=-0.08,
            relative_strength_world=0.08,
            fx_ret_60d=0.01,
            avg_volume_recent=102_000_000.0,
            avg_volume_prior=98_000_000.0,
            volume_ratio_5d=1.04,
            consecutive_up_weeks=2,
            ma_5=94.2,
            ma_10=93.5,
            ma_20=92.8,
            ma_60=90.5,
            ret_1d=0.004,
            ret_5d=0.017,
            turnover_ratio_20d=0.91,
            avg_turnover_ratio_3d=0.95,
            volume_up_days_2d=1,
            volume_up_days_3d=1,
            consecutive_up_days=1,
            source="test",
        )

        snapshot = build_regime_snapshot(
            feature=feature,
            weights=DEFAULT_WEIGHTS,
            thresholds=DEFAULT_THRESHOLDS,
            indicators=DEFAULT_INDICATORS,
            rule_version='regime_v4_parallel_entries',
        )

        self.assertEqual(snapshot.regime_status, "BULL")
        self.assertTrue(snapshot.trigger_flags["global_leader"])


if __name__ == "__main__":
    unittest.main()
