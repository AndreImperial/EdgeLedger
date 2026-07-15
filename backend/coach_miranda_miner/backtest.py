from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .indicators import alma, atr, cci, ema, macd, moving_average, relative_volume, rsi


MIN_VALIDATION_TRADES = 30


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    timeframe: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    total_return_pct: float
    max_drawdown_pct: float
    profit_factor: float
    expectancy_pct: float
    average_win_pct: float
    average_loss_pct: float
    long_trades: int = 0
    short_trades: int = 0
    sample_trades: list[dict] = field(default_factory=list)
    setup_stats: dict[str, dict] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def format(self) -> str:
        warning_lines = ""
        if self.warnings:
            warning_lines = "\nWarnings:\n" + "\n".join(f"- {warning}" for warning in self.warnings)
        samples = ""
        if self.sample_trades:
            lines = []
            for trade in self.sample_trades[:5]:
                lines.append(
                    f"- {trade['direction']} {trade['setup']} {trade['entry_time']} "
                    f"entry {trade['entry']:.6g} exit {trade['exit']:.6g} "
                    f"{trade['return_pct']:.2f}% via {trade['exit_reason']}"
                )
            samples = "\nRecent sample trades:\n" + "\n".join(lines)
        setup_lines = ""
        if self.setup_stats:
            lines = []
            for setup, stats in sorted(self.setup_stats.items()):
                lines.append(
                    f"- {setup}: trades {stats['trades']} | win {stats['win_rate']:.2%} "
                    f"| expectancy {stats['expectancy_pct']:.2f}% | "
                    f"L/S {stats['long_trades']}/{stats['short_trades']}"
                )
            setup_lines = "\nSetup breakdown:\n" + "\n".join(lines)
        return (
            f"Backtest {self.symbol} {self.timeframe}\n"
            f"Trades: {self.trades} | Wins: {self.wins} | Losses: {self.losses} "
            f"| Longs: {self.long_trades} | Shorts: {self.short_trades}\n"
            f"Win rate: {self.win_rate:.2%}\n"
            f"Total return: {self.total_return_pct:.2f}%\n"
            f"Max drawdown: {self.max_drawdown_pct:.2f}%\n"
            f"Profit factor: {self.profit_factor:.2f}\n"
            f"Expectancy: {self.expectancy_pct:.2f}% per trade\n"
            f"Avg win/loss: {self.average_win_pct:.2f}% / {self.average_loss_pct:.2f}%"
            f"{warning_lines}"
            f"{setup_lines}"
            f"{samples}"
        )


