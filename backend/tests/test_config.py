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
            "BACKTEST_CANDLE_LIMIT",
            "BACKTEST_MIN_RISK_REWARD",
            "BACKTEST_MIN_RELATIVE_VOLUME",
            "BACKTEST_MIN_BODY_ATR",
            "BACKTEST_MIN_EMA_GAP_ATR",
            "BACKTEST_MIN_MACD_HIST_ATR",
            "BACKTEST_MIN_RISK_PCT",
            "BACKTEST_SCALP_MIN_RISK_PCT",
            "BACKTEST_MIN_NET_TARGET_PCT",
            "BACKTEST_MA_SIDE",
            "BACKTEST_MA_STOP_ATR_MULTIPLE",
            "BACKTEST_MA_TARGET_R_MULTIPLE",
            "BACKTEST_MA_RSI_BUY_MAX",
            "BACKTEST_MA_MIN_BODY_ATR",
            "BACKTEST_MA_MIN_GAP_ATR",
            "BACKTEST_MA_MIN_RISK_PCT",
            "BACKTEST_MA_PREFERRED_BASES",
            "BACKTEST_MA_EXCLUDED_BASES",
            "BACKTEST_MA_MIN_BATCH_WIN_RATE",
            "BACKTEST_MA_VALIDATION_CANDLE_LIMIT",
            "BACKTEST_MA_MIN_VALIDATION_WIN_RATE",
            "BACKTEST_MA_SYMBOL_OVERRIDES",
            "BACKTEST_MIN_CONFLUENCE_SCORE",
            "BACKTEST_ALLOWED_SETUPS",
            "BACKTEST_BREAKEVEN_TRIGGER_R",
            "BACKTEST_PARTIAL_TARGET_R",
            "BACKTEST_PARTIAL_EXIT_FRACTION",
            "DASHBOARD_URL",
            "REQUIRE_WATCH_BEFORE_ENTER",
            "ACTIVE_SETUP_TTL_MINUTES",
            "MAX_ATR_PCT",
            "MAX_ALERTS_PER_SCAN",
            "MAX_SCALP_ALERTS_PER_SCAN",
            "SCALP_SCAN_LIMIT",
            "SCALP_UNIVERSE_LIMIT",
            "SCALP_CANDLE_LIMIT",
            "BACKTEST_SCALP_CANDLE_LIMIT",
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
            "BACKTEST_CANDLE_LIMIT",
            "BACKTEST_MIN_RISK_REWARD",
            "BACKTEST_MIN_RELATIVE_VOLUME",
            "BACKTEST_MIN_BODY_ATR",
            "BACKTEST_MIN_EMA_GAP_ATR",
            "BACKTEST_MIN_MACD_HIST_ATR",
            "BACKTEST_MIN_RISK_PCT",
            "BACKTEST_SCALP_MIN_RISK_PCT",
            "BACKTEST_MIN_NET_TARGET_PCT",
            "BACKTEST_MA_SIDE",
            "BACKTEST_MA_STOP_ATR_MULTIPLE",
            "BACKTEST_MA_TARGET_R_MULTIPLE",
            "BACKTEST_MA_RSI_BUY_MAX",
            "BACKTEST_MA_MIN_BODY_ATR",
            "BACKTEST_MA_MIN_GAP_ATR",
            "BACKTEST_MA_MIN_RISK_PCT",
            "BACKTEST_MA_PREFERRED_BASES",
            "BACKTEST_MA_EXCLUDED_BASES",
            "BACKTEST_MA_MIN_BATCH_WIN_RATE",
            "BACKTEST_MA_VALIDATION_CANDLE_LIMIT",
            "BACKTEST_MA_MIN_VALIDATION_WIN_RATE",
            "BACKTEST_MA_SYMBOL_OVERRIDES",
            "BACKTEST_MIN_CONFLUENCE_SCORE",
            "BACKTEST_ALLOWED_SETUPS",
            "BACKTEST_BREAKEVEN_TRIGGER_R",
            "BACKTEST_PARTIAL_TARGET_R",
            "BACKTEST_PARTIAL_EXIT_FRACTION",
            "DASHBOARD_URL",
            "REQUIRE_WATCH_BEFORE_ENTER",
            "ACTIVE_SETUP_TTL_MINUTES",
            "MAX_ATR_PCT",
            "MAX_ALERTS_PER_SCAN",
            "MAX_SCALP_ALERTS_PER_SCAN",
            "SCALP_SCAN_LIMIT",
            "SCALP_UNIVERSE_LIMIT",
            "SCALP_CANDLE_LIMIT",
            "BACKTEST_SCALP_CANDLE_LIMIT",
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
        self.assertEqual(settings.rsi_buy_max, 55)
        self.assertEqual(settings.backtest_limit, 25)
        self.assertEqual(settings.backtest_candle_limit, 60000)
        self.assertEqual(settings.backtest_target_r_multiple, 1)
        self.assertEqual(settings.backtest_min_risk_reward, 1)
        self.assertEqual(settings.backtest_min_relative_volume, 1.2)
        self.assertEqual(settings.backtest_min_body_atr, 0.15)
        self.assertEqual(settings.backtest_min_ema_gap_atr, 0.1)
        self.assertEqual(settings.backtest_min_macd_hist_atr, 0.02)
        self.assertEqual(settings.backtest_min_risk_pct, 0.25)
        self.assertEqual(settings.backtest_scalp_min_risk_pct, 0.2)
        self.assertEqual(settings.backtest_min_net_target_pct, 0)
        self.assertEqual(settings.backtest_ma_side, "short")
        self.assertEqual(settings.backtest_ma_stop_atr_multiple, 1.5)
        self.assertEqual(settings.backtest_ma_target_r_multiple, 0.75)
        self.assertEqual(settings.backtest_ma_rsi_buy_max, 60)
        self.assertEqual(settings.backtest_ma_min_body_atr, 0.1)
        self.assertEqual(settings.backtest_ma_min_gap_atr, 0.3)
        self.assertEqual(settings.backtest_ma_min_risk_pct, 0.35)
        self.assertEqual(settings.backtest_ma_preferred_bases, ["BTC", "ETH", "XRP", "DOT"])
        self.assertEqual(settings.backtest_ma_excluded_bases, ["DOGE", "AVAX"])
        self.assertEqual(settings.backtest_ma_min_batch_win_rate, 1.0)
        self.assertEqual(settings.backtest_ma_validation_candle_limit, 100000)
        self.assertEqual(settings.backtest_ma_min_validation_win_rate, 1.0)
        self.assertEqual(
            settings.backtest_ma_symbol_overrides,
            {
                "ETH": {
                    "rsi_buy_max": 50,
                    "target_r": 0.18,
                    "min_body_atr": 0.3,
                    "min_gap_atr": 0.75,
                    "min_risk_pct": 0.35,
                    "short_rsi_max": 75,
                    "max_short_close_position": 0.35,
                    "min_short_bearish_sequence": 2,
                },
                "XRP": {
                    "rsi_buy_max": 50,
                    "target_r": 0.3,
                    "min_body_atr": 0.2,
                    "min_gap_atr": 0.6,
                    "min_risk_pct": 0.35,
                    "short_rsi_max": 75,
                    "max_short_close_position": 0.5,
                },
            },
        )
        self.assertEqual(settings.backtest_min_confluence_score, 3)
        self.assertEqual(
            settings.backtest_allowed_setups,
            ["apex_squeeze", "bounce", "alma_cci_scalp"],
        )
        self.assertEqual(settings.backtest_breakeven_trigger_r, 99)
        self.assertEqual(settings.backtest_partial_target_r, 1)
        self.assertEqual(settings.backtest_partial_exit_fraction, 0)
        self.assertFalse(settings.require_watch_before_enter)
        self.assertEqual(settings.active_setup_ttl_minutes, 240)
        self.assertEqual(settings.max_atr_pct, 8)
        self.assertEqual(settings.max_alerts_per_scan, 5)
        self.assertEqual(settings.max_scalp_alerts_per_scan, 5)
        self.assertEqual(settings.scalp_scan_limit, 100)
        self.assertEqual(settings.scalp_universe_limit, 250)
        self.assertEqual(settings.scalp_candle_limit, 240)
        self.assertEqual(settings.backtest_scalp_candle_limit, 3000)
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
