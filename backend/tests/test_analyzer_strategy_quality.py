from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from coach_miranda_miner.analyzer import RuleBasedAnalyzer
from coach_miranda_miner.models import (
    Asset,
    Candidate,
    CandleSnapshot,
    IndicatorSnapshot,
    IntelligencePack,
    MarketRegime,
    Setup,
    SignalState,
)


class AnalyzerStrategyQualityTests(unittest.TestCase):
    def test_long_tabo_has_setup_score_evidence(self) -> None:
        thesis = RuleBasedAnalyzer().analyze(_pack("long"))

        self.assertEqual(thesis.setup, Setup.TABO)
        self.assertEqual(thesis.direction, "long")
        self.assertIn(thesis.signal, {SignalState.WATCH, SignalState.ENTER})
        self.assertTrue(any("Setup score components" in item for item in thesis.evidence))

    def test_short_tabo_is_mirrored_and_first_class(self) -> None:
        thesis = RuleBasedAnalyzer().analyze(_pack("short"))

        self.assertEqual(thesis.setup, Setup.TABO)
        self.assertEqual(thesis.direction, "short")
        self.assertIn(thesis.signal, {SignalState.WATCH, SignalState.ENTER})
        self.assertTrue(any("Short TABO" in item for item in thesis.evidence))

    def test_false_breakout_is_rejected(self) -> None:
        pack = _pack("long", false_breakout=True)

        thesis = RuleBasedAnalyzer().analyze(pack)

        self.assertEqual(thesis.signal, SignalState.REJECT)
        self.assertEqual(thesis.setup, Setup.NONE)
        self.assertIn("False breakout", thesis.invalidation_reason or "")


def _pack(direction: str, false_breakout: bool = False) -> IntelligencePack:
    return IntelligencePack(
        candidate=Candidate(
            asset=Asset(symbol="TEST/USD", base="TEST", quote="USD"),
            exchange_id="coinbase",
            route_symbol="TEST/USD",
            reason="test",
        ),
        market_regime=MarketRegime(
            btc_change_24h_pct=1.0,
            longs_allowed=True,
            shorts_allowed=True,
            reason="test regime",
        ),
        indicators=[
            IndicatorSnapshot(
                timeframe="15m",
                close=102.0 if direction == "long" else 98.0,
                volume=200.0,
                rsi=55.0 if direction == "long" else 45.0,
                macd=1.0 if direction == "long" else -1.0,
                macd_signal=0.5 if direction == "long" else -0.5,
                atr=1.0,
                relative_volume=2.0,
            ),
            IndicatorSnapshot(
                timeframe="1h",
                close=102.0 if direction == "long" else 98.0,
                volume=200.0,
                rsi=55.0 if direction == "long" else 45.0,
                macd=1.0 if direction == "long" else -1.0,
                macd_signal=0.5 if direction == "long" else -0.5,
                atr=1.0,
                relative_volume=1.5,
            ),
            IndicatorSnapshot(
                timeframe="4h",
                close=102.0 if direction == "long" else 98.0,
                volume=200.0,
                rsi=55.0 if direction == "long" else 45.0,
                macd=1.0 if direction == "long" else -1.0,
                macd_signal=0.5 if direction == "long" else -0.5,
                atr=1.0,
                relative_volume=1.5,
            ),
        ],
        candles={
            "15m": _prison_candles(direction, false_breakout),
            "1h": _trend_candles(direction),
            "4h": _trend_candles(direction),
        },
        news_summary="",
    )


def _prison_candles(direction: str, false_breakout: bool) -> list[CandleSnapshot]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles: list[CandleSnapshot] = []
    for index in range(24):
        close = 100.0
        high = 101.0
        low = 99.0
        if index == 22:
            close = 102.0 if direction == "long" else 98.0
        if index == 23:
            if false_breakout:
                close = 100.0
            else:
                close = 102.2 if direction == "long" else 97.8
        candles.append(
            CandleSnapshot(
                timestamp=start + timedelta(minutes=15 * index),
                open=close - 0.2 if direction == "long" else close + 0.2,
                high=max(high, close + 0.2),
                low=min(low, close - 0.2),
                close=close,
                volume=200.0,
            )
        )
    return candles


def _trend_candles(direction: str) -> list[CandleSnapshot]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[CandleSnapshot] = []
    for index in range(60):
        if direction == "long":
            close = 90.0 + index * 0.2
            high = 103.0 if index >= 55 else close + 0.5
            low = close - 0.5
        else:
            close = 110.0 - index * 0.2
            high = close + 0.5
            low = 97.0 if index >= 55 else close - 0.5
        rows.append(
            CandleSnapshot(
                timestamp=start + timedelta(hours=index),
                open=close - 0.1 if direction == "long" else close + 0.1,
                high=high,
                low=low,
                close=close,
                volume=200.0,
            )
        )
    return rows


if __name__ == "__main__":
    unittest.main()