class MovingAverageBacktester:
    def __init__(
        self,
        short_ma: int,
        long_ma: int,
        rsi_period: int,
        rsi_buy_max: float,
        fee_bps: float,
        slippage_bps: float,
        stop_atr_multiple: float,
        target_r_multiple: float,
    ) -> None:
        self.short_ma = short_ma
        self.long_ma = long_ma
        self.rsi_period = rsi_period
        self.rsi_buy_max = rsi_buy_max
        self.fee_rate = fee_bps / 10_000
        self.slippage_rate = slippage_bps / 10_000
        self.stop_atr_multiple = stop_atr_multiple
        self.target_r_multiple = target_r_multiple

    def run(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> BacktestResult:
        frame = candles.copy()
        frame["short_ma"] = moving_average(frame["close"], self.short_ma)
        frame["long_ma"] = moving_average(frame["close"], self.long_ma)
        frame["rsi"] = rsi(frame["close"], self.rsi_period)
        frame["atr"] = atr(frame, 14)

        in_position = False
        entry_price = 0.0
        stop_price = 0.0
        target_price = 0.0
        equity = 1.0
        peak = 1.0
        max_drawdown = 0.0
        wins = 0
        losses = 0
        returns: list[float] = []

        for row in frame.itertuples(index=False):
            if (
                pd.isna(row.short_ma)
                or pd.isna(row.long_ma)
                or pd.isna(row.rsi)
                or pd.isna(row.atr)
            ):
                continue

            if not in_position and row.short_ma > row.long_ma and row.rsi <= self.rsi_buy_max:
                in_position = True
                entry_price = float(row.close) * (1 + self.slippage_rate)
                risk = float(row.atr) * self.stop_atr_multiple
                stop_price = entry_price - risk
                target_price = entry_price + (risk * self.target_r_multiple)
                continue

            if in_position:
                exit_price = None
                if float(row.low) <= stop_price:
                    exit_price = stop_price * (1 - self.slippage_rate)
                elif float(row.high) >= target_price:
                    exit_price = target_price * (1 - self.slippage_rate)
                elif row.short_ma < row.long_ma:
                    exit_price = float(row.close) * (1 - self.slippage_rate)

                if exit_price is None:
                    peak = max(peak, equity)
                    drawdown = (peak - equity) / peak
                    max_drawdown = max(max_drawdown, drawdown)
                    continue

                trade_return = ((exit_price - entry_price) / entry_price) - (self.fee_rate * 2)
                equity *= max(0.0, 1 + trade_return)
                returns.append(trade_return)
                if trade_return > 0:
                    wins += 1
                else:
                    losses += 1
                peak = max(peak, equity)
                drawdown = (peak - equity) / peak
                max_drawdown = max(max_drawdown, drawdown)
                in_position = False

        trades = wins + losses
        win_rate = wins / trades if trades else 0.0
        gross_profit = sum(value for value in returns if value > 0)
        gross_loss = abs(sum(value for value in returns if value < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99.0 if gross_profit > 0 else 0.0
        average_win = gross_profit / wins if wins else 0.0
        average_loss = gross_loss / losses if losses else 0.0
        expectancy = sum(returns) / trades if trades else 0.0
        return BacktestResult(
            symbol=symbol,
            timeframe=timeframe,
            trades=trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            total_return_pct=(equity - 1) * 100,
            max_drawdown_pct=max_drawdown * 100,
            profit_factor=float(profit_factor),
            expectancy_pct=expectancy * 100,
            average_win_pct=average_win * 100,
            average_loss_pct=average_loss * 100,
            long_trades=trades,
            short_trades=0,
            warnings=_backtest_warnings(trades, wins, losses),
        )


@dataclass(frozen=True)
class StrategyBacktestConfig:
    fee_bps: float
    slippage_bps: float
    stop_atr_multiple: float
    target_r_multiple: float
    allow_longs: bool = True
    allow_shorts: bool = True
    min_relative_volume: float = 1.2
    min_risk_reward: float = 2.0
    max_hold_bars: int = 24


@dataclass(frozen=True)
class _Signal:
    direction: str
    setup: str
    entry: float
    stop: float
    target: float
    risk_reward: float


class MirandaStrategyBacktester:
    """Historical approximation of the deterministic Miranda setup rules."""

    def __init__(self, config: StrategyBacktestConfig) -> None:
        self.config = config
        self.fee_rate = config.fee_bps / 10_000
        self.slippage_rate = config.slippage_bps / 10_000

    def run(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> BacktestResult:
        frame = candles.copy().reset_index(drop=True)
        frame["rsi"] = rsi(frame["close"], 14)
        frame["macd"], frame["macd_signal"] = macd(frame["close"])
        frame["atr"] = atr(frame, 14)
        frame["relative_volume"] = relative_volume(frame["volume"], 20)
        frame["ema_20"] = frame["close"].ewm(span=20, adjust=False).mean()
        frame["ema_50"] = frame["close"].ewm(span=50, adjust=False).mean()

        returns: list[float] = []
        setup_returns: dict[str, list[tuple[float, str]]] = {}
        sample_trades: list[dict] = []
        equity = 1.0
        peak = 1.0
        max_drawdown = 0.0
        wins = 0
        losses = 0
        long_trades = 0
        short_trades = 0
        index = 60

        while index < len(frame) - 2:
            signal = self._signal_at(frame, index)
            if signal is None:
                index += 1
                continue

            exit_index, exit_price, exit_reason = self._resolve_exit(frame, index + 1, signal)
            trade_return = self._trade_return(signal, exit_price)
            returns.append(trade_return)
            setup_returns.setdefault(signal.setup, []).append((trade_return, signal.direction))
            equity *= max(0.0, 1 + trade_return)
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak if peak else 0.0
            max_drawdown = max(max_drawdown, drawdown)
            if trade_return > 0:
                wins += 1
            else:
                losses += 1
            if signal.direction == "long":
                long_trades += 1
            else:
                short_trades += 1
            if len(sample_trades) < 10:
                sample_trades.append(
                    {
                        "direction": signal.direction,
                        "setup": signal.setup,
                        "entry_time": str(frame.iloc[index]["timestamp"]),
                        "entry": signal.entry,
                        "exit": exit_price,
                        "return_pct": trade_return * 100,
                        "exit_reason": exit_reason,
                    }
                )
            index = max(exit_index + 1, index + 1)

        trades = wins + losses
        win_rate = wins / trades if trades else 0.0
        gross_profit = sum(value for value in returns if value > 0)
        gross_loss = abs(sum(value for value in returns if value < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99.0 if gross_profit > 0 else 0.0
        average_win = gross_profit / wins if wins else 0.0
        average_loss = gross_loss / losses if losses else 0.0
        expectancy = sum(returns) / trades if trades else 0.0
        return BacktestResult(
            symbol=symbol,
            timeframe=timeframe,
            trades=trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            total_return_pct=(equity - 1) * 100,
            max_drawdown_pct=max_drawdown * 100,
            profit_factor=float(profit_factor),
            expectancy_pct=expectancy * 100,
            average_win_pct=average_win * 100,
            average_loss_pct=average_loss * 100,
            long_trades=long_trades,
            short_trades=short_trades,
            sample_trades=sample_trades,
            setup_stats=_setup_stats(setup_returns),
            warnings=_backtest_warnings(trades, wins, losses),
        )

    def _signal_at(self, frame: pd.DataFrame, index: int) -> _Signal | None:
        row = frame.iloc[index]
        if row[["rsi", "macd", "macd_signal", "atr", "relative_volume", "ema_20", "ema_50"]].isna().any():
            return None
        recent = frame.iloc[index - 24 : index + 1]
        prior = frame.iloc[index - 60 : index]
        if len(recent) < 25 or len(prior) < 40:
            return None
        if float(row["relative_volume"]) < self.config.min_relative_volume:
            return None

        long_signal = self._long_signal(frame, index, recent, prior)
        short_signal = self._short_signal(frame, index, recent, prior)
        if long_signal and self.config.allow_longs:
            return long_signal
        if short_signal and self.config.allow_shorts:
            return short_signal
        return None

    def _long_signal(self, frame: pd.DataFrame, index: int, recent: pd.DataFrame, prior: pd.DataFrame) -> _Signal | None:
        row = frame.iloc[index]
        if float(row["ema_20"]) <= float(row["ema_50"]):
            return None
        if not (35 <= float(row["rsi"]) <= 99):
            return None
        if float(row["macd"]) <= float(row["macd_signal"]):
            return None
        setup = _long_setup_name(recent, prior)
        if setup is None:
            return None
        return self._build_signal("long", setup, float(row["close"]), float(row["atr"]))

    def _short_signal(self, frame: pd.DataFrame, index: int, recent: pd.DataFrame, prior: pd.DataFrame) -> _Signal | None:
        row = frame.iloc[index]
        if float(row["ema_20"]) >= float(row["ema_50"]):
            return None
        if not (1 <= float(row["rsi"]) <= 65):
            return None
        if float(row["macd"]) >= float(row["macd_signal"]):
            return None
        setup = _short_setup_name(recent, prior)
        if setup is None:
            return None
        return self._build_signal("short", setup, float(row["close"]), float(row["atr"]))

    def _build_signal(self, direction: str, setup: str, close: float, atr_value: float) -> _Signal | None:
        risk = atr_value * self.config.stop_atr_multiple
        if risk <= 0:
            return None
        if direction == "long":
            entry = close * (1 + self.slippage_rate)
            stop = entry - risk
            target = entry + (risk * self.config.target_r_multiple)
            risk_reward = (target - entry) / (entry - stop)
        else:
            entry = close * (1 - self.slippage_rate)
            stop = entry + risk
            target = entry - (risk * self.config.target_r_multiple)
            risk_reward = (entry - target) / (stop - entry)
        if risk_reward < self.config.min_risk_reward:
            return None
        return _Signal(direction, setup, entry, stop, target, risk_reward)

    def _resolve_exit(self, frame: pd.DataFrame, start_index: int, signal: _Signal) -> tuple[int, float, str]:
        last_index = min(len(frame) - 1, start_index + self.config.max_hold_bars)
        for index in range(start_index, last_index + 1):
            row = frame.iloc[index]
            high = float(row["high"])
            low = float(row["low"])
            if signal.direction == "long":
                if low <= signal.stop:
                    return index, signal.stop * (1 - self.slippage_rate), "stop"
                if high >= signal.target:
                    return index, signal.target * (1 - self.slippage_rate), "target"
            else:
                if high >= signal.stop:
                    return index, signal.stop * (1 + self.slippage_rate), "stop"
                if low <= signal.target:
                    return index, signal.target * (1 + self.slippage_rate), "target"
        close = float(frame.iloc[last_index]["close"])
        if signal.direction == "long":
            return last_index, close * (1 - self.slippage_rate), "time"
        return last_index, close * (1 + self.slippage_rate), "time"

    def _trade_return(self, signal: _Signal, exit_price: float) -> float:
        if signal.direction == "long":
            raw = (exit_price - signal.entry) / signal.entry
        else:
            raw = (signal.entry - exit_price) / signal.entry
        return raw - (self.fee_rate * 2)


def _long_setup_name(recent: pd.DataFrame, prior: pd.DataFrame) -> str | None:
    close = float(recent.iloc[-1]["close"])
    previous_close = float(recent.iloc[-2]["close"])
    prison = recent.iloc[:-3] if len(recent) > 3 else prior.tail(40)
    resistance = float(prison["high"].max())
    support = float(prior["low"].tail(40).min())
    compression = _compression_ratio_df(prior, recent)
    if close >= resistance * 0.999 and previous_close >= resistance * 0.999:
        return "apex_squeeze" if compression < 0.8 else "tabo"
    latest = recent.iloc[-1]
    prior_row = recent.iloc[-2]
    lower_wick = min(float(latest["open"]), float(latest["close"])) - float(latest["low"])
    body = abs(float(latest["close"]) - float(latest["open"])) or close * 0.0001
    if float(latest["low"]) <= support * 1.012 and close > float(prior_row["close"]) and lower_wick >= body * 0.5:
        return "bounce"
    return None


def _short_setup_name(recent: pd.DataFrame, prior: pd.DataFrame) -> str | None:
    close = float(recent.iloc[-1]["close"])
    previous_close = float(recent.iloc[-2]["close"])
    prison = recent.iloc[:-3] if len(recent) > 3 else prior.tail(40)
    support = float(prison["low"].min())
    resistance = float(prior["high"].tail(40).max())
    compression = _compression_ratio_df(prior, recent)
    if close <= support * 1.001 and previous_close <= support * 1.001:
        return "apex_squeeze" if compression < 0.8 else "tabo"
    latest = recent.iloc[-1]
    prior_row = recent.iloc[-2]
    upper_wick = float(latest["high"]) - max(float(latest["open"]), float(latest["close"]))
    body = abs(float(latest["close"]) - float(latest["open"])) or close * 0.0001
    if float(latest["high"]) >= resistance * 0.988 and close < float(prior_row["close"]) and upper_wick >= body * 0.5:
        return "bounce"
    return None


def _compression_ratio_df(prior: pd.DataFrame, recent: pd.DataFrame) -> float:
    prior_range = float(prior["high"].tail(40).max() - prior["low"].tail(40).min())
    recent_range = float(recent["high"].tail(20).max() - recent["low"].tail(20).min())
    if prior_range <= 0:
        return 1.0
    return recent_range / prior_range


def _setup_stats(setup_returns: dict[str, list[tuple[float, str]]]) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for setup, values in setup_returns.items():
        returns = [item[0] for item in values]
        trades = len(returns)
        wins = sum(1 for value in returns if value > 0)
        stats[setup] = {
            "trades": trades,
            "wins": wins,
            "losses": trades - wins,
            "win_rate": wins / trades if trades else 0.0,
            "expectancy_pct": (sum(returns) / trades) * 100 if trades else 0.0,
            "long_trades": sum(1 for _, direction in values if direction == "long"),
            "short_trades": sum(1 for _, direction in values if direction == "short"),
        }
    return stats


def _backtest_warnings(trades: int, wins: int, losses: int) -> list[str]:
    warnings: list[str] = []
    if trades < MIN_VALIDATION_TRADES:
        trade_label = "trade" if trades == 1 else "trades"
        warnings.append(
            f"Only {trades} {trade_label}; this is a smoke test, not strategy validation. "
            f"Minimum validation target is {MIN_VALIDATION_TRADES} trades."
        )
    if trades > 0 and losses == 0:
        warnings.append("No losing trades observed; profit factor is not statistically stable.")
    if trades > 0 and wins == 0:
        warnings.append("No winning trades observed; review setup and execution assumptions.")
    return warnings


class AlmaCciScalpBacktester:
    """Approximation of the 3m EMA9/ALMA20 plus CCI20 scalp rules."""

    def __init__(self, config: StrategyBacktestConfig) -> None:
        self.config = config
        self.fee_rate = config.fee_bps / 10_000
        self.slippage_rate = config.slippage_bps / 10_000

    def run(self, symbol: str, timeframe: str, candles: pd.DataFrame) -> BacktestResult:
        frame = candles.copy().reset_index(drop=True)
        frame["ema_9"] = ema(frame["close"], 9)
        frame["alma_20"] = alma(frame["close"], 20, 0.8, 8)
        frame["cci_20"] = cci(frame, 20)
        frame["atr"] = atr(frame, 14)
        frame["relative_volume"] = relative_volume(frame["volume"], 20)

        returns: list[float] = []
        setup_returns: dict[str, list[tuple[float, str]]] = {}
        sample_trades: list[dict] = []
        equity = 1.0
        peak = 1.0
        max_drawdown = 0.0
        wins = losses = long_trades = short_trades = 0
        index = 40
        while index < len(frame) - 2:
            signal = self._signal_at(frame, index)
            if signal is None:
                index += 1
                continue
            exit_index, exit_price, exit_reason = MirandaStrategyBacktester(self.config)._resolve_exit(
                frame,
                index + 1,
                signal,
            )
            trade_return = MirandaStrategyBacktester(self.config)._trade_return(signal, exit_price)
            returns.append(trade_return)
            setup_returns.setdefault(signal.setup, []).append((trade_return, signal.direction))
            equity *= max(0.0, 1 + trade_return)
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, (peak - equity) / peak if peak else 0.0)
            wins += int(trade_return > 0)
            losses += int(trade_return <= 0)
            long_trades += int(signal.direction == "long")
            short_trades += int(signal.direction == "short")
            if len(sample_trades) < 10:
                sample_trades.append(
                    {
                        "direction": signal.direction,
                        "setup": signal.setup,
                        "entry_time": str(frame.iloc[index]["timestamp"]),
                        "entry": signal.entry,
                        "exit": exit_price,
                        "return_pct": trade_return * 100,
                        "exit_reason": exit_reason,
                    }
                )
            index = max(exit_index + 1, index + 1)

        trades = wins + losses
        gross_profit = sum(value for value in returns if value > 0)
        gross_loss = abs(sum(value for value in returns if value < 0))
        return BacktestResult(
            symbol=symbol,
            timeframe=timeframe,
            trades=trades,
            wins=wins,
            losses=losses,
            win_rate=wins / trades if trades else 0.0,
            total_return_pct=(equity - 1) * 100,
            max_drawdown_pct=max_drawdown * 100,
            profit_factor=gross_profit / gross_loss if gross_loss > 0 else 99.0 if gross_profit > 0 else 0.0,
            expectancy_pct=(sum(returns) / trades) * 100 if trades else 0.0,
            average_win_pct=(gross_profit / wins) * 100 if wins else 0.0,
            average_loss_pct=(gross_loss / losses) * 100 if losses else 0.0,
            long_trades=long_trades,
            short_trades=short_trades,
            sample_trades=sample_trades,
            setup_stats=_setup_stats(setup_returns),
            warnings=_backtest_warnings(trades, wins, losses),
        )

    def _signal_at(self, frame: pd.DataFrame, index: int) -> _Signal | None:
        row = frame.iloc[index]
        if row[["ema_9", "alma_20", "cci_20", "atr", "relative_volume"]].isna().any():
            return None
        if float(row["relative_volume"]) < self.config.min_relative_volume:
            return None
        prior = frame.iloc[index - 1]
        long_cross = float(prior["ema_9"]) <= float(prior["alma_20"]) and float(row["ema_9"]) > float(row["alma_20"])
        short_cross = float(prior["ema_9"]) >= float(prior["alma_20"]) and float(row["ema_9"]) < float(row["alma_20"])
        long_cci = float(prior["cci_20"]) <= -100 < float(row["cci_20"])
        short_cci = float(prior["cci_20"]) >= 100 > float(row["cci_20"])
        if self.config.allow_longs and long_cross and long_cci:
            return self._build_signal("long", float(row["close"]), float(row["atr"]))
        if self.config.allow_shorts and short_cross and short_cci:
            return self._build_signal("short", float(row["close"]), float(row["atr"]))
        return None

    def _build_signal(self, direction: str, close: float, atr_value: float) -> _Signal | None:
        risk = atr_value * self.config.stop_atr_multiple
        if risk <= 0:
            return None
        if direction == "long":
            entry = close * (1 + self.slippage_rate)
            stop = entry - risk
            target = entry + risk * self.config.target_r_multiple
            rr = (target - entry) / (entry - stop)
        else:
            entry = close * (1 - self.slippage_rate)
            stop = entry + risk
            target = entry - risk * self.config.target_r_multiple
            rr = (entry - target) / (stop - entry)
        if rr < self.config.min_risk_reward:
            return None
        return _Signal(direction, "alma_cci_scalp", entry, stop, target, rr)
