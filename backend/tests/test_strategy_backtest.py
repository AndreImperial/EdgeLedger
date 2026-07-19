from __future__ import annotations

import unittest
from types import SimpleNamespace

import pandas as pd

from coach_miranda_miner.coach import CoachMirandaMiner
from coach_miranda_miner.backtest import (
    AlmaCciScalpBacktester,
    BacktestResult,
    MirandaStrategyBacktester,
    MovingAverageBacktester,
    StrategyBacktestConfig,
)
from coach_miranda_miner.models import Asset, Candidate
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

    def test_moving_average_backtest_can_take_short_trades(self) -> None:
        tester = MovingAverageBacktester(
            short_ma=5,
            long_ma=12,
            rsi_period=7,
            rsi_buy_max=100,
            fee_bps=0,
            slippage_bps=0,
            stop_atr_multiple=1.0,
            target_r_multiple=1.0,
            min_body_atr=0.0,
            min_ma_gap_atr=0.0,
            min_risk_pct=0.0,
            allow_longs=False,
            allow_shorts=True,
        )

        result = tester.run("TEST/USD", "15m", _trend_frame(direction="short"))

        self.assertGreater(result.trades, 0)
        self.assertEqual(result.long_trades, 0)
        self.assertGreater(result.short_trades, 0)

    def test_managed_exit_reduces_loss_after_partial_profit(self) -> None:
        tester = MirandaStrategyBacktester(
            StrategyBacktestConfig(
                fee_bps=0,
                slippage_bps=0,
                stop_atr_multiple=1.0,
                target_r_multiple=2.0,
                partial_target_r=0.5,
                partial_exit_fraction=0.5,
                breakeven_trigger_r=0.5,
            )
        )
        signal = tester._build_signal("long", "tabo", 100.0, 10.0)
        self.assertIsNotNone(signal)
        frame = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2026-01-01", tz="UTC"),
                    "open": 100.0,
                    "high": 105.0,
                    "low": 99.0,
                    "close": 101.0,
                    "volume": 100.0,
                },
                {
                    "timestamp": pd.Timestamp("2026-01-01 00:15", tz="UTC"),
                    "open": 101.0,
                    "high": 102.0,
                    "low": 100.0,
                    "close": 100.5,
                    "volume": 100.0,
                },
            ]
        )

        _, _, reason, trade_return = tester._resolve_trade(frame, 0, signal)

        self.assertEqual(reason, "breakeven")
        self.assertGreater(trade_return, 0)

    def test_signal_rejects_target_that_is_too_small_after_costs(self) -> None:
        tester = MirandaStrategyBacktester(
            StrategyBacktestConfig(
                fee_bps=10,
                slippage_bps=5,
                stop_atr_multiple=1.0,
                target_r_multiple=1.0,
                min_risk_reward=1.0,
                min_net_target_pct=0.05,
            )
        )

        self.assertIsNone(tester._build_signal("long", "bounce", 100.0, 0.25))
        self.assertIsNotNone(tester._build_signal("long", "bounce", 100.0, 0.6))

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

    def test_ma_batch_backtest_excludes_configured_weak_bases(self) -> None:
        coach = CoachMirandaMiner.__new__(CoachMirandaMiner)
        coach.settings = SimpleNamespace(
            backtest_limit=10,
            scan_workers=1,
            backtest_candle_limit=3000,
            backtest_ma_side="short",
            backtest_ma_preferred_bases=["BTC", "ETH"],
            backtest_ma_excluded_bases=["DOGE", "AVAX"],
            backtest_ma_min_batch_win_rate=0.60,
            backtest_ma_validation_candle_limit=0,
        )
        coach.discovery = _FakeDiscovery(
            [
                _candidate("BTC"),
                _candidate("SOL"),
                _candidate("DOGE"),
                _candidate("AVAX"),
                _candidate("ETH"),
            ]
        )
        def fake_backtest(symbol: str, *_args) -> BacktestResult:
            if symbol.startswith("ETH"):
                return _batch_result(symbol, 0.95, trades=20)
            return _batch_result(symbol, 0.6 if symbol.startswith("BTC") else 0.57)

        coach.backtest = fake_backtest

        rows = coach.batch_backtest(strategy="ma")

        self.assertEqual([row["symbol"] for row in rows], ["BTC/USDT"])

    def test_ma_batch_backtest_requires_validation_win_rate(self) -> None:
        coach = CoachMirandaMiner.__new__(CoachMirandaMiner)
        coach.settings = SimpleNamespace(
            backtest_limit=10,
            scan_workers=1,
            backtest_candle_limit=3000,
            backtest_ma_side="short",
            backtest_ma_preferred_bases=["BTC", "XRP"],
            backtest_ma_excluded_bases=[],
            backtest_ma_min_batch_win_rate=0.65,
            backtest_ma_validation_candle_limit=10000,
            backtest_ma_min_validation_win_rate=0.60,
        )
        coach.discovery = _FakeDiscovery([_candidate("BTC"), _candidate("XRP")])

        def fake_backtest(symbol: str, *_args, candle_limit: int | None = None) -> BacktestResult:
            if candle_limit == 10000:
                if symbol.startswith("BTC"):
                    return _batch_result(symbol, 0.95, trades=20)
                return _batch_result(symbol, 0.61)
            return _batch_result(symbol, 0.66)

        coach.backtest = fake_backtest

        rows = coach.batch_backtest(strategy="ma")

        self.assertEqual([row["symbol"] for row in rows], ["XRP/USDT"])
        self.assertEqual(rows[0]["validation_win_rate"], 0.61)
        self.assertAlmostEqual(rows[0]["validation_win_rate_delta"], -0.05)

    def test_moving_average_backtester_applies_symbol_override(self) -> None:
        coach = CoachMirandaMiner.__new__(CoachMirandaMiner)
        coach.settings = SimpleNamespace(
            short_ma=20,
            long_ma=50,
            rsi_period=14,
            backtest_ma_rsi_buy_max=60,
            backtest_fee_bps=10,
            backtest_slippage_bps=5,
            backtest_ma_stop_atr_multiple=1.5,
            backtest_ma_target_r_multiple=0.75,
            backtest_breakeven_trigger_r=99,
            backtest_partial_target_r=1,
            backtest_partial_exit_fraction=0,
            backtest_ma_min_body_atr=0.1,
            backtest_ma_min_gap_atr=0.3,
            backtest_ma_min_risk_pct=0.35,
            backtest_min_net_target_pct=0,
            backtest_ma_symbol_overrides={
                "XRP": {
                    "rsi_buy_max": 50,
                    "target_r": 0.3,
                    "min_body_atr": 0.2,
                    "min_gap_atr": 0.6,
                    "min_risk_pct": 0.35,
                    "short_rsi_max": 75,
                    "max_short_close_position": 0.5,
                    "min_short_bearish_sequence": 2,
                },
            },
        )

        xrp_tester = coach._moving_average_backtester("short", "XRP/USDT")
        btc_tester = coach._moving_average_backtester("short", "BTC/USDT")

        self.assertEqual(xrp_tester.rsi_buy_max, 50)
        self.assertEqual(xrp_tester.min_body_atr, 0.2)
        self.assertEqual(xrp_tester.min_ma_gap_atr, 0.6)
        self.assertEqual(xrp_tester.min_risk_pct, 0.35)
        self.assertEqual(xrp_tester.short_rsi_max, 75)
        self.assertEqual(xrp_tester.max_short_close_position, 0.5)
        self.assertEqual(xrp_tester.min_short_bearish_sequence, 2)
        self.assertEqual(xrp_tester.target_r_multiple, 0.3)
        self.assertEqual(btc_tester.min_ma_gap_atr, 0.3)
        self.assertEqual(btc_tester.target_r_multiple, 0.75)

    def test_optimize_backtest_validates_exact_candidate_settings(self) -> None:
        coach = CoachMirandaMiner.__new__(CoachMirandaMiner)
        coach.settings = SimpleNamespace(
            quote_currency="USDT",
            exchange_id="fixture",
            backtest_candle_limit=100,
            backtest_ma_side="short",
            backtest_ma_min_batch_win_rate=0.90,
            backtest_ma_validation_candle_limit=200,
            backtest_ma_min_validation_win_rate=0.90,
            short_ma=20,
            long_ma=50,
            rsi_period=14,
        )
        coach.router = _FakeRouter(_trend_frame("short"))

        rejected_tester = _FakeOptimizationTester(_batch_result("ETH/USDT", 0.50))
        stronger_tester = _FakeOptimizationTester(_batch_result("ETH/USDT", 0.93))
        weaker_tester = _FakeOptimizationTester(_batch_result("ETH/USDT", 0.95))

        def fake_optimization_results(*_args):
            yield "main-only mirage", _batch_result("ETH/USDT", 0.99), rejected_tester
            yield "validated floor", _batch_result("ETH/USDT", 0.94), stronger_tester
            yield "higher validation lower floor", _batch_result("ETH/USDT", 0.92), weaker_tester

        coach._optimization_results = fake_optimization_results

        rows = coach.optimize_backtest("ETH/USDT", strategy="ma", min_trades=30)

        self.assertEqual([row["label"] for row in rows], ["validated floor", "higher validation lower floor"])
        self.assertEqual(rows[0]["validation_win_rate"], 0.93)
        self.assertEqual(rows[0]["win_rate_floor"], 0.93)


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


