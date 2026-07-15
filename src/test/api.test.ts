import { describe, expect, it } from 'vitest'
import { adaptIntraday, adaptScalp } from '../api'

describe('CMM response adapters', () => {
  it('normalizes intraday strategy output', () => {
    const signal = adaptIntraday({ rank: 1, symbol: 'BTC/USD', source: 'coinbase', setup: 'apex_squeeze', signal: 'enter', direction: 'long', confidence: .84, entry: 100, stopLoss: 95, targets: [110], riskReward: 2, grade: 'A', approved: true, score: 88, evidence: ['confirmed'], validationReasons: [] }, '2026-07-15T10:00:00Z')
    expect(signal.lifecycle).toBe('ENTER')
    expect(signal.strategyLabel).toBe('Apex Squeeze')
    expect(signal.timeframe).toBe('15m')
  })

  it('normalizes scalper output with 3m execution', () => {
    const signal = adaptScalp({ symbol: 'SOL/USD', source: 'coinbase', setup: 'alma_cci_scalp', signal: 'watch', direction: 'long', confidence: .7, entry: 100, stopLoss: 99, targets: [102], grade: 'B', approved: false, score: 70, scannedAt: new Date().toISOString(), quality: ['cross forming'], validationReasons: ['wait'] })
    expect(signal.lifecycle).toBe('WATCH')
    expect(signal.riskReward).toBe(2)
    expect(signal.evidence).toEqual(['cross forming'])
    expect(signal.timeframe).toBe('3m')
  })
})
