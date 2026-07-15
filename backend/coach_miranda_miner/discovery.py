from __future__ import annotations

from .exchanges import ExchangeRouter
from .models import Asset, Candidate
from .market_cap import MarketCapProvider, StaticMarketCapProvider


DEFAULT_MAJORS = [
    "BTC",
    "ETH",
    "SOL",
    "BNB",
    "XRP",
    "DOGE",
    "ADA",
    "AVAX",
    "LINK",
    "DOT",
]


class DiscoveryEngine:
    def __init__(
        self,
        router: ExchangeRouter,
        quote_currency: str,
        market_cap_provider: MarketCapProvider | None = None,
        discovery_pool_limit: int = 100,
        min_market_cap_usd: float = 100_000_000,
        majors: list[str] | None = None,
    ) -> None:
        self.router = router
        self.quote_currency = quote_currency
        self.majors = DEFAULT_MAJORS if majors is None else majors
        self.market_cap_provider = market_cap_provider or StaticMarketCapProvider(self.majors)
        self.discovery_pool_limit = discovery_pool_limit
        self.min_market_cap_usd = min_market_cap_usd

    def discover(self, limit: int) -> list[Candidate]:
        candidates: list[Candidate] = []
        assets = self.market_cap_provider.top_assets(
            self.discovery_pool_limit,
            self.min_market_cap_usd,
        )
        for asset in assets:
            if len(candidates) >= limit:
                break
            base = asset.base
            route = self.router.first_available_route(base, self.quote_currency)
            if route is None:
                continue
            exchange_id, route_symbol = route
            routed_asset = Asset(
                symbol=route_symbol,
                base=base,
                quote=self.quote_currency,
                market_cap_usd=asset.market_cap_usd,
                is_major=asset.is_major,
            )
            candidates.append(
                Candidate(
                    asset=routed_asset,
                    exchange_id=exchange_id,
                    route_symbol=route_symbol,
                    reason="Major asset route selected.",
                    trading_link=ExchangeRouter.trading_link(exchange_id, route_symbol),
                )
            )
        return candidates


class ExchangeMomentumDiscoveryEngine:
    def __init__(
        self,
        router: ExchangeRouter,
        exchange_ids: list[str],
        quote_currency: str,
        min_volume_24h_usd: float,
        majors: list[str] | None = None,
    ) -> None:
        self.router = router
        self.exchange_ids = exchange_ids
        self.quote_currency = quote_currency
        self.min_volume_24h_usd = min_volume_24h_usd
        self.majors = DEFAULT_MAJORS if majors is None else majors

    def discover(self, limit: int) -> list[Candidate]:
        seen: set[str] = set()
        candidates: list[Candidate] = []

        for base in self.majors:
            route = self.router.first_available_route(base, self.quote_currency)
            if route is None:
                continue
            exchange_id, route_symbol = route
            ticker = self.router.fetch_ticker(exchange_id, route_symbol)
            seen.add(route_symbol)
            candidates.append(self._candidate(route_symbol, exchange_id, ticker, "Free major route."))

        movers = []
        mover_symbols: set[str] = set()
        for exchange_id in self.exchange_ids:
            for ticker in self.router.fetch_tickers(exchange_id):
                if ticker.symbol in seen or ticker.symbol in mover_symbols:
                    continue
                if not ticker.symbol.endswith(f"/{self.quote_currency}"):
                    continue
                if ticker.quote_volume is None or ticker.quote_volume < self.min_volume_24h_usd:
                    continue
                mover_symbols.add(ticker.symbol)
                movers.append((abs(ticker.percentage or 0.0), ticker))

        for _, ticker in sorted(movers, key=lambda item: item[0], reverse=True):
            if len(candidates) >= limit:
                break
            base = ticker.symbol.split("/")[0]
            route = self.router.first_available_route(base, self.quote_currency)
            if route is None:
                continue
            exchange_id, route_symbol = route
            seen.add(ticker.symbol)
            candidates.append(
                self._candidate(
                    route_symbol,
                    exchange_id,
                    ticker,
                    "Free exchange mover selected by 24h change and volume.",
                )
            )

        return candidates[:limit]

    def _candidate(
        self,
        route_symbol: str,
        exchange_id: str,
        ticker,
        reason: str,
    ) -> Candidate:
        base, quote = route_symbol.split("/")
        return Candidate(
            asset=Asset(
                symbol=route_symbol,
                base=base,
                quote=quote,
                is_major=base in self.majors,
            ),
            exchange_id=exchange_id,
            route_symbol=route_symbol,
            reason=reason,
            volume_24h_usd=ticker.quote_volume,
            trading_link=ExchangeRouter.trading_link(exchange_id, route_symbol),
        )
