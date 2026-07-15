from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd


@dataclass(frozen=True)
class DataQuality:
    source: str
    symbol: str
    timeframe: str
    retrieved_at: datetime
    latest_candle_at: datetime | None
    expected_interval_seconds: int | None
    age_seconds: int | None
    missing_intervals: int = 0
    duplicate_intervals: int = 0
    out_of_order_count: int = 0
    invalid_ohlc_count: int = 0
    too_few_candles: bool = False
    fallback_used: bool = False
    acceptable: bool = True
    warnings: list[str] = field(default_factory=list)


def validate_candle_frame(
    candles: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    source: str,
    min_candles: int = 20,
    fallback_used: bool = False,
    retrieved_at: datetime | None = None,
) -> DataQuality:
    now = retrieved_at or datetime.now(timezone.utc)
    interval_seconds = timeframe_seconds(timeframe)
    warnings: list[str] = []

    if candles.empty:
        return DataQuality(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            retrieved_at=now,
            latest_candle_at=None,
            expected_interval_seconds=interval_seconds,
            age_seconds=None,
            too_few_candles=True,
            fallback_used=fallback_used,
            acceptable=False,
            warnings=["No candles returned."],
        )

    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing_columns = sorted(required.difference(candles.columns))
    if missing_columns:
        return DataQuality(
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            retrieved_at=now,
            latest_candle_at=None,
            expected_interval_seconds=interval_seconds,
            age_seconds=None,
            fallback_used=fallback_used,
            acceptable=False,
            warnings=[f"Missing candle columns: {', '.join(missing_columns)}."],
        )

    frame = candles.copy()
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    invalid_timestamps = int(timestamps.isna().sum())
    if invalid_timestamps:
        warnings.append(f"{invalid_timestamps} candles have invalid timestamps.")
    frame["timestamp"] = timestamps
    frame = frame.dropna(subset=["timestamp"])

    duplicate_intervals = int(frame["timestamp"].duplicated().sum())
    if duplicate_intervals:
        warnings.append(f"{duplicate_intervals} duplicate candle timestamps detected.")

    out_of_order_count = int((frame["timestamp"].diff().dt.total_seconds().fillna(0) < 0).sum())
    if out_of_order_count:
        warnings.append(f"{out_of_order_count} candles are out of order.")

    missing_intervals = 0
    if interval_seconds and len(frame) > 1:
        gaps = frame.sort_values("timestamp")["timestamp"].diff().dt.total_seconds().dropna()
        missing_intervals = int(
            sum(max(int(round(gap / interval_seconds)) - 1, 0) for gap in gaps if gap > interval_seconds * 1.5)
        )
        if missing_intervals:
            warnings.append(f"{missing_intervals} expected candle intervals are missing.")

    invalid_ohlc_count = _invalid_ohlc_count(frame)
    if invalid_ohlc_count:
        warnings.append(f"{invalid_ohlc_count} candles have invalid OHLC or volume values.")

    too_few_candles = len(frame) < min_candles
    if too_few_candles:
        warnings.append(f"Only {len(frame)} candles returned; expected at least {min_candles}.")

    latest = frame["timestamp"].max().to_pydatetime() if not frame.empty else None
    age_seconds = int((now - latest).total_seconds()) if latest is not None else None
    if interval_seconds and age_seconds is not None and age_seconds > interval_seconds * 3:
        warnings.append(f"Latest candle is stale by {age_seconds} seconds.")

    structural_failures = (
        invalid_timestamps
        + duplicate_intervals
        + out_of_order_count
        + invalid_ohlc_count
    )
    acceptable = structural_failures == 0 and not too_few_candles

    return DataQuality(
        source=source,
        symbol=symbol,
        timeframe=timeframe,
        retrieved_at=now,
        latest_candle_at=latest,
        expected_interval_seconds=interval_seconds,
        age_seconds=age_seconds,
        missing_intervals=missing_intervals,
        duplicate_intervals=duplicate_intervals,
        out_of_order_count=out_of_order_count,
        invalid_ohlc_count=invalid_ohlc_count,
        too_few_candles=too_few_candles,
        fallback_used=fallback_used,
        acceptable=acceptable,
        warnings=warnings,
    )


def ensure_structurally_valid_candles(
    candles: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    source: str,
    min_candles: int = 20,
) -> DataQuality:
    quality = validate_candle_frame(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        min_candles=min_candles,
    )
    if not quality.acceptable:
        raise ValueError(
            f"Unacceptable candle data for {symbol} {timeframe} via {source}: "
            + "; ".join(quality.warnings)
        )
    return quality


def timeframe_seconds(timeframe: str) -> int | None:
    if len(timeframe) < 2 or not timeframe[:-1].isdigit():
        return None
    amount = int(timeframe[:-1])
    unit = timeframe[-1]
    if unit == "m":
        return amount * 60
    if unit == "h":
        return amount * 60 * 60
    if unit == "d":
        return amount * 24 * 60 * 60
    if unit == "w":
        return amount * 7 * 24 * 60 * 60
    return None


def _invalid_ohlc_count(frame: pd.DataFrame) -> int:
    numeric = frame[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    invalid = (
        numeric.isna().any(axis=1)
        | (numeric["open"] <= 0)
        | (numeric["high"] <= 0)
        | (numeric["low"] <= 0)
        | (numeric["close"] <= 0)
        | (numeric["volume"] < 0)
        | (numeric["high"] < numeric[["open", "close", "low"]].max(axis=1))
        | (numeric["low"] > numeric[["open", "close", "high"]].min(axis=1))
    )
    return int(invalid.sum())
