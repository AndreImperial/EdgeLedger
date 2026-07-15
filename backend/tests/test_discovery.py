from __future__ import annotations

import unittest

from coach_miranda_miner.discovery import ExchangeMomentumDiscoveryEngine
from coach_miranda_miner.exchanges import TickerSnapshot


class FakeRouter:
    def __init__(self) -> None:
        self.exchange_ids = ["ignored-a", "ignored-b"]

    def first_available_route(self, base: str, quote_currency: str):
        if quote_currency != "USD":
            return None
        return "coinbase", f"{base}/USD"

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        return TickerSnapshot(symbol=symbol, last=1.0, percentage=0.0, quote_volume=100_000_000)

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        return [
            TickerSnapshot("AAA/USD", 1.0, 12.0, 200_000_000),
            TickerSnapshot("AAA/USD", 1.0, 12.0, 200_000_000),
            TickerSnapshot("BBB/USD", 1.0, -8.0, 150_000_000),
        ]


class DiscoveryTests(unittest.TestCase):
    def test_movers_are_deduped_and_use_routed_exchange(self) -> None:
        engine = ExchangeMomentumDiscoveryEngine(
            FakeRouter(),
            ["ignored-a", "ignored-b"],
            "USD",
            min_volume_24h_usd=50_000_000,
            majors=[],
        )

        candidates = engine.discover(10)

        self.assertEqual([item.route_symbol for item in candidates], ["AAA/USD", "BBB/USD"])
        self.assertEqual({item.exchange_id for item in candidates}, {"coinbase"})


if __name__ == "__main__":
    unittest.main()
