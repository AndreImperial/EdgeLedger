from __future__ import annotations

import base64
import json
from pathlib import Path

from .models import CandleSnapshot, IntelligencePack, Setup, SignalState, TradeThesis
from .prompts import MIRANDA_SYSTEM_PROMPT


class Analyzer:
    def analyze(self, pack: IntelligencePack) -> TradeThesis:
        raise NotImplementedError


class RuleBasedAnalyzer(Analyzer):
    """Free deterministic Miranda analyzer using candles and indicators."""

    def analyze(self, pack: IntelligencePack) -> TradeThesis:
        by_timeframe = {item.timeframe: item for item in pack.indicators}
        tf_15m = by_timeframe.get("15m") or pack.indicators[-1]
        tf_1h = by_timeframe.get("1h") or pack.indicators[-1]
        tf_4h = by_timeframe.get("4h") or tf_1h
        candles_15m = pack.candles.get("15m", [])
        candles_1h = pack.candles.get("1h", [])
        candles_4h = pack.candles.get("4h", [])

        if not pack.market_regime.longs_allowed and not pack.market_regime.shorts_allowed:
            return TradeThesis(
                symbol=pack.candidate.route_symbol,
                setup=Setup.NONE,
                signal=SignalState.REJECT,
                direction="none",
                confidence=0.0,
                invalidation_reason=pack.market_regime.reason,
                evidence=[pack.market_regime.reason],
            )

        prison = _prison_break_state(candles_15m)
        short_prison = _short_prison_break_state(candles_15m)
        if _is_long_false_breakout(candles_15m) or _is_short_false_breakout(candles_15m):
            return TradeThesis(
                symbol=pack.candidate.route_symbol,
                setup=Setup.NONE,
                signal=SignalState.REJECT,
                direction="none",
                confidence=0.15,
                invalidation_reason="False breakout: price closed back inside the prison range.",
                evidence=[
                    "False breakout filter rejected the setup.",
                    "Price broke structure and then closed back inside the prior range.",
                ],
            )
        relative_volume = tf_15m.relative_volume or 0.0
        volume_confirmed = relative_volume >= 1.35
        breakout_volume_confirmed = relative_volume >= 1.55
        compression = _compression_ratio(candles_15m)
        support = _support_zone(candles_1h or candles_15m)
        resistance = _resistance_zone(candles_1h or candles_15m)
        trend_1h = _trend_bias(candles_1h)
        trend_4h = _trend_bias(candles_4h)
        long_trend_ok = trend_1h != "down" and trend_4h != "down"
        short_trend_ok = trend_1h != "up" and trend_4h != "up"
        long_continuation_ok = trend_1h == "up" and trend_4h != "down"
        short_continuation_ok = trend_1h == "down" and trend_4h != "up"
        macd_bullish = (
            tf_1h.macd is not None
            and tf_1h.macd_signal is not None
            and tf_1h.macd > tf_1h.macd_signal
        )
        macd_bearish = (
            tf_1h.macd is not None
            and tf_1h.macd_signal is not None
            and tf_1h.macd < tf_1h.macd_signal
        )
        rsi_ok = tf_15m.rsi is not None and 38 <= tf_15m.rsi <= 66
        short_rsi_ok = tf_15m.rsi is not None and 34 <= tf_15m.rsi <= 62
        long_overextended = tf_15m.rsi is not None and tf_15m.rsi > 74
        short_overextended = tf_15m.rsi is not None and tf_15m.rsi < 26
        if long_overextended and not pack.market_regime.shorts_allowed:
            return _rejected(pack, "overextended RSI", f"15m RSI is overheated at {tf_15m.rsi:.2f}.")
        if short_overextended and not pack.market_regime.longs_allowed:
            return _rejected(pack, "overextended RSI", f"15m RSI is washed out at {tf_15m.rsi:.2f}.")

        if pack.market_regime.longs_allowed and not long_overextended and long_trend_ok and _transition_play(tf_15m, tf_1h):
            return _long_thesis(
                pack,
                Setup.TRANSITION_PLAY,
                _enter_signal(prison, volume_confirmed),
                confidence=_setup_confidence(
                    Setup.TRANSITION_PLAY,
                    prison,
                    volume_confirmed,
                    compression,
                    macd_bullish,
                    long_trend_ok,
                    0.65,
                ),
                evidence=[
                    "RSI is recovering from a weak zone.",
                    "1h MACD momentum supports reversal conditions.",
                    _setup_score_evidence(Setup.TRANSITION_PLAY, 0.65, relative_volume, compression),
                    _trend_evidence(trend_1h, trend_4h),
                    f"15m prison-break state is {prison.value}.",
                ],
            )

        if (
            pack.market_regime.shorts_allowed
            and not short_overextended
            and short_trend_ok
            and _short_transition_play(tf_15m, tf_1h)
        ):
            return _short_thesis(
                pack,
                Setup.TRANSITION_PLAY,
                _enter_signal(short_prison, volume_confirmed),
                confidence=_setup_confidence(
                    Setup.TRANSITION_PLAY,
                    short_prison,
                    volume_confirmed,
                    compression,
                    macd_bearish,
                    short_trend_ok,
                    0.65,
                ),
                evidence=[
                    "Short transition: RSI is rolling over from a strong zone.",
                    "1h MACD momentum supports bearish reversal conditions.",
                    _setup_score_evidence(Setup.TRANSITION_PLAY, 0.65, relative_volume, compression),
                    _trend_evidence(trend_1h, trend_4h),
                    f"15m short prison-break state is {short_prison.value}.",
                ],
            )

        if (
            pack.market_regime.longs_allowed
            and long_trend_ok
            and support
            and _is_bounce(candles_15m, support)
            and rsi_ok
        ):
            return _long_thesis(
                pack,
                Setup.BOUNCE,
                _enter_signal(prison, volume_confirmed),
                confidence=_setup_confidence(
                    Setup.BOUNCE,
                    prison,
                    volume_confirmed,
                    compression,
                    macd_bullish,
                    long_trend_ok,
                    support["quality"],
                ),
                evidence=[
                    f"Support zone has {support['touches']} wick touches and quality {support['quality']:.2f}.",
                    "Latest candles show rejection near support.",
                    _setup_score_evidence(Setup.BOUNCE, support["quality"], relative_volume, compression),
                    _trend_evidence(trend_1h, trend_4h),
                    f"15m RSI is {tf_15m.rsi:.2f}.",
                ],
            )

        if (
            pack.market_regime.shorts_allowed
            and short_trend_ok
            and resistance
            and _is_resistance_rejection(candles_15m, resistance)
            and short_rsi_ok
        ):
            return _short_thesis(
                pack,
                Setup.BOUNCE,
                _enter_signal(short_prison, volume_confirmed),
                confidence=_setup_confidence(
                    Setup.BOUNCE,
                    short_prison,
                    volume_confirmed,
                    compression,
                    macd_bearish,
                    short_trend_ok,
                    resistance["quality"],
                ),
                evidence=[
                    f"Resistance zone has {resistance['touches']} wick touches and quality {resistance['quality']:.2f}.",
                    "Short bounce: latest candles show rejection near resistance.",
                    _setup_score_evidence(Setup.BOUNCE, resistance["quality"], relative_volume, compression),
                    _trend_evidence(trend_1h, trend_4h),
                    f"15m RSI is {tf_15m.rsi:.2f}.",
                ],
            )

        if (
            pack.market_regime.longs_allowed
            and long_continuation_ok
            and not long_overextended
            and compression < 0.7
            and prison in {SignalState.WATCH, SignalState.ENTER}
        ):
            evidence = [
                f"15m range compression ratio is {compression:.2f}.",
                f"15m prison-break state is {prison.value}.",
                _setup_score_evidence(Setup.APEX_SQUEEZE, 1.0 - compression, relative_volume, compression),
                _trend_evidence(trend_1h, trend_4h),
            ]
            if breakout_volume_confirmed:
                evidence.append("Relative volume confirms breakout.")
            else:
                evidence.append("Volume confirmation is not strong enough for ENTER.")
            return _long_thesis(
                pack,
                Setup.APEX_SQUEEZE,
                prison if breakout_volume_confirmed else SignalState.WATCH,
                confidence=_setup_confidence(
                    Setup.APEX_SQUEEZE,
                    prison,
                    breakout_volume_confirmed,
                    compression,
                    macd_bullish,
                    long_continuation_ok,
                    1.0 - compression,
                ),
                evidence=evidence,
            )

        if (
            pack.market_regime.shorts_allowed
            and short_continuation_ok
            and not short_overextended
            and compression < 0.7
            and short_prison in {SignalState.WATCH, SignalState.ENTER}
        ):
            evidence = [
                f"15m range compression ratio is {compression:.2f}.",
                f"15m short prison-break state is {short_prison.value}.",
                "Short apex squeeze: price is threatening a downside breakdown.",
                _setup_score_evidence(Setup.APEX_SQUEEZE, 1.0 - compression, relative_volume, compression),
                _trend_evidence(trend_1h, trend_4h),
            ]
            if breakout_volume_confirmed:
                evidence.append("Relative volume confirms bearish breakdown.")
            else:
                evidence.append("Volume confirmation is not strong enough for ENTER.")
            return _short_thesis(
                pack,
                Setup.APEX_SQUEEZE,
                short_prison if breakout_volume_confirmed else SignalState.WATCH,
                confidence=_setup_confidence(
                    Setup.APEX_SQUEEZE,
                    short_prison,
                    breakout_volume_confirmed,
                    compression,
                    macd_bearish,
                    short_continuation_ok,
                    1.0 - compression,
                ),
                evidence=evidence,
            )

        if (
            pack.market_regime.longs_allowed
            and long_continuation_ok
            and not long_overextended
            and rsi_ok
            and macd_bullish
            and (tf_4h.rsi is None or tf_4h.rsi < 72)
            and resistance is not None
        ):
            return _long_thesis(
                pack,
                Setup.TABO,
                prison if volume_confirmed else SignalState.WATCH,
                confidence=_setup_confidence(
                    Setup.TABO,
                    prison,
                    volume_confirmed,
                    compression,
                    macd_bullish,
                    long_continuation_ok,
                    resistance["quality"],
                ),
                evidence=[
                    "1h MACD is above signal.",
                    "15m RSI is in a tradable continuation range.",
                    _setup_score_evidence(Setup.TABO, resistance["quality"], relative_volume, compression),
                    _trend_evidence(trend_1h, trend_4h),
                    f"Nearby resistance zone has {resistance['touches']} wick touches and quality {resistance['quality']:.2f}.",
                    f"15m prison-break state is {prison.value}.",
                ],
            )

        if (
            pack.market_regime.shorts_allowed
            and short_continuation_ok
            and not short_overextended
            and short_rsi_ok
            and macd_bearish
            and (tf_4h.rsi is None or tf_4h.rsi > 28)
            and support is not None
        ):
            return _short_thesis(
                pack,
                Setup.TABO,
                short_prison if volume_confirmed else SignalState.WATCH,
                confidence=_setup_confidence(
                    Setup.TABO,
                    short_prison,
                    volume_confirmed,
                    compression,
                    macd_bearish,
                    short_continuation_ok,
                    support["quality"],
                ),
                evidence=[
                    "Short TABO: 1h MACD is below signal.",
                    "15m RSI is in a tradable bearish continuation range.",
                    _setup_score_evidence(Setup.TABO, support["quality"], relative_volume, compression),
                    _trend_evidence(trend_1h, trend_4h),
                    f"Nearby support zone has {support['touches']} wick touches and quality {support['quality']:.2f}.",
                    f"15m short prison-break state is {short_prison.value}.",
                ],
            )

        invalidations = _invalidation_reasons(
            long_trend_ok=long_trend_ok,
            short_trend_ok=short_trend_ok,
            volume_confirmed=volume_confirmed,
            support=support,
            resistance=resistance,
            long_overextended=long_overextended,
            short_overextended=short_overextended,
            rsi=tf_15m.rsi,
        )
        return TradeThesis(
            symbol=pack.candidate.route_symbol,
            setup=Setup.NONE,
            signal=SignalState.WAIT,
            direction="none",
            confidence=0.35,
            invalidation_reason="; ".join(invalidations) or "No deterministic setup passed the current filters.",
            evidence=[
                "Momentum, trend, volume, and entry timing are not aligned.",
                *invalidations,
                _trend_evidence(trend_1h, trend_4h),
            ],
        )


