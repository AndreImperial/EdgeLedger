from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import math
from threading import Lock
import time

from ccxt import BaseError as CcxtError
import pandas as pd
import requests

from .alerts import AlertFormatter, alert_grade, grade_rank, telegram_buttons
from .analyzer import OpenAIVisionAnalyzer, RuleBasedAnalyzer
from .backtest import (
    AlmaCciScalpBacktester,
    BacktestResult,
    MIN_VALIDATION_TRADES,
    MirandaStrategyBacktester,
    MovingAverageBacktester,
    StrategyBacktestConfig,
    prepare_miranda_backtest_frame,
    prepare_moving_average_backtest_frame,
    prepare_scalp_backtest_frame,
)
from .broker import PaperBroker
from .charts import ChartRenderer
from .config import Settings
from .data import MarketData
from .discovery import DEFAULT_MAJORS, DiscoveryEngine, ExchangeMomentumDiscoveryEngine
from .exchanges import (
    BitunixRouter,
    CoinGeckoRouter,
    CoinPaprikaRouter,
    CoinbaseRouter,
    ExchangeRouter,
    FixtureExchangeRouter,
    YahooFinanceRouter,
)
from .gatekeepers import Gatekeeper
from .intelligence import IntelligenceGatherer
from .journal import Journal
from .market_cap import CoinMarketCapProvider, StaticMarketCapProvider
from .market_data_quality import ensure_structurally_valid_candles
from .miner import SignalMiner
from .models import (
    Asset,
    Candidate,
    IndicatorSnapshot,
    IntelligencePack,
    MarketRegime,
    ScanSummary,
    Setup,
    SetupScore,
    SignalState,
    TradeThesis,
    ValidationResult,
)
from .news import CryptoPanicNewsProvider, EmptyNewsProvider
from .oi import OISnapshot, OpenInterestScanner
from .risk import RiskManager
from .scalper import AlmaCciScalper, ScalpScanResult
from .telegram import TelegramAlerter
from .validator import ThesisValidator


@dataclass(frozen=True)
class DeepScanResult:
    candidate: Candidate
    score: SetupScore
    pack: IntelligencePack
    thesis: TradeThesis
    validation: ValidationResult
    alert_sent: bool


