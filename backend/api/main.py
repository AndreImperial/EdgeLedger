from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from coach_miranda_miner.alerts import alert_grade
from coach_miranda_miner.coach import CoachMirandaMiner
from coach_miranda_miner.config import Settings
from coach_miranda_miner.indicators import macd, rsi


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"

app = FastAPI(title="EdgeLedger Integrated Scanner")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


def _settings(data_mode: str | None = None) -> Settings:
    base = Settings.from_env()
    if data_mode:
        return replace(base, data_mode=data_mode)
    return base


def _coach(data_mode: str | None = None) -> CoachMirandaMiner:
    return CoachMirandaMiner(_settings(data_mode))


@app.get("/api/health")
def health() -> dict[str, Any]:
    settings = _settings()
    coach = CoachMirandaMiner(settings)
    return {
        "status": "ok",
        "app": "CMMTrader",
        "tradingMode": settings.trading_mode,
        "dataMode": settings.data_mode,
        "analyzerMode": settings.analyzer_mode,
        "discoveryMode": settings.discovery_mode,
        "telegramConfigured": coach.telegram.configured,
        "coinalyzeConfigured": bool(settings.coinalyze_api_key),
        "paperOnly": settings.trading_mode == "paper",
        "scalpUniverseLimit": settings.scalp_universe_limit,
        "scalpScanLimit": settings.scalp_scan_limit,
        "scanWorkers": settings.scan_workers,
    }


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    settings = _settings()
    coach = CoachMirandaMiner(settings)
    return {
        "health": health(),
        "doctor": coach.doctor().splitlines(),
        "guardrails": {
            "maxPositionUsd": settings.max_position_usd,
            "maxDailyLossUsd": settings.max_daily_loss_usd,
            "btcKillSwitchDropPct": settings.btc_kill_switch_drop_pct,
            "minVolume24hUsd": settings.min_volume_24h_usd,
            "minRiskReward": settings.min_risk_reward,
            "minConfidence": settings.min_confidence,
        },
        "scanner": {
            "prefilterLimit": settings.prefilter_limit,
            "deepScanLimit": settings.deep_scan_limit,
            "scanWorkers": settings.scan_workers,
            "candleLimit": settings.candle_limit,
        },
    }


