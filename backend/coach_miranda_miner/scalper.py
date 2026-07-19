from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from .indicators import alma, atr, cci, ema, relative_volume
from .models import Candidate, Setup, SetupScore, SignalState, TradeThesis, ValidationResult
from .validator import ThesisValidator


@dataclass(frozen=True)
class ScalpQuality:
    grade: str
    score: float
    oi_price_read: str
    bias_strength: str
    structure_strength: str
    atr_pct: float | None
    cross_age_bars: int | None
    cci_slope: float | None
    spread_estimate_pct: float | None
    volatility_ok: bool
    reasons: list[str]


@dataclass(frozen=True)
class ScalpScanResult:
    candidate: Candidate
    score: SetupScore
    candles: dict[str, pd.DataFrame]
    thesis: TradeThesis
    validation: ValidationResult
    quality: ScalpQuality
    scanned_at: datetime
    execution_candle_time: datetime | None
    latest_candle_time: datetime | None
    alert_sent: bool = False


class AlmaCciScalper:
    def __init__(
        self,
        validator: ThesisValidator,
        alma_length: int = 20,
        alma_offset: float = 0.8,
        alma_sigma: float = 8.0,
        ema_length: int = 9,
        cci_length: int = 20,
        target_r_multiple: float = 2.0,
        min_atr_pct: float = 0.12,
        max_atr_pct: float = 2.8,
        cross_fresh_bars: int = 3,
    ) -> None:
        self.validator = validator
        self.alma_length = alma_length
        self.alma_offset = alma_offset
        self.alma_sigma = alma_sigma
        self.ema_length = ema_length
        self.cci_length = cci_length
        self.target_r_multiple = target_r_multiple
        self.min_atr_pct = min_atr_pct
        self.max_atr_pct = max_atr_pct
        self.cross_fresh_bars = cross_fresh_bars

    def analyze(
        self,
        candidate: Candidate,
        candles: dict[str, pd.DataFrame],
        rank: int,
        market_regime,
    ) -> ScalpScanResult:
        enriched = {timeframe: self._with_indicators(frame) for timeframe, frame in candles.items()}
        thesis = self._thesis(candidate, enriched, market_regime)
        execution_atr = _last_float(atr(enriched["3m"], 14))
        validation = self.validator.validate(thesis, market_regime, execution_atr)
        quality = _scalp_quality(
            candidate,
            thesis,
            enriched,
            self.min_atr_pct,
            self.max_atr_pct,
            self.cross_fresh_bars,
        )
        score = _scalp_score(candidate, rank, thesis, enriched, quality)
        return ScalpScanResult(
            candidate=candidate,
            score=score,
            candles=enriched,
            thesis=thesis,
            validation=validation,
            quality=quality,
            scanned_at=datetime.now(timezone.utc),
            execution_candle_time=_execution_candle_time(enriched["3m"], thesis.direction),
            latest_candle_time=_last_timestamp(enriched["3m"]),
        )

    def _with_indicators(self, candles: pd.DataFrame) -> pd.DataFrame:
        frame = candles.copy()
        frame["ema_9"] = ema(frame["close"], self.ema_length)
        frame["alma_20"] = alma(frame["close"], self.alma_length, self.alma_offset, self.alma_sigma)
        frame["cci_20"] = cci(frame, self.cci_length)
        frame["relative_volume"] = relative_volume(frame["volume"], 20)
        frame["atr"] = atr(frame, 14)
        return frame

    def _thesis(self, candidate: Candidate, candles: dict[str, pd.DataFrame], market_regime) -> TradeThesis:
        required = ("15m", "5m", "3m")
        if any(timeframe not in candles or len(candles[timeframe]) < self.cci_length for timeframe in required):
            return TradeThesis(
                symbol=candidate.route_symbol,
                setup=Setup.ALMA_CCI_SCALP,
                signal=SignalState.WAIT,
                direction="none",
                confidence=0.0,
                invalidation_reason="Not enough candles for CCI 20 scalp confirmation.",
                evidence=["Needs 15m, 5m, and 3m candles with at least 20 bars."],
            )

        bias = _bias(candles["15m"])
        long_structure = _aligned_long(candles["5m"])
        short_structure = _aligned_short(candles["5m"])
        execution = candles["3m"]
        rel_vol = _last_float(execution["relative_volume"]) or 0.0

        long_cross_age = _cross_age(execution["ema_9"], execution["alma_20"], "long", self.cross_fresh_bars)
        short_cross_age = _cross_age(execution["ema_9"], execution["alma_20"], "short", self.cross_fresh_bars)
        long_cross = long_cross_age is not None
        short_cross = short_cross_age is not None
        long_cci_cross = _cci_rising_from_lower_zone(execution["cci_20"], self.cross_fresh_bars)
        short_cci_cross = _cci_falling_from_upper_zone(execution["cci_20"], self.cross_fresh_bars)
        long_ready = bias == "long" and long_structure and _aligned_long(execution)
        short_ready = bias == "short" and short_structure and _aligned_short(execution)
        atr_pct = _atr_pct(execution)
        if atr_pct is not None and (atr_pct < self.min_atr_pct or atr_pct > self.max_atr_pct):
            return TradeThesis(
                symbol=candidate.route_symbol,
                setup=Setup.ALMA_CCI_SCALP,
                signal=SignalState.REJECT,
                direction="none",
                confidence=0.2,
                invalidation_reason=(
                    f"Scalp volatility out of range: ATR {atr_pct:.2f}% "
                    f"not within {self.min_atr_pct:.2f}% - {self.max_atr_pct:.2f}%."
                ),
                evidence=["Volatility floor/ceiling filter rejected this scalp candidate."],
            )

        if long_ready and long_cross and long_cci_cross and market_regime.longs_allowed:
            return self._build_trade(candidate, execution, "long", SignalState.ENTER, rel_vol, long_cross, long_cci_cross)
        if short_ready and short_cross and short_cci_cross and market_regime.shorts_allowed:
            return self._build_trade(
                candidate,
                execution,
                "short",
                SignalState.ENTER,
                rel_vol,
                short_cross,
                short_cci_cross,
            )
        if bias == "long" and long_structure and _aligned_long(execution):
            return self._build_trade(candidate, execution, "long", SignalState.WATCH, rel_vol, long_cross, long_cci_cross)
        if bias == "short" and short_structure and _aligned_short(execution):
            return self._build_trade(
                candidate,
                execution,
                "short",
                SignalState.WATCH,
                rel_vol,
                short_cross,
                short_cci_cross,
            )

        return TradeThesis(
            symbol=candidate.route_symbol,
            setup=Setup.ALMA_CCI_SCALP,
            signal=SignalState.WAIT,
            direction="none",
            confidence=0.25,
            invalidation_reason="No aligned scalp bias/structure/execution stack.",
            evidence=[
                f"15m bias: {bias}",
                f"5m long structure: {long_structure}",
                f"5m short structure: {short_structure}",
                f"3m EMA/ALMA cross age long/short: {long_cross_age}/{short_cross_age}",
                "3m execution has not aligned with ALMA/EMA plus CCI trigger.",
            ],
        )

    def _build_trade(
        self,
        candidate: Candidate,
        execution: pd.DataFrame,
        direction: str,
        signal: SignalState,
        rel_vol: float,
        alma_cross: bool,
        cci_cross: bool,
    ) -> TradeThesis:
        latest = execution.iloc[-1]
        entry = float(latest["close"])
        atr_value = _last_float(atr(execution, 14)) or max(entry * 0.003, 0.000001)
        recent = execution.tail(12)
        if direction == "long":
            swing_stop = float(recent["low"].min())
            stop = min(swing_stop, entry - atr_value)
            risk = max(entry - stop, atr_value * 0.5)
            stop = entry - risk
            target = entry + risk * self.target_r_multiple
        else:
            swing_stop = float(recent["high"].max())
            stop = max(swing_stop, entry + atr_value)
            risk = max(stop - entry, atr_value * 0.5)
            stop = entry + risk
            target = entry - risk * self.target_r_multiple
        confidence = 0.58
        if signal == SignalState.ENTER:
            confidence += 0.14
        if rel_vol >= 1.3:
            confidence += 0.08
        if alma_cross:
            confidence += 0.06
        if cci_cross:
            confidence += 0.06
        confidence = min(confidence, 0.88)
        trigger_text = "confirmed" if signal == SignalState.ENTER else "forming"
        return TradeThesis(
            symbol=candidate.route_symbol,
            setup=Setup.ALMA_CCI_SCALP,
            signal=signal,
            direction=direction,
            confidence=confidence,
            entry=entry,
            stop_loss=stop,
            targets=[target],
            risk_reward=self.target_r_multiple,
            evidence=[
                f"15m bias, 5m structure, and 3m execution are stacked {direction}.",
                f"3m EMA9 / ALMA(20, 0.8, 8) trigger is {trigger_text}.",
                f"CCI 20 momentum trigger is {trigger_text} from the -100/+100 zone; rel volume {rel_vol:.2f}x.",
                "Scalp model uses 15m bias, 5m structure, 3m execution.",
            ],
        )