class CoachMirandaMiner:
    def __init__(self, settings: Settings) -> None:
        if settings.trading_mode != "paper":
            raise ValueError("Only paper mode is supported in this scaffold.")

        self.settings = settings
        try:
            self.market_data = MarketData(settings.exchange_id)
        except AttributeError:
            self.market_data = None
        self.miner = SignalMiner(
            short_ma=settings.short_ma,
            long_ma=settings.long_ma,
            rsi_period=settings.rsi_period,
            rsi_buy_max=settings.rsi_buy_max,
            rsi_sell_min=settings.rsi_sell_min,
        )
        self.risk = RiskManager(settings.max_position_usd, settings.max_daily_loss_usd)
        self.broker = PaperBroker(settings.starting_cash)
        self.journal = Journal(settings.journal_db)
        self.router = (
            FixtureExchangeRouter(settings.exchange_ids)
            if settings.data_mode == "fixture"
            else CoinGeckoRouter(settings.exchange_ids)
            if settings.data_mode == "coingecko"
            else YahooFinanceRouter(settings.exchange_ids)
            if settings.data_mode == "yahoo"
            else CoinPaprikaRouter(settings.exchange_ids)
            if settings.data_mode == "paprika"
            else BitunixRouter(settings.exchange_ids, settings.fetch_timeout_seconds)
            if settings.data_mode == "bitunix"
            else CoinbaseRouter(settings.exchange_ids, settings.fetch_timeout_seconds)
            if settings.data_mode == "coinbase"
            else ExchangeRouter(settings.exchange_ids)
        )
        self.discovery = self._build_discovery()
        self.gatekeeper = Gatekeeper(
            self.router,
            settings.btc_kill_switch_drop_pct,
            settings.min_volume_24h_usd,
            settings.quote_currency,
        )
        chart_renderer = ChartRenderer(settings.chart_dir) if settings.render_charts else None
        news_provider = (
            CryptoPanicNewsProvider(settings.cryptopanic_api_key)
            if settings.cryptopanic_api_key
            else EmptyNewsProvider()
        )
        self.intelligence = IntelligenceGatherer(
            self.router,
            settings.timeframes,
            settings.candle_limit,
            chart_renderer,
            news_provider,
        )
        self.analyzer = (
            OpenAIVisionAnalyzer(settings.openai_model)
            if settings.analyzer_mode == "openai"
            else RuleBasedAnalyzer()
        )
        self.validator = ThesisValidator(
            settings.min_risk_reward,
            settings.min_confidence,
            settings.max_stop_atr_multiple,
            settings.max_atr_pct,
        )
        self.alerts = AlertFormatter()
        self.telegram = TelegramAlerter(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
        )
        self.backtester = MovingAverageBacktester(
            settings.short_ma,
            settings.long_ma,
            settings.rsi_period,
            settings.backtest_ma_rsi_buy_max,
            settings.backtest_fee_bps,
            settings.backtest_slippage_bps,
            settings.backtest_ma_stop_atr_multiple,
            settings.backtest_ma_target_r_multiple,
            settings.backtest_breakeven_trigger_r,
            settings.backtest_partial_target_r,
            settings.backtest_partial_exit_fraction,
            settings.backtest_ma_min_body_atr,
            settings.backtest_ma_min_gap_atr,
            settings.backtest_ma_min_risk_pct,
            settings.backtest_min_net_target_pct,
        )
        self.oi_scanner = OpenInterestScanner(
            self.router,
            settings.oi_bases,
            settings.coinalyze_api_key,
            fixture_mode=settings.data_mode == "fixture",
        )
        self.scalper = AlmaCciScalper(
            self.validator,
            min_atr_pct=settings.scalp_min_atr_pct,
            max_atr_pct=settings.scalp_max_atr_pct,
            cross_fresh_bars=settings.scalp_cross_fresh_bars,
        )

    def scan_setups(self) -> tuple[ScanSummary, list[SetupScore], list[DeepScanResult]]:
        started_at = time.perf_counter()
        warnings: list[str] = []
        worker_count = max(1, self.settings.scan_workers)
        outcome_updates = self._auto_update_outcomes()
        expired_setups = self._expire_active_setups()
        self._scan_ticker_cache = {}
        self._scan_candle_cache = {}
        self._scan_cache_lock = Lock()
        self._reset_alert_budget()
        try:
            market_regime = self.gatekeeper.market_regime()
        except (CcxtError, requests.RequestException, ValueError) as exc:
            summary = ScanSummary(
                candidates_scanned=0,
                deep_analyzed=0,
                warnings=[f"Market regime unavailable: {exc}"],
                coinalyze_enabled=bool(self.settings.coinalyze_api_key),
                duration_seconds=_elapsed(started_at),
                worker_count=worker_count,
            )
            return summary, [], []

        try:
            candidates = self.discovery.discover(self.settings.prefilter_limit)
        except (CcxtError, requests.RequestException, ValueError) as exc:
            summary = ScanSummary(
                candidates_scanned=0,
                deep_analyzed=0,
                warnings=[f"Discovery unavailable: {exc}", *warnings],
                coinalyze_enabled=bool(self.settings.coinalyze_api_key),
                market_regime=market_regime,
                duration_seconds=_elapsed(started_at),
                worker_count=worker_count,
            )
            return summary, [], []

        oi_by_base = self._coinalyze_rows_for_candidates(candidates, warnings)

        failed_symbols = 0
        scored: list[tuple[Candidate, SetupScore]] = []
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._score_candidate, candidate, oi_by_base, market_regime): candidate
                for candidate in candidates
            }
            done, pending = wait(futures, timeout=self.settings.fetch_timeout_seconds)
            for future in done:
                candidate = futures[future]
                try:
                    result = future.result()
                except (CcxtError, requests.RequestException, ValueError, IndexError) as exc:
                    failed_symbols += 1
                    warnings.append(f"{candidate.route_symbol} prefilter skipped: {exc}")
                    continue
                if result is None:
                    failed_symbols += 1
                    continue
                scored.append(result)
            for future in pending:
                failed_symbols += 1
                candidate = futures[future]
                future.cancel()
                warnings.append(
                    f"{candidate.route_symbol} prefilter timed out after "
                    f"{self.settings.fetch_timeout_seconds}s."
                )

        ranked_pairs = sorted(scored, key=lambda item: item[1].score, reverse=True)
        ranked: list[tuple[Candidate, SetupScore]] = []
        for rank, (candidate, score) in enumerate(ranked_pairs, start=1):
            ranked.append((candidate, score.model_copy(update={"rank": rank})))

        deep_results: list[DeepScanResult] = []
        deep_pairs = ranked[: self.settings.deep_scan_limit]
        with ThreadPoolExecutor(max_workers=max(1, min(worker_count, len(deep_pairs) or 1))) as executor:
            futures = {
                executor.submit(self._deep_scan_candidate, candidate, score, market_regime): (candidate, score)
                for candidate, score in deep_pairs
            }
            done, pending = wait(
                futures,
                timeout=max(self.settings.fetch_timeout_seconds, self.settings.fetch_timeout_seconds * len(deep_pairs)),
            )
            for future in done:
                candidate, _ = futures[future]
                try:
                    result = future.result()
                except (CcxtError, requests.RequestException, ValueError, IndexError) as exc:
                    failed_symbols += 1
                    warnings.append(f"{candidate.route_symbol} deep scan failed: {exc}")
                    continue
                if result is None:
                    continue
                deep_results.append(result)
        for future in pending:
            candidate, _ = futures[future]
            future.cancel()
            failed_symbols += 1
            warnings.append(f"{candidate.route_symbol} deep scan timed out.")

        ma_result = self._ma_profile_scan_result(len(deep_results) + 1, market_regime)
        if ma_result is not None:
            deep_results.append(ma_result)

        deep_results = sorted(deep_results, key=lambda item: item.score.rank)
        for result in deep_results:
            self._record_deep_result(result)

        summary = ScanSummary(
            candidates_scanned=len(ranked),
            deep_analyzed=len(deep_results),
            warnings=[
                *(
                    [f"Updated {outcome_updates} due signal outcomes."]
                    if outcome_updates
                    else []
                ),
                *(
                    [f"Expired {expired_setups} stale WATCH setups."]
                    if expired_setups
                    else []
                ),
                *warnings,
            ],
            coinalyze_enabled=bool(self.settings.coinalyze_api_key),
            market_regime=market_regime,
            duration_seconds=_elapsed(started_at),
            failed_symbols=failed_symbols,
            worker_count=worker_count,
        )
        return summary, [score for _, score in ranked], deep_results

    def scan_scalps(self) -> tuple[ScanSummary, list[ScalpScanResult]]:
        started_at = time.perf_counter()
        warnings: list[str] = []
        worker_count = max(1, self.settings.scan_workers)
        self._scan_ticker_cache = {}
        self._scan_candle_cache = {}
        self._scan_cache_lock = Lock()
        self._reset_alert_budget()
        try:
            market_regime = self.gatekeeper.market_regime()
            candidates = self._discover_scalp_candidates()
        except (CcxtError, requests.RequestException, ValueError) as exc:
            return (
                ScanSummary(
                    candidates_scanned=0,
                    deep_analyzed=0,
                    warnings=[f"Scalp discovery unavailable: {exc}"],
                    coinalyze_enabled=bool(self.settings.coinalyze_api_key),
                    duration_seconds=_elapsed(started_at),
                    worker_count=worker_count,
                ),
                [],
            )

        oi_by_base = self._coinalyze_rows_for_candidates(candidates, warnings)
        enriched: list[Candidate] = []
        failed_symbols = 0
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._enrich_scalp_candidate, candidate, oi_by_base): candidate
                for candidate in candidates
            }
            done, pending = wait(futures, timeout=self.settings.fetch_timeout_seconds)
            for future in done:
                candidate = futures[future]
                try:
                    enriched_candidate = future.result()
                except (CcxtError, requests.RequestException, ValueError, IndexError) as exc:
                    failed_symbols += 1
                    warnings.append(f"{candidate.route_symbol} scalp prefilter skipped: {exc}")
                    continue
                if enriched_candidate is None:
                    continue
                enriched.append(enriched_candidate)
            for future in pending:
                failed_symbols += 1
                candidate = futures[future]
                future.cancel()
                warnings.append(f"{candidate.route_symbol} scalp prefilter timed out.")

        ranked = sorted(enriched, key=_scalp_universe_score, reverse=True)
        scan_limit = max(1, getattr(self.settings, "scalp_scan_limit", 20))
        results: list[ScalpScanResult] = []
        with ThreadPoolExecutor(max_workers=max(1, min(worker_count, scan_limit))) as executor:
            futures = {
                executor.submit(self._deep_scalp_candidate, candidate, rank, market_regime): candidate
                for rank, candidate in enumerate(ranked[:scan_limit], start=1)
            }
            done, pending = wait(
                futures,
                timeout=max(self.settings.fetch_timeout_seconds, self.settings.fetch_timeout_seconds * scan_limit),
            )
            for future in done:
                candidate = futures[future]
                try:
                    result = future.result()
                except (CcxtError, requests.RequestException, ValueError, IndexError) as exc:
                    failed_symbols += 1
                    warnings.append(f"{candidate.route_symbol} scalp scan failed: {exc}")
                    continue
                if result is not None:
                    results.append(result)
            for future in pending:
                failed_symbols += 1
                candidate = futures[future]
                future.cancel()
                warnings.append(f"{candidate.route_symbol} scalp scan timed out.")

        results = sorted(results, key=lambda item: (item.thesis.signal.value != "enter", item.score.rank))
        summary = ScanSummary(
            candidates_scanned=len(ranked),
            deep_analyzed=len(results),
            warnings=warnings,
            coinalyze_enabled=bool(self.settings.coinalyze_api_key),
            market_regime=market_regime,
            duration_seconds=_elapsed(started_at),
            failed_symbols=failed_symbols,
            worker_count=worker_count,
        )
        return summary, results

    def _discover_scalp_candidates(self) -> list[Candidate]:
        limit = max(
            getattr(self.settings, "scalp_universe_limit", self.settings.prefilter_limit),
            getattr(self.settings, "scalp_scan_limit", 50),
        )
        candidates: list[Candidate] = []
        seen: set[str] = set()
        for exchange_id in self.settings.exchange_ids:
            tickers = (
                self.router.fetch_tickers(exchange_id, universe_limit=limit)
                if isinstance(self.router, (BitunixRouter, CoinbaseRouter))
                else self.router.fetch_tickers(exchange_id)
            )
            for ticker in tickers:
                if not ticker.symbol.endswith(f"/{self.settings.quote_currency}"):
                    continue
                if ticker.symbol in seen:
                    continue
                if ticker.quote_volume is not None and ticker.quote_volume < self.settings.scalp_min_volume_24h_usd:
                    continue
                base, quote = ticker.symbol.split("/")
                route = self.router.first_available_route(base, self.settings.quote_currency)
                if route is None:
                    continue
                route_exchange_id, route_symbol = route
                seen.add(route_symbol)
                candidates.append(
                    Candidate(
                        asset=Asset(symbol=route_symbol, base=base, quote=quote),
                        exchange_id=route_exchange_id,
                        route_symbol=route_symbol,
                        reason="Scalp universe selected by 24h volume and OI/movement ranking.",
                        volume_24h_usd=ticker.quote_volume,
                        trading_link=ExchangeRouter.trading_link(route_exchange_id, route_symbol),
                    )
                )
                if len(candidates) >= limit:
                    return candidates
        if candidates:
            return candidates[:limit]
        return self.discovery.discover(min(limit, self.settings.prefilter_limit))

    def _enrich_scalp_candidate(
        self,
        candidate: Candidate,
        oi_by_base: dict[str, OISnapshot],
    ) -> Candidate | None:
        ticker = self._cached_ticker(candidate.exchange_id, candidate.route_symbol)
        if ticker.quote_volume is not None and ticker.quote_volume < self.settings.scalp_min_volume_24h_usd:
            return None
        oi_row = oi_by_base.get(candidate.asset.base)
        return candidate.model_copy(
            update={
                "volume_24h_usd": ticker.quote_volume,
                "open_interest_change_24h_pct": oi_row.open_interest_change_24h_pct
                if oi_row
                else None,
            }
        )

    def _deep_scalp_candidate(
        self,
        candidate: Candidate,
        rank: int,
        market_regime: MarketRegime,
    ) -> ScalpScanResult | None:
        candles = {
            "15m": self._scalp_candles(candidate, "15m"),
            "5m": self._scalp_candles(candidate, "5m"),
            "3m": self._scalp_candles(candidate, "3m"),
        }
        result = self.scalper.analyze(candidate, candles, rank, market_regime)
        result.thesis.evidence.append(f"Scanned at {result.scanned_at.strftime('%Y-%m-%d %H:%M UTC')}.")
        if result.execution_candle_time is not None:
            age_minutes = max((result.scanned_at - result.execution_candle_time).total_seconds() / 60, 0)
            result.thesis.evidence.append(
                f"Execution candle {result.execution_candle_time.strftime('%Y-%m-%d %H:%M UTC')} "
                f"({age_minutes:.0f} minutes old)."
            )
        if result.latest_candle_time is not None:
            result.thesis.evidence.append(
                f"Latest 3m candle {result.latest_candle_time.strftime('%Y-%m-%d %H:%M UTC')}."
            )
        message = self.alerts.format(candidate, result.thesis, result.validation, result.score)
        alert_sent = self.maybe_send_telegram_alert(
            candidate,
            result.thesis,
            result.validation,
            message,
            result.score,
        )
        return ScalpScanResult(
            candidate=result.candidate,
            score=result.score,
            candles=result.candles,
            thesis=result.thesis,
            validation=result.validation,
            quality=result.quality,
            scanned_at=result.scanned_at,
            execution_candle_time=result.execution_candle_time,
            latest_candle_time=result.latest_candle_time,
            alert_sent=alert_sent,
        )

    def _scalp_candles(
        self,
        candidate: Candidate,
        timeframe: str,
        limit: int | None = None,
    ) -> pd.DataFrame:
        candle_limit = limit or getattr(self.settings, "scalp_candle_limit", 240)
        if timeframe != "3m" or isinstance(self.router, BitunixRouter):
            return self._cached_candles(candidate.exchange_id, candidate.route_symbol, timeframe, candle_limit)
        one_minute = self._cached_candles(candidate.exchange_id, candidate.route_symbol, "1m", candle_limit * 3)
        return _resample_ohlcv(one_minute, "3min").tail(candle_limit).reset_index(drop=True)

    def _score_candidate(
        self,
        candidate: Candidate,
        oi_by_base: dict[str, OISnapshot],
        market_regime: MarketRegime,
    ) -> tuple[Candidate, SetupScore]:
        ticker = self._cached_ticker(candidate.exchange_id, candidate.route_symbol)
        base = candidate.asset.base
        oi_row = oi_by_base.get(base)
        relative_volume = self._relative_volume_for(candidate, [])
        enriched = candidate.model_copy(
            update={
                "volume_24h_usd": ticker.quote_volume,
                "open_interest_change_24h_pct": oi_row.open_interest_change_24h_pct
                if oi_row
                else None,
            }
        )
        return (
            enriched,
            _setup_score(
                enriched,
                price_change_24h_pct=ticker.percentage,
                relative_volume=relative_volume,
                btc_regime_ok=market_regime.longs_allowed,
            ),
        )

    def _deep_scan_candidate(
        self,
        candidate: Candidate,
        score: SetupScore,
        market_regime: MarketRegime,
    ) -> DeepScanResult | None:
        if candidate.volume_24h_usd is not None and candidate.volume_24h_usd < self.settings.min_volume_24h_usd:
            return None
        gatherer = IntelligenceGatherer(
            self.router,
            self.settings.timeframes,
            self.settings.candle_limit,
            self.intelligence.chart_renderer,
            self.intelligence.news_provider,
            candle_fetcher=self._cached_candles,
        )
        pack = gatherer.gather(candidate, market_regime)
        thesis = self.analyzer.analyze(pack)
        atr = next((item.atr for item in pack.indicators if item.timeframe == "15m"), None)
        validation = self.validator.validate(thesis, market_regime, atr)
        message = self.alerts.format(candidate, thesis, validation, score)
        alert_sent = self.maybe_send_telegram_alert(candidate, thesis, validation, message, score)
        return DeepScanResult(
            candidate=candidate,
            score=score,
            pack=pack,
            thesis=thesis,
            validation=validation,
            alert_sent=alert_sent,
        )

    def _ma_profile_scan_result(
        self,
        rank: int,
        market_regime: MarketRegime,
    ) -> DeepScanResult | None:
        if not hasattr(self.router, "first_available_route"):
            return None
        quote_currency = getattr(self.settings, "quote_currency", "USDT")
        route = self.router.first_available_route("ETH", quote_currency)
        if route is None:
            return None
        exchange_id, route_symbol = route
        ticker = self._cached_ticker(exchange_id, route_symbol)
        candidate = Candidate(
            asset=Asset(symbol=route_symbol, base="ETH", quote=quote_currency),
            exchange_id=exchange_id,
            route_symbol=route_symbol,
            reason="validated-ma-short-profile",
            volume_24h_usd=ticker.quote_volume,
        )
        candle_limit = max(self.settings.candle_limit, self.settings.long_ma + self.settings.rsi_period + 30)
        candles = self._cached_candles(exchange_id, route_symbol, "15m", candle_limit)
        frame = prepare_moving_average_backtest_frame(
            candles,
            self.settings.short_ma,
            self.settings.long_ma,
            self.settings.rsi_period,
        )
        if frame.empty:
            return None
        latest = frame.iloc[-1]
        if pd.isna(latest[["short_ma", "long_ma", "rsi", "atr"]]).any():
            return None

        tester = self._moving_average_backtester("short", route_symbol)
        close = float(latest["close"])
        open_price = float(latest["open"])
        high = float(latest["high"])
        low = float(latest["low"])
        atr_value = float(latest["atr"])
        short_ma = float(latest["short_ma"])
        long_ma = float(latest["long_ma"])
        rsi_value = float(latest["rsi"])
        ma_gap = short_ma - long_ma
        candle_body = abs(close - open_price)
        candle_range = max(high - low, 0.0)
        close_position = (close - low) / candle_range if candle_range > 0 else 1.0
        bearish_sequence = tester._has_bearish_sequence(frame, len(frame) - 1)
        checks = {
            "EMA trend is bearish": short_ma < long_ma,
            "RSI is in short trigger band": rsi_value >= 100 - tester.rsi_buy_max
            and rsi_value <= tester.short_rsi_max,
            "MA gap clears ATR threshold": abs(ma_gap) >= atr_value * tester.min_ma_gap_atr,
            "Confirmation body clears ATR threshold": candle_body >= atr_value * tester.min_body_atr,
            "Close is in lower candle range": close_position <= tester.max_short_close_position,
            "Two-candle bearish sequence confirmed": bearish_sequence,
            "Candle closed red": close < open_price,
        }
        triggered = all(checks.values())
        risk = atr_value * tester.stop_atr_multiple
        entry = close * (1 - tester.slippage_rate) if triggered else None
        stop = entry + risk if entry is not None else None
        target = entry - risk * tester.target_r_multiple if entry is not None else None
        evidence = [
            "Validated MA short profile: 100.0% main win rate over 60k candles and 100.0% validation over 100k candles.",
            f"Profile filters: target {tester.target_r_multiple:g}R, body >= {tester.min_body_atr:g} ATR, "
            f"gap >= {tester.min_ma_gap_atr:g} ATR, close position <= {tester.max_short_close_position:g}, "
            f"bearish sequence >= {tester.min_short_bearish_sequence}.",
            f"Latest 15m read: RSI {rsi_value:.1f}, MA gap {abs(ma_gap) / atr_value:.2f} ATR, "
            f"body {candle_body / atr_value:.2f} ATR, close position {close_position:.2f}.",
        ]
        missing = [name for name, passed in checks.items() if not passed]
        validation = ValidationResult(
            approved=triggered,
            reasons=[] if triggered else [f"Waiting for MA confirmation: {', '.join(missing)}."],
        )
        thesis = TradeThesis(
            symbol=route_symbol,
            setup=Setup.MA_SHORT,
            signal=SignalState.ENTER if triggered else SignalState.WAIT,
            direction="short",
            confidence=0.97 if triggered else 0.72,
            entry=entry,
            stop_loss=stop,
            targets=[target] if target is not None else [],
            risk_reward=tester.target_r_multiple if triggered else None,
            evidence=evidence,
        )
        score = SetupScore(
            symbol=route_symbol,
            rank=rank,
            score=97.0 if triggered else 72.0,
            volume_24h_usd=ticker.quote_volume,
            price_change_24h_pct=ticker.percentage,
            oi_change_24h_pct=None,
            relative_volume=self._relative_volume_for(candidate, []),
            btc_regime_ok=market_regime.shorts_allowed,
            prefilter_reasons=["Validated MA short profile is always monitored for ETH/USDT."],
        )
        pack = IntelligencePack(
            candidate=candidate,
            market_regime=market_regime,
            indicators=[
                IndicatorSnapshot(
                    timeframe="15m",
                    close=close,
                    volume=float(latest["volume"]),
                    rsi=rsi_value,
                    macd=None,
                    macd_signal=None,
                    atr=atr_value,
                    relative_volume=None,
                )
            ],
            candles={},
            news_summary="News not evaluated for MA profile scanner row.",
        )
        message = self.alerts.format(candidate, thesis, validation, score)
        alert_sent = self.maybe_send_telegram_alert(candidate, thesis, validation, message, score)
        return DeepScanResult(candidate, score, pack, thesis, validation, alert_sent)

    def _record_deep_result(self, result: DeepScanResult) -> None:
        thesis = result.thesis
        validation = result.validation
        score = result.score
        self.journal.record_thesis(
            symbol=thesis.symbol,
            setup=thesis.setup.value,
            signal=thesis.signal.value,
            direction=thesis.direction,
            confidence=thesis.confidence,
            approved=validation.approved,
            payload_json=thesis.model_dump_json(),
            validation_json=validation.model_dump_json(),
        )
        self.journal.record_setup_score(
            symbol=thesis.symbol,
            setup=thesis.setup.value,
            signal=thesis.signal.value,
            rank=score.rank,
            score=score.score,
            confidence=thesis.confidence,
            approved=validation.approved,
            volume_24h_usd=score.volume_24h_usd,
            oi_change_24h_pct=score.oi_change_24h_pct,
            relative_volume=score.relative_volume,
        )
        self._record_invalidation(result)
        self._record_outcome_seeds(result)
        self._record_active_setup(result)

    def _record_invalidation(self, result: DeepScanResult) -> None:
        thesis = result.thesis
        if thesis.signal != SignalState.REJECT:
            return
        if not hasattr(self.journal, "invalidate_active_setup"):
            return
        direction = "short" if any("short" in item.lower() for item in thesis.evidence) else "long"
        setup = thesis.setup.value if thesis.setup.value != "none" else "tabo"
        reason = thesis.invalidation_reason or "invalidated"
        invalidated = self.journal.invalidate_active_setup(thesis.symbol, setup, direction, reason)
        if invalidated and self.telegram.configured:
            try:
                self.telegram.send(
                    f"Coach Miranda Alert\nINVALIDATED {direction.upper()}\n"
                    f"Symbol: {thesis.symbol}\nReason: {reason}"
                )
            except requests.RequestException:
                return

    def _record_active_setup(self, result: DeepScanResult) -> None:
        if not hasattr(self.journal, "record_active_setup"):
            return
        thesis = result.thesis
        if thesis.signal not in {SignalState.WATCH, SignalState.ENTER}:
            return
        if thesis.direction == "none" or thesis.setup.value == "none":
            return
        status = "confirmed" if thesis.signal == SignalState.ENTER else "watch"
        self.journal.record_active_setup(
            symbol=thesis.symbol,
            setup=thesis.setup.value,
            direction=thesis.direction,
            status=status,
            grade=alert_grade(thesis, result.validation, result.score),
            entry=thesis.entry,
            stop_loss=thesis.stop_loss,
            target=thesis.targets[0] if thesis.targets else None,
            score=result.score.score,
            confidence=thesis.confidence,
            ttl_minutes=getattr(self.settings, "active_setup_ttl_minutes", 240),
        )

    def _record_outcome_seeds(self, result: DeepScanResult) -> None:
        if not hasattr(self.journal, "record_signal_outcome_seed"):
            return
        thesis = result.thesis
        if thesis.signal not in {SignalState.WATCH, SignalState.ENTER}:
            return
        if thesis.direction == "none" or thesis.setup.value == "none":
            return
        if thesis.entry is None or thesis.stop_loss is None or not thesis.targets:
            return
        grade = alert_grade(thesis, result.validation, result.score)
        target = thesis.targets[0]
        for horizon in (1, 4, 24):
            self.journal.record_signal_outcome_seed(
                symbol=thesis.symbol,
                exchange_id=result.candidate.exchange_id,
                route_symbol=result.candidate.route_symbol,
                setup=thesis.setup.value,
                signal=thesis.signal.value,
                direction=thesis.direction,
                grade=grade,
                entry=thesis.entry,
                stop_loss=thesis.stop_loss,
                target=target,
                score=result.score.score,
                confidence=thesis.confidence,
                horizon_hours=horizon,
            )

    def _coinalyze_rows_for_candidates(
        self,
        candidates: list[Candidate],
        warnings: list[str],
    ) -> dict[str, OISnapshot]:
        if not self.settings.coinalyze_api_key:
            # Coinalyze is optional; candidate scoring continues with exchange volume.
            return {}
        bases = sorted({candidate.asset.base for candidate in candidates})
        scanner = OpenInterestScanner(self.router, bases, self.settings.coinalyze_api_key)
        rows = scanner.scan_coinalyze_only(warnings)
        return {row.symbol.split("/")[0]: row for row in rows}

    def _relative_volume_for(self, candidate: Candidate, warnings: list[str]) -> float | None:
        try:
            candles = self._cached_candles(
                candidate.exchange_id,
                candidate.route_symbol,
                "15m",
                self.settings.prefilter_candle_limit,
            )
        except (CcxtError, requests.RequestException, ValueError, IndexError) as exc:
            warnings.append(f"{candidate.route_symbol} relative volume unavailable: {exc}")
            return None
        if len(candles) < 21:
            return None
        latest = float(candles.iloc[-1]["volume"])
        average = float(candles["volume"].tail(21).head(20).mean())
        if average <= 0:
            return None
        return latest / average

    def _cached_ticker(self, exchange_id: str, symbol: str):
        self._ensure_scan_cache()
        cache_key = (exchange_id, symbol)
        with self._scan_cache_lock:
            if cache_key in self._scan_ticker_cache:
                return self._scan_ticker_cache[cache_key]
        ticker = self.router.fetch_ticker(exchange_id, symbol)
        with self._scan_cache_lock:
            self._scan_ticker_cache[cache_key] = ticker
        return ticker

    def _cached_candles(self, exchange_id: str, symbol: str, timeframe: str, limit: int):
        self._ensure_scan_cache()
        cache_key = (exchange_id, symbol, timeframe, limit)
        with self._scan_cache_lock:
            if cache_key in self._scan_candle_cache:
                return self._scan_candle_cache[cache_key].copy()
        candles = self.router.fetch_candles(exchange_id, symbol, timeframe, limit)
        ensure_structurally_valid_candles(
            candles,
            symbol=symbol,
            timeframe=timeframe,
            source=getattr(self.settings, "data_mode", "unknown"),
            min_candles=min(20, limit),
        )
        with self._scan_cache_lock:
            self._scan_candle_cache[cache_key] = candles.copy()
        return candles.copy()

    def _ensure_scan_cache(self) -> None:
        if not hasattr(self, "_scan_ticker_cache"):
            self._scan_ticker_cache = {}
        if not hasattr(self, "_scan_candle_cache"):
            self._scan_candle_cache = {}
        if not hasattr(self, "_scan_cache_lock"):
            self._scan_cache_lock = Lock()

    def _build_discovery(self):
        if self.settings.discovery_mode == "cmc" and self.settings.coinmarketcap_api_key:
            return DiscoveryEngine(
                self.router,
                self.settings.quote_currency,
                CoinMarketCapProvider(self.settings.coinmarketcap_api_key),
                self.settings.discovery_pool_limit,
                self.settings.min_market_cap_usd,
            )
        if self.settings.discovery_mode == "static":
            return DiscoveryEngine(
                self.router,
                self.settings.quote_currency,
                StaticMarketCapProvider(DEFAULT_MAJORS),
                self.settings.discovery_pool_limit,
                self.settings.min_market_cap_usd,
            )
        return ExchangeMomentumDiscoveryEngine(
            self.router,
            self.settings.exchange_ids,
            self.settings.quote_currency,
            self.settings.min_volume_24h_usd,
            DEFAULT_MAJORS,
        )

    def run_once(self) -> str:
        if self.market_data is not None:
            candles = self.market_data.fetch_candles(
                self.settings.symbol,
                self.settings.timeframe,
                self.settings.candle_limit,
            )
        else:
            route = self.router.first_available_route(
                self.settings.symbol.split("/")[0],
                self.settings.quote_currency,
            )
            if route is None:
                raise ValueError(f"No market route found for {self.settings.symbol}.")
            candles = self.router.fetch_candles(
                *route,
                self.settings.timeframe,
                self.settings.candle_limit,
            )
        signal = self.miner.mine(candles)
        risk_decision = self.risk.evaluate(signal.action, daily_pnl=0.0)

        self.journal.record_decision(
            symbol=self.settings.symbol,
            action=signal.action,
            confidence=signal.confidence,
            price=signal.price,
            reason=signal.reason,
            approved=risk_decision.approved,
            risk_reason=risk_decision.reason,
        )

        if not risk_decision.approved:
            return (
                f"Coach Miranda Miner: {signal.action.upper()} skipped for "
                f"{self.settings.symbol}. {signal.reason} Risk: {risk_decision.reason}"
            )

        fill = self.broker.place_order(
            signal.action,
            signal.price,
            risk_decision.notional_usd,
        )
        self.journal.record_fill(
            fill.action,
            fill.quantity,
            fill.price,
            fill.notional_usd,
            fill.message,
        )
        return (
            f"Coach Miranda Miner: {fill.message} {fill.quantity:.8f} "
            f"at {fill.price:.2f} ({fill.notional_usd:.2f} USD). "
            f"Signal reason: {signal.reason}"
        )

    def scan(self) -> list[str]:
        summary, _, results = self.scan_setups()
        if summary.market_regime is None:
            return [
                "Live data is not available right now.",
                f"Data mode: {self.settings.data_mode}",
                f"Reason: {'; '.join(summary.warnings)}",
                "Try DATA_MODE=paprika for hosted free prices, or DATA_MODE=fixture for offline demo mode.",
            ]
        messages: list[str] = []

        if self.settings.data_mode == "fixture":
            messages.append(
                "DEMO DATA MODE: prices are synthetic and repeatable. "
                "Use DATA_MODE=live for updating exchange prices."
            )

        for result in results:
            messages.append(
                self.alerts.format(
                    result.candidate,
                    result.thesis,
                    result.validation,
                    result.score,
                )
            )

        if not messages:
            messages.append("Coach Miranda Miner: no deep-scan candidates found.")
        return messages

    def maybe_send_telegram_alert(
        self,
        candidate: Candidate,
        thesis: TradeThesis,
        validation: ValidationResult,
        message: str,
        score: SetupScore | None = None,
    ) -> bool:
        if not self.telegram.configured:
            return False
        if not self._signal_meets_alert_threshold(thesis.signal):
            return False
        if thesis.direction == "none" or thesis.setup.value == "none":
            return False
        if not self._alert_budget_available(thesis):
            return False
        grade = alert_grade(thesis, validation, score)
        min_alert_grade = getattr(self.settings, "min_alert_grade", "B")
        if grade_rank(grade) < grade_rank(min_alert_grade):
            return False
        has_watch = self._has_active_watch(thesis)
        if thesis.signal == SignalState.ENTER and getattr(self.settings, "require_watch_before_enter", False):
            if not has_watch:
                return False
        cooldown_minutes = (
            getattr(self.settings, "scalp_alert_cooldown_minutes", self.settings.alert_cooldown_minutes)
            if thesis.setup.value == "alma_cci_scalp"
            else self.settings.alert_cooldown_minutes
        )
        if self.journal.alert_sent_recently(
            thesis.symbol,
            thesis.setup.value,
            thesis.signal.value,
            cooldown_minutes,
        ):
            return False
        prefix = "Coach Miranda Alert\n"
        if thesis.setup.value == "alma_cci_scalp":
            prefix = "Coach Miranda SCALP Alert\n"
        if thesis.signal == SignalState.WATCH:
            prefix += "Manual review: setup is forming, not confirmed entry.\n\n"
        if thesis.signal == SignalState.ENTER:
            if has_watch:
                prefix += "Manual review: WATCH setup confirmed into ENTER.\n\n"
            else:
                prefix += "Manual review: direct ENTER, no recent WATCH was stored.\n\n"
        try:
            buttons = telegram_buttons(candidate, getattr(self.settings, "dashboard_url", None))
            try:
                sent = self.telegram.send(prefix + message, buttons=buttons)
            except TypeError:
                sent = self.telegram.send(prefix + message)
        except requests.RequestException:
            return False
        if sent:
            self._consume_alert_budget(thesis)
            self.journal.record_alert(
                thesis.symbol,
                thesis.setup.value,
                thesis.signal.value,
                message,
            )
        return sent

    def _reset_alert_budget(self) -> None:
        self._intraday_alerts_sent_this_scan = 0
        self._scalp_alerts_sent_this_scan = 0

    def _alert_budget_available(self, thesis: TradeThesis) -> bool:
        if thesis.setup.value == "alma_cci_scalp":
            return self._scalp_alerts_sent_this_scan < getattr(self.settings, "max_scalp_alerts_per_scan", 5)
        return self._intraday_alerts_sent_this_scan < getattr(self.settings, "max_alerts_per_scan", 5)

    def _consume_alert_budget(self, thesis: TradeThesis) -> None:
        if thesis.setup.value == "alma_cci_scalp":
            self._scalp_alerts_sent_this_scan += 1
        else:
            self._intraday_alerts_sent_this_scan += 1

    def _has_active_watch(self, thesis: TradeThesis) -> bool:
        if not hasattr(self.journal, "active_watch_exists"):
            return False
        return self.journal.active_watch_exists(
            thesis.symbol,
            thesis.setup.value,
            thesis.direction,
            getattr(self.settings, "active_setup_ttl_minutes", 240),
        )

    def _signal_meets_alert_threshold(self, signal: SignalState) -> bool:
        thresholds = {
            "enter": {SignalState.ENTER},
            "watch": {SignalState.WATCH, SignalState.ENTER},
            "wait": {SignalState.WATCH, SignalState.ENTER},
        }
        return signal in thresholds.get(self.settings.telegram_min_signal, thresholds["watch"])

    def scan_for_alerts(self) -> str:
        messages = self.scan()
        return "\n\n".join(messages)

    def update_signal_outcomes(self, limit: int = 100) -> int:
        if not hasattr(self.journal, "pending_signal_outcomes"):
            return 0
        updated = 0
        for outcome in self.journal.pending_signal_outcomes(limit):
            created_at = datetime.fromisoformat(outcome["created_at"])
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            deadline = created_at + timedelta(hours=int(outcome["horizon_hours"]))
            if datetime.now(timezone.utc) < deadline:
                continue
            try:
                candles = self.router.fetch_candles(
                    outcome["exchange_id"],
                    outcome["route_symbol"],
                    "15m",
                    max(80, int(outcome["horizon_hours"]) * 4 + 20),
                )
            except (CcxtError, requests.RequestException, ValueError, IndexError):
                continue
            resolved = _resolve_outcome(outcome, candles, created_at, deadline)
            if resolved is None:
                continue
            status, return_pct, exit_reason = resolved
            self.journal.update_signal_outcome(
                outcome["id"],
                status,
                return_pct,
                exit_reason,
            )
            updated += 1
        return updated

    def _auto_update_outcomes(self) -> int:
        try:
            return self.update_signal_outcomes(limit=50)
        except (CcxtError, requests.RequestException, ValueError, IndexError, AttributeError):
            return 0

    def _expire_active_setups(self) -> int:
        if not hasattr(self.journal, "expire_active_setups"):
            return 0
        try:
            return self.journal.expire_active_setups()
        except (ValueError, AttributeError):
            return 0

    def high_oi_watchlist(
        self,
        limit: int | None = None,
        all_rows: bool = False,
    ) -> tuple[list[OISnapshot], list[str]]:
        if self.settings.coinalyze_api_key and not all_rows:
            rows, warnings = self._dynamic_coinalyze_watchlist()
            if rows:
                row_limit = self.settings.oi_limit if limit is None else limit
                if all_rows:
                    return rows, warnings
                return rows[:row_limit], warnings
        rows, warnings = self.oi_scanner.scan()
        if all_rows:
            return rows, warnings
        row_limit = self.settings.oi_limit if limit is None else limit
        return rows[:row_limit], warnings

    def _dynamic_coinalyze_watchlist(self) -> tuple[list[OISnapshot], list[str]]:
        warnings: list[str] = []
        try:
            candidates = self.discovery.discover(self.settings.prefilter_limit)
        except (CcxtError, requests.RequestException, ValueError) as exc:
            warnings.append(f"Dynamic OI universe unavailable: {exc}")
            return [], warnings
        bases = sorted({candidate.asset.base for candidate in candidates})
        scanner = OpenInterestScanner(self.router, bases, self.settings.coinalyze_api_key)
        rows = scanner.scan_coinalyze_only(warnings)
        return rows, warnings

    def backtest(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy: str = "miranda",
        side: str = "auto",
        candle_limit: int | None = None,
    ) -> BacktestResult:
        side = self._resolve_backtest_side(strategy, side)
        route_symbol = symbol or self.settings.symbol
        route_timeframe = timeframe or self.settings.timeframe
        base = route_symbol.split("/")[0]
        route = self.router.first_available_route(base, self.settings.quote_currency)
        exchange_id = self.settings.exchange_id
        if route is not None:
            exchange_id, route_symbol = route
        if strategy == "scalp" and route_timeframe == "3m":
            candidate = Candidate(
                asset=Asset(symbol=route_symbol, base=base, quote=self.settings.quote_currency),
                exchange_id=exchange_id,
                route_symbol=route_symbol,
                reason="backtest",
            )
            candles = self._scalp_candles(
                candidate,
                "3m",
                getattr(self.settings, "backtest_scalp_candle_limit", self.settings.scalp_candle_limit),
            )
        else:
            candles = self.router.fetch_candles(
                exchange_id,
                route_symbol,
                route_timeframe,
                candle_limit or self.settings.backtest_candle_limit,
            )
        self._record_candle_sample(route_symbol, route_timeframe, candles, source=self.settings.data_mode)
        if strategy == "scalp":
            tester = AlmaCciScalpBacktester(
                self._strategy_backtest_config(
                    side,
                    max_hold_bars=12,
                    min_risk_pct=self.settings.backtest_scalp_min_risk_pct,
                ),
            )
            return tester.run(route_symbol, route_timeframe, candles)
        if strategy == "miranda":
            tester = MirandaStrategyBacktester(
                self._strategy_backtest_config(side),
            )
            return tester.run(route_symbol, route_timeframe, candles)
        return self._moving_average_backtester(side, route_symbol).run(route_symbol, route_timeframe, candles)

    def walk_forward_backtest(
        self,
        symbol: str | None = None,
        timeframe: str | None = None,
        strategy: str = "miranda",
        side: str = "auto",
    ) -> dict:
        side = self._resolve_backtest_side(strategy, side)
        route_symbol = symbol or self.settings.symbol
        route_timeframe = timeframe or self.settings.timeframe
        base = route_symbol.split("/")[0]
        route = self.router.first_available_route(base, self.settings.quote_currency)
        exchange_id = self.settings.exchange_id
        if route is not None:
            exchange_id, route_symbol = route
        candles = self.router.fetch_candles(
            exchange_id,
            route_symbol,
            route_timeframe,
            self.settings.backtest_candle_limit,
        )
        self._record_candle_sample(route_symbol, route_timeframe, candles, source=self.settings.data_mode)
        split = max(80, int(len(candles) * 0.6))
        if split >= len(candles) - 20:
            split = max(1, len(candles) // 2)
        train = self._run_backtest_on_frame(route_symbol, route_timeframe, strategy, side, candles.iloc[:split])
        test = self._run_backtest_on_frame(route_symbol, route_timeframe, strategy, side, candles.iloc[split:])
        return {
            "symbol": route_symbol,
            "timeframe": route_timeframe,
            "train": train,
            "test": test,
            "train_expectancy_pct": train.expectancy_pct,
            "test_expectancy_pct": test.expectancy_pct,
            "degradation_pct": test.expectancy_pct - train.expectancy_pct,
        }

    def optimize_backtest(
        self,
        symbol: str | None = None,
        timeframe: str = "15m",
        strategy: str = "miranda",
        side: str = "auto",
        min_trades: int = 30,
        limit: int = 10,
        max_configs: int = 100,
    ) -> list[dict]:
        side = self._resolve_backtest_side(strategy, side)
        route_symbol = symbol or self.settings.symbol
        base = route_symbol.split("/")[0]
        route = self.router.first_available_route(base, self.settings.quote_currency)
        exchange_id = self.settings.exchange_id
        if route is not None:
            exchange_id, route_symbol = route
        validation_candles = None
        validation_limit = (
            self.settings.backtest_ma_validation_candle_limit
            if strategy == "ma"
            else 0
        )
        if strategy == "scalp" and timeframe == "3m":
            candidate = Candidate(
                asset=Asset(symbol=route_symbol, base=base, quote=self.settings.quote_currency),
                exchange_id=exchange_id,
                route_symbol=route_symbol,
                reason="backtest-optimize",
            )
            candles = self._scalp_candles(
                candidate,
                "3m",
                getattr(self.settings, "backtest_scalp_candle_limit", self.settings.scalp_candle_limit),
            )
        else:
            candles = self.router.fetch_candles(
                exchange_id,
                route_symbol,
                timeframe,
                self.settings.backtest_candle_limit,
            )
            if validation_limit > self.settings.backtest_candle_limit:
                validation_candles = self.router.fetch_candles(
                    exchange_id,
                    route_symbol,
                    timeframe,
                    validation_limit,
                )
        if strategy == "ma":
            candles = prepare_moving_average_backtest_frame(
                candles,
                self.settings.short_ma,
                self.settings.long_ma,
                self.settings.rsi_period,
            )
            if validation_candles is not None:
                validation_candles = prepare_moving_average_backtest_frame(
                    validation_candles,
                    self.settings.short_ma,
                    self.settings.long_ma,
                    self.settings.rsi_period,
                )
        elif strategy == "scalp":
            candles = prepare_scalp_backtest_frame(candles)
        else:
            candles = prepare_miranda_backtest_frame(candles)
        rows: list[dict] = []
        for label, result, tester in self._optimization_results(
            route_symbol,
            timeframe,
            strategy,
            side,
            candles,
            max_configs,
        ):
            if result.trades < min_trades:
                continue
            if strategy == "ma" and result.win_rate < self.settings.backtest_ma_min_batch_win_rate:
                continue
            validation_result = None
            if validation_candles is not None:
                validation_result = tester.run(route_symbol, timeframe, validation_candles)
                if validation_result.trades < min_trades:
                    continue
                if (
                    strategy == "ma"
                    and validation_result.win_rate
                    < self.settings.backtest_ma_min_validation_win_rate
                ):
                    continue
            win_rate_floor = (
                min(result.win_rate, validation_result.win_rate)
                if validation_result is not None
                else result.win_rate
            )
            rows.append(
                {
                    "label": label,
                    "symbol": result.symbol,
                    "timeframe": result.timeframe,
                    "trades": result.trades,
                    "win_rate": result.win_rate,
                    "return_pct": result.total_return_pct,
                    "drawdown_pct": result.max_drawdown_pct,
                    "profit_factor": result.profit_factor,
                    "expectancy_pct": result.expectancy_pct,
                    "long_trades": result.long_trades,
                    "short_trades": result.short_trades,
                    "best_setup": _best_setup_name(result.setup_stats),
                    "win_rate_floor": win_rate_floor,
                }
            )
            if validation_result is not None:
                rows[-1].update(
                    {
                        "validation_trades": validation_result.trades,
                        "validation_win_rate": validation_result.win_rate,
                        "validation_win_rate_delta": validation_result.win_rate - result.win_rate,
                        "validation_expectancy_pct": validation_result.expectancy_pct,
                    }
                )
        return sorted(
            rows,
            key=lambda row: (
                row["win_rate_floor"],
                row.get("validation_win_rate", row["win_rate"]),
                row["win_rate"],
                row["expectancy_pct"],
                row["profit_factor"],
                row["trades"],
            ),
            reverse=True,
        )[:limit]

    def _optimization_results(
        self,
        symbol: str,
        timeframe: str,
        strategy: str,
        side: str,
        candles: pd.DataFrame,
        max_configs: int | None = None,
    ):
        tested = 0

        def can_test_next() -> bool:
            nonlocal tested
            if max_configs is not None and tested >= max_configs:
                return False
            tested += 1
            return True

        if strategy == "ma":
            overrides = self._ma_symbol_overrides(symbol)
            rsi_values = (
                overrides.get("rsi_buy_max", self.settings.backtest_ma_rsi_buy_max),
                55,
                50,
                48,
                46,
                45,
            )
            for rsi_max in dict.fromkeys(rsi_values):
                target_values = (
                    overrides.get("target_r", self.settings.backtest_ma_target_r_multiple),
                    0.12,
                    0.14,
                    0.16,
                    0.18,
                    0.2,
                    0.22,
                    0.3,
                    0.75,
                )
                stop_values = (
                    overrides.get("stop_atr", self.settings.backtest_ma_stop_atr_multiple),
                    1.0,
                    1.25,
                    1.5,
                    2.0,
                )
                body_values = (
                    overrides.get("min_body_atr", self.settings.backtest_ma_min_body_atr),
                    0.15,
                    0.2,
                    0.25,
                    0.3,
                    0.4,
                )
                gap_values = (
                    overrides.get("min_gap_atr", self.settings.backtest_ma_min_gap_atr),
                    0.6,
                    0.7,
                    0.75,
                    0.8,
                    0.9,
                    1.0,
                )
                risk_values = (
                    overrides.get("min_risk_pct", self.settings.backtest_ma_min_risk_pct),
                    0.25,
                    0.35,
                    0.5,
                )
                short_rsi_values = (
                    overrides.get("short_rsi_max", 100.0),
                    65,
                    70,
                    75,
                    80,
                )
                close_position_values = (
                    overrides.get("max_short_close_position", 1.0),
                    0.25,
                    0.3,
                    0.35,
                    0.4,
                    0.45,
                    0.5,
                )
                bearish_sequence_values = (
                    int(overrides.get("min_short_bearish_sequence", 1)),
                    1,
                    2,
                    3,
                )
                for stop_atr in dict.fromkeys(stop_values):
                    for body_atr in dict.fromkeys(body_values):
                        for gap_atr in dict.fromkeys(gap_values):
                            for risk_pct in dict.fromkeys(risk_values):
                                for short_rsi_max in dict.fromkeys(short_rsi_values):
                                    for close_position in dict.fromkeys(close_position_values):
                                        for bearish_sequence in dict.fromkeys(bearish_sequence_values):
                                            for target_r in dict.fromkeys(target_values):
                                                if not can_test_next():
                                                    return
                                                tester = MovingAverageBacktester(
                                                    self.settings.short_ma,
                                                    self.settings.long_ma,
                                                    self.settings.rsi_period,
                                                    rsi_max,
                                                    self.settings.backtest_fee_bps,
                                                    self.settings.backtest_slippage_bps,
                                                    stop_atr,
                                                    target_r,
                                                    self.settings.backtest_breakeven_trigger_r,
                                                    self.settings.backtest_partial_target_r,
                                                    self.settings.backtest_partial_exit_fraction,
                                                    body_atr,
                                                    gap_atr,
                                                    risk_pct,
                                                    self.settings.backtest_min_net_target_pct,
                                                    short_rsi_max,
                                                    close_position,
                                                    bearish_sequence,
                                                    allow_longs=side in {"both", "long"},
                                                    allow_shorts=side in {"both", "short"},
                                                )
                                                label = (
                                                    f"side={side} rsi<={rsi_max:g} shortRsi<={short_rsi_max:g} "
                                                    f"target={target_r:g} stopATR={stop_atr:g} bodyATR={body_atr:g} "
                                                    f"gapATR={gap_atr:g} riskPct={risk_pct:g} "
                                                    f"closePos<={close_position:g} bearSeq={bearish_sequence}"
                                                )
                                                yield label, tester.run(symbol, timeframe, candles), tester
            return

        setup_sets = (
            ("apex_squeeze", "bounce", "tabo"),
            ("bounce", "tabo"),
            ("apex_squeeze", "tabo"),
            ("apex_squeeze", "bounce"),
            ("apex_squeeze",),
            ("bounce",),
            ("tabo",),
        )
        if strategy == "scalp":
            setup_sets = (("alma_cci_scalp",),)
        base_config = self._strategy_backtest_config(
            side,
            max_hold_bars=12 if strategy == "scalp" else 24,
            min_risk_pct=(
                self.settings.backtest_scalp_min_risk_pct
                if strategy == "scalp"
                else self.settings.backtest_min_risk_pct
            ),
        )
        for target_r in (1.0, 0.75, 1.25):
            for stop_atr in (1.5, 1.0, 2.0):
                for rel_vol in (1.2, 1.5, 2.0):
                    for risk_pct in (
                        (0.08, 0.04, 0.12)
                        if strategy == "scalp"
                        else (0.25, 0.35, 0.2, 0.5)
                    ):
                        for score in (3, 4, 2, 5):
                            for body_atr in (0.15, 0.25, 0.4):
                                for ema_gap_atr in (0.1, 0.2, 0.35):
                                    for setups in setup_sets:
                                        if not can_test_next():
                                            return
                                        config = replace(
                                            base_config,
                                            stop_atr_multiple=stop_atr,
                                            target_r_multiple=target_r,
                                            min_risk_reward=target_r,
                                            min_relative_volume=rel_vol,
                                            min_risk_pct=risk_pct,
                                            min_confluence_score=score,
                                            min_body_atr=body_atr,
                                            min_ema_gap_atr=ema_gap_atr,
                                            allowed_setups=setups,
                                        )
                                        tester = (
                                            AlmaCciScalpBacktester(config)
                                            if strategy == "scalp"
                                            else MirandaStrategyBacktester(config)
                                        )
                                        label = (
                                            f"target={target_r:g} stopATR={stop_atr:g} rv>={rel_vol:g} "
                                            f"riskPct={risk_pct:g} score={score} bodyATR={body_atr:g} "
                                            f"emaGapATR={ema_gap_atr:g} setups={'+'.join(setups)}"
                                        )
                                        yield label, tester.run(symbol, timeframe, candles), tester

    def _run_backtest_on_frame(
        self,
        symbol: str,
        timeframe: str,
        strategy: str,
        side: str,
        candles: pd.DataFrame,
    ) -> BacktestResult:
        if strategy == "scalp":
            return AlmaCciScalpBacktester(
                self._strategy_backtest_config(
                    side,
                    max_hold_bars=12,
                    min_risk_pct=self.settings.backtest_scalp_min_risk_pct,
                ),
            ).run(symbol, timeframe, candles)
        if strategy == "miranda":
            return MirandaStrategyBacktester(
                self._strategy_backtest_config(side),
            ).run(symbol, timeframe, candles)
        return self._moving_average_backtester(side, symbol).run(symbol, timeframe, candles)

    def _moving_average_backtester(self, side: str, symbol: str | None = None) -> MovingAverageBacktester:
        overrides = self._ma_symbol_overrides(symbol)
        rsi_buy_max = overrides.get("rsi_buy_max", self.settings.backtest_ma_rsi_buy_max)
        stop_atr = overrides.get("stop_atr", self.settings.backtest_ma_stop_atr_multiple)
        target_r = overrides.get("target_r", self.settings.backtest_ma_target_r_multiple)
        min_body_atr = overrides.get("min_body_atr", self.settings.backtest_ma_min_body_atr)
        min_gap_atr = overrides.get("min_gap_atr", self.settings.backtest_ma_min_gap_atr)
        min_risk_pct = overrides.get("min_risk_pct", self.settings.backtest_ma_min_risk_pct)
        short_rsi_max = overrides.get("short_rsi_max", 100.0)
        max_short_close_position = overrides.get("max_short_close_position", 1.0)
        min_short_bearish_sequence = int(overrides.get("min_short_bearish_sequence", 1))
        return MovingAverageBacktester(
            self.settings.short_ma,
            self.settings.long_ma,
            self.settings.rsi_period,
            rsi_buy_max,
            self.settings.backtest_fee_bps,
            self.settings.backtest_slippage_bps,
            stop_atr,
            target_r,
            self.settings.backtest_breakeven_trigger_r,
            self.settings.backtest_partial_target_r,
            self.settings.backtest_partial_exit_fraction,
            min_body_atr,
            min_gap_atr,
            min_risk_pct,
            self.settings.backtest_min_net_target_pct,
            short_rsi_max,
            max_short_close_position,
            min_short_bearish_sequence,
            allow_longs=side in {"both", "long"},
            allow_shorts=side in {"both", "short"},
        )

    def _ma_symbol_overrides(self, symbol: str | None) -> dict[str, float]:
        if not symbol:
            return {}
        base = symbol.split("/")[0].upper()
        return self.settings.backtest_ma_symbol_overrides.get(base, {})

    def _resolve_backtest_side(self, strategy: str, side: str) -> str:
        if side != "auto":
            return side
        if strategy == "ma":
            return self.settings.backtest_ma_side
        return "both"

    def _strategy_backtest_config(
        self,
        side: str,
        max_hold_bars: int = 24,
        min_risk_pct: float | None = None,
    ) -> StrategyBacktestConfig:
        return StrategyBacktestConfig(
            fee_bps=self.settings.backtest_fee_bps,
            slippage_bps=self.settings.backtest_slippage_bps,
            stop_atr_multiple=self.settings.backtest_stop_atr_multiple,
            target_r_multiple=self.settings.backtest_target_r_multiple,
            allow_longs=side in {"both", "long"},
            allow_shorts=side in {"both", "short"},
            min_relative_volume=self.settings.backtest_min_relative_volume,
            min_risk_reward=self.settings.backtest_min_risk_reward,
            max_hold_bars=max_hold_bars,
            breakeven_trigger_r=self.settings.backtest_breakeven_trigger_r,
            partial_target_r=self.settings.backtest_partial_target_r,
            partial_exit_fraction=self.settings.backtest_partial_exit_fraction,
            min_body_atr=self.settings.backtest_min_body_atr,
            min_ema_gap_atr=self.settings.backtest_min_ema_gap_atr,
            min_macd_hist_atr=self.settings.backtest_min_macd_hist_atr,
            min_risk_pct=self.settings.backtest_min_risk_pct
            if min_risk_pct is None
            else min_risk_pct,
            min_net_target_pct=self.settings.backtest_min_net_target_pct,
            min_confluence_score=self.settings.backtest_min_confluence_score,
            allowed_setups=tuple(self.settings.backtest_allowed_setups),
        )

    def _record_candle_sample(
        self,
        symbol: str,
        timeframe: str,
        candles: pd.DataFrame,
        source: str,
    ) -> None:
        if not hasattr(self.journal, "record_candle_sample"):
            return
        try:
            self.journal.record_candle_sample(symbol, timeframe, candles, source)
        except (ValueError, TypeError, AttributeError):
            return

    def batch_backtest(
        self,
        limit: int | None = None,
        timeframe: str = "15m",
        strategy: str = "miranda",
        side: str = "auto",
    ) -> list[dict]:
        side = self._resolve_backtest_side(strategy, side)
        row_limit = limit or self.settings.backtest_limit
        try:
            candidates = self.discovery.discover(row_limit)
        except (CcxtError, requests.RequestException, ValueError):
            candidates = []
        if strategy == "ma":
            preferred = {base.upper() for base in self.settings.backtest_ma_preferred_bases}
            excluded = {base.upper() for base in self.settings.backtest_ma_excluded_bases}
            candidates = [
                candidate
                for candidate in candidates
                if not preferred or candidate.asset.base.upper() in preferred
            ]
            candidates = [
                candidate
                for candidate in candidates
                if candidate.asset.base.upper() not in excluded
            ]
        rows: list[dict] = []
        worker_count = max(1, min(self.settings.scan_workers, row_limit))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    self.backtest,
                    candidate.route_symbol,
                    timeframe,
                    strategy,
                    side,
                ): candidate
                for candidate in candidates[:row_limit]
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                except (CcxtError, requests.RequestException, ValueError, IndexError):
                    continue
                rows.append(
                    {
                        "symbol": result.symbol,
                        "timeframe": result.timeframe,
                        "trades": result.trades,
                        "win_rate": result.win_rate,
                        "return_pct": result.total_return_pct,
                        "drawdown_pct": result.max_drawdown_pct,
                        "profit_factor": result.profit_factor,
                        "expectancy_pct": result.expectancy_pct,
                        "long_trades": result.long_trades,
                        "short_trades": result.short_trades,
                        "best_setup": _best_setup_name(result.setup_stats),
                    }
                )
        if strategy == "ma":
            rows = [
                row
                for row in rows
                if row["win_rate"] >= self.settings.backtest_ma_min_batch_win_rate
                and row["trades"] >= MIN_VALIDATION_TRADES
            ]
            validation_limit = self.settings.backtest_ma_validation_candle_limit
            if validation_limit > self.settings.backtest_candle_limit:
                validated_rows = []
                for row in rows:
                    try:
                        validation = self.backtest(
                            row["symbol"],
                            timeframe,
                            strategy,
                            side,
                            candle_limit=validation_limit,
                        )
                    except (CcxtError, requests.RequestException, ValueError, IndexError):
                        continue
                    if validation.trades < MIN_VALIDATION_TRADES:
                        continue
                    if validation.win_rate < self.settings.backtest_ma_min_validation_win_rate:
                        continue
                    row = {
                        **row,
                        "validation_trades": validation.trades,
                        "validation_win_rate": validation.win_rate,
                        "validation_win_rate_delta": validation.win_rate - row["win_rate"],
                        "validation_expectancy_pct": validation.expectancy_pct,
                    }
                    validated_rows.append(row)
                rows = validated_rows
            return sorted(
                rows,
                key=lambda row: (
                    row.get("validation_win_rate", row["win_rate"]),
                    row["win_rate"],
                    row["trades"],
                    row["expectancy_pct"],
                ),
                reverse=True,
            )
        return sorted(
            rows,
            key=lambda row: (row["expectancy_pct"], row["profit_factor"], row["trades"]),
            reverse=True,
        )

    def price(self, symbol: str | None = None) -> str:
        route_symbol = symbol or self.settings.symbol
        route = self.router.first_available_route(
            route_symbol.split("/")[0],
            self.settings.quote_currency,
        )
        if route is None:
            return f"No route available for {route_symbol}."
        exchange_id, routed_symbol = route
        try:
            ticker = self.router.fetch_ticker(exchange_id, routed_symbol)
        except (CcxtError, requests.RequestException, ValueError) as exc:
            return (
                f"Could not fetch live price for {routed_symbol} using "
                f"{self.settings.data_mode}: {exc}"
            )
        return (
            f"{routed_symbol} via {self.settings.data_mode}: "
            f"{ticker.last:,.6g} | 24h: {(ticker.percentage or 0):.2f}% | "
            f"volume: {(ticker.quote_volume or 0):,.0f}"
        )

    def doctor(self) -> str:
        free_core = (
            self.settings.discovery_mode == "exchange"
            and self.settings.analyzer_mode == "rule"
        )
        lines = [
            "Coach Miranda Miner Doctor",
            f"Free core: {'yes' if free_core else 'mixed'}",
            f"Data mode: {self.settings.data_mode}",
            f"Discovery mode: {self.settings.discovery_mode}",
            f"Analyzer mode: {self.settings.analyzer_mode}",
            f"Exchange IDs: {', '.join(self.settings.exchange_ids)}",
            f"Telegram configured: {'yes' if self.telegram.configured else 'no'}",
            f"Charts enabled: {'yes' if self.settings.render_charts else 'no'}",
            f"Journal DB: {self.settings.journal_db}",
        ]
        if self.settings.data_mode == "fixture":
            lines.append("Warning: fixture mode uses demo prices; numbers will not update like live markets.")
        if self.settings.data_mode == "live":
            lines.append("Direct exchange mode can fail on hosted servers if the exchange blocks that region.")
        if self.settings.data_mode == "paprika":
            lines.append("Paprika mode uses live prices with local intraday candle scaffolding.")
        if self.settings.data_mode == "coinbase":
            lines.append("Coinbase mode uses real public OHLCV candles without API keys.")
        if self.settings.analyzer_mode == "openai":
            lines.append("OpenAI analyzer is optional and requires OPENAI_API_KEY.")
        return "\n".join(lines)


