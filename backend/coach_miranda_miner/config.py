from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when environment configuration is invalid."""


DATA_MODES = {"fixture", "live", "coinbase", "bitunix", "paprika", "yahoo", "coingecko"}
ANALYZER_MODES = {"rule", "openai"}
DISCOVERY_MODES = {"exchange", "cmc", "static"}
TRADING_MODES = {"paper"}
TELEGRAM_SIGNAL_THRESHOLDS = {"wait", "watch", "enter"}
ALERT_GRADES = {"A", "B", "C", "D"}


@dataclass(frozen=True)
class Settings:
    trading_mode: str
    data_mode: str
    analyzer_mode: str
    discovery_mode: str
    openai_model: str
    coinmarketcap_api_key: str | None
    cryptopanic_api_key: str | None
    coinalyze_api_key: str | None
    coinglass_api_key: str | None
    exchange_ids: list[str]
    exchange_id: str
    symbol: str
    quote_currency: str
    timeframe: str
    timeframes: list[str]
    candle_limit: int
    backtest_candle_limit: int
    discovery_limit: int
    discovery_pool_limit: int
    prefilter_limit: int
    deep_scan_limit: int
    scan_workers: int
    fetch_timeout_seconds: int
    prefilter_candle_limit: int
    auto_scan_enabled: bool
    auto_scan_interval_seconds: int
    min_market_cap_usd: float
    oi_bases: list[str]
    oi_limit: int
    scan_interval_seconds: int
    render_charts: bool
    chart_dir: str
    short_ma: int
    long_ma: int
    rsi_period: int
    rsi_buy_max: float
    rsi_sell_min: float
    starting_cash: float
    max_position_usd: float
    max_daily_loss_usd: float
    btc_kill_switch_drop_pct: float
    min_volume_24h_usd: float
    min_risk_reward: float
    min_confidence: float
    max_stop_atr_multiple: float
    max_atr_pct: float
    backtest_fee_bps: float
    backtest_slippage_bps: float
    backtest_stop_atr_multiple: float
    backtest_target_r_multiple: float
    backtest_min_risk_reward: float
    backtest_min_relative_volume: float
    backtest_min_body_atr: float
    backtest_min_ema_gap_atr: float
    backtest_min_macd_hist_atr: float
    backtest_min_risk_pct: float
    backtest_scalp_min_risk_pct: float
    backtest_min_net_target_pct: float
    backtest_ma_side: str
    backtest_ma_stop_atr_multiple: float
    backtest_ma_target_r_multiple: float
    backtest_ma_rsi_buy_max: float
    backtest_ma_min_body_atr: float
    backtest_ma_min_gap_atr: float
    backtest_ma_min_risk_pct: float
    backtest_ma_preferred_bases: list[str]
    backtest_ma_excluded_bases: list[str]
    backtest_ma_min_batch_win_rate: float
    backtest_ma_validation_candle_limit: int
    backtest_ma_min_validation_win_rate: float
    backtest_ma_symbol_overrides: dict[str, dict[str, float]]
    backtest_min_confluence_score: int
    backtest_allowed_setups: list[str]
    backtest_breakeven_trigger_r: float
    backtest_partial_target_r: float
    backtest_partial_exit_fraction: float
    backtest_limit: int
    journal_db: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    telegram_min_signal: str
    min_alert_grade: str
    dashboard_url: str | None
    require_watch_before_enter: bool
    active_setup_ttl_minutes: int
    alert_cooldown_minutes: int
    max_alerts_per_scan: int
    max_scalp_alerts_per_scan: int
    scalp_scan_limit: int
    scalp_universe_limit: int
    scalp_candle_limit: int
    backtest_scalp_candle_limit: int
    scalp_min_volume_24h_usd: float
    scalp_alert_cooldown_minutes: int
    scalp_min_atr_pct: float
    scalp_max_atr_pct: float
    scalp_cross_fresh_bars: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        discovery_limit = _env_int("DISCOVERY_LIMIT", "100", min_value=1)
        scan_interval_seconds = _env_int("SCAN_INTERVAL_SECONDS", "900", min_value=30)
        timeframe = _env_str("TIMEFRAME", "1h")
        timeframes = _env_csv("TIMEFRAMES", "1d,4h,1h,15m")
        _validate_timeframe("TIMEFRAME", timeframe)
        for item in timeframes:
            _validate_timeframe("TIMEFRAMES", item)
        return cls(
            trading_mode=_env_choice("TRADING_MODE", "paper", TRADING_MODES),
            data_mode=_env_choice("DATA_MODE", "coinbase", DATA_MODES),
            analyzer_mode=_env_choice("ANALYZER_MODE", "rule", ANALYZER_MODES),
            discovery_mode=_env_choice("DISCOVERY_MODE", "exchange", DISCOVERY_MODES),
            openai_model=_env_str("OPENAI_MODEL", "gpt-4o-mini"),
            coinmarketcap_api_key=_optional(os.getenv("COINMARKETCAP_API_KEY")),
            cryptopanic_api_key=_optional(os.getenv("CRYPTOPANIC_API_KEY")),
            coinalyze_api_key=_first_optional(
                "COINALYZE_API_KEY",
                "COINALAYZE_API_KEY",
            ),
            coinglass_api_key=_optional(os.getenv("COINGLASS_API_KEY")),
            exchange_ids=_env_csv("EXCHANGE_IDS", "binance,bybit,okx"),
            exchange_id=_env_str("EXCHANGE_ID", "binance"),
            symbol=_env_str("SYMBOL", "BTC/USDT"),
            quote_currency=_env_str("QUOTE_CURRENCY", "USDT"),
            timeframe=timeframe,
            timeframes=timeframes,
            candle_limit=_env_int("CANDLE_LIMIT", "200", min_value=50),
            backtest_candle_limit=_env_int("BACKTEST_CANDLE_LIMIT", "60000", min_value=50),
            discovery_limit=discovery_limit,
            discovery_pool_limit=_env_int("DISCOVERY_POOL_LIMIT", "250", min_value=1),
            prefilter_limit=_env_int("PREFILTER_LIMIT", str(discovery_limit), min_value=1),
            deep_scan_limit=_env_int("DEEP_SCAN_LIMIT", "20", min_value=1),
            scan_workers=_env_int("SCAN_WORKERS", "8", min_value=1, max_value=32),
            fetch_timeout_seconds=_env_int("FETCH_TIMEOUT_SECONDS", "20", min_value=1),
            prefilter_candle_limit=_env_int("PREFILTER_CANDLE_LIMIT", "40", min_value=10),
            auto_scan_enabled=_env_bool("AUTO_SCAN_ENABLED", "true"),
            auto_scan_interval_seconds=_env_int(
                "AUTO_SCAN_INTERVAL_SECONDS",
                str(scan_interval_seconds),
                min_value=30,
            ),
            min_market_cap_usd=_env_float("MIN_MARKET_CAP_USD", "100000000", min_value=0),
            oi_bases=_env_csv("OI_BASES", "BTC,ETH,SOL,XRP,DOGE,ADA,AVAX,LINK,DOT"),
            oi_limit=_env_int("OI_LIMIT", "8", min_value=1),
            scan_interval_seconds=scan_interval_seconds,
            render_charts=_env_bool("RENDER_CHARTS", "true"),
            chart_dir=_env_str("CHART_DIR", "charts"),
            short_ma=_env_int("SHORT_MA", "20", min_value=1),
            long_ma=_env_int("LONG_MA", "50", min_value=2),
            rsi_period=_env_int("RSI_PERIOD", "14", min_value=2),
            rsi_buy_max=_env_float("RSI_BUY_MAX", "55", min_value=0, max_value=100),
            rsi_sell_min=_env_float("RSI_SELL_MIN", "35", min_value=0, max_value=100),
            starting_cash=_env_float("STARTING_CASH", "10000", min_value=0),
            max_position_usd=_env_float("MAX_POSITION_USD", "1000", min_value=0),
            max_daily_loss_usd=_env_float("MAX_DAILY_LOSS_USD", "250", min_value=0),
            btc_kill_switch_drop_pct=_env_float("BTC_KILL_SWITCH_DROP_PCT", "3", min_value=0),
            min_volume_24h_usd=_env_float("MIN_VOLUME_24H_USD", "50000000", min_value=0),
            min_risk_reward=_env_float("MIN_RISK_REWARD", "2.0", min_value=0.01),
            min_confidence=_env_float("MIN_CONFIDENCE", "0.72", min_value=0, max_value=1),
            max_stop_atr_multiple=_env_float("MAX_STOP_ATR_MULTIPLE", "3", min_value=0.01),
            max_atr_pct=_env_float("MAX_ATR_PCT", "8", min_value=0.01),
            backtest_fee_bps=_env_float("BACKTEST_FEE_BPS", "10", min_value=0),
            backtest_slippage_bps=_env_float("BACKTEST_SLIPPAGE_BPS", "5", min_value=0),
            backtest_stop_atr_multiple=_env_float(
                "BACKTEST_STOP_ATR_MULTIPLE",
                "1.5",
                min_value=0.01,
            ),
            backtest_target_r_multiple=_env_float(
                "BACKTEST_TARGET_R_MULTIPLE",
                "1",
                min_value=0.01,
            ),
            backtest_min_risk_reward=_env_float(
                "BACKTEST_MIN_RISK_REWARD",
                "1",
                min_value=0.01,
            ),
            backtest_min_relative_volume=_env_float(
                "BACKTEST_MIN_RELATIVE_VOLUME",
                "1.2",
                min_value=0,
            ),
            backtest_min_body_atr=_env_float(
                "BACKTEST_MIN_BODY_ATR",
                "0.15",
                min_value=0,
            ),
            backtest_min_ema_gap_atr=_env_float(
                "BACKTEST_MIN_EMA_GAP_ATR",
                "0.1",
                min_value=0,
            ),
            backtest_min_macd_hist_atr=_env_float(
                "BACKTEST_MIN_MACD_HIST_ATR",
                "0.02",
                min_value=0,
            ),
            backtest_min_risk_pct=_env_float(
                "BACKTEST_MIN_RISK_PCT",
                "0.25",
                min_value=0,
            ),
            backtest_scalp_min_risk_pct=_env_float(
                "BACKTEST_SCALP_MIN_RISK_PCT",
                "0.2",
                min_value=0,
            ),
            backtest_min_net_target_pct=_env_float(
                "BACKTEST_MIN_NET_TARGET_PCT",
                "0",
                min_value=0,
            ),
            backtest_ma_side=_env_choice("BACKTEST_MA_SIDE", "short", {"both", "long", "short"}),
            backtest_ma_stop_atr_multiple=_env_float(
                "BACKTEST_MA_STOP_ATR_MULTIPLE",
                "1.5",
                min_value=0.01,
            ),
            backtest_ma_target_r_multiple=_env_float(
                "BACKTEST_MA_TARGET_R_MULTIPLE",
                "0.75",
                min_value=0.01,
            ),
            backtest_ma_rsi_buy_max=_env_float(
                "BACKTEST_MA_RSI_BUY_MAX",
                "60",
                min_value=0,
                max_value=100,
            ),
            backtest_ma_min_body_atr=_env_float(
                "BACKTEST_MA_MIN_BODY_ATR",
                "0.1",
                min_value=0,
            ),
            backtest_ma_min_gap_atr=_env_float(
                "BACKTEST_MA_MIN_GAP_ATR",
                "0.3",
                min_value=0,
            ),
            backtest_ma_min_risk_pct=_env_float(
                "BACKTEST_MA_MIN_RISK_PCT",
                "0.35",
                min_value=0,
            ),
            backtest_ma_preferred_bases=_env_csv("BACKTEST_MA_PREFERRED_BASES", "BTC,ETH,XRP,DOT"),
            backtest_ma_excluded_bases=_env_csv("BACKTEST_MA_EXCLUDED_BASES", "DOGE,AVAX"),
            backtest_ma_min_batch_win_rate=_env_float(
                "BACKTEST_MA_MIN_BATCH_WIN_RATE",
                "1.0",
                min_value=0,
                max_value=1,
            ),
            backtest_ma_validation_candle_limit=_env_int(
                "BACKTEST_MA_VALIDATION_CANDLE_LIMIT",
                "100000",
                min_value=0,
            ),
            backtest_ma_min_validation_win_rate=_env_float(
                "BACKTEST_MA_MIN_VALIDATION_WIN_RATE",
                "1.0",
                min_value=0,
                max_value=1,
            ),
            backtest_ma_symbol_overrides=_env_symbol_float_overrides(
                "BACKTEST_MA_SYMBOL_OVERRIDES",
                "ETH:rsi_buy_max=50,target_r=0.18,min_body_atr=0.3,min_gap_atr=0.75,min_risk_pct=0.35,short_rsi_max=75,max_short_close_position=0.35,min_short_bearish_sequence=2;XRP:rsi_buy_max=50,target_r=0.3,min_body_atr=0.2,min_gap_atr=0.6,min_risk_pct=0.35,short_rsi_max=75,max_short_close_position=0.5",
            ),
            backtest_min_confluence_score=_env_int(
                "BACKTEST_MIN_CONFLUENCE_SCORE",
                "3",
                min_value=0,
            ),
            backtest_allowed_setups=_env_csv(
                "BACKTEST_ALLOWED_SETUPS",
                "apex_squeeze,bounce,alma_cci_scalp",
            ),
            backtest_breakeven_trigger_r=_env_float(
                "BACKTEST_BREAKEVEN_TRIGGER_R",
                "99",
                min_value=0.01,
            ),
            backtest_partial_target_r=_env_float(
                "BACKTEST_PARTIAL_TARGET_R",
                "1",
                min_value=0.01,
            ),
            backtest_partial_exit_fraction=_env_float(
                "BACKTEST_PARTIAL_EXIT_FRACTION",
                "0",
                min_value=0,
                max_value=1,
            ),
            backtest_limit=_env_int("BACKTEST_LIMIT", "25", min_value=1),
            journal_db=_env_str("JOURNAL_DB", "coach_miranda_miner.sqlite3"),
            telegram_bot_token=_optional(os.getenv("TELEGRAM_BOT_TOKEN")),
            telegram_chat_id=_optional(os.getenv("TELEGRAM_CHAT_ID")),
            telegram_min_signal=_env_choice(
                "TELEGRAM_MIN_SIGNAL",
                "watch",
                TELEGRAM_SIGNAL_THRESHOLDS,
            ),
            min_alert_grade=_env_choice("MIN_ALERT_GRADE", "B", ALERT_GRADES, upper=True),
            dashboard_url=_optional(os.getenv("DASHBOARD_URL")),
            require_watch_before_enter=_env_bool("REQUIRE_WATCH_BEFORE_ENTER", "false"),
            active_setup_ttl_minutes=_env_int("ACTIVE_SETUP_TTL_MINUTES", "240", min_value=1),
            alert_cooldown_minutes=_env_int("ALERT_COOLDOWN_MINUTES", "180", min_value=0),
            max_alerts_per_scan=_env_int("MAX_ALERTS_PER_SCAN", "5", min_value=0),
            max_scalp_alerts_per_scan=_env_int("MAX_SCALP_ALERTS_PER_SCAN", "5", min_value=0),
            scalp_scan_limit=_env_int("SCALP_SCAN_LIMIT", "100", min_value=1),
            scalp_universe_limit=_env_int("SCALP_UNIVERSE_LIMIT", "250", min_value=1),
            scalp_candle_limit=_env_int("SCALP_CANDLE_LIMIT", "240", min_value=50),
            backtest_scalp_candle_limit=_env_int(
                "BACKTEST_SCALP_CANDLE_LIMIT",
                "3000",
                min_value=50,
            ),
            scalp_min_volume_24h_usd=_env_float(
                "SCALP_MIN_VOLUME_24H_USD",
                "5000000",
                min_value=0,
            ),
            scalp_alert_cooldown_minutes=_env_int(
                "SCALP_ALERT_COOLDOWN_MINUTES",
                "45",
                min_value=0,
            ),
            scalp_min_atr_pct=_env_float("SCALP_MIN_ATR_PCT", "0.12", min_value=0),
            scalp_max_atr_pct=_env_float("SCALP_MAX_ATR_PCT", "2.8", min_value=0),
            scalp_cross_fresh_bars=_env_int("SCALP_CROSS_FRESH_BARS", "3", min_value=1),
        )


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise ConfigurationError(f"{name} must not be empty.")
    return value


def _env_csv(name: str, default: str) -> list[str]:
    values = _csv(os.getenv(name, default))
    if not values:
        raise ConfigurationError(f"{name} must contain at least one value.")
    return values


def _env_int(
    name: str,
    default: str,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    raw = os.getenv(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}.") from exc
    _validate_range(name, value, min_value=min_value, max_value=max_value)
    return value


def _env_float(
    name: str,
    default: str,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    raw = os.getenv(name, default)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be a number, got {raw!r}.") from exc
    _validate_range(name, value, min_value=min_value, max_value=max_value)
    return value


def _env_symbol_float_overrides(name: str, default: str) -> dict[str, dict[str, float]]:
    raw = os.getenv(name, default).strip()
    if not raw:
        return {}
    overrides: dict[str, dict[str, float]] = {}
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ConfigurationError(f"{name} entries must look like BASE:key=value.")
        base, assignments = item.split(":", 1)
        base = base.strip().upper()
        if not base:
            raise ConfigurationError(f"{name} override base must not be empty.")
        values: dict[str, float] = {}
        for assignment in assignments.split(","):
            assignment = assignment.strip()
            if not assignment:
                continue
            if "=" not in assignment:
                raise ConfigurationError(f"{name} assignments must look like key=value.")
            key, raw_value = assignment.split("=", 1)
            key = key.strip().lower()
            try:
                values[key] = float(raw_value)
            except ValueError as exc:
                raise ConfigurationError(
                    f"{name} override {base}:{key} must be numeric, got {raw_value!r}."
                ) from exc
        if not values:
            raise ConfigurationError(f"{name} override {base} must include at least one assignment.")
        overrides[base] = values
    return overrides


def _env_bool(name: str, default: str) -> bool:
    value = os.getenv(name, default).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean value, got {value!r}.")


def _env_choice(name: str, default: str, allowed: set[str], *, upper: bool = False) -> str:
    value = os.getenv(name, default).strip()
    value = value.upper() if upper else value.lower()
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ConfigurationError(f"{name} must be one of: {choices}. Got {value!r}.")
    return value


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _validate_range(
    name: str,
    value: int | float,
    *,
    min_value: int | float | None,
    max_value: int | float | None,
) -> None:
    if min_value is not None and value < min_value:
        raise ConfigurationError(f"{name} must be at least {min_value}, got {value}.")
    if max_value is not None and value > max_value:
        raise ConfigurationError(f"{name} must be at most {max_value}, got {value}.")


def _validate_timeframe(name: str, value: str) -> None:
    if not value[:-1].isdigit() or value[-1] not in {"m", "h", "d", "w"}:
        raise ConfigurationError(f"{name} contains unsupported timeframe {value!r}.")


def _optional(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def _first_optional(*names: str) -> str | None:
    for name in names:
        value = _optional(os.getenv(name))
        if value is not None:
            return value
    return None