class OpenAIVisionAnalyzer(Analyzer):
    def __init__(self, model: str) -> None:
        from openai import OpenAI

        self.client = OpenAI()
        self.model = model

    def analyze(self, pack: IntelligencePack) -> TradeThesis:
        response = self.client.responses.create(
            model=self.model,
            instructions=MIRANDA_SYSTEM_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": self._content(pack),
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "trade_thesis",
                    "schema": _strict_schema(),
                    "strict": True,
                }
            },
        )
        return TradeThesis.model_validate_json(response.output_text)

    def _content(self, pack: IntelligencePack) -> list[dict]:
        content: list[dict] = [
            {
                "type": "input_text",
                "text": json.dumps(
                    {
                        "candidate": pack.candidate.model_dump(),
                        "market_regime": pack.market_regime.model_dump(),
                        "indicators": [item.model_dump() for item in pack.indicators],
                        "news_summary": pack.news_summary,
                    },
                    default=str,
                ),
            }
        ]
        for chart_path in pack.chart_paths:
            content.append(
                {
                    "type": "input_image",
                    "image_url": _image_data_url(chart_path),
                }
            )
        return content


def _image_data_url(path: str) -> str:
    raw = Path(path).read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _strict_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "symbol",
            "setup",
            "signal",
            "direction",
            "confidence",
            "entry",
            "stop_loss",
            "targets",
            "risk_reward",
            "invalidation_reason",
            "evidence",
            "news_veto",
        ],
        "properties": {
            "symbol": {"type": "string"},
            "setup": {
                "type": "string",
                "enum": ["bounce", "apex_squeeze", "transition_play", "tabo", "none"],
            },
            "signal": {
                "type": "string",
                "enum": ["wait", "watch", "enter", "reject"],
            },
            "direction": {"type": "string", "enum": ["long", "short", "none"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "entry": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "stop_loss": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "targets": {"type": "array", "items": {"type": "number"}},
            "risk_reward": {"anyOf": [{"type": "number"}, {"type": "null"}]},
            "invalidation_reason": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
            },
            "evidence": {"type": "array", "items": {"type": "string"}},
            "news_veto": {"type": "boolean"},
        },
    }


