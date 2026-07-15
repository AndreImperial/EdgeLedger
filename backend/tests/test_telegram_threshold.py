from __future__ import annotations

from types import SimpleNamespace
import unittest

from coach_miranda_miner.coach import CoachMirandaMiner
from coach_miranda_miner.models import Asset, Candidate, Setup, SignalState, TradeThesis, ValidationResult


class TelegramThresholdTests(unittest.TestCase):
    def test_watch_threshold_sends_watch_and_enter_only(self) -> None:
        coach = CoachMirandaMiner.__new__(CoachMirandaMiner)
        coach.settings = SimpleNamespace(
            telegram_min_signal="watch",
            alert_cooldown_minutes=60,
            max_alerts_per_scan=5,
            max_scalp_alerts_per_scan=5,
        )
        coach.telegram = FakeTelegram()
        coach.journal = FakeJournal()
        coach._reset_alert_budget()

        candidate = Candidate(
            asset=Asset(symbol="BTC/USD", base="BTC", quote="USD"),
            exchange_id="coinbase",
            route_symbol="BTC/USD",
            reason="test",
        )

        self.assertTrue(
            coach.maybe_send_telegram_alert(
                candidate,
                _thesis(SignalState.WATCH),
                ValidationResult(approved=False, reasons=[]),
                "watch message",
            )
        )
        self.assertTrue(
            coach.maybe_send_telegram_alert(
                candidate,
                _thesis(SignalState.ENTER),
                ValidationResult(approved=True, reasons=[]),
                "enter message",
            )
        )
        self.assertFalse(
            coach.maybe_send_telegram_alert(
                candidate,
                _thesis(SignalState.WAIT),
                ValidationResult(approved=False, reasons=[]),
                "wait message",
            )
        )
        self.assertFalse(
            coach.maybe_send_telegram_alert(
                candidate,
                _thesis(SignalState.REJECT),
                ValidationResult(approved=False, reasons=[]),
                "reject message",
            )
        )
        self.assertEqual(len(coach.telegram.messages), 2)

    def test_alert_budget_caps_messages_per_scan(self) -> None:
        coach = CoachMirandaMiner.__new__(CoachMirandaMiner)
        coach.settings = SimpleNamespace(
            telegram_min_signal="watch",
            alert_cooldown_minutes=60,
            max_alerts_per_scan=1,
            max_scalp_alerts_per_scan=5,
        )
        coach.telegram = FakeTelegram()
        coach.journal = FakeJournal()
        coach._reset_alert_budget()
        candidate = Candidate(
            asset=Asset(symbol="BTC/USD", base="BTC", quote="USD"),
            exchange_id="coinbase",
            route_symbol="BTC/USD",
            reason="test",
        )

        self.assertTrue(
            coach.maybe_send_telegram_alert(
                candidate,
                _thesis(SignalState.WATCH),
                ValidationResult(approved=False, reasons=[]),
                "watch message",
            )
        )
        self.assertFalse(
            coach.maybe_send_telegram_alert(
                candidate,
                _thesis(SignalState.ENTER),
                ValidationResult(approved=True, reasons=[]),
                "enter message",
            )
        )
        self.assertEqual(len(coach.telegram.messages), 1)


def _thesis(signal: SignalState) -> TradeThesis:
    return TradeThesis(
        symbol="BTC/USD",
        setup=Setup.TABO,
        signal=signal,
        direction="long",
        confidence=0.75,
        entry=100.0,
        stop_loss=98.0,
        targets=[104.0],
        risk_reward=2.0,
    )


class FakeTelegram:
    configured = True

    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, message: str) -> bool:
        self.messages.append(message)
        return True


class FakeJournal:
    def alert_sent_recently(self, *args) -> bool:
        return False

    def record_alert(self, *args) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
