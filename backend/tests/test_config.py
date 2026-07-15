from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from coach_miranda_miner.config import ConfigurationError, Settings


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["COINALYZE_API_KEY"] = ""
        os.environ["COINALAYZE_API_KEY"] = ""
        for name in [
            "PREFILTER_LIMIT",
            "DISCOVERY_LIMIT",
            "DEEP_SCAN_LIMIT",
            "SCAN_WORKERS",
            "FETCH_TIMEOUT_SECONDS",
            "PREFILTER_CANDLE_LIMIT",
            "AUTO_SCAN_ENABLED",
            "AUTO_SCAN_INTERVAL_SECONDS",
            "SCAN_INTERVAL_SECONDS",
            "TELEGRAM_MIN_SIGNAL",
            "MIN_ALERT_GRADE",
            "BACKTEST_LIMIT",
            "DASHBOARD_URL",
            "REQUIRE_WATCH_BEFORE_ENTER",
            "ACTIVE_SETUP_TTL_MINUTES",
            "MAX_ATR_PCT",
            "MAX_ALERTS_PER_SCAN",
            "MAX_SCALP_ALERTS_PER_SCAN",
            "SCALP_SCAN_LIMIT",
            "SCALP_UNIVERSE_LIMIT",
            "SCALP_CANDLE_LIMIT",
            "SCALP_MIN_VOLUME_24H_USD",
            "SCALP_ALERT_COOLDOWN_MINUTES",
            "SCALP_MIN_ATR_PCT",
            "SCALP_MAX_ATR_PCT",
            "SCALP_CROSS_FRESH_BARS",
            "DATA_MODE",
            "TRADING_MODE",
            "MIN_CONFIDENCE",
            "RENDER_CHARTS",
            "TIMEFRAME",
        ]:
            os.environ.pop(name, None)
        os.environ["DISCOVERY_LIMIT"] = "100"

    def tearDown(self) -> None:
        for name in [
            "COINALYZE_API_KEY",
            "COINALAYZE_API_KEY",
            "PREFILTER_LIMIT",
            "DISCOVERY_LIMIT",
            "DEEP_SCAN_LIMIT",
            "SCAN_WORKERS",
            "FETCH_TIMEOUT_SECONDS",
            "PREFILTER_CANDLE_LIMIT",
            "AUTO_SCAN_ENABLED",
            "AUTO_SCAN_INTERVAL_SECONDS",
            "SCAN_INTERVAL_SECONDS",
            "TELEGRAM_MIN_SIGNAL",
            "MIN_ALERT_GRADE",
            "BACKTEST_LIMIT",
            "DASHBOARD_URL",
            "REQUIRE_WATCH_BEFORE_ENTER",
            "ACTIVE_SETUP_TTL_MINUTES",
            "MAX_ATR_PCT",
            "MAX_ALERTS_PER_SCAN",
            "MAX_SCALP_ALERTS_PER_SCAN",
            "SCALP_SCAN_LIMIT",
            "SCALP_UNIVERSE_LIMIT",
            "SCALP_CANDLE_LIMIT",
            "SCALP_MIN_VOLUME_24H_USD",
            "SCALP_ALERT_COOLDOWN_MINUTES",
            "SCALP_MIN_ATR_PCT",
            "SCALP_MAX_ATR_PCT",
            "SCALP_CROSS_FRESH_BARS",
            "DATA_MODE",
            "TRADING_MODE",
            "MIN_CONFIDENCE",
            "RENDER_CHARTS",
            "TIMEFRAME",
        ]:
            os.environ.pop(name, None)

    def test_coinalyze_key_uses_canonical_name(self) -> None:
        os.environ["COINALYZE_API_KEY"] = "canonical-key"

        self.assertEqual(Settings.from_env().coinalyze_api_key, "canonical-key")

    def test_coinalyze_key_accepts_common_misspelling(self) -> None:
        os.environ["COINALAYZE_API_KEY"] = "misspelled-key"

        self.assertEqual(Settings.from_env().coinalyze_api_key, "misspelled-key")

    def test_alert_upgrade_defaults(self) -> None:
        with patch("coach_miranda_miner.config.load_dotenv"):
            settings = Settings.from_env()

        self.assertEqual(settings.prefilter_limit, 100)
        self.assertEqual(settings.deep_scan_limit, 20)
        self.assertEqual(settings.scan_workers, 8)
        self.assertEqual(settings.fetch_timeout_seconds, 20)
        self.assertEqual(settings.prefilter_candle_limit, 40)
        self.assertTrue(settings.auto_scan_enabled)
        self.assertEqual(settings.auto_scan_interval_seconds, settings.scan_interval_seconds)
        self.assertEqual(settings.telegram_min_signal, "watch")
        self.assertEqual(settings.min_alert_grade, "B")
        self.assertEqual(settings.backtest_limit, 25)
        self.assertFalse(settings.require_watch_before_enter)
        self.assertEqual(settings.active_setup_ttl_minutes, 240)
        self.assertEqual(settings.max_atr_pct, 8)
        self.assertEqual(settings.max_alerts_per_scan, 5)
        self.assertEqual(settings.max_scalp_alerts_per_scan, 5)
        self.assertEqual(settings.scalp_scan_limit, 100)
        self.assertEqual(settings.scalp_universe_limit, 250)
        self.assertEqual(settings.scalp_candle_limit, 240)
        self.assertEqual(settings.scalp_min_volume_24h_usd, 5_000_000)
        self.assertEqual(settings.scalp_alert_cooldown_minutes, 45)
        self.assertEqual(settings.scalp_min_atr_pct, 0.12)
        self.assertEqual(settings.scalp_max_atr_pct, 2.8)
        self.assertEqual(settings.scalp_cross_fresh_bars, 3)

    def test_invalid_mode_raises_clear_error(self) -> None:
        os.environ["DATA_MODE"] = "mystery"

        with self.assertRaisesRegex(ConfigurationError, "DATA_MODE"):
            Settings.from_env()

    def test_invalid_numeric_value_raises_clear_error(self) -> None:
        os.environ["MIN_CONFIDENCE"] = "1.2"

        with self.assertRaisesRegex(ConfigurationError, "MIN_CONFIDENCE"):
            Settings.from_env()

    def test_invalid_boolean_raises_clear_error(self) -> None:
        os.environ["RENDER_CHARTS"] = "sometimes"

        with self.assertRaisesRegex(ConfigurationError, "RENDER_CHARTS"):
            Settings.from_env()

    def test_live_trading_mode_is_not_allowed(self) -> None:
        os.environ["TRADING_MODE"] = "live"

        with self.assertRaisesRegex(ConfigurationError, "TRADING_MODE"):
            Settings.from_env()


if __name__ == "__main__":
    unittest.main()
