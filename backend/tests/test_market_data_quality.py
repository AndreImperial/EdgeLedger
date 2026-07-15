from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

import pandas as pd

from coach_miranda_miner.market_data_quality import (
    ensure_structurally_valid_candles,
    validate_candle_frame,
)


class MarketDataQualityTests(unittest.TestCase):
    def test_valid_candles_are_acceptable(self) -> None:
        frame = _candles()

        quality = validate_candle_frame(
            frame,
            symbol="BTC/USD",
            timeframe="1h",
            source="fixture",
            retrieved_at=datetime.now(timezone.utc),
        )

        self.assertTrue(quality.acceptable)
        self.assertEqual(quality.duplicate_intervals, 0)
        self.assertEqual(quality.invalid_ohlc_count, 0)

    def test_duplicate_timestamps_are_rejected(self) -> None:
        frame = _candles()
        frame.loc[1, "timestamp"] = frame.loc[0, "timestamp"]

        quality = validate_candle_frame(
            frame,
            symbol="BTC/USD",
            timeframe="1h",
            source="fixture",
        )

        self.assertFalse(quality.acceptable)
        self.assertEqual(quality.duplicate_intervals, 1)

    def test_invalid_ohlc_is_rejected(self) -> None:
        frame = _candles()
        frame.loc[3, "high"] = frame.loc[3, "low"] - 1

        with self.assertRaisesRegex(ValueError, "invalid OHLC"):
            ensure_structurally_valid_candles(
                frame,
                symbol="BTC/USD",
                timeframe="1h",
                source="fixture",
            )

    def test_missing_intervals_are_reported(self) -> None:
        frame = _candles().drop(index=[4]).reset_index(drop=True)

        quality = validate_candle_frame(
            frame,
            symbol="BTC/USD",
            timeframe="1h",
            source="fixture",
            min_candles=10,
        )

        self.assertEqual(quality.missing_intervals, 1)
        self.assertIn("missing", " ".join(quality.warnings))


def _candles() -> pd.DataFrame:
    start = datetime.now(timezone.utc) - timedelta(hours=30)
    rows = []
    for index in range(30):
        close = 100 + index
        rows.append(
            {
                "timestamp": start + timedelta(hours=index),
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 1000 + index,
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()