@app.post("/api/scan")
def scan(data_mode: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        coach = _coach(data_mode)
        summary, scores, results = coach.scan_setups()
        return {
            "summary": summary.model_dump(mode="json"),
            "scores": [score.model_dump(mode="json") for score in scores[:100]],
            "results": [_deep_result(result) for result in results],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/scalp")
def scalp(data_mode: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        coach = _coach(data_mode)
        summary, results = coach.scan_scalps()
        return {
            "summary": summary.model_dump(mode="json"),
            "results": [_scalp_result(result) for result in results],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/open-interest")
def open_interest(data_mode: str | None = Query(default=None)) -> dict[str, Any]:
    try:
        rows, warnings = _coach(data_mode).high_oi_watchlist()
        return {
            "warnings": warnings,
            "rows": [row.__dict__ for row in rows],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/market-screener")
def market_screener(
    limit: int = Query(default=8, ge=1, le=12),
    data_mode: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return live ticker and technical context from CMMTrader's market-data router."""
    try:
        coach = _coach(data_mode)
        candidates = coach.discovery.discover(limit)
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        worker_count = min(4, max(1, len(candidates)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_market_screener_row, coach, candidate): candidate
                for candidate in candidates
            }
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    rows.append(future.result())
                except Exception as exc:
                    warnings.append(f"{candidate.route_symbol}: {exc}")
        rows.sort(key=lambda row: abs(row["change24h"] or 0), reverse=True)
        return {
            "source": coach.settings.data_mode,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "warnings": warnings,
            "rows": rows,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/backtest")
def backtest(
    symbol: str = Query(default="BTC/USD"),
    timeframe: str = Query(default="1h"),
    strategy: str = Query(default="miranda"),
    side: str = Query(default="both"),
    data_mode: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        result = _coach(data_mode).backtest(symbol, timeframe, strategy, side)
        return {
            "result": result.__dict__,
            "formatted": result.format(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/journal")
def journal() -> dict[str, Any]:
    coach = _coach()
    return {
        "activeSetups": coach.journal.recent_active_setups(50)
        if hasattr(coach.journal, "recent_active_setups")
        else [],
        "theses": coach.journal.recent_theses(30),
        "alerts": coach.journal.recent_alerts(30),
        "outcomes": coach.journal.recent_signal_outcomes(30),
        "calibration": coach.journal.setup_calibration(500),
    }


def _deep_result(result) -> dict[str, Any]:
    thesis = result.thesis
    validation = result.validation
    return {
        "rank": result.score.rank,
        "symbol": result.candidate.route_symbol,
        "source": result.candidate.exchange_id,
        "setup": thesis.setup.value,
        "signal": thesis.signal.value,
        "direction": thesis.direction,
        "confidence": thesis.confidence,
        "entry": thesis.entry,
        "stopLoss": thesis.stop_loss,
        "targets": thesis.targets,
        "riskReward": thesis.risk_reward,
        "grade": alert_grade(thesis, validation, result.score),
        "approved": validation.approved,
        "alertSent": result.alert_sent,
        "score": result.score.score,
        "volume24hUsd": result.candidate.volume_24h_usd,
        "evidence": thesis.evidence,
        "validationReasons": validation.reasons,
        "prefilterReasons": result.score.prefilter_reasons,
        "tradingLink": result.candidate.trading_link,
    }


def _scalp_result(result) -> dict[str, Any]:
    setup_age_minutes = None
    if result.execution_candle_time is not None:
        setup_age_minutes = max(
            (result.scanned_at - result.execution_candle_time).total_seconds() / 60,
            0,
        )
    return {
        "rank": result.score.rank,
        "symbol": result.candidate.route_symbol,
        "source": result.candidate.exchange_id,
        "setup": result.thesis.setup.value,
        "signal": result.thesis.signal.value,
        "direction": result.thesis.direction,
        "confidence": result.thesis.confidence,
        "entry": result.thesis.entry,
        "stopLoss": result.thesis.stop_loss,
        "targets": result.thesis.targets,
        "riskReward": result.thesis.risk_reward,
        "score": result.score.score,
        "grade": result.quality.grade,
        "approved": result.validation.approved,
        "scannedAt": result.scanned_at.isoformat(),
        "executionCandleTime": result.execution_candle_time.isoformat()
        if result.execution_candle_time
        else None,
        "latestCandleTime": result.latest_candle_time.isoformat()
        if result.latest_candle_time
        else None,
        "setupAgeMinutes": setup_age_minutes,
        "quality": result.quality.reasons,
        "qualityMetrics": {
            "oiPriceRead": result.quality.oi_price_read,
            "biasStrength": result.quality.bias_strength,
            "structureStrength": result.quality.structure_strength,
            "atrPct": result.quality.atr_pct,
            "crossAgeBars": result.quality.cross_age_bars,
            "cciSlope": result.quality.cci_slope,
            "spreadEstimatePct": result.quality.spread_estimate_pct,
            "volatilityOk": result.quality.volatility_ok,
        },
        "openInterestChange24hPct": result.candidate.open_interest_change_24h_pct,
        "volume24hUsd": result.candidate.volume_24h_usd,
        "relativeVolume3m": result.score.relative_volume,
        "evidence": result.thesis.evidence,
        "prefilterReasons": result.score.prefilter_reasons,
        "invalidationReason": result.thesis.invalidation_reason,
        "validationReasons": result.validation.reasons,
        "alertSent": result.alert_sent,
    }


def _market_screener_row(coach: CoachMirandaMiner, candidate) -> dict[str, Any]:
    ticker = coach.router.fetch_ticker(candidate.exchange_id, candidate.route_symbol)
    snapshots: dict[str, dict[str, Any]] = {}
    latest_candle_at = None
    for timeframe in ("1d", "4h", "1h"):
        candles = coach.router.fetch_candles(
            candidate.exchange_id,
            candidate.route_symbol,
            timeframe,
            80,
        )
        close = candles["close"]
        macd_line, signal_line = macd(close)
        snapshots[timeframe] = {
            "rsi": _last_number(rsi(close, 14)),
            "macd": _macd_label(_last_number(macd_line), _last_number(signal_line)),
        }
        candle_at = candles.iloc[-1]["timestamp"]
        if latest_candle_at is None or candle_at > latest_candle_at:
            latest_candle_at = candle_at

    return {
        "symbol": candidate.asset.base,
        "market": candidate.route_symbol,
        "source": candidate.exchange_id,
        "price": ticker.last,
        "change24h": ticker.percentage,
        "volume24hUsd": ticker.quote_volume,
        "rsi4h": snapshots["4h"]["rsi"],
        "rsi1h": snapshots["1h"]["rsi"],
        "macd1d": snapshots["1d"]["macd"],
        "macd4h": snapshots["4h"]["macd"],
        "macd1h": snapshots["1h"]["macd"],
        "updatedAt": latest_candle_at.isoformat()
        if latest_candle_at is not None
        else datetime.now(timezone.utc).isoformat(),
    }


def _last_number(series) -> float | None:
    value = series.iloc[-1]
    return None if value is None or pd.isna(value) else float(value)


def _macd_label(line: float | None, signal: float | None) -> str:
    if line is None or signal is None:
        return "Unavailable"
    zone = "Bull Zone" if line >= 0 else "Bear Zone"
    cross = "Bull Cross" if line >= signal else "Bear Cross"
    return f"{zone} · {cross}"


@app.get("/{full_path:path}")
def frontend(full_path: str):
    file_path = FRONTEND_DIST / full_path
    if full_path and file_path.is_file():
        return FileResponse(file_path)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "message": "React frontend has not been built yet.",
        "build": "Run `pnpm --dir frontend install` and `pnpm --dir frontend build`.",
    }
