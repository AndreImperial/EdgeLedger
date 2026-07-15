from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators import moving_average, rsi


@dataclass(frozen=True)
class Signal:
    action: str
    confidence: float
    reason: str
    price: float


class SignalMiner:
    def __init__(
        self,
        short_ma: int,
        long_ma: int,
        rsi_period: int,
        rsi_buy_max: float,
        rsi_sell_min: float,
    ) -> None:
        self.short_ma = short_ma
        self.long_ma = long_ma
        self.rsi_period = rsi_period
        self.rsi_buy_max = rsi_buy_max
        self.rsi_sell_min = rsi_sell_min

    def mine(self, candles: pd.DataFrame) -> Signal:
        working = candles.copy()
        working["short_ma"] = moving_average(working["close"], self.short_ma)
        working["long_ma"] = moving_average(working["close"], self.long_ma)
        working["rsi"] = rsi(working["close"], self.rsi_period)

        latest = working.iloc[-1]
        price = float(latest["close"])

        if pd.isna(latest["short_ma"]) or pd.isna(latest["long_ma"]) or pd.isna(latest["rsi"]):
            return Signal("hold", 0.0, "Not enough candle history for indicators.", price)

        if latest["short_ma"] > latest["long_ma"] and latest["rsi"] <= self.rsi_buy_max:
            return Signal(
                "buy",
                0.65,
                f"Short MA is above long MA and RSI is {latest['rsi']:.2f}.",
                price,
            )

        if latest["short_ma"] < latest["long_ma"] and latest["rsi"] >= self.rsi_sell_min:
            return Signal(
                "sell",
                0.65,
                f"Short MA is below long MA and RSI is {latest['rsi']:.2f}.",
                price,
            )

        return Signal("hold", 0.4, f"No clean trend signal. RSI is {latest['rsi']:.2f}.", price)