def _scalp_score(
    candidate: Candidate,
    rank: int,
    thesis: TradeThesis,
    candles: dict[str, pd.DataFrame],
    quality: ScalpQuality,
) -> SetupScore:
    rel_vol = _last_float(candles["3m"]["relative_volume"])
    cci_value = _last_float(candles["3m"]["cci_20"])
    score = quality.score
    if thesis.signal == SignalState.ENTER:
        score += 15
    if rel_vol is not None:
        score += min(max((rel_vol - 1.0) * 10, 0), 15)
    reasons = [
        f"Scalp signal: {thesis.signal.value.upper()} {thesis.direction.upper()}",
        f"Scalp grade: {quality.grade}.",
        f"OI/price read: {quality.oi_price_read}.",
    ]
    if rel_vol is not None:
        reasons.append(f"3m relative volume {rel_vol:.2f}x.")
    if cci_value is not None:
        reasons.append(f"3m CCI 20 is {cci_value:.1f}.")
    reasons.extend(quality.reasons[:4])
    return SetupScore(
        symbol=candidate.route_symbol,
        rank=rank,
        score=score,
        volume_24h_usd=candidate.volume_24h_usd,
        price_change_24h_pct=None,
        oi_change_24h_pct=candidate.open_interest_change_24h_pct,
        relative_volume=rel_vol,
        btc_regime_ok=True,
        prefilter_reasons=reasons,
    )


