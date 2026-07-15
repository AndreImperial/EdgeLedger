from __future__ import annotations

import unittest

from coach_miranda_miner.exchanges import CoinbaseRouter


class FakeResponse:
    status_code = 200

    def __init__(self, payload) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.headers = {}

    def get(self, url: str, params=None, timeout=None) -> FakeResponse:
        return FakeResponse(
            [
                {
                    "base_currency": "AAA",
                    "quote_currency": "USD",
                    "id": "AAA-USD",
                    "status": "online",
                    "trading_disabled": False,
                },
                {
                    "base_currency": "BBB",
                    "quote_currency": "USDT",
                    "id": "BBB-USDT",
                    "status": "online",
                    "trading_disabled": False,
                },
                {
                    "base_currency": "CCC",
                    "quote_currency": "USD",
                    "id": "CCC-USD",
                    "status": "offline",
                    "trading_disabled": False,
                },
            ]
        )


class CoinbaseRouterTests(unittest.TestCase):
    def test_products_are_loaded_from_public_coinbase_endpoint(self) -> None:
        router = CoinbaseRouter(["coinbase"])
        router.session = FakeSession()

        self.assertEqual(router.first_available_route("AAA", "USD"), ("coinbase", "AAA/USD"))
        self.assertIsNone(router.first_available_route("BBB", "USD"))
        self.assertIsNone(router.first_available_route("CCC", "USD"))


if __name__ == "__main__":
    unittest.main()
