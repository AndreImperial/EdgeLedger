import type { NormalizedSignal } from './types'

export interface EdgeAlert {
  id: string
  symbol: string
  strategy: string
  lifecycle: string
  grade: string
  confidence: number
  createdAt: string
  read: boolean
}

const STORAGE_KEY = 'edgeledger-alerts'

export function readAlerts(): EdgeAlert[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') as EdgeAlert[] } catch { return [] }
}

export function recordSignalAlerts(signals: NormalizedSignal[]) {
  const current = readAlerts()
  const additions = signals.filter((signal) => signal.lifecycle === 'ENTER' || signal.lifecycle === 'WATCH').map((signal) => ({ id: signal.id, symbol: signal.symbol, strategy: signal.strategyLabel, lifecycle: signal.lifecycle, grade: signal.grade, confidence: signal.confidence, createdAt: signal.scannedAt, read: false }))
  const merged = [...additions, ...current].filter((alert, index, all) => all.findIndex((item) => item.id === alert.id) === index).slice(0, 30)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
  window.dispatchEvent(new CustomEvent('edgeledger-alerts', { detail: merged }))
}

export function markAlertsRead() {
  const alerts = readAlerts().map((alert) => ({ ...alert, read: true }))
  localStorage.setItem(STORAGE_KEY, JSON.stringify(alerts))
  window.dispatchEvent(new CustomEvent('edgeledger-alerts', { detail: alerts }))
}