def _scalp_quality(
    candidate: Candidate,
    thesis: TradeThesis,
    candles: dict[str, pd.DataFrame],
    min_atr_pct: float,
    max_atr_pct: float,
    cross_fresh_bars: int,
) -> ScalpQuality:
    execution = candles["3m"]
    fifteen = candles["15m"]
    five = candles["5m"]
    atr_pct = _atr_pct(execution)
    rel_vol = _last_float(execution["relative_volume"]) or 0.0
    cci_slope = _cci_slope(execution["cci_20"])
    direction = thesis.direction
    cross_age = (
        _cross_age(execution["ema_9"], execution["alma_20"], direction, cross_fresh_bars)
        if direction in {"long", "short"}
        else None
    )
    price_change = _price_change_pct(fifteen, 24)
    oi_change = candidate.open_interest_change_24h_pct
    oi_price_read = _oi_price_read(price_change, oi_change)
    bias_strength = _bias_strength(fifteen)
    structure_strength = _structure_strength(five, direction)
    spread_estimate = _spread_estimate_pct(execution)
    volatility_ok = atr_pct is not None and min_atr_pct <= atr_pct <= max_atr_pct
    score = thesis.confidence * 45
    if thesis.signal == SignalState.ENTER:
        score += 18
    elif thesis.signal == SignalState.WATCH:
        score += 8
    if rel_vol >= 1.5:
        score += 10
    if oi_change is not None:
        score += min(abs(oi_change) * 0.7, 18)
    if oi_price_read in {"long accumulation", "short buildup"}:
        score += 10
    if cross_age is not None:
        score += max(0, (cross_fresh_bars + 1 - cross_age) * 3)
    if volatility_ok:
        score += 8
    if abs(cci_slope or 0.0) >= 25:
        score += 5
    if spread_estimate is not None and spread_estimate <= 0.45:
        score += 4
    score = round(min(score, 100.0), 2)
    grade = "A+" if score >= 88 else "A" if score >= 76 else "B" if score >= 62 else "C" if score >= 48 else "D"
    reasons = [
        f"15m bias strength: {bias_strength}",
        f"5m structure strength: {structure_strength}",
    ]
    if atr_pct is not None:
        reasons.append(f"3m ATR volatility {atr_pct:.2f}%.")
    if cross_age is not None:
        reasons.append(f"EMA9/ALMA20 cross is {cross_age} bars old.")
    if cci_slope is not None:
        reasons.append(f"CCI20 slope {cci_slope:.1f}.")
    if spread_estimate is not None:
        reasons.append(f"Estimated spread/liquidity noise {spread_estimate:.2f}%.")
    return ScalpQuality(
        grade=grade,
        score=score,
        oi_price_read=oi_price_read,
        bias_strength=bias_strength,
        structure_strength=structure_strength,
        atr_pct=atr_pct,
        cross_age_bars=cross_age,
        cci_slope=cci_slope,
        spread_estimate_pct=spread_estimate,
        volatility_ok=volatility_ok,
        reasons=reasons,
    )


