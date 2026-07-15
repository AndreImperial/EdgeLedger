from __future__ import annotations

import ccxt
import pandas as pd


class MarketData:
    def __init__(self, exchange_id: str) -> None:
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({"enableRateLimit": True})

    def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        candles = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        frame = pd.DataFrame(
            candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
        return frame

