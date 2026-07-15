from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

import pandas as pd

from coach_miranda_miner.coach import CoachMirandaMiner, _scalp_universe_score, _setup_score
from coach_miranda_miner.exchanges import TickerSnapshot
from coach_miranda_miner.models import (
    Asset,
    Candidate,
    CandleSnapshot,
    IndicatorSnapshot,
    IntelligencePack,
    MarketRegime,
    Setup,
    SignalState,
    TradeThesis,
    ValidationResult,
)


def _candidate(base: str) -> Candidate:
    return Candidate(
        asset=Asset(symbol=f"{base}/USD", base=base, quote="USD"),
        exchange_id="coinbase",
        route_symbol=f"{base}/USD",
        reason="test",
        trading_link=f"https://example.test/{base}",
    )


class TwoStageScanTests(unittest.TestCase):
    def test_prefilter_score_rewards_volume_oi_and_relative_volume(self) -> None:
        strong = _candidate("AAA").model_copy(
            update={"volume_24h_usd": 2_000_000_000, "open_interest_change_24h_pct": 35.0}
        )
        weak = _candidate("BBB").model_copy(
            update={"volume_24h_usd": 60_000_000, "open_interest_change_24h_pct": 1.0}
        )

        strong_score = _setup_score(strong, 8.0, 2.4, True)
        weak_score = _setup_score(weak, 0.5, 1.0, True)

        self.assertGreater(strong_score.score, weak_score.score)
        self.assertIn("Coinalyze 24h OI change", " ".join(strong_score.prefilter_reasons))

    def test_scalp_universe_score_prioritizes_oi_movement_with_volume(self) -> None:
        high_oi = _candidate("HOT").model_copy(
            update={"volume_24h_usd": 250_000_000, "open_interest_change_24h_pct": 35.0}
        )
        sleepy_large_cap = _candidate("SLEEP").model_copy(
            update={"volume_24h_usd": 1_000_000_000, "open_interest_change_24h_pct": 1.0}
        )

        self.assertGreater(_scalp_universe_score(high_oi), _scalp_universe_score(sleepy_large_cap))

    def test_scan_setups_respects_deep_scan_limit_and_skips_symbol_failures(self) -> None:
        coach = CoachMirandaMiner.__new__(CoachMirandaMiner)
        coach.settings = SimpleNamespace(
            prefilter_limit=4,
            deep_scan_limit=2,
            scan_workers=2,
            fetch_timeout_seconds=20,
            prefilter_candle_limit=40,
            timeframes=["15m"],
            candle_limit=40,
            coinalyze_api_key=None,
            oi_limit=10,
            min_volume_24h_usd=50_000_000,
        )
        coach.gatekeeper = FakeGatekeeper()
        coach.discovery = FakeDiscovery()
        coach.router = FakeRouter()
        coach.oi_scanner = FakeOIScanner()
        coach.intelligence = FakeIntelligence()
        coach.analyzer = FakeAnalyzer()
        coach.validator = FakeValidator()
        coach.journal = FakeJournal()
        coach.alerts = FakeFormatter()
        coach.telegram = FakeTelegram()

        summary, scores, results = coach.scan_setups()

        self.assertEqual(summary.candidates_scanned, 3)
        self.assertEqual(summary.deep_analyzed, 2)
        self.assertEqual(len(results), 2)
        self.assertEqual([item.symbol for item in scores], ["AAA/USD", "CCC/USD", "BBB/USD"])
        self.assertTrue(any("BAD/USD prefilter skipped" in warning for warning in summary.warnings))
        self.assertEqual(summary.worker_count, 2)
        self.assertGreaterEqual(summary.failed_symbols, 1)

    def test_scan_caches_duplicate_prefilter_fetches(self) -> None:
        coach = CoachMirandaMiner.__new__(CoachMirandaMiner)
        coach.settings = SimpleNamespace(
            prefilter_limit=2,
            deep_scan_limit=0,
            scan_workers=1,
            fetch_timeout_seconds=20,
            prefilter_candle_limit=40,
            timeframes=["15m"],
            candle_limit=40,
            coinalyze_api_key=None,
            oi_limit=10,
            min_volume_24h_usd=50_000_000,
        )
        coach.gatekeeper = FakeGatekeeper()
        coach.discovery = DuplicateDiscovery()
        coach.router = FakeRouter()
        coach.oi_scanner = FakeOIScanner()
        coach.intelligence = FakeIntelligence()
        coach.analyzer = FakeAnalyzer()
        coach.validator = FakeValidator()
        coach.journal = FakeJournal()
        coach.alerts = FakeFormatter()
        coach.telegram = FakeTelegram()

        summary, scores, results = coach.scan_setups()

        self.assertEqual(summary.candidates_scanned, 2)
        self.assertEqual(len(scores), 2)
        self.assertEqual(results, [])
        self.assertEqual(coach.router.ticker_calls["AAA/USD"], 1)
        self.assertEqual(coach.router.candle_calls["AAA/USD"], 1)


