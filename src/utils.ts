import type { LinkedJournalTrade, NormalizedSignal } from './types'

export const money = (value: number, digits = 2) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: digits }).format(value)

export const number = (value: number, digits = 2) =>
  new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value)

export function calculateTrade(entry: number, exit: number, quantity: number, direction: 'long' | 'short', fees = 0) {
  const gross = direction === 'long' ? (exit - entry) * quantity : (entry - exit) * quantity
  return gross - fees
}

export function calculateR(entry: number, exit: number, stop: number, direction: 'long' | 'short') {
  const risk = Math.abs(entry - stop)
  if (!risk) return 0
  return direction === 'long' ? (exit - entry) / risk : (entry - exit) / risk
}

export function positionSize(balance: number, riskPercent: number, entry: number, stop: number) {
  const riskAmount = balance * (riskPercent / 100)
  const distance = Math.abs(entry - stop)
  return distance ? riskAmount / distance : 0
}

export function stableSignalId(signal: Pick<NormalizedSignal, 'symbol' | 'strategy' | 'direction' | 'timeframe' | 'scannedAt'>) {
  return [signal.symbol, signal.strategy, signal.direction, signal.timeframe, signal.scannedAt.slice(0, 16), 'v1'].join(':')
}

export function summarizeTrades(trades: LinkedJournalTrade[]) {
  const closed = trades.filter((trade) => trade.exit != null)
  const pnl = closed.reduce((sum, trade) => sum + trade.pnl, 0)
  const wins = closed.filter((trade) => trade.pnl > 0).length
  const losses = closed.filter((trade) => trade.pnl < 0)
  const profits = closed.filter((trade) => trade.pnl > 0).reduce((sum, trade) => sum + trade.pnl, 0)
  const lossTotal = Math.abs(losses.reduce((sum, trade) => sum + trade.pnl, 0))
  const averageR = closed.length ? closed.reduce((sum, trade) => sum + (trade.rMultiple ?? 0), 0) / closed.length : 0
  return {
    closed: closed.length,
    pnl,
    winRate: closed.length ? (wins / closed.length) * 100 : 0,
    profitFactor: lossTotal ? profits / lossTotal : profits ? profits : 0,
    expectancy: averageR,
  }
}