def _long_thesis(
    pack: IntelligencePack,
    setup: Setup,
    signal: SignalState,
    confidence: float,
    evidence: list[str],
) -> TradeThesis:
    tf_15m = {item.timeframe: item for item in pack.indicators}.get("15m") or pack.indicators[-1]
    entry = tf_15m.close
    stop_distance = tf_15m.atr or entry * 0.015
    stop = entry - stop_distance
    targets = [entry + (stop_distance * 1.5), entry + (stop_distance * 2.5)]
    risk_reward = (targets[-1] - entry) / stop_distance if stop_distance > 0 else None
    if signal == SignalState.WAIT:
        evidence.append("Price remains inside consolidation; waiting avoids fakeouts.")
    if signal == SignalState.WATCH:
        evidence.append("Breakout needs follow-through or retest confirmation before entry.")
    if signal == SignalState.ENTER:
        evidence.append("15m confirmation candle closed outside the prison range.")
    evidence.append(f"ATR stop distance is {stop_distance:.6g}.")
    return TradeThesis(
        symbol=pack.candidate.route_symbol,
        setup=setup,
        signal=signal,
        direction="long",
        confidence=confidence,
        entry=entry,
        stop_loss=stop,
        targets=targets,
        risk_reward=risk_reward,
        evidence=evidence,
    )