class FakeGatekeeper:
    def market_regime(self) -> MarketRegime:
        return MarketRegime(btc_change_24h_pct=1.0, longs_allowed=True, reason="BTC ok")

    def filter_candidate(self, candidate: Candidate):
        return True, []


class FakeDiscovery:
    def discover(self, limit: int) -> list[Candidate]:
        return [_candidate("AAA"), _candidate("BBB"), _candidate("BAD"), _candidate("CCC")]


class DuplicateDiscovery:
    def discover(self, limit: int) -> list[Candidate]:
        return [_candidate("AAA"), _candidate("AAA")]


class FakeRouter:
    def __init__(self) -> None:
        self.ticker_calls: dict[str, int] = {}
        self.candle_calls: dict[str, int] = {}

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        self.ticker_calls[symbol] = self.ticker_calls.get(symbol, 0) + 1
        if symbol == "BAD/USD":
            raise ValueError("no ticker")
        values = {
            "AAA/USD": TickerSnapshot(symbol, 10.0, 8.0, 2_000_000_000),
            "BBB/USD": TickerSnapshot(symbol, 10.0, 1.0, 60_000_000),
            "CCC/USD": TickerSnapshot(symbol, 10.0, 5.0, 500_000_000),
        }
        return values[symbol]

    def fetch_candles(self, exchange_id: str, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        self.candle_calls[symbol] = self.candle_calls.get(symbol, 0) + 1
        volumes = [100.0] * 39 + ([300.0] if symbol == "AAA/USD" else [120.0])
        return pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01", periods=40, freq="15min", tz="UTC"),
                "open": [10.0] * 40,
                "high": [11.0] * 40,
                "low": [9.0] * 40,
                "close": [10.0] * 40,
                "volume": volumes,
            }
        )


class FakeOIScanner:
    def scan(self):
        return [], ["Coinalyze test warning"]


class TestOptionalCoinalyzeFallback(unittest.TestCase):
    def test_missing_key_does_not_warn_during_scan_prefilter(self) -> None:
        coach = object.__new__(CoachMirandaMiner)
        coach.settings = SimpleNamespace(coinalyze_api_key=None)
        warnings: list[str] = []

        rows = coach._coinalyze_rows_for_candidates([], warnings)

        self.assertEqual(rows, {})
        self.assertEqual(warnings, [])


class FakeIntelligence:
    chart_renderer = None
    news_provider = None

    def gather(self, candidate: Candidate, market_regime: MarketRegime) -> IntelligencePack:
        candle = CandleSnapshot(
            timestamp=datetime.now(timezone.utc),
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.0,
            volume=100.0,
        )
        return IntelligencePack(
            candidate=candidate,
            market_regime=market_regime,
            indicators=[
                IndicatorSnapshot(
                    timeframe="15m",
                    close=10.0,
                    volume=100.0,
                    rsi=55.0,
                    macd=1.0,
                    macd_signal=0.5,
                    atr=1.0,
                    relative_volume=1.2,
                )
            ],
            candles={"15m": [candle]},
            news_summary="",
        )


class FakeAnalyzer:
    def analyze(self, pack: IntelligencePack) -> TradeThesis:
        return TradeThesis(
            symbol=pack.candidate.route_symbol,
            setup=Setup.TABO,
            signal=SignalState.WATCH,
            direction="long",
            confidence=0.75,
            entry=10.0,
            stop_loss=9.0,
            targets=[12.0],
            risk_reward=2.0,
        )


class FakeValidator:
    def validate(self, thesis: TradeThesis, market_regime: MarketRegime, atr: float | None):
        return ValidationResult(approved=False, reasons=["Signal is watch; no execution approved."])


class FakeJournal:
    def record_thesis(self, **kwargs) -> None:
        return None

    def record_setup_score(self, **kwargs) -> None:
        return None

    def alert_sent_recently(self, *args) -> bool:
        return False

    def record_alert(self, *args) -> None:
        return None


class FakeFormatter:
    def format(self, candidate, thesis, validation, score=None) -> str:
        return f"{candidate.route_symbol} {thesis.signal.value}"


class FakeTelegram:
    configured = False


if __name__ == "__main__":
    unittest.main()
