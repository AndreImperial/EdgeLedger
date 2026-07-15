from __future__ import annotations

import math

import pandas as pd


def moving_average(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def alma(series: pd.Series, length: int = 20, offset: float = 0.8, sigma: float = 8.0) -> pd.Series:
    if length <= 0:
        raise ValueError("ALMA length must be positive.")
    m = offset * (length - 1)
    s = length / sigma
    weights = pd.Series(
        [math.exp(-((index - m) ** 2) / (2 * s * s)) for index in range(length)],
        dtype="float64",
    )
    weights_array = (weights / weights.sum()).to_numpy()
    return series.rolling(window=length, min_periods=length).apply(
        lambda window: float((window * weights_array).sum()),
        raw=True,
    )


def cci(candles: pd.DataFrame, period: int = 200) -> pd.Series:
    typical_price = (candles["high"] + candles["low"] + candles["close"]) / 3
    mean = typical_price.rolling(window=period, min_periods=period).mean()
    mean_deviation = typical_price.rolling(window=period, min_periods=period).apply(
        lambda window: float((abs(window - window.mean())).mean()),
        raw=False,
    )
    return (typical_price - mean) / (0.015 * mean_deviation.replace(0, pd.NA))


def rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period, min_periods=period).mean()
    loss = -delta.clip(upper=0).rolling(window=period, min_periods=period).mean()
    relative_strength = gain / loss.replace(0, pd.NA)
    value = 100 - (100 / (1 + relative_strength))
    value = value.mask((loss == 0) & (gain > 0), 100)
    value = value.mask((gain == 0) & (loss > 0), 0)
    return value


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series]:
    fast_ema = series.ewm(span=fast, adjust=False).mean()
    slow_ema = series.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def atr(candles: pd.DataFrame, period: int) -> pd.Series:
    high_low = candles["high"] - candles["low"]
    high_close = (candles["high"] - candles["close"].shift()).abs()
    low_close = (candles["low"] - candles["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=period, min_periods=period).mean()


def relative_volume(volume: pd.Series, period: int) -> pd.Series:
    average_volume = volume.rolling(window=period, min_periods=period).mean()
    return volume / average_volume.replace(0, pd.NA)