def _short_thesis(
    pack: IntelligencePack,
    setup: Setup,
    signal: SignalState,
    confidence: float,
    evidence: list[str],
) -> TradeThesis:
    tf_15m = {item.timeframe: item for item in pack.indicators}.get("15m") or pack.indicators[-1]
    entry = tf_15m.close
    stop_distance = tf_15m.atr or entry * 0.015
    stop = entry + stop_distance
    targets = [entry - (stop_distance * 1.5), entry - (stop_distance * 2.5)]
    risk_reward = (entry - targets[-1]) / stop_distance if stop_distance > 0 else None
    if signal == SignalState.WAIT:
        evidence.append("Price remains inside consolidation; waiting avoids fake breakdowns.")
    if signal == SignalState.WATCH:
        evidence.append("Bearish break needs follow-through or retest confirmation before entry.")
    if signal == SignalState.ENTER:
        evidence.append("15m confirmation candle closed below the prison range.")
    evidence.append(f"ATR stop distance is {stop_distance:.6g}.")
    return TradeThesis(
        symbol=pack.candidate.route_symbol,
        setup=setup,
        signal=signal,
        direction="short",
        confidence=confidence,
        entry=entry,
        stop_loss=stop,
        targets=[target for target in targets if target > 0],
        risk_reward=risk_reward,
        evidence=evidence,
    )


