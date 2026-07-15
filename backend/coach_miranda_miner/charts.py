from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


class ChartRenderer:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> str:
        safe_symbol = symbol.replace("/", "_")
        path = self.output_dir / f"{safe_symbol}_{timeframe}.png"

        recent = candles.tail(80).copy()
        dates = mdates.date2num(recent["timestamp"].dt.to_pydatetime())

        fig, (price_ax, volume_ax) = plt.subplots(
            2,
            1,
            figsize=(12, 7),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )
        fig.patch.set_facecolor("#101418")
        price_ax.set_facecolor("#101418")
        volume_ax.set_facecolor("#101418")

        width = _candle_width(dates)
        for date, row in zip(dates, recent.itertuples(index=False), strict=True):
            color = "#2fd17c" if row.close >= row.open else "#ff5b5b"
            price_ax.vlines(date, row.low, row.high, color=color, linewidth=1.0)
            lower = min(row.open, row.close)
            height = abs(row.close - row.open) or row.close * 0.0001
            price_ax.add_patch(
                plt.Rectangle(
                    (date - width / 2, lower),
                    width,
                    height,
                    facecolor=color,
                    edgecolor=color,
                    linewidth=0.8,
                )
            )
            volume_ax.bar(date, row.volume, width=width, color=color, alpha=0.6)

        price_ax.set_title(f"{symbol} {timeframe}", color="#f5f7fb", fontsize=14)
        price_ax.grid(color="#2b333c", linewidth=0.5)
        volume_ax.grid(color="#2b333c", linewidth=0.5)
        for axis in (price_ax, volume_ax):
            axis.tick_params(colors="#c8d0d9")
            for spine in axis.spines.values():
                spine.set_color("#2b333c")

        volume_ax.xaxis_date()
        volume_ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(path, dpi=140)
        plt.close(fig)
        return str(path)


def _candle_width(dates) -> float:
    if len(dates) < 2:
        return 0.02
    return max((dates[-1] - dates[-2]) * 0.7, 0.005)