class _FakeDiscovery:
    def __init__(self, candidates: list[Candidate]) -> None:
        self._candidates = candidates

    def discover(self, _limit: int) -> list[Candidate]:
        return self._candidates


class _FakeRouter:
    def __init__(self, candles: pd.DataFrame) -> None:
        self._candles = candles

    def first_available_route(self, base: str, quote: str) -> tuple[str, str]:
        return "fixture", f"{base}/{quote}"

    def fetch_candles(
        self,
        _exchange_id: str,
        _symbol: str,
        _timeframe: str,
        _limit: int,
    ) -> pd.DataFrame:
        return self._candles


class _FakeOptimizationTester:
    def __init__(self, result: BacktestResult) -> None:
        self._result = result

    def run(self, _symbol: str, _timeframe: str, _candles: pd.DataFrame) -> BacktestResult:
        return self._result


def _candidate(base: str) -> Candidate:
    return Candidate(
        asset=Asset(symbol=f"{base}/USDT", base=base, quote="USDT"),
        exchange_id="fixture",
        route_symbol=f"{base}/USDT",
        reason="test",
    )


def _batch_result(symbol: str, win_rate: float, trades: int = 100) -> BacktestResult:
    wins = int(win_rate * trades)
    losses = trades - wins
    return BacktestResult(
        symbol=symbol,
        timeframe="15m",
        trades=trades,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        total_return_pct=0.0,
        max_drawdown_pct=0.0,
        profit_factor=1.0,
        expectancy_pct=0.0,
        average_win_pct=0.0,
        average_loss_pct=0.0,
    )


if __name__ == "__main__":
    unittest.main()