def _setup_score(
    candidate: Candidate,
    price_change_24h_pct: float | None,
    relative_volume: float | None,
    btc_regime_ok: bool,
) -> SetupScore:
    volume = candidate.volume_24h_usd or 0.0
    oi_change = candidate.open_interest_change_24h_pct
    reasons: list[str] = []

    volume_score = min(max(math.log10(volume) - 6.0, 0.0) * 12.0, 36.0) if volume > 0 else 0.0
    change_score = min(abs(price_change_24h_pct or 0.0) * 1.6, 18.0)
    relvol_score = min(max((relative_volume or 0.0) - 1.0, 0.0) * 18.0, 24.0)
    oi_score = min(abs(oi_change or 0.0) * 1.2, 28.0)
    regime_score = 6.0 if btc_regime_ok else -25.0
    score = max(0.0, volume_score + change_score + relvol_score + oi_score + regime_score)

    if volume:
        reasons.append(f"24h volume supports liquidity at ${volume:,.0f}.")
    if price_change_24h_pct is not None:
        reasons.append(f"24h price move is {price_change_24h_pct:.2f}%.")
    if relative_volume is not None:
        reasons.append(f"15m relative volume is {relative_volume:.2f}x.")
    if oi_change is not None:
        reasons.append(f"Coinalyze 24h OI change is {oi_change:.2f}%.")
    if btc_regime_ok:
        reasons.append("BTC regime allows long setups.")
    else:
        reasons.append("BTC regime blocks aggressive long setups.")

    return SetupScore(
        symbol=candidate.route_symbol,
        rank=0,
        score=round(score, 2),
        volume_24h_usd=candidate.volume_24h_usd,
        price_change_24h_pct=price_change_24h_pct,
        oi_change_24h_pct=oi_change,
        relative_volume=relative_volume,
        btc_regime_ok=btc_regime_ok,
        prefilter_reasons=reasons,
    )