def _bias(candles: pd.DataFrame) -> str:
    if _aligned_long(candles) and (_last_float(candles["cci_20"]) or 0) > 0:
        return "long"
    if _aligned_short(candles) and (_last_float(candles["cci_20"]) or 0) < 0:
        return "short"
    return "neutral"


def _aligned_long(candles: pd.DataFrame) -> bool:
    latest = candles.iloc[-1]
    return _valid(latest["alma_20"], latest["ema_9"], latest["cci_20"]) and (
        latest["ema_9"] > latest["alma_20"] and latest["cci_20"] > -100
    )


def _aligned_short(candles: pd.DataFrame) -> bool:
    latest = candles.iloc[-1]
    return _valid(latest["alma_20"], latest["ema_9"], latest["cci_20"]) and (
        latest["ema_9"] < latest["alma_20"] and latest["cci_20"] < 100
    )


def _crossed_above(left: pd.Series, right: pd.Series) -> bool:
    return _valid_pair(left, right) and left.iloc[-2] <= right.iloc[-2] and left.iloc[-1] > right.iloc[-1]


def _crossed_below(left: pd.Series, right: pd.Series) -> bool:
    return _valid_pair(left, right) and left.iloc[-2] >= right.iloc[-2] and left.iloc[-1] < right.iloc[-1]


def _cci_rising_from_lower_zone(series: pd.Series, lookback: int = 3) -> bool:
    start = max(1, len(series) - lookback)
    for index in range(start, len(series)):
        if not _valid(series.iloc[index - 1], series.iloc[index]):
            continue
        previous = float(series.iloc[index - 1])
        current = float(series.iloc[index])
        if current > previous and previous <= -100 and current > -100:
            return True
    return False


def _cci_falling_from_upper_zone(series: pd.Series, lookback: int = 3) -> bool:
    start = max(1, len(series) - lookback)
    for index in range(start, len(series)):
        if not _valid(series.iloc[index - 1], series.iloc[index]):
            continue
        previous = float(series.iloc[index - 1])
        current = float(series.iloc[index])
        if current < previous and previous >= 100 and current < 100:
            return True
    return False


def _cross_age(left: pd.Series, right: pd.Series, direction: str, lookback: int) -> int | None:
    start = max(1, len(left) - lookback)
    for index in range(len(left) - 1, start - 1, -1):
        if not _valid(left.iloc[index - 1], left.iloc[index], right.iloc[index - 1], right.iloc[index]):
            continue
        if direction == "long" and left.iloc[index - 1] <= right.iloc[index - 1] and left.iloc[index] > right.iloc[index]:
            return len(left) - 1 - index
        if direction == "short" and left.iloc[index - 1] >= right.iloc[index - 1] and left.iloc[index] < right.iloc[index]:
            return len(left) - 1 - index
    return None


