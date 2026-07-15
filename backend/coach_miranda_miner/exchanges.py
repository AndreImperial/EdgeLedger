from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import threading
import time
from urllib.parse import quote

import ccxt
import pandas as pd
import requests


@dataclass(frozen=True)
class TickerSnapshot:
    symbol: str
    last: float
    percentage: float | None
    quote_volume: float | None


class ExchangeRouter:
    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids
        self._exchanges = {
            exchange_id: getattr(ccxt, exchange_id)({"enableRateLimit": True})
            for exchange_id in exchange_ids
        }

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        ticker = self._exchanges[exchange_id].fetch_ticker(symbol)
        return TickerSnapshot(
            symbol=symbol,
            last=float(ticker["last"]),
            percentage=ticker.get("percentage"),
            quote_volume=ticker.get("quoteVolume"),
        )

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        tickers = self._exchanges[exchange_id].fetch_tickers()
        snapshots: list[TickerSnapshot] = []
        for symbol, ticker in tickers.items():
            if not symbol.endswith("/USDT"):
                continue
            last = ticker.get("last")
            if last is None:
                continue
            snapshots.append(
                TickerSnapshot(
                    symbol=symbol,
                    last=float(last),
                    percentage=ticker.get("percentage"),
                    quote_volume=ticker.get("quoteVolume"),
                )
            )
        return snapshots

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        candles = self._exchanges[exchange_id].fetch_ohlcv(
            symbol,
            timeframe=timeframe,
            limit=limit,
        )
        frame = pd.DataFrame(
            candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
        return frame

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        preferred_symbol = f"{base}/{quote_currency}"
        for exchange_id, exchange in self._exchanges.items():
            exchange.load_markets()
            if preferred_symbol in exchange.markets:
                return exchange_id, preferred_symbol
        return None

    @staticmethod
    def trading_link(exchange_id: str, symbol: str) -> str | None:
        compact = symbol.replace("/", "")
        if exchange_id == "binance":
            return f"https://www.binance.com/en/trade/{symbol.replace('/', '_')}"
        if exchange_id == "bybit":
            return f"https://www.bybit.com/trade/usdt/{compact}"
        if exchange_id == "okx":
            return f"https://www.okx.com/trade-spot/{quote(symbol.replace('/', '-'))}"
        if exchange_id == "coinbase":
            return f"https://www.coinbase.com/advanced-trade/spot/{symbol.replace('/', '-')}"
        if exchange_id == "bitunix":
            return f"https://www.bitunix.com/futures-trade/{compact}"
        return None


class FixtureExchangeRouter:
    """Offline market-data router for development and repeatable tests."""

    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        base = symbol.split("/")[0]
        last = _base_price(base)
        change = -1.1 if base == "BTC" else 4.2
        volume = 1_000_000_000 if base in {"BTC", "ETH", "SOL"} else 120_000_000
        return TickerSnapshot(
            symbol=symbol,
            last=last,
            percentage=change,
            quote_volume=volume,
        )

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        symbols = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT"]
        return [
            self.fetch_ticker(exchange_id, f"{base}/USDT")
            for base in symbols
        ]

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        base = symbol.split("/")[0]
        price = _base_price(base)
        minutes = _timeframe_minutes(timeframe)
        start = datetime.now(timezone.utc) - timedelta(minutes=minutes * limit)
        rows = []
        for index in range(limit):
            pattern_index = index - max(limit - 80, 0)
            if pattern_index >= 0:
                center = price * 1.04
                if pattern_index < 40:
                    amplitude = price * 0.018
                    close = center + math.sin(pattern_index / 3) * amplitude
                elif pattern_index < 77:
                    amplitude = price * 0.005
                    close = center + math.sin(pattern_index / 2) * amplitude
                elif pattern_index == 77:
                    close = center + price * 0.002
                elif pattern_index == 78:
                    close = center + price * 0.008
                else:
                    close = center + price * 0.012
                open_price = close - (math.sin(index / 3) * price * 0.002)
                high = max(open_price, close) + price * 0.0025
                low = min(open_price, close) - price * 0.0025
            else:
                drift = index * price * 0.0002
                wave = math.sin(index / 5) * price * 0.008
                close = price + drift + wave
                open_price = close - (math.sin(index / 3) * price * 0.003)
                high = max(open_price, close) + price * 0.004
                low = min(open_price, close) - price * 0.004
            volume = 1000 + (index % 20) * 50
            if index == limit - 1:
                volume *= 2.2
            rows.append(
                {
                    "timestamp": start + timedelta(minutes=minutes * index),
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
        return pd.DataFrame(rows)

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        exchange_id = self.exchange_ids[0] if self.exchange_ids else "binance"
        return exchange_id, f"{base}/{quote_currency}"


def _base_price(base: str) -> float:
    return {
        "BTC": 100_000.0,
        "ETH": 3_500.0,
        "SOL": 180.0,
        "BNB": 700.0,
        "XRP": 2.2,
        "DOGE": 0.22,
        "ADA": 0.8,
        "AVAX": 45.0,
        "LINK": 22.0,
        "DOT": 8.0,
    }.get(base, 10.0)


def _timeframe_minutes(timeframe: str) -> int:
    return {
        "1m": 1,
        "3m": 3,
        "5m": 5,
        "15m": 15,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
    }.get(timeframe, 60)


COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "DOT": "polkadot",
}


class CoinGeckoRouter:
    """Free live market data through CoinGecko public endpoints."""

    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids
        self.session = requests.Session()
        self.base_url = "https://api.coingecko.com/api/v3"

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        base = symbol.split("/")[0]
        coin_id = _coingecko_id(base)
        response = self.session.get(
            f"{self.base_url}/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": coin_id,
                "price_change_percentage": "24h",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if not data:
            raise ValueError(f"CoinGecko returned no ticker for {symbol}.")
        item = data[0]
        return TickerSnapshot(
            symbol=symbol,
            last=float(item["current_price"]),
            percentage=item.get("price_change_percentage_24h"),
            quote_volume=item.get("total_volume"),
        )

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        response = self.session.get(
            f"{self.base_url}/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "volume_desc",
                "per_page": 50,
                "page": 1,
                "price_change_percentage": "24h",
            },
            timeout=30,
        )
        response.raise_for_status()
        snapshots: list[TickerSnapshot] = []
        for item in response.json():
            symbol = f"{str(item['symbol']).upper()}/USDT"
            snapshots.append(
                TickerSnapshot(
                    symbol=symbol,
                    last=float(item["current_price"]),
                    percentage=item.get("price_change_percentage_24h"),
                    quote_volume=item.get("total_volume"),
                )
            )
        return snapshots

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        base = symbol.split("/")[0]
        coin_id = _coingecko_id(base)
        days = _coingecko_days(timeframe, limit)
        response = self.session.get(
            f"{self.base_url}/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        prices = pd.DataFrame(payload["prices"], columns=["timestamp", "price"])
        volumes = pd.DataFrame(payload["total_volumes"], columns=["timestamp", "volume"])
        frame = prices.merge(volumes, on="timestamp", how="left")
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
        frame = frame.set_index("timestamp").sort_index()

        rule = _pandas_rule(timeframe)
        ohlc = frame["price"].resample(rule).ohlc()
        volume = frame["volume"].resample(rule).last().fillna(0)
        candles = ohlc.join(volume).dropna().reset_index()
        candles.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        return candles.tail(limit).reset_index(drop=True)

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        if base.upper() not in COINGECKO_IDS:
            return None
        return "coingecko", f"{base.upper()}/{quote_currency}"


def _coingecko_id(base: str) -> str:
    coin_id = COINGECKO_IDS.get(base.upper())
    if coin_id is None:
        raise ValueError(f"No CoinGecko id configured for {base}.")
    return coin_id


def _coingecko_days(timeframe: str, limit: int) -> str:
    minutes = _timeframe_minutes(timeframe)
    days = max(1, math.ceil((minutes * limit) / 1440))
    return str(min(days, 90))


def _pandas_rule(timeframe: str) -> str:
    return {
        "1m": "1min",
        "3m": "3min",
        "5m": "5min",
        "15m": "15min",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
    }.get(timeframe, "1h")


YAHOO_SYMBOLS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "BNB": "BNB-USD",
    "XRP": "XRP-USD",
    "DOGE": "DOGE-USD",
    "ADA": "ADA-USD",
    "AVAX": "AVAX-USD",
    "LINK": "LINK-USD",
    "DOT": "DOT-USD",
}

PAPRIKA_IDS = {
    "BTC": "btc-bitcoin",
    "ETH": "eth-ethereum",
    "SOL": "sol-solana",
    "BNB": "bnb-binance-coin",
    "XRP": "xrp-xrp",
    "DOGE": "doge-dogecoin",
    "ADA": "ada-cardano",
    "AVAX": "avax-avalanche",
    "LINK": "link-chainlink",
    "DOT": "dot-polkadot",
}

COINBASE_PRODUCTS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "BNB": "BNB-USD",
    "XRP": "XRP-USD",
    "DOGE": "DOGE-USD",
    "ADA": "ADA-USD",
    "AVAX": "AVAX-USD",
    "LINK": "LINK-USD",
    "DOT": "DOT-USD",
}


class YahooFinanceRouter:
    """Free updating crypto data from Yahoo Finance chart endpoints."""

    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids
        self.session = requests.Session()
        self.base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
        self._ticker_cache: dict[str, TickerSnapshot] = {}

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        if symbol in self._ticker_cache:
            return self._ticker_cache[symbol]
        frame = self.fetch_candles(exchange_id, symbol, "1h", 48)
        latest = frame.iloc[-1]
        first = frame.iloc[0]
        last = float(latest["close"])
        start = float(first["close"])
        change = ((last - start) / start) * 100 if start else 0.0
        volume = float(frame["volume"].tail(24).sum())
        ticker = TickerSnapshot(
            symbol=symbol,
            last=last,
            percentage=change,
            quote_volume=volume,
        )
        self._ticker_cache[symbol] = ticker
        return ticker

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        snapshots = []
        for base in YAHOO_SYMBOLS:
            try:
                snapshots.append(self.fetch_ticker(exchange_id, f"{base}/USDT"))
            except Exception:
                continue
        return snapshots

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        yahoo_symbol = _yahoo_symbol(symbol.split("/")[0])
        response = self.session.get(
            f"{self.base_url}/{yahoo_symbol}",
            params={
                "range": _yahoo_range(timeframe, limit),
                "interval": _yahoo_interval(timeframe),
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote_data = result["indicators"]["quote"][0]
        frame = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(timestamps, unit="s", utc=True),
                "open": quote_data["open"],
                "high": quote_data["high"],
                "low": quote_data["low"],
                "close": quote_data["close"],
                "volume": quote_data["volume"],
            }
        )
        return frame.dropna().tail(limit).reset_index(drop=True)

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        if base.upper() not in YAHOO_SYMBOLS:
            return None
        return "yahoo", f"{base.upper()}/{quote_currency}"


def _yahoo_symbol(base: str) -> str:
    symbol = YAHOO_SYMBOLS.get(base.upper())
    if symbol is None:
        raise ValueError(f"No Yahoo Finance symbol configured for {base}.")
    return symbol


def _yahoo_interval(timeframe: str) -> str:
    return {
        "1m": "1m",
        "3m": "5m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "1h",
        "1d": "1d",
    }.get(timeframe, "1h")


def _yahoo_range(timeframe: str, limit: int) -> str:
    if timeframe in {"1m", "3m", "5m", "15m"}:
        return "5d"
    if timeframe in {"1h", "4h"}:
        return "3mo"
    return "1y"


class CoinPaprikaRouter:
    """Free live tickers from CoinPaprika with local chart scaffolding."""

    def __init__(self, exchange_ids: list[str]) -> None:
        self.exchange_ids = exchange_ids
        self.session = requests.Session()
        self.base_url = "https://api.coinpaprika.com/v1"
        self._ticker_cache: dict[str, TickerSnapshot] = {}

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        if symbol in self._ticker_cache:
            return self._ticker_cache[symbol]
        base = symbol.split("/")[0]
        response = self.session.get(
            f"{self.base_url}/tickers/{_paprika_id(base)}",
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        quote = payload["quotes"]["USD"]
        ticker = TickerSnapshot(
            symbol=symbol,
            last=float(quote["price"]),
            percentage=quote.get("percent_change_24h"),
            quote_volume=quote.get("volume_24h"),
        )
        self._ticker_cache[symbol] = ticker
        return ticker

    def fetch_tickers(self, exchange_id: str) -> list[TickerSnapshot]:
        snapshots = []
        for base in PAPRIKA_IDS:
            try:
                snapshots.append(self.fetch_ticker(exchange_id, f"{base}/USDT"))
            except Exception:
                continue
        return snapshots

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        ticker = self.fetch_ticker(exchange_id, symbol)
        return _synthetic_candles_from_price(symbol, ticker.last, timeframe, limit)

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        if base.upper() not in PAPRIKA_IDS:
            return None
        return "paprika", f"{base.upper()}/{quote_currency}"


def _paprika_id(base: str) -> str:
    coin_id = PAPRIKA_IDS.get(base.upper())
    if coin_id is None:
        raise ValueError(f"No CoinPaprika id configured for {base}.")
    return coin_id


def _synthetic_candles_from_price(
    symbol: str,
    live_price: float,
    timeframe: str,
    limit: int,
) -> pd.DataFrame:
    minutes = _timeframe_minutes(timeframe)
    start = datetime.now(timezone.utc) - timedelta(minutes=minutes * limit)
    rows = []
    for index in range(limit):
        pattern_index = index - max(limit - 80, 0)
        if pattern_index >= 0:
            center = live_price * 0.988
            if pattern_index < 40:
                amplitude = live_price * 0.018
                close = center + math.sin(pattern_index / 3) * amplitude
            elif pattern_index < 77:
                amplitude = live_price * 0.005
                close = center + math.sin(pattern_index / 2) * amplitude
            elif pattern_index == 77:
                close = center + live_price * 0.002
            elif pattern_index == 78:
                close = center + live_price * 0.008
            else:
                close = live_price
            open_price = close - (math.sin(index / 3) * live_price * 0.002)
            high = max(open_price, close) + live_price * 0.0025
            low = min(open_price, close) - live_price * 0.0025
        else:
            wave = math.sin(index / 5) * live_price * 0.008
            close = live_price * 0.97 + wave
            open_price = close - (math.sin(index / 3) * live_price * 0.003)
            high = max(open_price, close) + live_price * 0.004
            low = min(open_price, close) - live_price * 0.004
        volume = 1000 + (index % 20) * 50
        if index == limit - 1:
            volume *= 2.2
        rows.append(
            {
                "timestamp": start + timedelta(minutes=minutes * index),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
    return pd.DataFrame(rows)


class BitunixRouter:
    """Public Bitunix USDT perpetual market data; no account key required."""

    def __init__(self, exchange_ids: list[str], timeout_seconds: int = 20) -> None:
        self.exchange_ids = ["bitunix"]
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "EdgeLedger"})
        self.base_url = "https://fapi.bitunix.com/api/v1/futures/market"
        self._ticker_cache: dict[str, TickerSnapshot] = {}
        self._candle_cache: dict[tuple[str, str, int], pd.DataFrame] = {}
        self._products: set[str] | None = None
        self._request_lock = threading.Lock()
        self._last_request_at = 0.0

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        compact = _bitunix_symbol(symbol)
        cached = self._ticker_cache.get(compact)
        if cached is not None:
            return cached
        response = self._request(f"{self.base_url}/tickers", params={"symbols": compact})
        rows = _bitunix_data(response)
        if not rows:
            raise ValueError(f"Bitunix returned no ticker for {compact}.")
        ticker = _bitunix_ticker(rows[0])
        self._ticker_cache[compact] = ticker
        return ticker

    def fetch_tickers(self, exchange_id: str, universe_limit: int | None = None) -> list[TickerSnapshot]:
        response = self._request(f"{self.base_url}/tickers")
        snapshots = []
        for item in _bitunix_data(response):
            try:
                ticker = _bitunix_ticker(item)
            except (KeyError, TypeError, ValueError):
                continue
            self._ticker_cache[_bitunix_symbol(ticker.symbol)] = ticker
            snapshots.append(ticker)
        snapshots.sort(key=lambda item: item.quote_volume or 0.0, reverse=True)
        return snapshots[:universe_limit] if universe_limit is not None else snapshots

    def fetch_candles(self, exchange_id: str, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        cache_key = (symbol, timeframe, limit)
        if cache_key in self._candle_cache:
            return self._candle_cache[cache_key].copy()
        compact = _bitunix_symbol(symbol)
        rows: list[dict] = []
        remaining = limit
        end_time: int | None = None
        while remaining > 0:
            chunk = min(remaining, 200)
            params: dict[str, str | int] = {"symbol": compact, "interval": timeframe, "limit": chunk, "type": "LAST_PRICE"}
            if end_time is not None:
                params["endTime"] = end_time
            response = self._request(f"{self.base_url}/kline", params=params)
            page = _bitunix_data(response)
            if not page:
                break
            rows.extend(page)
            end_time = min(int(item["time"]) for item in page) - 1
            remaining -= len(page)
            if len(page) < chunk:
                break
        frame = pd.DataFrame(rows)
        if frame.empty:
            raise ValueError(f"Bitunix returned no candles for {compact} {timeframe}.")
        timestamps = pd.to_numeric(frame["time"], errors="raise")
        frame["timestamp"] = pd.to_datetime(timestamps, unit="ms", utc=True)
        frame["volume"] = pd.to_numeric(frame["quoteVol"], errors="coerce").fillna(0.0)
        for column in ("open", "high", "low", "close"):
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        frame["high"] = frame[["open", "high", "close"]].max(axis=1)
        frame["low"] = frame[["open", "low", "close"]].min(axis=1)
        candles = frame[["timestamp", "open", "high", "low", "close", "volume"]].sort_values("timestamp").drop_duplicates(subset=["timestamp"]).tail(limit).reset_index(drop=True)
        self._candle_cache[cache_key] = candles
        return candles.copy()

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        if quote_currency.upper() != "USDT":
            return None
        compact = f"{base.upper()}USDT"
        if compact not in self._bitunix_products():
            return None
        return "bitunix", f"{base.upper()}/USDT"

    def _bitunix_products(self) -> set[str]:
        if self._products is not None:
            return self._products
        response = self._request(f"{self.base_url}/trading_pairs")
        self._products = {str(item.get("symbol", "")).upper() for item in _bitunix_data(response) if item.get("symbolStatus") == "OPEN" and item.get("quote") == "USDT"}
        return self._products

    def _request(self, url: str, params: dict | None = None) -> requests.Response:
        for attempt in range(4):
            with self._request_lock:
                wait_seconds = 0.12 - (time.monotonic() - self._last_request_at)
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
                response = _get_with_retry(
                    self.session,
                    url,
                    params=params,
                    timeout=self.timeout_seconds,
                )
                self._last_request_at = time.monotonic()
            payload = response.json()
            if payload.get("code") == 0:
                return response
            if "frequent" not in str(payload.get("msg", "")).lower() or attempt == 3:
                return response
            time.sleep(0.5 * (attempt + 1))
        return response


def _bitunix_symbol(symbol: str) -> str:
    return symbol.replace("/", "").replace(":USDT", "USDT").upper()


def _bitunix_data(response: requests.Response) -> list[dict]:
    payload = response.json()
    if payload.get("code") != 0:
        raise ValueError(f"Bitunix error: {payload.get('msg') or payload.get('code')}")
    data = payload.get("data")
    return data if isinstance(data, list) else []


def _bitunix_ticker(item: dict) -> TickerSnapshot:
    compact = str(item["symbol"]).upper()
    if not compact.endswith("USDT"):
        raise ValueError("Bitunix ticker is not USDT quoted.")
    last = float(item.get("lastPrice") or item.get("last"))
    open_price = float(item.get("open") or last)
    return TickerSnapshot(symbol=f"{compact[:-4]}/USDT", last=last, percentage=((last - open_price) / open_price) * 100 if open_price else 0.0, quote_volume=float(item.get("quoteVol") or 0.0))


class CoinbaseRouter:
    """Free public Coinbase Exchange OHLCV candles, no API key required."""

    def __init__(self, exchange_ids: list[str], timeout_seconds: int = 30) -> None:
        self.exchange_ids = exchange_ids
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CMMTrader"})
        self.base_url = "https://api.exchange.coinbase.com"
        self._ticker_cache: dict[str, TickerSnapshot] = {}
        self._candle_cache: dict[tuple[str, str, int], pd.DataFrame] = {}
        self._product_cache: dict[str, str] | None = None

    def fetch_ticker(self, exchange_id: str, symbol: str) -> TickerSnapshot:
        if symbol in self._ticker_cache:
            return self._ticker_cache[symbol]
        product = self._coinbase_product(symbol.split("/")[0])
        ticker_response = _get_with_retry(
            self.session,
            f"{self.base_url}/products/{product}/ticker",
            timeout=self.timeout_seconds,
        )
        stats_response = _get_with_retry(
            self.session,
            f"{self.base_url}/products/{product}/stats",
            timeout=self.timeout_seconds,
        )
        ticker_payload = ticker_response.json()
        stats_payload = stats_response.json()
        last = float(ticker_payload["price"])
        open_price = float(stats_payload.get("open") or last)
        change = ((last - open_price) / open_price) * 100 if open_price else 0.0
        base_volume = float(stats_payload.get("volume") or 0.0)
        ticker = TickerSnapshot(
            symbol=symbol,
            last=last,
            percentage=change,
            quote_volume=base_volume * last,
        )
        self._ticker_cache[symbol] = ticker
        return ticker

    def fetch_tickers(
        self,
        exchange_id: str,
        universe_limit: int | None = None,
    ) -> list[TickerSnapshot]:
        bases = list(self._coinbase_products())
        if universe_limit is not None:
            pool_size = max(20, universe_limit * 4)
            bases = bases[:pool_size]

        snapshots = []
        worker_count = max(1, min(12, len(bases)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self.fetch_ticker, exchange_id, f"{base}/USD"): base
                for base in bases
            }
            for future in as_completed(futures):
                try:
                    snapshots.append(future.result())
                except Exception:
                    continue
        return sorted(
            snapshots,
            key=lambda item: item.quote_volume or 0.0,
            reverse=True,
        )

    def fetch_candles(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        cache_key = (symbol, timeframe, limit)
        if cache_key in self._candle_cache:
            return self._candle_cache[cache_key].copy()

        product = self._coinbase_product(symbol.split("/")[0])
        granularity = _coinbase_granularity(timeframe)
        rows = _coinbase_candle_rows(
            self.session,
            f"{self.base_url}/products/{product}/candles",
            granularity,
            limit,
            timeout=self.timeout_seconds,
        )
        frame = pd.DataFrame(rows, columns=["timestamp", "low", "high", "open", "close", "volume"])
        if frame.empty:
            raise ValueError(f"Coinbase returned no candles for {symbol} {timeframe}.")
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
        frame = frame.sort_values("timestamp").drop_duplicates(subset=["timestamp"])
        candles = frame[["timestamp", "open", "high", "low", "close", "volume"]].tail(limit).reset_index(drop=True)
        self._candle_cache[cache_key] = candles
        return candles.copy()

    def first_available_route(self, base: str, quote_currency: str) -> tuple[str, str] | None:
        if quote_currency.upper() != "USD":
            return None
        if base.upper() not in self._coinbase_products():
            return None
        return "coinbase", f"{base.upper()}/USD"

    def _coinbase_product(self, base: str) -> str:
        products = self._coinbase_products()
        product = products.get(base.upper())
        if product is None:
            raise ValueError(f"No Coinbase product configured for {base}.")
        return product

    def _coinbase_products(self) -> dict[str, str]:
        if self._product_cache is not None:
            return self._product_cache

        products = dict(COINBASE_PRODUCTS)
        try:
            response = _get_with_retry(
                self.session,
                f"{self.base_url}/products",
                timeout=self.timeout_seconds,
            )
            for item in response.json():
                base = str(item.get("base_currency") or "").upper()
                quote = str(item.get("quote_currency") or "").upper()
                product_id = item.get("id")
                if not base or quote != "USD" or not product_id:
                    continue
                if item.get("trading_disabled") or item.get("status") != "online":
                    continue
                products[base] = str(product_id)
        except requests.RequestException:
            pass

        self._product_cache = products
        return products


def _coinbase_product(base: str) -> str:
    product = COINBASE_PRODUCTS.get(base.upper())
    if product is None:
        raise ValueError(f"No Coinbase product configured for {base}.")
    return product


def _coinbase_granularity(timeframe: str) -> int:
    return {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 21600,
        "1d": 86400,
    }.get(timeframe, 3600)


def _coinbase_candle_rows(
    session: requests.Session,
    url: str,
    granularity: int,
    limit: int,
    timeout: int = 30,
) -> list:
    if limit <= 300:
        response = _get_with_retry(
            session,
            url,
            params={"granularity": granularity},
            timeout=timeout,
        )
        return response.json()
    rows: list = []
    end = datetime.now(timezone.utc)
    remaining = limit
    while remaining > 0:
        chunk = min(remaining, 300)
        start = end - timedelta(seconds=granularity * chunk)
        response = _get_with_retry(
            session,
            url,
            params={
                "granularity": granularity,
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
            timeout=timeout,
        )
        payload = response.json()
        if not payload:
            break
        rows.extend(payload)
        remaining -= chunk
        end = start
        time.sleep(0.05)
    return rows


def _get_with_retry(
    session: requests.Session,
    url: str,
    params: dict | None = None,
    attempts: int = 3,
    timeout: int = 30,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = session.get(url, params=params, timeout=timeout)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
                time.sleep(0.75 * (attempt + 1))
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(0.75 * (attempt + 1))
                continue
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Request failed for {url}")
