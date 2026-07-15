import { describe, expect, it } from 'vitest'
import { calculateR, calculateTrade, positionSize, stableSignalId, summarizeTrades } from '../utils'

describe('trading calculations', () => {
  it('calculates long and short PNL after fees', () => {
    expect(calculateTrade(100, 110, 2, 'long', 1)).toBe(19)
    expect(calculateTrade(100, 90, 2, 'short', 1)).toBe(19)
  })

  it('calculates direction-aware R multiples', () => {
    expect(calculateR(100, 120, 90, 'long')).toBe(2)
    expect(calculateR(100, 80, 110, 'short')).toBe(2)
  })

  it('sizes a position from account risk and stop distance', () => {
    expect(positionSize(10_000, 1, 100, 95)).toBe(20)
    expect(positionSize(10_000, 1, 100, 100)).toBe(0)
  })

  it('creates stable versioned signal identities', () => {
    const base = { symbol: 'BTC/USD', strategy: 'bounce' as const, direction: 'long' as const, timeframe: '15m', scannedAt: '2026-07-15T10:22:30Z' }
    expect(stableSignalId(base)).toBe(stableSignalId({ ...base, scannedAt: '2026-07-15T10:22:59Z' }))
    expect(stableSignalId(base)).toContain('v1')
  })

  it('summarizes realized trades only', () => {
    const result = summarizeTrades([
      { openedAt: '2026-01-01', closedAt: '2026-01-02', symbol: 'BTC/USD', exchange: 'x', direction: 'long', strategy: 'manual', entry: 1, exit: 2, quantity: 1, leverage: 1, fees: 0, pnl: 100, rMultiple: 2, session: 'London', emotion: 'Calm', notes: '' },
      { openedAt: '2026-01-03', symbol: 'ETH/USD', exchange: 'x', direction: 'long', strategy: 'manual', entry: 1, quantity: 1, leverage: 1, fees: 0, pnl: 0, session: 'London', emotion: 'Calm', notes: '' },
    ])
    expect(result.closed).toBe(1)
    expect(result.pnl).toBe(100)
    expect(result.winRate).toBe(100)
  })
})
