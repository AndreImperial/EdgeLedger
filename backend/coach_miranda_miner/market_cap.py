from __future__ import annotations

import requests

from .models import Asset


STABLECOINS = {
    "USDT",
    "USDC",
    "DAI",
    "FDUSD",
    "TUSD",
    "USDE",
    "USDD",
    "PYUSD",
    "USDP",
}


class MarketCapProvider:
    def top_assets(self, limit: int, min_market_cap_usd: float) -> list[Asset]:
        raise NotImplementedError


class StaticMarketCapProvider(MarketCapProvider):
    def __init__(self, bases: list[str]) -> None:
        self.bases = bases

    def top_assets(self, limit: int, min_market_cap_usd: float) -> list[Asset]:
        return [
            Asset(symbol=f"{base}/USDT", base=base, market_cap_usd=None, is_major=True)
            for base in self.bases[:limit]
            if base not in STABLECOINS
        ]


class CoinMarketCapProvider(MarketCapProvider):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def top_assets(self, limit: int, min_market_cap_usd: float) -> list[Asset]:
        response = requests.get(
            "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
            headers={"X-CMC_PRO_API_KEY": self.api_key},
            params={
                "start": 1,
                "limit": limit,
                "convert": "USD",
                "sort": "market_cap",
                "sort_dir": "desc",
            },
            timeout=30,
        )
        response.raise_for_status()
        assets: list[Asset] = []
        for item in response.json().get("data", []):
            base = item.get("symbol")
            quote = item.get("quote", {}).get("USD", {})
            market_cap = quote.get("market_cap")
            if not base or base in STABLECOINS:
                continue
            if market_cap is None or float(market_cap) < min_market_cap_usd:
                continue
            assets.append(
                Asset(
                    symbol=f"{base}/USDT",
                    base=base,
                    market_cap_usd=float(market_cap),
                    is_major=len(assets) < 30,
                )
            )
        return assets
