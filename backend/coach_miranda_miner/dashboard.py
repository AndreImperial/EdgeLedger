from __future__ import annotations

from dataclasses import replace
from html import escape
from pathlib import Path
import sys
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from .alerts import alert_grade
    from .coach import CoachMirandaMiner
    from .config import Settings
    from .models import IntelligencePack, TradeThesis
except ImportError:
    from coach_miranda_miner.alerts import alert_grade
    from coach_miranda_miner.coach import CoachMirandaMiner
    from coach_miranda_miner.config import Settings
    from coach_miranda_miner.models import (
        IntelligencePack,
        TradeThesis,
    )


DATA_MODES = {
    "Real candles: Coinbase public API": "coinbase",
    "Updating prices: CoinPaprika": "paprika",
    "Direct exchange APIs: Binance/Bybit/OKX (may be region-blocked)": "live",
    "CoinGecko free API": "coingecko",
    "Yahoo free API": "yahoo",
    "Offline demo": "fixture",
}

SIGNAL_PRIORITY = {"enter": 0, "watch": 1, "wait": 2, "reject": 3}
TRADINGVIEW_HEIGHT = 760
NAVIGATION_LABELS = [
    "Overview",
    "Market Scanner",
    "Scalper",
    "Open Interest",
    "Backtests",
    "Journal",
    "System Health",
]


def main() -> None:
    st.set_page_config(
        page_title="Coach Miranda Miner",
        page_icon="CM",
        layout="wide",
    )
    _apply_theme()

    base_settings = Settings.from_env()
    with st.sidebar:
        st.header("Controls")
        data_label = st.selectbox(
            "Data source",
            list(DATA_MODES.keys()),
            index=_mode_index(base_settings.data_mode),
        )
        discovery_limit = st.slider("Top universe", 1, 100, min(base_settings.prefilter_limit, 100))
        deep_scan_limit = st.slider("Deep analysis limit", 1, 30, min(base_settings.deep_scan_limit, 30))
        scalp_universe_limit = st.slider(
            "Scalp universe",
            20,
            300,
            min(base_settings.scalp_universe_limit, 300),
        )
        scalp_scan_limit = st.slider("Scalp scan limit", 5, 150, min(base_settings.scalp_scan_limit, 150))
        candle_limit = st.slider("Candles per timeframe", 80, 300, base_settings.candle_limit)
        auto_refresh = st.checkbox("Auto scan", value=base_settings.auto_scan_enabled)
        refresh_seconds = st.selectbox(
            "Refresh interval",
            [60, 180, 300, 900],
            index=_refresh_index(base_settings.auto_scan_interval_seconds),
        )
        run_scan = st.button("Run Intraday Scan", type="primary", use_container_width=True)
        clear_cache = st.button("Clear Scan Cache", use_container_width=True)
        show_history = st.checkbox("Show signal history", value=True)
        show_oi = st.checkbox("Show High OI + Volume", value=True)
        use_tradingview = st.checkbox("Use TradingView charts", value=True)

        st.divider()
        st.write("Execution")
        st.warning("Live auto-trading is disabled. Use signals manually for now.")

    settings = replace(
        base_settings,
        data_mode=DATA_MODES[data_label],
        discovery_limit=discovery_limit,
        prefilter_limit=discovery_limit,
        deep_scan_limit=deep_scan_limit,
        scalp_scan_limit=scalp_scan_limit,
        scalp_universe_limit=scalp_universe_limit,
        candle_limit=candle_limit,
        render_charts=False,
        auto_scan_enabled=auto_refresh,
        auto_scan_interval_seconds=refresh_seconds,
    )
    coach = CoachMirandaMiner(settings)

    _render_app_header(settings)
    _render_status_strip(settings, coach)

    if clear_cache:
        st.session_state.pop("scan_cache", None)
        st.session_state.pop("scalp_cache", None)
        st.session_state.pop("high_oi_cache", None)
        st.success("Scan cache cleared.")

    view = st.radio(
        "View",
        NAVIGATION_LABELS,
        horizontal=True,
        label_visibility="collapsed",
    )
    if view == "Overview":
        _render_overview(settings, coach)

    if view == "Market Scanner":
        if run_scan or auto_refresh:
            render_scan(
                coach,
                use_tradingview,
                show_oi=False,
                force_refresh=run_scan,
                cache_seconds=refresh_seconds,
            )
        else:
            st.info("Press Run Intraday Scan to look for intraday setups.")

    if view == "Scalper":
        render_scalper(
            coach,
            use_tradingview,
            cache_seconds=refresh_seconds,
        )

    if view == "Open Interest":
        if show_oi:
            render_high_oi(coach, cache_seconds=refresh_seconds)
        else:
            st.info("Enable High OI + Volume in the sidebar.")

    if view == "Backtests":
        render_backtest(coach)

    if view == "Journal":
        if show_history:
            render_history(coach)
            render_outcomes(coach)
            render_calibration(coach)
        else:
            st.info("Enable signal history in the sidebar.")

    if view == "System Health":
        _render_system_health(settings, coach)

    if auto_refresh and view == "Market Scanner":
        time.sleep(refresh_seconds)
        st.rerun()


