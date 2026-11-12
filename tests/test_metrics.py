"""
Unit tests for FX metrics calculations using standard unittest (and pytest compatible).
Run with:
    pytest tests/
or:
    python -m unittest discover tests
"""

import unittest
import numpy as np
import pandas as pd
from src.metrics import (
    calculate_cumulative_returns,
    calculate_annualized_volatility,
    calculate_max_drawdown,
    calculate_momentum,
    calculate_sharpe_ratio,
    calculate_skewness_kurtosis,
    detect_market_regime
)


class TestFXMetrics(unittest.TestCase):

    def setUp(self):
        """Generates a synthetic 300-day FX price series (Units per USD)."""
        np.random.seed(42)
        dates = pd.date_range(start="2023-01-01", periods=300, freq="B")
        # Simulating a weakening USD / strengthening local currency (rate decreases from 20 to 16)
        trend = np.linspace(20.0, 16.0, 300)
        noise = np.random.normal(0, 0.2, 300)
        prices = trend + noise
        self.sample_price_series = pd.Series(prices, index=dates)

    def test_cumulative_returns(self):
        returns = calculate_cumulative_returns(self.sample_price_series)
        self.assertIsInstance(returns, dict)
        self.assertIn("7d", returns)
        self.assertIn("30d", returns)
        self.assertIn("1y", returns)
        # Since currency strengthened vs USD (20 -> 16), 1y return of holding currency should be positive
        self.assertGreater(returns["1y"], 0.0)

    def test_annualized_volatility(self):
        vol = calculate_annualized_volatility(self.sample_price_series)
        self.assertIsInstance(vol, float)
        self.assertGreater(vol, 0.0)
        self.assertLess(vol, 100.0)

    def test_max_drawdown(self):
        mdd, duration = calculate_max_drawdown(self.sample_price_series)
        self.assertIsInstance(mdd, float)
        self.assertLessEqual(mdd, 0.0) # Drawdowns are negative or zero
        self.assertIsInstance(duration, int)
        self.assertGreaterEqual(duration, 0)

    def test_momentum(self):
        mom = calculate_momentum(self.sample_price_series)
        self.assertIn("pct_20d", mom)
        self.assertIn("slope_60d", mom)
        self.assertIsInstance(mom["pct_60d"], float)

    def test_sharpe_ratio(self):
        sharpe = calculate_sharpe_ratio(self.sample_price_series, rf_annual=0.05)
        self.assertIsInstance(sharpe, float)

    def test_skewness_kurtosis(self):
        skew, kurt = calculate_skewness_kurtosis(self.sample_price_series)
        self.assertIsInstance(skew, float)
        self.assertIsInstance(kurt, float)

    def test_regime_detection(self):
        regime, emoji, conf = detect_market_regime(self.sample_price_series)
        self.assertIn(emoji, ["🟢", "🟡", "🔴", "⚪"])
        self.assertIsInstance(conf, float)


if __name__ == "__main__":
    unittest.main()
