from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

import pandas as pd

from coach_miranda_miner.models import Asset, Candidate, MarketRegime, SignalState
from coach_miranda_miner.scalper import AlmaCciScalper
from coach_miranda_miner.validator import ThesisValidator


class ScalpStrategyTests(unittest.TestCase):
    def test_long_scalp_enter_triggers_on_alma_ema_and_cci_cross(self) -> None:
        result = _scalper().analyze(
            _candidate(),
            {
                "15m": _trend_frame("long"),
                "5m": _trend_frame("long"),
                "3m": _execution_frame("long"),
            },
            rank=1,
            market_regime=_regime(),
        )

        self.assertEqual(result.thesis.signal, SignalState.ENTER)
        self.assertEqual(result.thesis.direction, "long")
        self.assertGreater(result.thesis.entry, result.thesis.stop_loss)
        self.assertGreater(result.thesis.targets[0], result.thesis.entry)

    def test_short_scalp_enter_triggers_on_mirrored_cross(self) -> None:
        result = _scalper().analyze(
            _candidate(),
            {
                "15m": _trend_frame("short"),
                "5m": _trend_frame("short"),
                "3m": _execution_frame("short"),
            },
            rank=1,
            market_regime=_regime(),
        )

        self.assertEqual(result.thesis.signal, SignalState.ENTER)
        self.assertEqual(result.thesis.direction, "short")
        self.assertLess(result.thesis.entry, result.thesis.stop_loss)
        self.assertLess(result.thesis.targets[0], result.thesis.entry)


def _scalper() -> AlmaCciScalper:
    return AlmaCciScalper(
        ThesisValidator(
            min_risk_reward=2.0,
            min_confidence=0.72,
            max_stop_atr_multiple=10.0,
            max_atr_pct=20.0,
        )
    )


def _candidate() -> Candidate:
    return Candidate(
        asset=Asset(symbol="TEST/USD", base="TEST", quote="USD"),
        exchange_id="coinbase",
        route_symbol="TEST/USD",
        reason="test",
        volume_24h_usd=100_000_000,
    )


def _regime() -> MarketRegime:
    return MarketRegime(
        btc_change_24h_pct=0.5,
        longs_allowed=True,
        shorts_allowed=True,
        reason="test",
    )


def _trend_frame(direction: str) -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(240):
        close = 100 + index * 0.08 if direction == "long" else 120 - index * 0.08
        rows.append(_row(start, index, 15, close, 1000 + index))
    return pd.DataFrame(rows)


def _execution_frame(direction: str) -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(238):
        close = 110 + index * 0.005 if direction == "long" else 110 - index * 0.005
        rows.append(_row(start, index, 3, close, 1000))
    if direction == "long":
        rows.append(_row(start, 238, 3, 109.0, 1100))
        rows.append(_row(start, 239, 3, 121.0, 2200))
    else:
        rows.append(_row(start, 238, 3, 111.0, 1100))
        rows.append(_row(start, 239, 3, 99.0, 2200))
    return pd.DataFrame(rows)


def _row(start: datetime, index: int, minutes: int, close: float, volume: float) -> dict:
    return {
        "timestamp": start + timedelta(minutes=minutes * index),
        "open": close * 0.999,
        "high": close * 1.002,
        "low": close * 0.998,
        "close": close,
        "volume": volume,
    }


if __name__ == "__main__":
    unittest.main()
