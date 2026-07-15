from __future__ import annotations

from .models import MarketRegime, SignalState, TradeThesis, ValidationResult


class ThesisValidator:
    def __init__(
        self,
        min_risk_reward: float,
        min_confidence: float,
        max_stop_atr_multiple: float,
        max_atr_pct: float = 8.0,
    ) -> None:
        self.min_risk_reward = min_risk_reward
        self.min_confidence = min_confidence
        self.max_stop_atr_multiple = max_stop_atr_multiple
        self.max_atr_pct = max_atr_pct

    def validate(
        self,
        thesis: TradeThesis,
        market_regime: MarketRegime,
        atr: float | None = None,
    ) -> ValidationResult:
        reasons: list[str] = []

        if thesis.news_veto and thesis.direction == "long":
            reasons.append("News veto blocks bullish setup.")

        if thesis.direction == "long" and not market_regime.longs_allowed:
            reasons.append(market_regime.reason)

        if thesis.direction == "short" and not market_regime.shorts_allowed:
            reasons.append("Market regime blocks short setup.")

        if thesis.confidence < self.min_confidence and thesis.signal == SignalState.ENTER:
            reasons.append(f"Confidence below minimum {self.min_confidence:.2f}.")

        if thesis.entry is not None and atr is not None and atr > 0:
            atr_pct = (atr / thesis.entry) * 100
            if atr_pct > self.max_atr_pct:
                reasons.append(f"Volatility too high: ATR is {atr_pct:.2f}% of entry.")

        if thesis.direction == "long" and thesis.entry is not None and thesis.stop_loss is not None:
            if thesis.stop_loss >= thesis.entry:
                reasons.append("Long stop loss must be below entry.")
            for target in thesis.targets:
                if target <= thesis.entry:
                    reasons.append("Long targets must be above entry.")
                    break
            if atr is not None and atr > 0:
                stop_distance = thesis.entry - thesis.stop_loss
                if stop_distance < atr * 0.25:
                    reasons.append(
                        "Stop distance is too tight versus ATR "
                        f"({stop_distance / atr:.2f}x)."
                    )
                if stop_distance > atr * self.max_stop_atr_multiple:
                    reasons.append(
                        "Stop distance is too wide versus ATR "
                        f"({stop_distance / atr:.2f}x)."
                    )
        if thesis.direction == "short" and thesis.entry is not None and thesis.stop_loss is not None:
            if thesis.stop_loss <= thesis.entry:
                reasons.append("Short stop loss must be above entry.")
            for target in thesis.targets:
                if target >= thesis.entry:
                    reasons.append("Short targets must be below entry.")
                    break
            if atr is not None and atr > 0:
                stop_distance = thesis.stop_loss - thesis.entry
                if stop_distance < atr * 0.25:
                    reasons.append(
                        "Stop distance is too tight versus ATR "
                        f"({stop_distance / atr:.2f}x)."
                    )
                if stop_distance > atr * self.max_stop_atr_multiple:
                    reasons.append(
                        "Stop distance is too wide versus ATR "
                        f"({stop_distance / atr:.2f}x)."
                    )

        if thesis.signal == SignalState.ENTER:
            if thesis.entry is None or thesis.stop_loss is None or not thesis.targets:
                reasons.append("ENTER requires entry, stop_loss, and at least one target.")
            if thesis.risk_reward is None or thesis.risk_reward < self.min_risk_reward:
                reasons.append(f"Risk/reward below minimum {self.min_risk_reward:.2f}.")

        if thesis.signal in {SignalState.WAIT, SignalState.WATCH, SignalState.REJECT}:
            reasons.append(f"Signal is {thesis.signal.value}; no execution approved.")

        return ValidationResult(approved=len(reasons) == 0, reasons=reasons)
