from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


Direction = Literal["long", "short", "none"]


class Setup(str, Enum):
    BOUNCE = "bounce"
    APEX_SQUEEZE = "apex_squeeze"
    TRANSITION_PLAY = "transition_play"
    TABO = "tabo"
    ALMA_CCI_SCALP = "alma_cci_scalp"
    MA_SHORT = "ma_short"
    NONE = "none"


class SignalState(str, Enum):
    WAIT = "wait"
    WATCH = "watch"
    ENTER = "enter"
    REJECT = "reject"


class Asset(BaseModel):
    symbol: str
    base: str
    quote: str = "USDT"
    market_cap_usd: float | None = None
    is_major: bool = False


class Candidate(BaseModel):
    asset: Asset
    exchange_id: str
    route_symbol: str
    reason: str
    volume_24h_usd: float | None = None
    open_interest_change_24h_pct: float | None = None
    trading_link: str | None = None


class MarketRegime(BaseModel):
    btc_change_24h_pct: float
    longs_allowed: bool
    shorts_allowed: bool = True
    eth_change_24h_pct: float | None = None
    trend_score: float = 0.0
    risk_mode: str = "neutral"
    reason: str


class IndicatorSnapshot(BaseModel):
    timeframe: str
    close: float
    volume: float
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    atr: float | None
    relative_volume: float | None


class CandleSnapshot(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class IntelligencePack(BaseModel):
    candidate: Candidate
    market_regime: MarketRegime
    indicators: list[IndicatorSnapshot]
    candles: dict[str, list[CandleSnapshot]] = Field(default_factory=dict)
    news_summary: str
    chart_paths: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TradeThesis(BaseModel):
    symbol: str
    setup: Setup
    signal: SignalState
    direction: Direction
    confidence: float = Field(ge=0.0, le=1.0)
    entry: float | None = None
    stop_loss: float | None = None
    targets: list[float] = Field(default_factory=list)
    risk_reward: float | None = None
    invalidation_reason: str | None = None
    evidence: list[str] = Field(default_factory=list)
    news_veto: bool = False

    @field_validator("targets")
    @classmethod
    def targets_must_be_positive(cls, value: list[float]) -> list[float]:
        for target in value:
            if target <= 0:
                raise ValueError("targets must be positive")
        return value


class ValidationResult(BaseModel):
    approved: bool
    reasons: list[str] = Field(default_factory=list)


class SetupScore(BaseModel):
    symbol: str
    rank: int
    score: float
    volume_24h_usd: float | None = None
    price_change_24h_pct: float | None = None
    oi_change_24h_pct: float | None = None
    relative_volume: float | None = None
    btc_regime_ok: bool
    prefilter_reasons: list[str] = Field(default_factory=list)


class ScanSummary(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    candidates_scanned: int
    deep_analyzed: int
    warnings: list[str] = Field(default_factory=list)
    coinalyze_enabled: bool = False
    market_regime: MarketRegime | None = None
    duration_seconds: float | None = None
    failed_symbols: int = 0
    worker_count: int = 1