def _apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --cmm-bg: #080b0f;
            --cmm-bg-2: #0d1218;
            --cmm-panel: #121821;
            --cmm-panel-soft: #18212b;
            --cmm-panel-hard: #0d131a;
            --cmm-border: #263241;
            --cmm-border-bright: #3a4b5f;
            --cmm-text: #eef4f8;
            --cmm-muted: #9aa8b8;
            --cmm-faint: #6f7d8c;
            --cmm-good: #32d296;
            --cmm-warn: #f0b84f;
            --cmm-bad: #f06f6f;
            --cmm-info: #64b5f6;
            --cmm-cyan: #71e6ff;
            --cmm-shadow: 0 18px 48px rgba(0,0,0,.35);
            --cmm-ease: cubic-bezier(.2,.8,.2,1);
        }
        .stApp {
            color: var(--cmm-text);
            background:
              radial-gradient(circle at 14% 0%, rgba(113,230,255,.11), transparent 30rem),
              radial-gradient(circle at 92% 8%, rgba(50,210,150,.08), transparent 28rem),
              linear-gradient(180deg, var(--cmm-bg) 0%, #0b0f14 48%, #090c10 100%);
        }
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: .24;
            background-image:
                linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,.028) 1px, transparent 1px);
            background-size: 42px 42px;
            mask-image: linear-gradient(to bottom, black, transparent 78%);
        }
        .block-container {padding-top: 1.15rem; max-width: 1540px;}
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b1016 0%, #090d12 100%);
            border-right: 1px solid var(--cmm-border);
        }
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        section[data-testid="stSidebar"] label {color: var(--cmm-muted);}
        h1, h2, h3, [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 {
            letter-spacing: 0;
        }
        .stButton > button, .stDownloadButton > button, a[data-testid="stLinkButton"] {
            border-radius: 8px !important;
            min-height: 42px;
            border: 1px solid var(--cmm-border-bright) !important;
            background: linear-gradient(180deg, #1a2531, #111923) !important;
            color: var(--cmm-text) !important;
            box-shadow: 0 10px 24px rgba(0,0,0,.22);
            transition: transform 160ms var(--cmm-ease), border-color 160ms var(--cmm-ease);
        }
        .stButton > button:hover, .stDownloadButton > button:hover, a[data-testid="stLinkButton"]:hover {
            transform: translateY(-1px);
            border-color: rgba(113,230,255,.75) !important;
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #1a7f73, #1261a5) !important;
            border-color: rgba(113,230,255,.8) !important;
        }
        div[role="radiogroup"] {
            background: rgba(18,24,33,.78);
            border: 1px solid var(--cmm-border);
            border-radius: 8px;
            padding: .35rem;
            gap: .25rem;
        }
        div[role="radiogroup"] label {
            border-radius: 6px;
            padding: .28rem .55rem;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--cmm-border);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: var(--cmm-shadow);
        }
        div[data-testid="stExpander"] {
            border: 1px solid var(--cmm-border) !important;
            border-radius: 8px !important;
            background: rgba(18,24,33,.72) !important;
            box-shadow: 0 16px 32px rgba(0,0,0,.22);
        }
        div[data-testid="stMetric"] {
            background:
                linear-gradient(180deg, rgba(255,255,255,.035), transparent),
                var(--cmm-panel);
            border: 1px solid var(--cmm-border);
            border-radius: 8px;
            padding: 0.82rem 0.92rem;
            box-shadow: 0 12px 30px rgba(0,0,0,.24);
        }
        div[data-testid="stMetricLabel"] p {color: var(--cmm-muted); font-size: 0.78rem;}
        div[data-testid="stMetricValue"] {font-size: 1.22rem; color: var(--cmm-text);}
        .cmm-header {
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(113,230,255,.24);
            background:
                linear-gradient(135deg, rgba(19,29,39,.98) 0%, rgba(11,16,22,.98) 62%, rgba(18,32,34,.96) 100%);
            border-radius: 8px;
            padding: 1.2rem 1.25rem;
            margin-bottom: 1rem;
            box-shadow: var(--cmm-shadow);
        }
        .cmm-header::after {
            content: "";
            position: absolute;
            inset: auto 1.25rem 0 1.25rem;
            height: 2px;
            background: linear-gradient(90deg, var(--cmm-cyan), var(--cmm-good), transparent);
            opacity: .9;
        }
        .cmm-title {
            font-size: 2rem;
            font-weight: 760;
            letter-spacing: 0;
            color: var(--cmm-text);
            margin: 0;
        }
        .cmm-subtitle {color: var(--cmm-muted); margin-top: 0.25rem; max-width: 72ch;}
        .cmm-badges {display: flex; gap: 0.45rem; flex-wrap: wrap; margin-top: 0.8rem;}
        .cmm-badge {
            border: 1px solid var(--cmm-border);
            background: var(--cmm-panel-soft);
            border-radius: 6px;
            padding: 0.26rem 0.58rem;
            color: var(--cmm-text);
            font-size: 0.78rem;
            font-weight: 650;
        }
        .cmm-badge.good {border-color: rgba(56,180,135,.55); color: #9ee8cc;}
        .cmm-badge.warn {border-color: rgba(217,164,65,.65); color: #f0cf86;}
        .cmm-badge.bad {border-color: rgba(216,97,97,.65); color: #f2a0a0;}
        .cmm-section-title {
            color: var(--cmm-text);
            font-size: 1.15rem;
            font-weight: 720;
            margin: 1.1rem 0 0.5rem;
        }
        .cmm-command-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .65rem;
            margin: .85rem 0 1rem;
        }
        .cmm-command-card, .cmm-signal-card {
            background:
                linear-gradient(180deg, rgba(255,255,255,.038), transparent),
                rgba(18,24,33,.86);
            border: 1px solid var(--cmm-border);
            border-radius: 8px;
            box-shadow: var(--cmm-shadow);
        }
        .cmm-command-card {padding: .85rem .9rem;}
        .cmm-kicker {
            color: var(--cmm-faint);
            font-size: .72rem;
            font-weight: 720;
            text-transform: uppercase;
            letter-spacing: .08em;
        }
        .cmm-command-value {
            margin-top: .22rem;
            color: var(--cmm-text);
            font-size: 1.08rem;
            font-weight: 760;
        }
        .cmm-command-note {color: var(--cmm-muted); font-size: .78rem; margin-top: .18rem;}
        .cmm-signal-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .75rem;
            margin: .75rem 0 1rem;
        }
        .cmm-signal-card {padding: .9rem; border-left: 3px solid var(--cmm-border-bright);}
        .cmm-signal-card.enter {border-left-color: var(--cmm-good);}
        .cmm-signal-card.watch {border-left-color: var(--cmm-warn);}
        .cmm-signal-card.reject, .cmm-signal-card.wait {border-left-color: var(--cmm-bad);}
        .cmm-signal-top {display:flex; justify-content:space-between; gap:.7rem; align-items:flex-start;}
        .cmm-symbol {font-size:1.08rem; font-weight:780; color:var(--cmm-text);}
        .cmm-strategy {color:var(--cmm-muted); font-size:.82rem; margin-top:.1rem;}
        .cmm-pill {
            border: 1px solid var(--cmm-border);
            border-radius: 6px;
            padding: .18rem .45rem;
            font-size: .72rem;
            font-weight: 760;
            color: var(--cmm-text);
            white-space: nowrap;
        }
        .cmm-pill.enter {color:#a6f4d4; border-color:rgba(50,210,150,.55);}
        .cmm-pill.watch {color:#ffd890; border-color:rgba(240,184,79,.6);}
        .cmm-pill.wait, .cmm-pill.reject {color:#ffb0b0; border-color:rgba(240,111,111,.58);}
        .cmm-signal-metrics {
            display:grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap:.5rem;
            margin-top:.85rem;
        }
        .cmm-mini-metric {
            background: rgba(8,11,15,.55);
            border: 1px solid rgba(255,255,255,.06);
            border-radius: 6px;
            padding: .48rem .5rem;
            min-width: 0;
        }
        .cmm-mini-label {color:var(--cmm-faint); font-size:.68rem; text-transform:uppercase; font-weight:720;}
        .cmm-mini-value {color:var(--cmm-text); font-size:.86rem; font-weight:720; overflow-wrap:anywhere;}
        @media (max-width: 980px) {
            .cmm-command-grid, .cmm-signal-grid {grid-template-columns: 1fr;}
            .cmm-signal-metrics {grid-template-columns: repeat(2, minmax(0, 1fr));}
        }
        @media (prefers-reduced-motion: reduce) {
            * {transition: none !important;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_app_header(settings: Settings) -> None:
    paper_class = "good" if settings.trading_mode == "paper" else "bad"
    data_class = "warn" if settings.data_mode in {"fixture", "paprika"} else "good"
    st.markdown(
        f"""
        <section class="cmm-header">
          <h1 class="cmm-title">Coach Miranda Miner</h1>
          <div class="cmm-subtitle">Crypto setup operations console. Paper and manual alert flow only.</div>
          <div class="cmm-badges">
            <span class="cmm-badge {paper_class}">Trading: {settings.trading_mode.upper()}</span>
            <span class="cmm-badge {data_class}">Data: {settings.data_mode}</span>
            <span class="cmm-badge">Analyzer: {settings.analyzer_mode}</span>
            <span class="cmm-badge">Min R/R: {settings.min_risk_reward:.1f}</span>
            <span class="cmm-badge">Min confidence: {settings.min_confidence:.0%}</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_status_strip(settings: Settings, coach: CoachMirandaMiner) -> None:
    status_cols = st.columns(5)
    status_cols[0].metric("Data Source", settings.data_mode)
    status_cols[1].metric("Universe", settings.prefilter_limit)
    status_cols[2].metric("Deep Limit", settings.deep_scan_limit)
    status_cols[3].metric("Telegram", _status_label(coach.telegram.configured))
    status_cols[4].metric("Coinalyze", _status_label(bool(settings.coinalyze_api_key)))
    if settings.data_mode == "coinbase":
        st.success("Using real public Coinbase OHLCV candles.")
    elif settings.data_mode == "paprika":
        st.warning("CoinPaprika mode has live prices but approximated intraday candles.")
    elif settings.data_mode == "live":
        st.warning("Direct exchange mode may be blocked by Render server location.")
    elif settings.data_mode == "fixture":
        st.warning("Offline demo mode uses synthetic candles.")


def _render_overview(settings: Settings, coach: CoachMirandaMiner) -> None:
    st.markdown('<div class="cmm-section-title">Operating Snapshot</div>', unsafe_allow_html=True)
    cached_scan = st.session_state.get("scan_cache")
    cached_scalp = st.session_state.get("scalp_cache")
    cached_oi = st.session_state.get("high_oi_cache")
    st.markdown(
        _command_grid(
            [
                ("Trading Mode", settings.trading_mode.upper(), "Live execution disabled"),
                ("Auto Scan", _status_label(settings.auto_scan_enabled), f"{settings.auto_scan_interval_seconds}s cadence"),
                ("Alert Threshold", settings.telegram_min_signal.upper(), f"Grade {settings.min_alert_grade}+"),
                ("Journal", Path(settings.journal_db).name, "SQLite decision trail"),
                ("Intraday Cache", _cache_age_label(cached_scan), "Latest market scanner run"),
                ("Scalp Cache", _cache_age_label(cached_scalp), "Latest execution scan"),
                ("OI Cache", _cache_age_label(cached_oi), "Latest derivatives context"),
                ("Data Profile", settings.data_mode, "Source transparency required"),
            ]
        ),
        unsafe_allow_html=True,
    )

    st.markdown('<div class="cmm-section-title">Current Guardrails</div>', unsafe_allow_html=True)
    guard_cols = st.columns(4)
    guard_cols[0].metric("Max Position", f"${settings.max_position_usd:,.0f}")
    guard_cols[1].metric("Daily Loss Cap", f"${settings.max_daily_loss_usd:,.0f}")
    guard_cols[2].metric("BTC Kill Switch", f"{settings.btc_kill_switch_drop_pct:.1f}%")
    guard_cols[3].metric("Min Volume", f"${settings.min_volume_24h_usd / 1_000_000:.0f}M")


def _render_system_health(settings: Settings, coach: CoachMirandaMiner) -> None:
    st.markdown('<div class="cmm-section-title">System Health</div>', unsafe_allow_html=True)
    for line in coach.doctor().splitlines():
        if line.startswith("Warning:"):
            st.warning(line.replace("Warning: ", "", 1))
        else:
            st.caption(line)
    health_cols = st.columns(4)
    health_cols[0].metric("Workers", settings.scan_workers)
    health_cols[1].metric("Fetch Timeout", f"{settings.fetch_timeout_seconds}s")
    health_cols[2].metric("Candles", settings.candle_limit)
    health_cols[3].metric("Charts", _status_label(settings.render_charts))


def _status_label(enabled: bool) -> str:
    return "On" if enabled else "Off"


def _cache_age_label(cache: dict | None) -> str:
    if not cache:
        return "None"
    age = max(int(time.time() - cache.get("saved_at", 0)), 0)
    return f"{age}s"


def _command_grid(items: list[tuple[str, str, str]]) -> str:
    cards = []
    for label, value, note in items:
        cards.append(
            '<article class="cmm-command-card">'
            f'<div class="cmm-kicker">{escape(str(label))}</div>'
            f'<div class="cmm-command-value">{escape(str(value))}</div>'
            f'<div class="cmm-command-note">{escape(str(note))}</div>'
            "</article>"
        )
    return '<div class="cmm-command-grid">' + "".join(cards) + "</div>"


def render_scan(
    coach: CoachMirandaMiner,
    use_tradingview: bool = True,
    show_oi: bool = True,
    force_refresh: bool = False,
    cache_seconds: int = 900,
) -> None:
    cache_key = _scan_cache_key(coach.settings)
    cached = st.session_state.get("scan_cache")
    cache_is_valid = (
        cached is not None
        and cached.get("key") == cache_key
        and time.time() - cached.get("saved_at", 0) < cache_seconds
    )
    if cache_is_valid and not force_refresh:
        summary, scores, results = cached["payload"]
        cache_age = int(time.time() - cached.get("saved_at", 0))
        st.caption(f"Using cached scan result from {cache_age}s ago. Press Run Intraday Scan to force a fresh scan.")
    else:
        with st.spinner("Scanning top universe, ranking candidates, and deep-analyzing setups..."):
            summary, scores, results = coach.scan_setups()
        st.session_state["scan_cache"] = {
            "key": cache_key,
            "saved_at": time.time(),
            "payload": (summary, scores, results),
        }

    status_cols = st.columns(6)
    status_cols[0].metric("Candidates Scanned", summary.candidates_scanned)
    status_cols[1].metric("Deep Analyzed", summary.deep_analyzed)
    status_cols[2].metric("Failed Symbols", summary.failed_symbols)
    status_cols[3].metric("Duration", f"{summary.duration_seconds or 0:.1f}s")
    status_cols[4].metric("Workers", summary.worker_count)
    status_cols[5].metric("Coinalyze", "On" if summary.coinalyze_enabled else "Off")
    st.caption(f"Last scan: {summary.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
    if summary.market_regime is not None:
        st.subheader("Market Regime")
        regime_cols = st.columns(4)
        regime_cols[0].metric("Mode", summary.market_regime.risk_mode)
        regime_cols[1].metric("Trend Score", f"{summary.market_regime.trend_score:.2f}")
        regime_cols[2].metric("BTC 24h", f"{summary.market_regime.btc_change_24h_pct:.2f}%")
        eth_change = summary.market_regime.eth_change_24h_pct
        regime_cols[3].metric("ETH 24h", f"{eth_change:.2f}%" if eth_change is not None else "n/a")
        st.write(summary.market_regime.reason)
    for warning in summary.warnings[:6]:
        st.caption(warning)

    render_prefilter(scores)
    render_short_candidates(results)
    if show_oi:
        render_high_oi_from_scores(scores)
    render_deep_scan(results, use_tradingview)


def render_scalper(
    coach: CoachMirandaMiner,
    use_tradingview: bool = True,
    force_refresh: bool = False,
    cache_seconds: int = 300,
) -> None:
    st.subheader("ALMA EMA CCI Scalper")
    st.caption("15m bias, 5m structure, 3m execution. Manual trading only.")
    action_cols = st.columns([2, 1, 1])
    run_scalp = action_cols[0].button("Search Scalpable Setups", type="primary", use_container_width=True)
    force_scalp = action_cols[1].button("Force Fresh Scalp Scan", use_container_width=True)
    clear_scalp = action_cols[2].button("Clear Scalp Cache", use_container_width=True)
    if clear_scalp:
        st.session_state.pop("scalp_cache", None)
        st.success("Scalp cache cleared.")
    cache_key = ("scalp", _scan_cache_key(coach.settings))
    cached = st.session_state.get("scalp_cache")
    cache_is_valid = (
        cached is not None
        and cached.get("key") == cache_key
        and time.time() - cached.get("saved_at", 0) < cache_seconds
    )
    if cached is not None:
        age = int(time.time() - cached.get("saved_at", 0))
        st.caption(f"Last scalp scan cache age: {age}s.")
    else:
        st.caption("Scalp status: idle. No scalp scan has run in this browser session.")
    should_scan = run_scalp or force_scalp or force_refresh
    if not should_scan and not cache_is_valid:
        st.info("Press Search Scalpable Setups to scan for ALMA/EMA + CCI scalp setups.")
        return
    if cache_is_valid and not should_scan:
        summary, results = cached["payload"]
        cache_age = int(time.time() - cached.get("saved_at", 0))
        st.caption(f"Using cached scalp scan from {cache_age}s ago.")
    else:
        status = st.status("Starting scalp scan...", expanded=True)
        status.write("Step 1/4: discovering liquid markets.")
        status.write("Step 2/4: fetching 15m bias, 5m structure, and 1m execution candles.")
        status.write("Step 3/4: building 3m execution candles and calculating EMA9, ALMA20, CCI20.")
        with st.spinner("Scanning scalpable setups now..."):
            summary, results = coach.scan_scalps()
        status.write(
            f"Step 4/4: scan complete. {summary.deep_analyzed} symbols scanned, "
            f"{summary.failed_symbols} failed."
        )
        status.update(label="Scalp scan complete", state="complete", expanded=False)
        st.session_state["scalp_cache"] = {
            "key": cache_key,
            "saved_at": time.time(),
            "payload": (summary, results),
        }

    status_cols = st.columns(5)
    status_cols[0].metric("Candidates", summary.candidates_scanned)
    status_cols[1].metric("Scanned", summary.deep_analyzed)
    status_cols[2].metric("Failed", summary.failed_symbols)
    status_cols[3].metric("Duration", f"{summary.duration_seconds or 0:.1f}s")
    status_cols[4].metric("Workers", summary.worker_count)
    for warning in summary.warnings[:5]:
        st.caption(warning)

    rows = [
        {
            "rank": result.score.rank,
            "symbol": result.candidate.route_symbol,
            "grade": result.quality.grade,
            "scanned_at": _time_fmt(result.scanned_at),
            "signal_candle": _time_fmt(result.execution_candle_time),
            "latest_3m": _time_fmt(result.latest_candle_time),
            "setup_age_min": _age_minutes(result.execution_candle_time, result.scanned_at),
            "signal": result.thesis.signal.value,
            "direction": result.thesis.direction,
            "confidence": result.thesis.confidence,
            "score": result.score.score,
            "oi_price_read": result.quality.oi_price_read,
            "bias_strength": result.quality.bias_strength,
            "structure": result.quality.structure_strength,
            "atr_pct": result.quality.atr_pct,
            "cross_age": result.quality.cross_age_bars,
            "cci_slope": result.quality.cci_slope,
            "entry": result.thesis.entry,
            "stop": result.thesis.stop_loss,
            "target": result.thesis.targets[0] if result.thesis.targets else None,
            "rr": result.thesis.risk_reward,
            "oi_change_24h_pct": result.candidate.open_interest_change_24h_pct,
            "volume_24h_usd": result.candidate.volume_24h_usd,
            "rel_volume_3m": result.score.relative_volume,
            "alert_sent": result.alert_sent,
        }
        for result in results
    ]
    _render_scalp_summary_sections(results)
    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
                "score": st.column_config.NumberColumn("Score", format="%.1f"),
                "setup_age_min": st.column_config.NumberColumn("Age Min", format="%.0f"),
                "atr_pct": st.column_config.NumberColumn("3m ATR %", format="%.2f%%"),
                "cci_slope": st.column_config.NumberColumn("CCI Slope", format="%.1f"),
                "entry": st.column_config.NumberColumn("Entry", format="%.6f"),
                "stop": st.column_config.NumberColumn("Stop", format="%.6f"),
                "target": st.column_config.NumberColumn("Target", format="%.6f"),
                "rr": st.column_config.NumberColumn("R/R", format="%.2f"),
                "oi_change_24h_pct": st.column_config.NumberColumn("OI 24h %", format="%.2f%%"),
                "volume_24h_usd": st.column_config.NumberColumn("24h Volume", format="$%.0f"),
                "rel_volume_3m": st.column_config.NumberColumn("3m Rel Vol", format="%.2fx"),
            },
        )
    else:
        st.info("No scalpable setups found in this scan.")

    for result in results:
        if result.thesis.signal.value not in {"watch", "enter"}:
            continue
        with st.expander(
            f"#{result.score.rank} {result.candidate.route_symbol} - "
            f"{result.thesis.signal.value.upper()} {result.thesis.direction.upper()}",
            expanded=result.thesis.signal.value == "enter",
        ):
            if use_tradingview:
                components.html(
                    _tradingview_widget(result.candidate.route_symbol, "3m"),
                    height=TRADINGVIEW_HEIGHT,
                )
                st.caption("TradingView may show the nearest supported low timeframe if 3m is unavailable.")
            else:
                st.plotly_chart(
                    _scalp_chart(result),
                    use_container_width=True,
                    key=f"scalp-chart-{result.candidate.route_symbol}",
                )
            detail_cols = st.columns(4)
            detail_cols[0].metric("Signal", result.thesis.signal.value.upper())
            detail_cols[1].metric("Direction", result.thesis.direction.upper())
            detail_cols[2].metric("Confidence", f"{result.thesis.confidence:.0%}")
            detail_cols[3].metric("Grade", result.quality.grade)
            time_cols = st.columns(3)
            time_cols[0].metric("Scan Time", _time_fmt(result.scanned_at))
            time_cols[1].metric("Signal Candle", _time_fmt(result.execution_candle_time))
            time_cols[2].metric("Setup Age", _age_label(result.execution_candle_time, result.scanned_at))
            st.write("Quality")
            for item in result.quality.reasons:
                st.write(f"- {item}")
            st.write("Entry", _fmt(result.thesis.entry))
            st.write("Stop", _fmt(result.thesis.stop_loss))
            st.write("Target", ", ".join(_fmt(item) for item in result.thesis.targets) or "n/a")
            st.write("Evidence")
            for item in [*result.score.prefilter_reasons, *result.thesis.evidence]:
                st.write(f"- {item}")
            if result.validation.approved:
                st.success("Approved ENTER setup")
            else:
                for reason in result.validation.reasons:
                    st.warning(reason)


def _render_scalp_summary_sections(results) -> None:
    if not results:
        return
    top_oi = sorted(
        results,
        key=lambda item: (
            abs(item.candidate.open_interest_change_24h_pct or 0.0),
            item.candidate.volume_24h_usd or 0.0,
        ),
        reverse=True,
    )[:10]
    enter_rows = [item for item in results if item.thesis.signal.value == "enter"]
    watch_rows = [item for item in results if item.thesis.signal.value == "watch"]
    rejected_rows = [item for item in results if item.thesis.signal.value in {"reject", "wait"}]
    cols = st.columns(4)
    cols[0].metric("Top OI Movers", len(top_oi))
    cols[1].metric("ENTER Setups", len(enter_rows))
    cols[2].metric("WATCH Setups", len(watch_rows))
    cols[3].metric("Rejected/Waiting", len(rejected_rows))
    with st.expander("Top OI Movers Feeding The Scalper", expanded=True):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "symbol": item.candidate.route_symbol,
                        "scanned_at": _time_fmt(item.scanned_at),
                        "signal_candle": _time_fmt(item.execution_candle_time),
                        "setup_age_min": _age_minutes(item.execution_candle_time, item.scanned_at),
                        "oi_change_24h_pct": item.candidate.open_interest_change_24h_pct,
                        "volume_24h_usd": item.candidate.volume_24h_usd,
                        "oi_price_read": item.quality.oi_price_read,
                        "grade": item.quality.grade,
                        "signal": item.thesis.signal.value,
                    }
                    for item in top_oi
                ]
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "oi_change_24h_pct": st.column_config.NumberColumn("OI 24h %", format="%.2f%%"),
                "volume_24h_usd": st.column_config.NumberColumn("24h Volume", format="$%.0f"),
                "setup_age_min": st.column_config.NumberColumn("Age Min", format="%.0f"),
            },
        )
    if rejected_rows:
        with st.expander("Rejected / Waiting Reasons"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "symbol": item.candidate.route_symbol,
                            "signal": item.thesis.signal.value,
                            "reason": item.thesis.invalidation_reason or "conditions not aligned",
                            "oi_price_read": item.quality.oi_price_read,
                        }
                        for item in rejected_rows[:25]
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )


def render_prefilter(scores) -> None:
    st.subheader("Top 100 Prefilter")
    if not scores:
        st.info("No prefilter candidates available.")
        return
    frame = _score_frame(scores[:100])
    st.dataframe(
        frame.head(25),
        use_container_width=True,
        hide_index=True,
        column_config=_score_column_config(),
    )
    if len(frame) > 25:
        with st.expander("Show full top 100 prefilter"):
            st.dataframe(
                frame,
                use_container_width=True,
                hide_index=True,
                column_config=_score_column_config(),
            )


def _score_frame(scores) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rank": item.rank,
                "symbol": item.symbol,
                "score": item.score,
                "volume_24h_usd": item.volume_24h_usd,
                "price_change_24h_pct": item.price_change_24h_pct,
                "oi_change_24h_pct": item.oi_change_24h_pct,
                "relative_volume": item.relative_volume,
                "btc_regime_ok": item.btc_regime_ok,
                "why": " ".join(item.prefilter_reasons[:3]),
            }
            for item in scores[:100]
        ]
    )


def _score_column_config() -> dict:
    return {
        "volume_24h_usd": st.column_config.NumberColumn("24h Volume", format="$%.0f"),
        "price_change_24h_pct": st.column_config.NumberColumn("24h %", format="%.2f%%"),
        "oi_change_24h_pct": st.column_config.NumberColumn("OI 24h %", format="%.2f%%"),
        "relative_volume": st.column_config.NumberColumn("15m Rel Vol", format="%.2fx"),
        "score": st.column_config.NumberColumn("Score", format="%.1f"),
    }


def render_deep_scan(results, use_tradingview: bool) -> None:
    st.subheader("Deep Scan Results")
    rows = sorted(
        [
            {
                "rank": result.score.rank,
                "symbol": result.candidate.route_symbol,
                "source": result.candidate.exchange_id,
                "score": result.score.score,
                "setup": result.thesis.setup.value,
                "signal": result.thesis.signal.value,
                "direction": result.thesis.direction,
                "confidence": result.thesis.confidence,
                "entry": result.thesis.entry,
                "stop": result.thesis.stop_loss,
                "target_1": result.thesis.targets[0] if result.thesis.targets else None,
                "grade": alert_grade(result.thesis, result.validation, result.score),
                "approved": result.validation.approved,
                "alert_sent": result.alert_sent,
            }
            for result in results
        ],
        key=lambda item: (
            SIGNAL_PRIORITY.get(item.get("signal", "reject"), 9),
            int(item["rank"]),
        ),
    )
    if rows:
        st.markdown(_signal_card_grid(results), unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No deep scan candidates produced a setup table.")

    for result in results:
        candidate = result.candidate
        pack = result.pack
        thesis = result.thesis
        validation = result.validation
        with st.expander(
            (
                f"#{result.score.rank} {candidate.route_symbol} - "
                f"{thesis.direction.upper()} {thesis.setup.value} / {thesis.signal.value}"
            ),
            expanded=thesis.signal.value in {"watch", "enter"},
        ):
            timeframe = st.selectbox(
                "Chart timeframe",
                list(pack.candles.keys()),
                index=max(list(pack.candles.keys()).index("15m"), 0)
                if "15m" in pack.candles
                else 0,
                key=f"tf-{candidate.route_symbol}",
            )
            if use_tradingview:
                components.html(
                    _tradingview_widget(candidate.route_symbol, timeframe),
                    height=TRADINGVIEW_HEIGHT,
                )
                st.caption("TradingView tools are available inside the full-width chart.")
            else:
                st.plotly_chart(
                    _candlestick(pack, timeframe, thesis),
                    use_container_width=True,
                    key=f"chart-{candidate.route_symbol}-{timeframe}",
                )

            st.divider()
            detail_cols = st.columns(4)
            with detail_cols[0]:
                st.metric("Signal", thesis.signal.value.upper())
                st.metric("Direction", thesis.direction.upper())
            with detail_cols[1]:
                st.metric("Confidence", f"{thesis.confidence:.0%}")
                st.metric("Rank Score", f"{result.score.score:.1f}")
            with detail_cols[2]:
                st.metric("Risk/Reward", thesis.risk_reward or "n/a")
                st.write("Entry", _fmt(thesis.entry))
            with detail_cols[3]:
                st.write("Stop", _fmt(thesis.stop_loss))
                st.write("Targets", ", ".join(_fmt(item) for item in thesis.targets) or "n/a")

            detail_left, detail_right = st.columns(2)
            with detail_left:
                st.write("Evidence")
                for reason in result.score.prefilter_reasons[:3]:
                    st.write(f"- {reason}")
                for item in thesis.evidence:
                    st.write(f"- {item}")
                if candidate.trading_link:
                    st.link_button("Open Trading Page", candidate.trading_link)
            with detail_right:
                st.write("Validation")
                if validation.approved:
                    st.success("Approved")
                else:
                    for reason in validation.reasons:
                        st.warning(reason)


def render_short_candidates(results) -> None:
    short_rows = [
        {
            "rank": result.score.rank,
            "symbol": result.candidate.route_symbol,
            "setup": result.thesis.setup.value,
            "signal": result.thesis.signal.value,
            "confidence": result.thesis.confidence,
            "entry": result.thesis.entry,
            "stop": result.thesis.stop_loss,
            "target_1": result.thesis.targets[0] if result.thesis.targets else None,
            "grade": alert_grade(result.thesis, result.validation, result.score),
        }
        for result in results
        if result.thesis.direction == "short"
    ]
    st.subheader("Short Candidates")
    if not short_rows:
        st.caption("No short setups in the latest deep scan.")
        return
    st.dataframe(
        pd.DataFrame(short_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
            "entry": st.column_config.NumberColumn("Entry", format="%.6f"),
            "stop": st.column_config.NumberColumn("Stop", format="%.6f"),
            "target_1": st.column_config.NumberColumn("Target 1", format="%.6f"),
        },
    )


def _signal_card_grid(results) -> str:
    sorted_results = sorted(
        results,
        key=lambda item: (
            SIGNAL_PRIORITY.get(item.thesis.signal.value, 9),
            int(item.score.rank),
        ),
    )[:8]
    cards = []
    for result in sorted_results:
        thesis = result.thesis
        signal = thesis.signal.value
        grade = alert_grade(thesis, result.validation, result.score)
        cards.append(
            f'<article class="cmm-signal-card {escape(signal)}">'
            '<div class="cmm-signal-top">'
            "<div>"
            f'<div class="cmm-symbol">#{result.score.rank} {escape(result.candidate.route_symbol)}</div>'
            f'<div class="cmm-strategy">{escape(thesis.setup.value)} · '
            f"{escape(thesis.direction.upper())} · Grade {escape(grade)}</div>"
            "</div>"
            f'<span class="cmm-pill {escape(signal)}">{escape(signal.upper())}</span>'
            "</div>"
            '<div class="cmm-signal-metrics">'
            f'{_mini_metric("Entry", _fmt(thesis.entry))}'
            f'{_mini_metric("Stop", _fmt(thesis.stop_loss))}'
            f'{_mini_metric("Target", _fmt(thesis.targets[0] if thesis.targets else None))}'
            f'{_mini_metric("R/R", f"{thesis.risk_reward:.2f}" if thesis.risk_reward else "n/a")}'
            "</div>"
            '<div class="cmm-signal-metrics">'
            f'{_mini_metric("Confidence", f"{thesis.confidence:.0%}")}'
            f'{_mini_metric("Score", f"{result.score.score:.1f}")}'
            f'{_mini_metric("Source", result.candidate.exchange_id)}'
            f'{_mini_metric("Alert", "Sent" if result.alert_sent else "Ready")}'
            "</div>"
            "</article>"
        )
    return '<div class="cmm-signal-grid">' + "".join(cards) + "</div>"


def _mini_metric(label: str, value: str | float | int | None) -> str:
    return (
        '<div class="cmm-mini-metric">'
        f'<div class="cmm-mini-label">{escape(str(label))}</div>'
        f'<div class="cmm-mini-value">{escape(str(value if value is not None else "n/a"))}</div>'
        "</div>"
    )


def render_high_oi(coach: CoachMirandaMiner, cache_seconds: int = 300) -> None:
    st.subheader("High OI + Volume")
    action_cols = st.columns([2, 1, 1])
    run_oi = action_cols[0].button("Scan High OI + Volume", type="primary", use_container_width=True)
    force_oi = action_cols[1].button("Force Fresh OI", use_container_width=True)
    clear_oi = action_cols[2].button("Clear OI Cache", use_container_width=True)
    if clear_oi:
        st.session_state.pop("high_oi_cache", None)
        st.success("High OI cache cleared.")

    cache_key = ("high_oi", _scan_cache_key(coach.settings))
    cached = st.session_state.get("high_oi_cache")
    cache_is_valid = (
        cached is not None
        and cached.get("key") == cache_key
        and time.time() - cached.get("saved_at", 0) < cache_seconds
    )
    cached_payload = _cached_scan_payload()
    if cached_payload is not None:
        _, scores, _ = cached_payload
        st.caption("Scanner cache is available. You can view scan-derived OI context below or run a fresh OI scan.")
        render_high_oi_from_scores(scores, title="High OI + Volume From Latest Scanner Cache")

    if cached is not None:
        age = int(time.time() - cached.get("saved_at", 0))
        st.caption(f"Last dedicated High OI scan cache age: {age}s.")
    else:
        st.caption("High OI status: idle. No dedicated OI scan has run in this browser session.")

    should_scan = run_oi or force_oi or (cached_payload is None and cached is None)
    if not should_scan and not cache_is_valid:
        st.info("Press Scan High OI + Volume to refresh this tab.")
        return
    if cache_is_valid and not should_scan:
        rows, warnings = cached["payload"]
        st.caption("Using cached dedicated High OI scan.")
    else:
        status = st.status("Starting High OI scan...", expanded=True)
        status.write("Step 1/3: building the current top market universe.")
        status.write("Step 2/3: requesting Coinalyze OI when configured and volume fallback data.")
        with st.spinner("Scanning high OI and high-volume coins..."):
            rows, warnings = coach.high_oi_watchlist(limit=100)
        status.write(f"Step 3/3: scan complete. {len(rows)} rows returned.")
        status.update(label="High OI scan complete", state="complete", expanded=False)
        st.session_state["high_oi_cache"] = {
            "key": cache_key,
            "saved_at": time.time(),
            "payload": (rows, warnings),
        }

    for warning in warnings[:3]:
        st.caption(warning)
    if not rows:
        st.info("No OI or volume rows available from the configured sources.")
        return

    frame = pd.DataFrame(
        [
            {
                "symbol": row.symbol,
                "source": row.source,
                "open_interest_usd": row.open_interest_usd,
                "oi_change_24h_pct": row.open_interest_change_24h_pct,
                "volume_24h_usd": row.volume_24h_usd,
                "score": row.score,
                "price": row.price,
                "status": row.status,
                "updated": row.updated_at.isoformat(timespec="minutes"),
            }
            for row in rows[:100]
        ]
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "open_interest_usd": st.column_config.NumberColumn("OI USD", format="$%.0f"),
            "oi_change_24h_pct": st.column_config.NumberColumn("OI 24h %", format="%.2f%%"),
            "volume_24h_usd": st.column_config.NumberColumn("24h Volume", format="$%.0f"),
            "score": st.column_config.NumberColumn("OI/Vol Score", format="%.0f"),
            "price": st.column_config.NumberColumn("Price", format="$%.4f"),
        },
    )


def render_high_oi_from_scores(scores, title: str = "High OI + Volume") -> None:
    st.subheader(title)
    rows = [
        item
        for item in scores
        if item.oi_change_24h_pct is not None or item.volume_24h_usd is not None
    ]
    if not rows:
        st.info("No OI or volume rows available from the current scan.")
        return
    frame = pd.DataFrame(
        [
            {
                "rank": item.rank,
                "symbol": item.symbol,
                "score": item.score,
                "oi_change_24h_pct": item.oi_change_24h_pct,
                "volume_24h_usd": item.volume_24h_usd,
                "relative_volume": item.relative_volume,
            }
            for item in sorted(
                rows,
                key=lambda row: (
                    abs(row.oi_change_24h_pct or 0.0),
                    row.volume_24h_usd or 0.0,
                ),
                reverse=True,
            )[:30]
        ]
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "oi_change_24h_pct": st.column_config.NumberColumn("OI 24h %", format="%.2f%%"),
            "volume_24h_usd": st.column_config.NumberColumn("24h Volume", format="$%.0f"),
            "relative_volume": st.column_config.NumberColumn("15m Rel Vol", format="%.2fx"),
            "score": st.column_config.NumberColumn("Score", format="%.1f"),
        },
    )


def render_history(coach: CoachMirandaMiner) -> None:
    st.subheader("Active WATCH/ENTER Lifecycle")
    active_rows = (
        coach.journal.recent_active_setups(50)
        if hasattr(coach.journal, "recent_active_setups")
        else []
    )
    if active_rows:
        active_frame = pd.DataFrame(active_rows)
        st.download_button(
            "Download Active Setups CSV",
            active_frame.to_csv(index=False),
            file_name="active_setups.csv",
            mime="text/csv",
        )
        st.dataframe(
            active_frame,
            use_container_width=True,
            hide_index=True,
            column_config={
                "entry": st.column_config.NumberColumn("Entry", format="%.6f"),
                "stop_loss": st.column_config.NumberColumn("Stop", format="%.6f"),
                "target": st.column_config.NumberColumn("Target", format="%.6f"),
                "score": st.column_config.NumberColumn("Score", format="%.1f"),
                "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
            },
        )
    else:
        st.caption("No active setup lifecycle rows yet.")

    st.subheader("Recent Signal History")
    rows = coach.journal.recent_theses(20)
    if not rows:
        st.caption("No saved signals yet.")
    else:
        frame = pd.DataFrame(
            [
                {
                    "time": row["created_at"],
                    "symbol": row["symbol"],
                    "setup": row["setup"],
                    "signal": row["signal"],
                    "confidence": row["confidence"],
                    "approved": row["approved"],
                }
                for row in rows
            ]
        )
        st.dataframe(frame, use_container_width=True, hide_index=True)

    st.subheader("Recent Alerts")
    alerts = coach.journal.recent_alerts(20)
    if not alerts:
        st.caption("No Telegram alerts sent yet.")
        return
    alert_frame = pd.DataFrame(
        [
            {
                "time": row["created_at"],
                "symbol": row["symbol"],
                "setup": row["setup"],
                "signal": row["signal"],
            }
            for row in alerts
        ]
    )
    st.download_button(
        "Download Alerts CSV",
        alert_frame.to_csv(index=False),
        file_name="telegram_alerts.csv",
        mime="text/csv",
    )
    st.dataframe(alert_frame, use_container_width=True, hide_index=True)


def render_calibration(coach: CoachMirandaMiner) -> None:
    st.subheader("Setup Calibration")
    rows = coach.journal.setup_calibration(500)
    if not rows:
        st.caption("No setup score history yet.")
        return
    frame = pd.DataFrame(rows)
    st.download_button(
        "Download Setup Calibration CSV",
        frame.to_csv(index=False),
        file_name="setup_calibration.csv",
        mime="text/csv",
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "avg_score": st.column_config.NumberColumn("Avg Score", format="%.1f"),
            "avg_confidence": st.column_config.NumberColumn("Avg Confidence", format="%.2f"),
            "avg_relative_volume": st.column_config.NumberColumn("Avg Rel Vol", format="%.2fx"),
            "avg_oi_change_24h_pct": st.column_config.NumberColumn("Avg OI 24h %", format="%.2f%%"),
        },
    )


def render_outcomes(coach: CoachMirandaMiner) -> None:
    st.subheader("Outcome Tracking")
    if st.button("Update Due Outcomes"):
        with st.spinner("Checking 15m candles for target/stop/time outcomes..."):
            updated = coach.update_signal_outcomes()
        st.success(f"Updated {updated} due outcome rows.")

    summary = coach.journal.outcome_summary(500)
    if summary:
        summary_frame = pd.DataFrame(summary)
        st.download_button(
            "Download Outcome Summary CSV",
            summary_frame.to_csv(index=False),
            file_name="outcome_summary.csv",
            mime="text/csv",
        )
        st.dataframe(
            summary_frame,
            use_container_width=True,
            hide_index=True,
            column_config={
                "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1%%"),
                "avg_return_pct": st.column_config.NumberColumn("Avg Return", format="%.2f%%"),
            },
        )

    rows = coach.journal.recent_signal_outcomes(50)
    if not rows:
        st.caption("No tracked signal outcomes yet.")
        return
    outcome_frame = pd.DataFrame(rows)
    st.download_button(
        "Download Recent Outcomes CSV",
        outcome_frame.to_csv(index=False),
        file_name="recent_outcomes.csv",
        mime="text/csv",
    )
    st.dataframe(
        outcome_frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "entry": st.column_config.NumberColumn("Entry", format="%.6f"),
            "stop_loss": st.column_config.NumberColumn("Stop", format="%.6f"),
            "target": st.column_config.NumberColumn("Target", format="%.6f"),
            "score": st.column_config.NumberColumn("Score", format="%.1f"),
            "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
            "return_pct": st.column_config.NumberColumn("Return", format="%.2f%%"),
        },
    )
    candle_rows = (
        coach.journal.recent_candle_samples(50)
        if hasattr(coach.journal, "recent_candle_samples")
        else []
    )
    if candle_rows:
        st.subheader("Historical Candle Samples")
        candle_frame = pd.DataFrame(candle_rows)
        st.download_button(
            "Download Candle Sample Log CSV",
            candle_frame.to_csv(index=False),
            file_name="candle_samples.csv",
            mime="text/csv",
        )
        st.dataframe(candle_frame, use_container_width=True, hide_index=True)


def render_backtest(coach: CoachMirandaMiner) -> None:
    st.subheader("Strategy Backtest")
    cols = st.columns(4)
    with cols[0]:
        symbol = st.text_input("Symbol", value=coach.settings.symbol.replace("USDT", "USD"))
    with cols[1]:
        timeframe = st.selectbox("Timeframe", ["3m", "5m", "15m", "1h", "4h", "1d"], index=2)
    with cols[2]:
        strategy = st.selectbox("Strategy", ["miranda", "scalp", "ma"], index=0)
    with cols[3]:
        side = st.selectbox("Side", ["both", "long", "short"], index=0)

    left_action, right_action = st.columns(2)
    run_single = left_action.button("Run Backtest", type="primary", use_container_width=True)
    run_batch = right_action.button("Run Batch Top Coins", use_container_width=True)
    run_walk = st.button("Run Walk-Forward Test", use_container_width=True)
    if not run_single and not run_batch and not run_walk:
        st.caption("Backtests use the configured data source and candle limit.")
        return

    if run_walk:
        with st.spinner("Running walk-forward validation..."):
            try:
                result = coach.walk_forward_backtest(symbol, timeframe, strategy, side)
            except Exception as exc:
                st.error("Walk-forward test failed.")
                st.code(str(exc))
                return
        rows = [
            {
                "segment": "train",
                "trades": result["train"].trades,
                "win_rate": result["train"].win_rate,
                "expectancy_pct": result["train"].expectancy_pct,
                "return_pct": result["train"].total_return_pct,
                "drawdown_pct": result["train"].max_drawdown_pct,
            },
            {
                "segment": "test",
                "trades": result["test"].trades,
                "win_rate": result["test"].win_rate,
                "expectancy_pct": result["test"].expectancy_pct,
                "return_pct": result["test"].total_return_pct,
                "drawdown_pct": result["test"].max_drawdown_pct,
            },
        ]
        st.metric("Expectancy Degradation", f"{result['degradation_pct']:.2f}%")
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1%%"),
                "expectancy_pct": st.column_config.NumberColumn("Expectancy", format="%.2f%%"),
                "return_pct": st.column_config.NumberColumn("Return", format="%.2f%%"),
                "drawdown_pct": st.column_config.NumberColumn("Drawdown", format="%.2f%%"),
            },
        )
        return

    if run_batch:
        with st.spinner("Running batch backtests across the current universe..."):
            rows = coach.batch_backtest(
                limit=coach.settings.backtest_limit,
                timeframe=timeframe,
                strategy=strategy,
                side=side,
            )
        if not rows:
            st.info("Batch backtest did not return any rows from the current data source.")
            return
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1%%"),
                "return_pct": st.column_config.NumberColumn("Return", format="%.2f%%"),
                "drawdown_pct": st.column_config.NumberColumn("Drawdown", format="%.2f%%"),
                "profit_factor": st.column_config.NumberColumn("Profit Factor", format="%.2f"),
                "expectancy_pct": st.column_config.NumberColumn("Expectancy", format="%.2f%%"),
            },
        )
        return

    with st.spinner("Running backtest..."):
        try:
            result = coach.backtest(symbol, timeframe, strategy, side)
        except Exception as exc:
            st.error("Backtest failed.")
            st.code(str(exc))
            return

    metrics = st.columns(6)
    metrics[0].metric("Trades", result.trades)
    metrics[1].metric("Win Rate", f"{result.win_rate:.1%}")
    metrics[2].metric("Return", f"{result.total_return_pct:.2f}%")
    metrics[3].metric("Drawdown", f"{result.max_drawdown_pct:.2f}%")
    metrics[4].metric("Profit Factor", f"{result.profit_factor:.2f}")
    metrics[5].metric("Expectancy", f"{result.expectancy_pct:.2f}%")
    st.write(f"Longs: {result.long_trades} | Shorts: {result.short_trades}")
    if result.setup_stats:
        setup_rows = [
            {"setup": setup, **stats}
            for setup, stats in sorted(
                result.setup_stats.items(),
                key=lambda item: item[1].get("expectancy_pct", 0.0),
                reverse=True,
            )
        ]
        st.write("Setup Breakdown")
        st.dataframe(
            pd.DataFrame(setup_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1%%"),
                "expectancy_pct": st.column_config.NumberColumn("Expectancy", format="%.2f%%"),
            },
        )
    if result.sample_trades:
        st.dataframe(pd.DataFrame(result.sample_trades), use_container_width=True, hide_index=True)
    st.code(result.format())


def _candlestick(pack: IntelligencePack, timeframe: str, thesis: TradeThesis) -> go.Figure:
    candles = pack.candles[timeframe]
    frame = pd.DataFrame([item.model_dump() for item in candles])
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=frame["timestamp"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            name=timeframe,
        )
    )
    fig.add_trace(
        go.Bar(
            x=frame["timestamp"],
            y=frame["volume"],
            name="Volume",
            marker_color="rgba(120, 160, 220, 0.35)",
            yaxis="y2",
        )
    )
    for value, color, label in [
        (thesis.entry, "#3b82f6", "Entry"),
        (thesis.stop_loss, "#ef4444", "Stop"),
    ]:
        if value is not None:
            fig.add_hline(y=value, line_color=color, line_dash="dash", annotation_text=label)
    for index, target in enumerate(thesis.targets, start=1):
        fig.add_hline(
            y=target,
            line_color="#22c55e",
            line_dash="dot",
            annotation_text=f"Target {index}",
        )
    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=35, b=10),
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title=f"{pack.candidate.route_symbol} {timeframe}",
        yaxis2=dict(
            overlaying="y",
            side="right",
            showgrid=False,
            visible=False,
        ),
    )
    return fig


def _scalp_chart(result) -> go.Figure:
    frame = result.candles["3m"].tail(120)
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=frame["timestamp"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            name="3m",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frame["timestamp"],
            y=frame["ema_9"],
            mode="lines",
            name="EMA 9",
            line=dict(color="#f59e0b", width=1.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frame["timestamp"],
            y=frame["alma_20"],
            mode="lines",
            name="ALMA 20",
            line=dict(color="#22c55e", width=1.8),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frame["timestamp"],
            y=frame["cci_20"],
            mode="lines",
            name="CCI 20",
            yaxis="y2",
            line=dict(color="#38bdf8", width=1.4),
        )
    )
    for value, color, label in [
        (result.thesis.entry, "#3b82f6", "Entry"),
        (result.thesis.stop_loss, "#ef4444", "Stop"),
    ]:
        if value is not None:
            fig.add_hline(y=value, line_color=color, line_dash="dash", annotation_text=label)
    for target in result.thesis.targets:
        fig.add_hline(y=target, line_color="#22c55e", line_dash="dot", annotation_text="Target")
    fig.update_layout(
        height=720,
        margin=dict(l=10, r=10, t=35, b=10),
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title=f"{result.candidate.route_symbol} 3m ALMA/EMA/CCI",
        yaxis2=dict(
            title="CCI",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
    )
    return fig


def _tradingview_widget(symbol: str, timeframe: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        html, body {{
          height: 100%;
          width: 100%;
          margin: 0;
          overflow: hidden;
          background: #0b0e11;
        }}
        .tradingview-widget-container,
        .tradingview-widget-container__widget {{
          height: 100%;
          width: 100%;
        }}
      </style>
    </head>
    <body>
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {{
        "width": "100%",
        "height": {TRADINGVIEW_HEIGHT},
        "symbol": "{_tradingview_symbol(symbol)}",
        "interval": "{_tradingview_interval(timeframe)}",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "withdateranges": true,
        "hide_side_toolbar": false,
        "details": true,
        "hotlist": true,
        "calendar": false,
        "support_host": "https://www.tradingview.com"
      }}
      </script>
    </div>
    </body>
    </html>
    """


def _tradingview_symbol(symbol: str) -> str:
    base = symbol.split("/")[0].upper()
    return f"COINBASE:{base}USD"


def _tradingview_interval(timeframe: str) -> str:
    return {
        "3m": "3",
        "5m": "5",
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1d": "D",
    }.get(timeframe, "15")


def _mode_index(mode: str) -> int:
    values = list(DATA_MODES.values())
    return values.index(mode) if mode in values else 0


def _refresh_index(seconds: int) -> int:
    values = [60, 180, 300, 900]
    return values.index(seconds) if seconds in values else 3


def _scan_cache_key(settings: Settings) -> tuple:
    return (
        settings.data_mode,
        settings.prefilter_limit,
        settings.deep_scan_limit,
        settings.candle_limit,
        tuple(settings.timeframes),
        settings.min_confidence,
        settings.min_risk_reward,
        settings.min_volume_24h_usd,
        bool(settings.coinalyze_api_key),
        settings.telegram_min_signal,
        getattr(settings, "min_alert_grade", "B"),
        getattr(settings, "require_watch_before_enter", False),
        getattr(settings, "active_setup_ttl_minutes", 240),
        settings.scan_workers,
        settings.prefilter_candle_limit,
        getattr(settings, "scalp_scan_limit", 20),
        getattr(settings, "scalp_universe_limit", 250),
        getattr(settings, "scalp_candle_limit", 240),
        getattr(settings, "scalp_min_volume_24h_usd", 25_000_000),
        getattr(settings, "scalp_alert_cooldown_minutes", 45),
        getattr(settings, "scalp_min_atr_pct", 0.12),
        getattr(settings, "scalp_max_atr_pct", 2.8),
        getattr(settings, "scalp_cross_fresh_bars", 3),
    )


def _cached_scan_payload():
    cached = st.session_state.get("scan_cache")
    if cached is None:
        return None
    return cached.get("payload")


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value >= 100:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:.4f}"
    return f"{value:.6f}"


def _time_fmt(value) -> str:
    if value is None:
        return "n/a"
    try:
        timestamp = pd.to_datetime(value, utc=True)
    except (ValueError, TypeError):
        return "n/a"
    return timestamp.strftime("%H:%M UTC")


def _age_minutes(start, end) -> float | None:
    if start is None or end is None:
        return None
    start_time = pd.to_datetime(start, utc=True)
    end_time = pd.to_datetime(end, utc=True)
    return max((end_time - start_time).total_seconds() / 60, 0)


def _age_label(start, end) -> str:
    minutes = _age_minutes(start, end)
    if minutes is None:
        return "n/a"
    return f"{minutes:.0f}m"


if __name__ == "__main__":
    main()
