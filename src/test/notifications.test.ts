import { beforeEach, describe, expect, it } from 'vitest'
import { markAlertsRead, readAlerts, recordSignalAlerts } from '../notifications'
import type { NormalizedSignal } from '../types'

const signal = (id: string, lifecycle: NormalizedSignal['lifecycle']): NormalizedSignal => ({
  id,
  symbol: 'BTC/USD',
  strategy: 'bounce',
  strategyLabel: 'Bounce',
  direction: 'long',
  lifecycle,
  grade: 'A',
  confidence: 0.82,
  score: 85,
  entry: 65000,
  stopLoss: 64000,
  targets: [67000],
  riskReward: 2,
  source: 'coinbase',
  scannedAt: '2026-07-15T06:00:00Z',
  timeframe: '15m',
  evidence: [],
  validationReasons: [],
  approved: true,
  freshness: 'live',
})

describe('in-app signal notifications', () => {
  beforeEach(() => localStorage.clear())

  it('records only actionable WATCH and ENTER states and deduplicates them', () => {
    recordSignalAlerts([signal('wait', 'WAIT'), signal('watch', 'WATCH'), signal('enter', 'ENTER')])
    recordSignalAlerts([signal('watch', 'WATCH')])

    expect(readAlerts().map((alert) => alert.id)).toEqual(['watch', 'enter'])
  })

  it('marks stored alerts as read without deleting them', () => {
    recordSignalAlerts([signal('enter', 'ENTER')])
    markAlertsRead()

    expect(readAlerts()).toMatchObject([{ id: 'enter', read: true }])
  })
})
