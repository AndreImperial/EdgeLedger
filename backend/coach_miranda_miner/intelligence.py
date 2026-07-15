from __future__ import annotations

import pandas as pd

from .exchanges import ExchangeRouter
from .indicators import atr, macd, relative_volume, rsi
from .models import (
    Candidate,
    CandleSnapshot,
    IndicatorSnapshot,
    IntelligencePack,
    MarketRegime,
)
from .charts import ChartRenderer
from .news import EmptyNewsProvider, NewsProvider


class IntelligenceGatherer:
    def __init__(
        self,
        router: ExchangeRouter,
        timeframes: list[str],
        candle_limit: int,
        chart_renderer: ChartRenderer | None = None,
        news_provider: NewsProvider | None = None,
        candle_fetcher=None,
    ) -> None:
        self.router = router
        self.timeframes = timeframes
        self.candle_limit = candle_limit
        self.chart_renderer = chart_renderer
        self.news_provider = news_provider or EmptyNewsProvider()
        self.candle_fetcher = candle_fetcher

    def gather(self, candidate: Candidate, market_regime: MarketRegime) -> IntelligencePack:
        snapshots: list[IndicatorSnapshot] = []
        candles_by_timeframe: dict[str, list[CandleSnapshot]] = {}
        chart_paths: list[str] = []
        for timeframe in self.timeframes:
            fetch_candles = self.candle_fetcher or self.router.fetch_candles
            candles = fetch_candles(candidate.exchange_id, candidate.route_symbol, timeframe, self.candle_limit)
            if self.chart_renderer is not None:
                try:
                    chart_paths.append(
                        self.chart_renderer.render(candidate.route_symbol, timeframe, candles)
                    )
                except OSError:
                    pass
            candles_by_timeframe[timeframe] = [
                CandleSnapshot(
                    timestamp=row.timestamp.to_pydatetime(),
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    volume=float(row.volume),
                )
                for row in candles.tail(80).itertuples(index=False)
            ]
            rsi_series = rsi(candles["close"], 14)
            macd_line, signal_line = macd(candles["close"])
            atr_series = atr(candles, 14)
            rel_volume = relative_volume(candles["volume"], 20)
            latest = candles.iloc[-1]
            snapshots.append(
                IndicatorSnapshot(
                    timeframe=timeframe,
                    close=float(latest["close"]),
                    volume=float(latest["volume"]),
                    rsi=_last_float(rsi_series),
                    macd=_last_float(macd_line),
                    macd_signal=_last_float(signal_line),
                    atr=_last_float(atr_series),
                    relative_volume=_last_float(rel_volume),
                )
            )

        return IntelligencePack(
            candidate=candidate,
            market_regime=market_regime,
            indicators=snapshots,
            candles=candles_by_timeframe,
            news_summary=self.news_provider.summarize(candidate.asset.base),
            chart_paths=chart_paths,
        )


def _last_float(series) -> float | None:
    value = series.iloc[-1]
    if value is None or pd.isna(value):
        return None
    return float(value)