def _prison_break_state(candles: list[CandleSnapshot]) -> SignalState:
    if len(candles) < 24:
        return SignalState.WAIT
    prison = candles[-23:-3]
    last_three = candles[-3:]
    high = max(candle.high for candle in prison)
    low = min(candle.low for candle in prison)
    prev_close = last_three[-2].close
    last_close = last_three[-1].close

    if low <= last_close <= high:
        if prev_close > high or prev_close < low:
            return SignalState.REJECT
        return SignalState.WAIT
    if last_close > high:
        return SignalState.ENTER if prev_close > high else SignalState.WATCH
    if last_close < low:
        return SignalState.REJECT
    return SignalState.WAIT


def _short_prison_break_state(candles: list[CandleSnapshot]) -> SignalState:
    if len(candles) < 24:
        return SignalState.WAIT
    prison = candles[-23:-3]
    last_three = candles[-3:]
    high = max(candle.high for candle in prison)
    low = min(candle.low for candle in prison)
    prev_close = last_three[-2].close
    last_close = last_three[-1].close

    if low <= last_close <= high:
        if prev_close > high or prev_close < low:
            return SignalState.REJECT
        return SignalState.WAIT
    if last_close < low:
        return SignalState.ENTER if prev_close < low else SignalState.WATCH
    if last_close > high:
        return SignalState.REJECT
    return SignalState.WAIT


def _is_long_false_breakout(candles: list[CandleSnapshot]) -> bool:
    if len(candles) < 24:
        return False
    prison = candles[-23:-3]
    last_three = candles[-3:]
    high = max(candle.high for candle in prison)
    low = min(candle.low for candle in prison)
    prev_close = last_three[-2].close
    last_close = last_three[-1].close
    return prev_close > high and low <= last_close <= high


def _is_short_false_breakout(candles: list[CandleSnapshot]) -> bool:
    if len(candles) < 24:
        return False
    prison = candles[-23:-3]
    last_three = candles[-3:]
    high = max(candle.high for candle in prison)
    low = min(candle.low for candle in prison)
    prev_close = last_three[-2].close
    last_close = last_three[-1].close
    return prev_close < low and low <= last_close <= high


