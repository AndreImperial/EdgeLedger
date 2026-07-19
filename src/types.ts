export type SignalLifecycle =
  | 'WAIT'
  | 'WATCH'
  | 'ENTER'
  | 'REJECT'
  | 'INVALIDATED'
  | 'EXPIRED'
  | 'TARGET_HIT'
  | 'STOPPED'
  | 'MANUALLY_DISMISSED'

export type Direction = 'long' | 'short' | 'none'
export type StrategyKey = 'bounce' | 'apex_squeeze' | 'transition_play' | 'tabo' | 'alma_cci_scalp' | 'ma_short'

export interface NormalizedSignal {
  id: string
  symbol: string
  strategy: StrategyKey
  strategyLabel: string
  direction: Direction
  lifecycle: SignalLifecycle
  grade: string
  confidence: number
  score: number
  entry?: number
  stopLoss?: number
  targets: number[]
  riskReward?: number
  source: string
  scannedAt: string
  timeframe: string
  evidence: string[]
  validationReasons: string[]
  approved: boolean
  freshness: 'live' | 'fresh' | 'stale'
  scalpDetails?: ScalpDetails
}

export interface CmmScanResult {
  rank: number
  symbol: string
  source: string
  setup: StrategyKey
  signal: string
  direction: Direction
  confidence: number
  entry?: number
  stopLoss?: number
  targets?: number[]
  riskReward?: number
  grade: string
  approved: boolean
  score: number
  evidence?: string[]
  validationReasons?: string[]
}

export interface ScalpQualityMetrics {
  oiPriceRead: string
  biasStrength: string
  structureStrength: string
  atrPct: number | null
  crossAgeBars: number | null
  cciSlope: number | null
  spreadEstimatePct: number | null
  volatilityOk: boolean
}

export interface ScalpDetails {
  rank: number
  setupAgeMinutes: number | null
  executionCandleTime?: string
  latestCandleTime?: string
  quality: string[]
  metrics: ScalpQualityMetrics
  openInterestChange24hPct: number | null
  volume24hUsd: number | null
  relativeVolume3m: number | null
  prefilterReasons: string[]
  invalidationReason?: string
}

export interface CmmScalpResult extends Omit<CmmScanResult, 'rank'> {
  rank?: number
  scannedAt?: string
  executionCandleTime?: string
  latestCandleTime?: string
  setupAgeMinutes?: number | null
  quality?: string[]
  qualityMetrics?: ScalpQualityMetrics
  openInterestChange24hPct?: number | null
  volume24hUsd?: number | null
  relativeVolume3m?: number | null
  prefilterReasons?: string[]
  invalidationReason?: string
}

export interface ScanRunSummary {
  candidates: number
  scanned: number
  failed: number
  durationSeconds: number
  workers: number
}

export interface LinkedJournalTrade {
  id?: number
  externalId?: string
  signalId?: string
  openedAt: string
  closedAt?: string
  symbol: string
  exchange: string
  direction: Exclude<Direction, 'none'>
  strategy: StrategyKey | 'manual'
  entry: number
  exit?: number
  stopLoss?: number
  target?: number
  quantity: number
  leverage: number
  fees: number
  pnl: number
  rMultiple?: number
  session: string
  emotion: string
  notes: string
  chartUrl?: string
}

export interface TradePlan {
  signalId: string
  symbol: string
  direction: Direction
  strategy: StrategyKey
  entry?: number
  stopLoss?: number
  targets: number[]
  riskPercent: number
  accountBalance: number
  notes: string
}

export interface StrategyTemplate {
  key: StrategyKey
  name: string
  family: 'Intraday' | 'Scalper'
  timeframe: string
  summary: string
  rules: string[]
  defaults: string[]
  accent: string
}

export interface MarketEvent {
  id: string
  date: string
  time: string
  code: string
  title: string
  impact: 'high' | 'medium'
  note: string
}

export interface ScreenerRow {
  symbol: string
  market: string
  source: string
  price: number
  change24h: number | null
  volume24hUsd: number | null
  rsi4h: number | null
  rsi1h: number | null
  macd1d: string
  macd4h: string
  macd1h: string
  updatedAt: string
}

export interface OpenInterestRow {
  symbol: string
  source: string
  open_interest: number | null
  open_interest_usd: number | null
  open_interest_change_24h_pct: number | null
  volume_24h_usd: number | null
  price: number | null
  status: string
  updated_at: string
}

export interface BacktestBatchRow {
  symbol: string
  timeframe: string
  trades: number
  win_rate: number
  return_pct: number
  drawdown_pct: number
  profit_factor: number
  expectancy_pct: number
  long_trades: number
  short_trades: number
  best_setup?: string | null
  validation_trades?: number
  validation_win_rate?: number
  validation_win_rate_delta?: number
  validation_expectancy_pct?: number
}