def _scalp_universe_score(candidate: Candidate) -> float:
    volume = candidate.volume_24h_usd or 0.0
    oi_change = abs(candidate.open_interest_change_24h_pct or 0.0)
    volume_score = min(max(math.log10(volume) - 6.0, 0.0) * 18.0, 54.0) if volume > 0 else 0.0
    oi_score = min(oi_change * 2.0, 80.0)
    return volume_score + oi_score


def _elapsed(started_at: float) -> float:
    return round(time.perf_counter() - started_at, 2)


def _resample_ohlcv(candles: pd.DataFrame, rule: str) -> pd.DataFrame:
    frame = candles.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    resampled = (
        frame.set_index("timestamp")
        .resample(rule)
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
        .reset_index()
    )
    return resampled[["timestamp", "open", "high", "low", "close", "volume"]]


def _best_setup_name(setup_stats: dict[str, dict]) -> str | None:
    if not setup_stats:
        return None
    setup, _ = max(
        setup_stats.items(),
        key=lambda item: (
            item[1].get("expectancy_pct", 0.0),
            item[1].get("trades", 0),
        ),
    )
    return setup


def _resolve_outcome(
    outcome: dict,
    candles: pd.DataFrame,
    created_at: datetime,
    deadline: datetime,
) -> tuple[str, float, str] | None:
    if candles.empty or "timestamp" not in candles:
        return None
    frame = candles.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    window = frame[(frame["timestamp"] >= created_at) & (frame["timestamp"] <= deadline)]
    if window.empty:
        window = frame.tail(1)

    entry = float(outcome["entry"])
    stop = float(outcome["stop_loss"])
    target = float(outcome["target"])
    direction = outcome["direction"]

    for row in window.itertuples(index=False):
        high = float(row.high)
        low = float(row.low)
        if direction == "long":
            if low <= stop:
                return "stop", ((stop - entry) / entry) * 100, "stop"
            if high >= target:
                return "target", ((target - entry) / entry) * 100, "target"
        if direction == "short":
            if high >= stop:
                return "stop", ((entry - stop) / entry) * 100, "stop"
            if low <= target:
                return "target", ((entry - target) / entry) * 100, "target"

    close = float(window.iloc[-1]["close"])
    if direction == "short":
        return "time", ((entry - close) / entry) * 100, "time"
    return "time", ((close - entry) / entry) * 100, "time"
