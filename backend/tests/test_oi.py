from __future__ import annotations

import requests
import unittest

from coach_miranda_miner.oi import OpenInterestScanner


class FakeTicker:
    def __init__(self, last: float, quote_volume: float) -> None:
        self.last = last
        self.quote_volume = quote_volume


class FakeRouter:
    def fetch_ticker(self, exchange_id: str, symbol: str) -> FakeTicker:
        values = {
            "BTC/USD": FakeTicker(100.0, 1_000_000),
            "ETH/USD": FakeTicker(10.0, 500_000),
        }
        return values[symbol]


class FakeResponse:
    def __init__(self, payload, status_code: int = 200, text: str = "") -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = text
        self.headers = {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.headers = {}
        self.last_params = None

    def get(self, url: str, params=None, timeout=None) -> FakeResponse:
        self.last_params = params
        return FakeResponse(self.payload)


class OIScannerTests(unittest.TestCase):
    def test_volume_only_fallback_is_sorted(self) -> None:
        scanner = OpenInterestScanner(FakeRouter(), ["ETH", "BTC"])
        rows = scanner._volume_only_fallback()
        self.assertEqual(rows[0].symbol, "BTC/USD")
        self.assertEqual(rows[0].status, "Volume only; OI unavailable")
        self.assertIsNone(rows[0].open_interest_usd)

    def test_fixture_mode_does_not_call_external_oi_endpoints(self) -> None:
        scanner = OpenInterestScanner(FakeRouter(), ["ETH", "BTC"], fixture_mode=True)

        def blocked_get(*args, **kwargs):
            raise AssertionError("fixture mode should not call external OI endpoints")

        scanner.session.get = blocked_get
        rows, warnings = scanner.scan()

        self.assertEqual(rows[0].source, "Fixture")
        self.assertEqual(rows[0].status, "Synthetic fixture OI")
        self.assertIn("synthetic", warnings[0].lower())

    def test_coinalyze_symbols_use_perpetual_flag(self) -> None:
        scanner = OpenInterestScanner(FakeRouter(), ["BTC"], "test-key")
        self.assertEqual(scanner.session.headers["api_key"], "test-key")
        scanner.session = FakeSession(
            [
                {
                    "base_asset": "BTC",
                    "quote_asset": "USDT",
                    "symbol": "BTCUSDT.6",
                    "is_perpetual": False,
                },
                {
                    "base_asset": "BTC",
                    "quote_asset": "USDT",
                    "symbol": "BTCUSDT_PERP.A",
                    "is_perpetual": True,
                },
            ]
        )

        self.assertEqual(scanner._coinalyze_symbols(), {"BTC": "BTCUSDT_PERP.A"})
        self.assertIsNone(scanner.session.last_params)

    def test_scan_coinalyze_only_skips_exchange_fallbacks(self) -> None:
        scanner = OpenInterestScanner(FakeRouter(), ["BTC"], None)

        warnings = []
        rows = scanner.scan_coinalyze_only(warnings)

        self.assertEqual(rows, [])
        self.assertIn("Coinalyze API key not configured", warnings[0])

    def test_coinalyze_http_errors_show_render_secret_hint(self) -> None:
        scanner = OpenInterestScanner(FakeRouter(), ["BTC"], "bad-key")
        scanner.session = FakeSession([])

        def get(url: str, params=None, timeout=None) -> FakeResponse:
            return FakeResponse({"error": "invalid"}, status_code=401, text="invalid api key")

        scanner.session.get = get
        warnings = []
        rows = scanner._scan_coinalyze(warnings)

        self.assertEqual(rows, [])
        self.assertIn("invalid or missing COINALYZE_API_KEY", warnings[0])


if __name__ == "__main__":
    unittest.main()