def _enter_signal(signal: SignalState, volume_confirmed: bool) -> SignalState:
    if signal == SignalState.ENTER and not volume_confirmed:
        return SignalState.WATCH
    return signal


def _compression_ratio(candles: list[CandleSnapshot]) -> float:
    if len(candles) < 40:
        return 1.0
    prior = candles[-40:-20]
    recent = candles[-20:]
    prior_range = max(item.high for item in prior) - min(item.low for item in prior)
    recent_range = max(item.high for item in recent) - min(item.low for item in recent)
    if prior_range <= 0:
        return 1.0
    return recent_range / prior_range


def _support_zone(candles: list[CandleSnapshot]) -> dict | None:
    if len(candles) < 20:
        return None
    lows = [candle.low for candle in candles[-50:]]
    support = min(lows)
    tolerance = support * 0.006
    touches = sum(1 for low in lows if abs(low - support) <= tolerance)
    if touches < 3:
        return None
    recent_touch_index = max(
        (index for index, candle in enumerate(candles[-50:]) if abs(candle.low - support) <= tolerance),
        default=0,
    )
    recency = (recent_touch_index + 1) / min(len(candles), 50)
    tightness = max(0.0, 1.0 - (tolerance / support if support else 1.0) * 20)
    quality = _zone_quality(touches, recency, tightness)
    if quality < 0.45:
        return None
    return {"price": support, "touches": touches, "quality": quality, "recency": recency, "tightness": tightness}


def _resistance_zone(candles: list[CandleSnapshot]) -> dict | None:
    if len(candles) < 20:
        return None
    highs = [candle.high for candle in candles[-50:]]
    resistance = max(highs)
    tolerance = resistance * 0.006
    touches = sum(1 for high in highs if abs(high - resistance) <= tolerance)
    if touches < 3:
        return None
    recent_touch_index = max(
        (index for index, candle in enumerate(candles[-50:]) if abs(candle.high - resistance) <= tolerance),
        default=0,
    )
    recency = (recent_touch_index + 1) / min(len(candles), 50)
    tightness = max(0.0, 1.0 - (tolerance / resistance if resistance else 1.0) * 20)
    quality = _zone_quality(touches, recency, tightness)
    if quality < 0.45:
        return None
    return {"price": resistance, "touches": touches, "quality": quality, "recency": recency, "tightness": tightness}


def _zone_quality(touches: int, recency: float, tightness: float) -> float:
    touch_score = min(touches / 6, 1.0)
    score = (touch_score * 0.5) + (recency * 0.3) + (tightness * 0.2)
    return round(max(0.0, min(score, 1.0)), 2)


def _is_bounce(candles: list[CandleSnapshot], support: dict) -> bool:
    if len(candles) < 3:
        return False
    latest = candles[-1]
    prior = candles[-2]
    support_price = support["price"]
    near_support = min(latest.low, prior.low) <= support_price * 1.012
    bullish_rejection = latest.close > latest.open and latest.close > prior.close
    lower_wick = min(latest.open, latest.close) - latest.low
    body = abs(latest.close - latest.open) or latest.close * 0.0001
    return near_support and bullish_rejection and lower_wick >= body * 0.5


def _is_resistance_rejection(candles: list[CandleSnapshot], resistance: dict) -> bool:
    if len(candles) < 3:
        return False
    latest = candles[-1]
    prior = candles[-2]
    resistance_price = resistance["price"]
    near_resistance = max(latest.high, prior.high) >= resistance_price * 0.988
    bearish_rejection = latest.close < latest.open and latest.close < prior.close
    upper_wick = latest.high - max(latest.open, latest.close)
    body = abs(latest.close - latest.open) or latest.close * 0.0001
    return near_resistance and bearish_rejection and upper_wick >= body * 0.5


