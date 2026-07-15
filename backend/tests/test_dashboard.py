from __future__ import annotations

import unittest
from types import SimpleNamespace

from coach_miranda_miner.dashboard import (
    NAVIGATION_LABELS,
    TRADINGVIEW_HEIGHT,
    _command_grid,
    _mini_metric,
    _scan_cache_key,
    _status_label,
    _tradingview_widget,
)


class DashboardTests(unittest.TestCase):
    def test_tradingview_widget_uses_fixed_height(self) -> None:
        html = _tradingview_widget("BTC/USD", "1h")

        self.assertIn(f'"height": {TRADINGVIEW_HEIGHT}', html)
        self.assertIn('"width": "100%"', html)
        self.assertNotIn('"autosize": true', html)

    def test_tradingview_widget_supports_scalp_interval(self) -> None:
        html = _tradingview_widget("BTC/USD", "3m")

        self.assertIn('"interval": "3"', html)

    def test_scan_cache_key_changes_with_speed_settings(self) -> None:
        base = _settings(scan_workers=8, prefilter_candle_limit=40)
        changed_workers = _settings(scan_workers=4, prefilter_candle_limit=40)
        changed_candles = _settings(scan_workers=8, prefilter_candle_limit=60)

        self.assertNotEqual(_scan_cache_key(base), _scan_cache_key(changed_workers))
        self.assertNotEqual(_scan_cache_key(base), _scan_cache_key(changed_candles))

    def test_navigation_exposes_operations_console_views(self) -> None:
        self.assertEqual(NAVIGATION_LABELS[0], "Overview")
        self.assertIn("Market Scanner", NAVIGATION_LABELS)
        self.assertIn("System Health", NAVIGATION_LABELS)

    def test_status_label_is_stable(self) -> None:
        self.assertEqual(_status_label(True), "On")
        self.assertEqual(_status_label(False), "Off")

    def test_reskin_helpers_escape_values(self) -> None:
        metric = _mini_metric("Entry", "<script>")
        grid = _command_grid([("Mode", "paper", "<unsafe>")])

        self.assertIn("&lt;script&gt;", metric)
        self.assertIn("&lt;unsafe&gt;", grid)
        self.assertIn("cmm-command-grid", grid)


def _settings(scan_workers: int, prefilter_candle_limit: int):
    return SimpleNamespace(
        data_mode="coinbase",
        prefilter_limit=100,
        deep_scan_limit=20,
        candle_limit=200,
        timeframes=["1d", "4h", "1h", "15m"],
        min_confidence=0.72,
        min_risk_reward=2.0,
        min_volume_24h_usd=50_000_000,
        coinalyze_api_key=None,
        telegram_min_signal="watch",
        scan_workers=scan_workers,
        prefilter_candle_limit=prefilter_candle_limit,
        scalp_scan_limit=100,
        scalp_universe_limit=250,
        scalp_candle_limit=240,
        scalp_min_volume_24h_usd=5_000_000,
        scalp_alert_cooldown_minutes=45,
        scalp_min_atr_pct=0.12,
        scalp_max_atr_pct=2.8,
        scalp_cross_fresh_bars=3,
    )


if __name__ == "__main__":
    unittest.main()
