import unittest
from datetime import date

from packages.domain_core.selection.entities import StockScreenObservation, StockSeed
from packages.domain_core.selection.rules import evaluate_daily_candidate


class SelectionRuleTests(unittest.TestCase):
    def test_daily_candidate_passes_when_lagging_setup_turns_strong(self) -> None:
        seed = StockSeed(
            market_code="US_EQ",
            ticker="QUBT",
            company_name="Quantum Computing Inc.",
            sector="Technology",
            industry="Semiconductors",
            exchange="NCM",
            currency="USD",
            country_code="US",
            seed_type="bull_theme_lagging_candidate",
            theme_tags=["semiconductors", "technology", "auto_heat"],
            theme_score=88.0,
            valuation_score=92.0,
            size_score=85.0,
            valuation_band="attractive",
            market_cap_bucket="small_cap",
        )
        observation = StockScreenObservation(
            market_code="US_EQ",
            ticker="QUBT",
            trade_date=date(2026, 5, 25),
            close=21.0,
            ma_20=20.0,
            ma_60=19.5,
            ma_120=18.5,
            ma_200=17.5,
            ret_5d=0.036,
            ret_20d=0.082,
            ret_60d=0.18,
            avg_dollar_volume_3d=15_500_000,
            avg_dollar_volume_5d=16_000_000,
            avg_dollar_volume_20d=12_000_000,
            volume_ratio_3d=1.29,
            volume_ratio_5d=1.33,
            volume_up_days_5d=3,
            distance_to_60d_high=0.09,
            momentum_acceleration=0.016,
            vol_20d=0.24,
            source="test",
        )

        passed, composite_score, component_scores, flags = evaluate_daily_candidate(
            seed=seed,
            observation=observation,
            weights={
                "theme": 20,
                "lagging": 25,
                "trend_recovery": 20,
                "momentum_acceleration": 20,
                "volume_probe": 10,
                "risk_control": 5,
            },
            thresholds={
                "min_price": 10,
                "min_avg_dollar_volume_20d": 10_000_000,
                "min_volume_ratio_3d": 1.1,
                "max_distance_to_60d_high": 0.18,
                "max_vol_20d": 0.7,
                "min_composite_score": 60,
                "min_ret_5d": 0.01,
                "max_ret_5d": 0.08,
                "max_ret_20d": 0.15,
                "min_ma20_to_ma60_ratio": 0.98,
                "min_momentum_acceleration": 0.0,
                "min_volume_up_days_5d": 2,
                "max_close_to_ma20_extension": 0.12,
            },
        )

        self.assertTrue(passed)
        self.assertGreaterEqual(composite_score, 90.0)
        self.assertEqual(component_scores["lagging_score"], 100.0)
        self.assertEqual(component_scores["trend_recovery_score"], 100.0)
        self.assertEqual(component_scores["momentum_acceleration_score"], 100.0)
        self.assertEqual(component_scores["volume_probe_score"], 100.0)
        self.assertEqual(component_scores["risk_control_score"], 100.0)
        self.assertEqual(
            flags,
            {
                "theme_ok": True,
                "min_price_ok": True,
                "liquidity_ok": True,
                "lagging_ok": True,
                "trend_recovery_ok": True,
                "momentum_acceleration_ok": True,
                "volume_probe_ok": True,
                "risk_control_ok": True,
                "composite_score_ok": True,
            },
        )

    def test_daily_candidate_does_not_repeat_theme_filtering_when_setup_is_strong(self) -> None:
        seed = StockSeed(
            market_code="US_EQ",
            ticker="POOL1",
            company_name="Seed Pool Stock",
            sector="Technology",
            industry="Semiconductors",
            exchange="NCM",
            currency="USD",
            country_code="US",
            seed_type="bull_theme_lagging_candidate",
            theme_tags=["semiconductors", "technology", "auto_heat"],
            theme_score=0.0,
            valuation_score=25.0,
            size_score=20.0,
            valuation_band="expensive",
            market_cap_bucket="large_cap",
        )
        observation = StockScreenObservation(
            market_code="US_EQ",
            ticker="POOL1",
            trade_date=date(2026, 5, 25),
            close=22.0,
            ma_20=20.5,
            ma_60=20.0,
            ma_120=19.0,
            ma_200=18.0,
            ret_5d=0.032,
            ret_20d=0.07,
            ret_60d=0.16,
            avg_dollar_volume_3d=18_000_000,
            avg_dollar_volume_5d=17_000_000,
            avg_dollar_volume_20d=14_000_000,
            volume_ratio_3d=1.28,
            volume_ratio_5d=1.21,
            volume_up_days_5d=3,
            distance_to_60d_high=0.08,
            momentum_acceleration=0.014,
            vol_20d=0.28,
            source="test",
        )

        passed, composite_score, component_scores, flags = evaluate_daily_candidate(
            seed=seed,
            observation=observation,
            weights={
                "theme": 20,
                "lagging": 25,
                "trend_recovery": 20,
                "momentum_acceleration": 20,
                "volume_probe": 10,
                "risk_control": 5,
            },
            thresholds={
                "min_price": 10,
                "min_avg_dollar_volume_20d": 10_000_000,
                "min_volume_ratio_3d": 1.1,
                "max_distance_to_60d_high": 0.18,
                "max_vol_20d": 0.7,
                "min_composite_score": 60,
                "min_ret_5d": 0.01,
                "max_ret_5d": 0.08,
                "max_ret_20d": 0.15,
                "min_ma20_to_ma60_ratio": 0.98,
                "min_momentum_acceleration": 0.0,
                "min_volume_up_days_5d": 2,
                "max_close_to_ma20_extension": 0.12,
            },
        )

        self.assertTrue(passed)
        self.assertGreaterEqual(composite_score, 80.0)
        self.assertEqual(component_scores["theme_score"], 0.0)
        self.assertFalse(flags["theme_ok"])
        self.assertTrue(flags["composite_score_ok"])


if __name__ == "__main__":
    unittest.main()
