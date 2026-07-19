import { demoSignals } from './data'
import type { BacktestBatchRow, CmmScalpResult, CmmScanResult, NormalizedSignal, OpenInterestRow, ScanRunSummary, ScreenerRow, SignalLifecycle, StrategyKey } from './types'
import { stableSignalId } from './utils'

const API_URL = (import.meta.env.VITE_CMM_API_URL || '').replace(/\/$/, '')
const labels: Record<StrategyKey, string> = { bounce: 'Bounce', apex_squeeze: 'Apex Squeeze', transition_play: 'Transition Play', tabo: 'TABO', alma_cci_scalp: 'ALMA / CCI Scalp', ma_short: 'Validated MA Short' }

export interface ApiStatus { connected: boolean; mode: 'live' | 'demo'; message: string; dataMode?: string; paperOnly?: boolean }

async function request<T>(path: string, init?: RequestInit, timeoutMs = 180000): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${API_URL}${path}`, { ...init, signal: controller.signal })
    if (!response.ok) throw new Error(`EdgeLedger scanner returned ${response.status}`)
    return await response.json() as T
  } finally { window.clearTimeout(timeout) }
}

export async function checkHealth(): Promise<ApiStatus> {
  try {
    const health = await request<{ status: string; dataMode: string; paperOnly: boolean }>('/api/health')
    return { connected: true, mode: 'live', message: `Integrated scanner · ${health.dataMode}`, dataMode: health.dataMode, paperOnly: health.paperOnly }
  } catch {
    return { connected: false, mode: 'demo', message: 'Demo data · integrated scanner offline' }
  }
}

function lifecycle(value: string): SignalLifecycle {
  const normalized = value.toUpperCase() as SignalLifecycle
  return ['WAIT', 'WATCH', 'ENTER', 'REJECT', 'INVALIDATED', 'EXPIRED', 'TARGET_HIT', 'STOPPED', 'MANUALLY_DISMISSED'].includes(normalized) ? normalized : 'WAIT'
}

function freshness(timestamp: string): NormalizedSignal['freshness'] {
  const age = Date.now() - new Date(timestamp).getTime()
  return age < 60_000 ? 'live' : age < 15 * 60_000 ? 'fresh' : 'stale'
}

export function adaptIntraday(row: CmmScanResult, scannedAt = new Date().toISOString()): NormalizedSignal {
  const base: NormalizedSignal = { id: '', symbol: row.symbol, strategy: row.setup, strategyLabel: labels[row.setup] ?? row.setup, direction: row.direction, lifecycle: lifecycle(row.signal), grade: row.grade, confidence: row.confidence, score: row.score, entry: row.entry, stopLoss: row.stopLoss, targets: row.targets ?? [], riskReward: row.riskReward, source: row.source, scannedAt, timeframe: '15m', evidence: row.evidence ?? [], validationReasons: row.validationReasons ?? [], approved: row.approved, freshness: freshness(scannedAt) }
  base.id = stableSignalId(base)
  return base
}

export function adaptScalp(row: CmmScalpResult): NormalizedSignal {
  const scannedAt = row.scannedAt ?? new Date().toISOString()
  const base = adaptIntraday({ ...row, rank: row.rank ?? 0, riskReward: row.riskReward ?? (row.targets?.length && row.entry && row.stopLoss ? Math.abs(row.targets[0] - row.entry) / Math.abs(row.entry - row.stopLoss) : 2), approved: row.approved ?? !row.validationReasons?.length }, scannedAt)
  return {
    ...base,
    timeframe: '3m',
    evidence: row.evidence?.length ? row.evidence : row.quality ?? [],
    freshness: freshness(row.latestCandleTime ?? scannedAt),
    scalpDetails: row.qualityMetrics ? {
      rank: row.rank ?? 0,
      setupAgeMinutes: row.setupAgeMinutes ?? null,
      executionCandleTime: row.executionCandleTime,
      latestCandleTime: row.latestCandleTime,
      quality: row.quality ?? [],
      metrics: row.qualityMetrics,
      openInterestChange24hPct: row.openInterestChange24hPct ?? null,
      volume24hUsd: row.volume24hUsd ?? null,
      relativeVolume3m: row.relativeVolume3m ?? null,
      prefilterReasons: row.prefilterReasons ?? [],
      invalidationReason: row.invalidationReason,
    } : undefined,
  }
}

const scanSummary = (summary: { candidates_scanned?: number; deep_analyzed?: number; failed_symbols?: number; duration_seconds?: number; worker_count?: number }): ScanRunSummary => ({
  candidates: summary.candidates_scanned ?? 0,
  scanned: summary.deep_analyzed ?? 0,
  failed: summary.failed_symbols ?? 0,
  durationSeconds: summary.duration_seconds ?? 0,
  workers: summary.worker_count ?? 0,
})

export async function runScan(mode: 'intraday' | 'scalp'): Promise<{ signals: NormalizedSignal[]; status: ApiStatus; warnings: string[]; summary?: ScanRunSummary }> {
  try {
    if (mode === 'intraday') {
      const payload = await request<{ summary: { created_at?: string; warnings?: string[]; candidates_scanned?: number; deep_analyzed?: number; failed_symbols?: number; duration_seconds?: number; worker_count?: number }; results: CmmScanResult[] }>('/api/scan', { method: 'POST' })
      const at = payload.summary.created_at ?? new Date().toISOString()
      return { signals: payload.results.map((row) => adaptIntraday(row, at)), status: { connected: true, mode: 'live', message: 'Live CMM intraday scan' }, warnings: payload.summary.warnings ?? [], summary: scanSummary(payload.summary) }
    }
    const payload = await request<{ summary: { warnings?: string[]; candidates_scanned?: number; deep_analyzed?: number; failed_symbols?: number; duration_seconds?: number; worker_count?: number }; results: CmmScalpResult[] }>('/api/scalp', { method: 'POST' })
    return { signals: payload.results.map(adaptScalp), status: { connected: true, mode: 'live', message: 'Live CMM scalp scan' }, warnings: payload.summary.warnings ?? [], summary: scanSummary(payload.summary) }
  } catch (error) {
    const family = mode === 'scalp' ? demoSignals.filter((item) => item.strategy === 'alma_cci_scalp') : demoSignals.filter((item) => item.strategy !== 'alma_cci_scalp')
    return { signals: family, status: { connected: false, mode: 'demo', message: 'Demo results · integrated scanner unavailable' }, warnings: [error instanceof Error ? error.message : 'Unable to reach the integrated scanner'] }
  }
}

export async function fetchJournal() {
  return request<{ activeSetups: unknown[]; theses: unknown[]; alerts: unknown[]; outcomes: unknown[]; calibration: unknown[] }>('/api/journal')
}

export async function fetchOpenInterest() {
  return request<{ warnings: string[]; rows: OpenInterestRow[] }>('/api/open-interest')
}

export async function fetchMarketScreener() {
  return request<{ source: string; updatedAt: string; warnings: string[]; rows: ScreenerRow[] }>('/api/market-screener')
}

export async function runBacktestBatch() {
  return request<{ source: string; timeframe: string; strategy: string; side: string; rows: BacktestBatchRow[] }>(
    '/api/backtest-batch?strategy=ma&timeframe=15m&side=auto',
    { method: 'POST' },
    900000,
  )
}

export { API_URL }
