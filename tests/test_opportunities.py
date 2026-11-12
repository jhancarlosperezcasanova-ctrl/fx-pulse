"""
Tests for FX Opportunities Board, conviction calculation, and high conviction alert trigger logic.
"""

import unittest
import numpy as np
import pandas as pd
from src.opportunities import (
    is_high_conviction,
    get_pair_spread_and_rank,
    compute_directional_pair_metrics,
    scan_top_opportunities
)


class TestOpportunities(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        dates = pd.date_range(start="2023-01-01", periods=180, freq="B")
        # Synthetic currencies:
        # USD base: units per 1 USD
        # EUR: appreciating vs USD (0.95 -> 0.90)
        # JPY: depreciating vs USD (130 -> 155)
        eur = np.linspace(0.95, 0.90, 180) + np.random.normal(0, 0.005, 180)
        jpy = np.linspace(130.0, 155.0, 180) + np.random.normal(0, 0.5, 180)
        mxn = np.linspace(18.0, 17.0, 180) + np.random.normal(0, 0.1, 180)

        self.df = pd.DataFrame({
            "EUR": eur,
            "JPY": jpy,
            "MXN": mxn
        }, index=dates)

    def test_spread_and_rank(self):
        spread, rank = get_pair_spread_and_rank("EUR", "USD")
        self.assertEqual(rank, "major")
        self.assertLess(spread, 10.0)

        spread_cross, rank_cross = get_pair_spread_and_rank("EUR", "MXN")
        self.assertEqual(rank_cross, "cross")

    def test_directional_metrics(self):
        m = compute_directional_pair_metrics("JPY", "EUR", self.df)
        self.assertIsNotNone(m)
        self.assertEqual(m["origen"], "JPY")
        self.assertEqual(m["destino"], "EUR")
        self.assertIn("score_compuesto", m)
        self.assertGreaterEqual(m["score_compuesto"], 0.0)
        self.assertLessEqual(m["score_compuesto"], 1.0)

    def test_is_high_conviction_rule(self):
        # Case 1: Meets all conditions
        opp_valid = {
            "score_compuesto": 0.82,
            "momentum_60d": 0.045, # 4.5%
            "sharpe_par": 1.75,
            "volatilidad_30d": 0.14, # 14%
            "spread_estimado_bps": 8.0,
            "liquidez_rank": "cross"
        }
        self.assertTrue(is_high_conviction(opp_valid))

        # Case 2: Sharpe fails (< 1.5)
        opp_low_sharpe = opp_valid.copy()
        opp_low_sharpe["sharpe_par"] = 1.2
        self.assertFalse(is_high_conviction(opp_low_sharpe))

        # Case 3: Exotic liquidity fails
        opp_exotic = opp_valid.copy()
        opp_exotic["liquidez_rank"] = "exotic"
        self.assertFalse(is_high_conviction(opp_exotic))

        # Case 4: High volatility fails (> 25%)
        opp_high_vol = opp_valid.copy()
        opp_high_vol["volatilidad_30d"] = 0.28
        self.assertFalse(is_high_conviction(opp_high_vol))


if __name__ == "__main__":
    unittest.main()