def _atr_pct(candles: pd.DataFrame) -> float | None:
    latest_atr = _last_float(candles["atr"]) if "atr" in candles else None
    close = float(candles.iloc[-1]["close"])
    if latest_atr is None or close <= 0:
        return None
    return (latest_atr / close) * 100


def _cci_slope(series: pd.Series) -> float | None:
    if len(series) < 4 or not _valid(series.iloc[-1], series.iloc[-4]):
        return None
    return float(series.iloc[-1] - series.iloc[-4]) / 3


def _price_change_pct(candles: pd.DataFrame, bars: int) -> float | None:
    if len(candles) <= bars:
        return None
    start = float(candles.iloc[-bars]["close"])
    end = float(candles.iloc[-1]["close"])
    if start <= 0:
        return None
    return ((end - start) / start) * 100


def _oi_price_read(price_change: float | None, oi_change: float | None) -> str:
    if price_change is None or oi_change is None:
        return "OI unavailable"
    if oi_change > 5 and price_change > 0:
        return "long accumulation"
    if oi_change > 5 and price_change < 0:
        return "short buildup"
    if oi_change < -5:
        return "position unwind"
    return "neutral"


def _bias_strength(candles: pd.DataFrame) -> str:
    latest = candles.iloc[-1]
    distance = abs(float(latest["ema_9"]) - float(latest["alma_20"])) / max(float(latest["close"]), 0.000001) * 100
    cci_value = abs(float(latest["cci_20"])) if _valid(latest["cci_20"]) else 0.0
    if distance >= 0.25 and cci_value >= 100:
        return "strong"
    if distance >= 0.08:
        return "moderate"
    return "weak"


def _structure_strength(candles: pd.DataFrame, direction: str) -> str:
    if direction not in {"long", "short"} or len(candles) < 12:
        return "unclear"
    recent = candles.tail(12)
    higher = float(recent["close"].iloc[-1]) > float(recent["close"].iloc[0])
    rel_vol = _last_float(candles["relative_volume"]) or 0.0
    aligned = higher if direction == "long" else not higher
    if aligned and rel_vol >= 1.4:
        return "strong"
    if aligned:
        return "moderate"
    return "weak"


def _spread_estimate_pct(candles: pd.DataFrame) -> float | None:
    latest = candles.iloc[-1]
    close = float(latest["close"])
    if close <= 0:
        return None
    return ((float(latest["high"]) - float(latest["low"])) / close) * 100


def _valid_pair(left: pd.Series, right: pd.Series) -> bool:
    return _valid(left.iloc[-2], left.iloc[-1], right.iloc[-2], right.iloc[-1])


def _valid(*values) -> bool:
    return all(value is not None and not pd.isna(value) for value in values)


def _last_float(series: pd.Series) -> float | None:
    value = series.iloc[-1]
    if value is None or pd.isna(value):
        return None
    return float(value)


def _last_timestamp(candles: pd.DataFrame) -> datetime | None:
    if candles.empty or "timestamp" not in candles:
        return None
    value = pd.to_datetime(candles.iloc[-1]["timestamp"], utc=True)
    return value.to_pydatetime()


def _execution_candle_time(candles: pd.DataFrame, direction: str) -> datetime | None:
    if direction not in {"long", "short"} or len(candles) < 2:
        return _last_timestamp(candles)
    lookback = min(6, len(candles) - 1)
    for index in range(len(candles) - 1, len(candles) - 1 - lookback, -1):
        if index <= 0:
            break
        left_prev = candles["ema_9"].iloc[index - 1]
        left_now = candles["ema_9"].iloc[index]
        right_prev = candles["alma_20"].iloc[index - 1]
        right_now = candles["alma_20"].iloc[index]
        if not _valid(left_prev, left_now, right_prev, right_now):
            continue
        if direction == "long" and left_prev <= right_prev and left_now > right_now:
            return pd.to_datetime(candles.iloc[index]["timestamp"], utc=True).to_pydatetime()
        if direction == "short" and left_prev >= right_prev and left_now < right_now:
            return pd.to_datetime(candles.iloc[index]["timestamp"], utc=True).to_pydatetime()
    return _last_timestamp(candles)
