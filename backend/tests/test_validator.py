from __future__ import annotations

import unittest

from coach_miranda_miner.models import MarketRegime, Setup, SignalState, TradeThesis
from coach_miranda_miner.validator import ThesisValidator


class ThesisValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ThesisValidator(
            min_risk_reward=1.5,
            min_confidence=0.6,
            max_stop_atr_multiple=3,
        )
        self.regime = MarketRegime(
            btc_change_24h_pct=1.0,
            longs_allowed=True,
            reason="BTC regime acceptable.",
        )

    def test_watch_signal_is_not_approved(self) -> None:
        thesis = TradeThesis(
            symbol="BTC/USDT",
            setup=Setup.TABO,
            signal=SignalState.WATCH,
            direction="long",
            confidence=0.75,
            entry=100.0,
            stop_loss=98.0,
            targets=[104.0],
            risk_reward=2.0,
        )
        result = self.validator.validate(thesis, self.regime, atr=2.0)
        self.assertFalse(result.approved)
        self.assertIn("Signal is watch; no execution approved.", result.reasons)

    def test_enter_requires_valid_long_geometry(self) -> None:
        thesis = TradeThesis(
            symbol="BTC/USDT",
            setup=Setup.TABO,
            signal=SignalState.ENTER,
            direction="long",
            confidence=0.75,
            entry=100.0,
            stop_loss=101.0,
            targets=[99.0],
            risk_reward=2.0,
        )
        result = self.validator.validate(thesis, self.regime, atr=2.0)
        self.assertFalse(result.approved)
        self.assertIn("Long stop loss must be below entry.", result.reasons)
        self.assertIn("Long targets must be above entry.", result.reasons)

    def test_enter_can_be_approved(self) -> None:
        thesis = TradeThesis(
            symbol="BTC/USDT",
            setup=Setup.TABO,
            signal=SignalState.ENTER,
            direction="long",
            confidence=0.75,
            entry=100.0,
            stop_loss=98.5,
            targets=[103.0],
            risk_reward=2.0,
        )
        result = self.validator.validate(thesis, self.regime, atr=2.0)
        self.assertTrue(result.approved)

    def test_short_enter_requires_valid_short_geometry(self) -> None:
        thesis = TradeThesis(
            symbol="BTC/USDT",
            setup=Setup.TABO,
            signal=SignalState.ENTER,
            direction="short",
            confidence=0.75,
            entry=100.0,
            stop_loss=99.0,
            targets=[101.0],
            risk_reward=2.0,
        )
        result = self.validator.validate(thesis, self.regime, atr=2.0)
        self.assertFalse(result.approved)
        self.assertIn("Short stop loss must be above entry.", result.reasons)
        self.assertIn("Short targets must be below entry.", result.reasons)

    def test_short_enter_can_be_approved(self) -> None:
        thesis = TradeThesis(
            symbol="BTC/USDT",
            setup=Setup.TABO,
            signal=SignalState.ENTER,
            direction="short",
            confidence=0.75,
            entry=100.0,
            stop_loss=101.5,
            targets=[97.0],
            risk_reward=2.0,
        )
        result = self.validator.validate(thesis, self.regime, atr=2.0)
        self.assertTrue(result.approved)

    def test_enter_rejects_too_tight_atr_stop(self) -> None:
        thesis = TradeThesis(
            symbol="BTC/USDT",
            setup=Setup.TABO,
            signal=SignalState.ENTER,
            direction="long",
            confidence=0.75,
            entry=100.0,
            stop_loss=99.8,
            targets=[101.0],
            risk_reward=5.0,
        )

        result = self.validator.validate(thesis, self.regime, atr=2.0)

        self.assertFalse(result.approved)
        self.assertTrue(any("too tight versus ATR" in reason for reason in result.reasons))


if __name__ == "__main__":
    unittest.main()
