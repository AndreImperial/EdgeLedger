from __future__ import annotations

import unittest

import pandas as pd

from coach_miranda_miner.backtest import (
    AlmaCciScalpBacktester,
    BacktestResult,
    MirandaStrategyBacktester,
    StrategyBacktestConfig,
)
from tests.test_scalper import _execution_frame


class StrategyBacktestTests(unittest.TestCase):
    def test_miranda_backtest_can_take_long_trades(self) -> None:
        result = _tester(allow_longs=True, allow_shorts=False).run(
            "TEST/USD",
            "15m",
            _trend_frame(direction="long"),
        )

        self.assertGreater(result.trades, 0)
        self.assertGreater(result.long_trades, 0)
        self.assertEqual(result.short_trades, 0)
        self.assertTrue(result.setup_stats)
        self.assertTrue(result.warnings)

    def test_miranda_backtest_can_take_short_trades(self) -> None:
        result = _tester(allow_longs=False, allow_shorts=True).run(
            "TEST/USD",
            "15m",
            _trend_frame(direction="short"),
        )

        self.assertGreater(result.trades, 0)
        self.assertGreater(result.short_trades, 0)
        self.assertEqual(result.long_trades, 0)
        self.assertTrue(result.setup_stats)

    def test_scalp_backtest_smoke_supports_both_sides(self) -> None:
        tester = AlmaCciScalpBacktester(
            StrategyBacktestConfig(
                fee_bps=10,
                slippage_bps=5,
                stop_atr_multiple=1.5,
                target_r_multiple=2.0,
                allow_longs=True,
                allow_shorts=True,
                min_relative_volume=0.1,
                min_risk_reward=2.0,
                max_hold_bars=12,
            )
        )

        result = tester.run("TEST/USD", "3m", _execution_frame("long"))

        self.assertEqual(result.symbol, "TEST/USD")
        self.assertGreaterEqual(result.trades, 0)

    def test_backtest_format_shows_validation_warnings(self) -> None:
        result = BacktestResult(
            symbol="TEST/USD",
            timeframe="1h",
            trades=1,
            wins=1,
            losses=0,
            win_rate=1.0,
            total_return_pct=1.0,
            max_drawdown_pct=0.0,
            profit_factor=99.0,
            expectancy_pct=1.0,
            average_win_pct=1.0,
            average_loss_pct=0.0,
            warnings=["Only 1 trade; this is not validation."],
        )

        self.assertIn("Warnings:", result.format())
        self.assertIn("Only 1 trade", result.format())


def _tester(allow_longs: bool, allow_shorts: bool) -> MirandaStrategyBacktester:
    return MirandaStrategyBacktester(
        StrategyBacktestConfig(
            fee_bps=0,
            slippage_bps=0,
            stop_atr_multiple=1.0,
            target_r_multiple=2.0,
            allow_longs=allow_longs,
            allow_shorts=allow_shorts,
            min_relative_volume=1.0,
            min_risk_reward=2.0,
            max_hold_bars=12,
        )
    )


def _trend_frame(direction: str) -> pd.DataFrame:
    rows = []
    price = 100.0
    for index in range(120):
        if direction == "long":
            price += (0.24 if index % 5 else -0.12) if index < 75 else 0.35
            if index == 75:
                price += 3.5
        else:
            price += (-0.24 if index % 5 else 0.12) if index < 75 else -0.35
            if index == 75:
                price -= 3.5
        open_price = price - 0.08 if direction == "long" else price + 0.08
        close = price
        high = max(open_price, close) + 0.35
        low = min(open_price, close) - 0.35
        volume = 100.0
        if index in {75, 76, 77}:
            volume = 400.0
        rows.append(
            {
                "timestamp": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(minutes=15 * index),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()