def _transition_play(tf_15m, tf_1h) -> bool:
    if tf_15m.rsi is None or tf_1h.macd is None or tf_1h.macd_signal is None:
        return False
    return 35 <= tf_15m.rsi <= 48 and tf_1h.macd > tf_1h.macd_signal


def _short_transition_play(tf_15m, tf_1h) -> bool:
    if tf_15m.rsi is None or tf_1h.macd is None or tf_1h.macd_signal is None:
        return False
    return 55 <= tf_15m.rsi <= 70 and tf_1h.macd < tf_1h.macd_signal


def _trend_bias(candles: list[CandleSnapshot]) -> str:
    if len(candles) < 55:
        return "neutral"
    closes = [item.close for item in candles]
    ma_20 = sum(closes[-20:]) / 20
    ma_50 = sum(closes[-50:]) / 50
    last = closes[-1]
    slope_20 = ma_20 - (sum(closes[-25:-5]) / 20)
    if last > ma_20 > ma_50 and slope_20 > 0:
        return "up"
    if last < ma_20 < ma_50 and slope_20 < 0:
        return "down"
    return "neutral"


def _trend_evidence(trend_1h: str, trend_4h: str) -> str:
    return f"Trend filter: 1h is {trend_1h}, 4h is {trend_4h}."


def _setup_confidence(
    setup: Setup,
    prison: SignalState,
    volume_confirmed: bool,
    compression: float,
    momentum_aligned: bool,
    trend_aligned: bool,
    structure_quality: float,
) -> float:
    score = {
        Setup.TABO: 0.56,
        Setup.APEX_SQUEEZE: 0.60,
        Setup.BOUNCE: 0.57,
        Setup.TRANSITION_PLAY: 0.56,
    }.get(setup, 0.45)
    if prison == SignalState.WATCH:
        score += 0.04
    if prison == SignalState.ENTER:
        score += 0.12
    if volume_confirmed:
        score += 0.08
    if setup == Setup.APEX_SQUEEZE and compression < 0.7:
        score += 0.07
    elif compression < 0.85:
        score += 0.03
    if momentum_aligned:
        score += 0.04
    if trend_aligned:
        score += 0.05
    else:
        score -= 0.08
    score += max(0.0, min(structure_quality, 1.0)) * 0.08
    if prison == SignalState.REJECT:
        score -= 0.18
    return max(0.0, min(score, 0.92))


def _setup_score_evidence(
    setup: Setup,
    structure_quality: float,
    relative_volume: float,
    compression: float,
) -> str:
    return (
        f"Setup score components for {setup.value}: structure {structure_quality:.2f}, "
        f"relative volume {relative_volume:.2f}x, compression {compression:.2f}."
    )


def _invalidation_reasons(
    *,
    long_trend_ok: bool,
    short_trend_ok: bool,
    volume_confirmed: bool,
    support: dict | None,
    resistance: dict | None,
    long_overextended: bool,
    short_overextended: bool,
    rsi: float | None,
) -> list[str]:
    reasons: list[str] = []
    if not long_trend_ok and not short_trend_ok:
        reasons.append("bad trend: 1h/4h structure is conflicted.")
    if not volume_confirmed:
        reasons.append("low volume: relative volume is below confirmation threshold.")
    if support is None and resistance is None:
        reasons.append("weak zone: no high-quality support/resistance zone.")
    if long_overextended and rsi is not None:
        reasons.append(f"overextended RSI: bullish chase risk at {rsi:.2f}.")
    if short_overextended and rsi is not None:
        reasons.append(f"overextended RSI: bearish chase risk at {rsi:.2f}.")
    return reasons


def _rejected(pack: IntelligencePack, reason: str, detail: str) -> TradeThesis:
    return TradeThesis(
        symbol=pack.candidate.route_symbol,
        setup=Setup.NONE,
        signal=SignalState.REJECT,
        direction="none",
        confidence=0.2,
        invalidation_reason=f"{reason}: {detail}",
        evidence=[detail],
    )
