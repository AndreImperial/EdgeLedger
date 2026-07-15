from __future__ import annotations

from .exchanges import ExchangeRouter
from .indicators import moving_average
from .models import Candidate, MarketRegime


class Gatekeeper:
    def __init__(
        self,
        router: ExchangeRouter,
        btc_kill_switch_drop_pct: float,
        min_volume_24h_usd: float,
        quote_currency: str = "USDT",
    ) -> None:
        self.router = router
        self.btc_kill_switch_drop_pct = abs(btc_kill_switch_drop_pct)
        self.min_volume_24h_usd = min_volume_24h_usd
        self.quote_currency = quote_currency

    def market_regime(self) -> MarketRegime:
        route = self._route("BTC")
        if route is None:
            raise ValueError("No BTC route available for market regime check.")
        exchange_id, symbol = route
        ticker = self.router.fetch_ticker(exchange_id, symbol)
        change = float(ticker.percentage or 0.0)
        btc_trend = self._trend_state(exchange_id, symbol)
        eth_change = None
        eth_trend = 0.0
        eth_route = self._route("ETH")
        if eth_route is not None:
            eth_exchange, eth_symbol = eth_route
            try:
                eth_ticker = self.router.fetch_ticker(eth_exchange, eth_symbol)
                eth_change = float(eth_ticker.percentage or 0.0)
                eth_trend = self._trend_state(eth_exchange, eth_symbol)
            except Exception:
                eth_change = None
                eth_trend = 0.0

        trend_score = round((btc_trend * 0.7) + (eth_trend * 0.3), 2)
        risk_mode = "risk_on" if trend_score >= 0.5 else "risk_off" if trend_score <= -0.5 else "neutral"
        shorts_allowed = trend_score <= 0.75
        if change <= -self.btc_kill_switch_drop_pct:
            return MarketRegime(
                btc_change_24h_pct=change,
                longs_allowed=False,
                shorts_allowed=True,
                eth_change_24h_pct=eth_change,
                trend_score=trend_score,
                risk_mode="risk_off",
                reason=(
                    f"BTC is down {change:.2f}% in 24h; long analysis halted. "
                    f"Trend score {trend_score:.2f}."
                ),
            )
        longs_allowed = trend_score >= -0.25
        reason = (
            f"BTC 24h {change:.2f}%, ETH 24h "
            f"{eth_change:.2f}%." if eth_change is not None else f"BTC 24h {change:.2f}%."
        )
        return MarketRegime(
            btc_change_24h_pct=change,
            longs_allowed=longs_allowed,
            shorts_allowed=shorts_allowed,
            eth_change_24h_pct=eth_change,
            trend_score=trend_score,
            risk_mode=risk_mode,
            reason=f"{reason} Market mode {risk_mode}; trend score {trend_score:.2f}.",
        )

    def _route(self, base: str) -> tuple[str, str] | None:
        route = self.router.first_available_route(base, self.quote_currency)
        if route is None and self.quote_currency != "USD":
            route = self.router.first_available_route(base, "USD")
        if route is None and self.quote_currency != "USDT":
            route = self.router.first_available_route(base, "USDT")
        return route

    def _trend_state(self, exchange_id: str, symbol: str) -> float:
        try:
            candles = self.router.fetch_candles(exchange_id, symbol, "1h", 80)
        except Exception:
            return 0.0
        if len(candles) < 55:
            return 0.0
        close = candles["close"]
        ema_20 = moving_average(close, 20).iloc[-1]
        ema_50 = moving_average(close, 50).iloc[-1]
        last = float(close.iloc[-1])
        if ema_20 > ema_50 and last > ema_20:
            return 1.0
        if ema_20 < ema_50 and last < ema_20:
            return -1.0
        return 0.0

    def filter_candidate(self, candidate: Candidate) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        ticker = self.router.fetch_ticker(candidate.exchange_id, candidate.route_symbol)
        if ticker.quote_volume is not None and ticker.quote_volume < self.min_volume_24h_usd:
            reasons.append(
                f"24h quote volume {ticker.quote_volume:.0f} below "
                f"{self.min_volume_24h_usd:.0f}."
            )
        return len(reasons) == 0, reasons
