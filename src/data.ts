import { addDays, format, startOfMonth } from 'date-fns'
import type { MarketEvent, NormalizedSignal, StrategyTemplate } from './types'

export const strategies: StrategyTemplate[] = [
  { key: 'bounce', name: 'Bounce', family: 'Intraday', timeframe: '4h / 1h / 15m', accent: '#2de1c2', summary: 'Trade a confirmed rejection from a repeatedly tested support or resistance zone.', rules: ['Higher-timeframe trend must not oppose the trade', 'Zone needs at least three quality touches', '15m candle must reject the zone with a meaningful wick', 'RSI, relative volume, and Prison Break state confirm timing'], defaults: ['Relative volume confirmation: 1.35x', '15m execution', 'ATR-based invalidation'] },
  { key: 'transition_play', name: 'Transition Play', family: 'Intraday', timeframe: '4h / 1h / 15m', accent: '#f6c453', summary: 'Capture momentum turning out of a weak or extended zone with MACD support.', rules: ['Long RSI recovery zone: 35-48', 'Short RSI rollover zone: 55-70', '1h MACD must support the reversal direction', 'Higher-timeframe structure cannot directly oppose entry'], defaults: ['Prison Break confirmation', 'Relative volume: 1.35x', 'Avoid overextended RSI'] },
  { key: 'apex_squeeze', name: 'Apex Squeeze', family: 'Intraday', timeframe: '4h / 1h / 15m', accent: '#7da8ff', summary: 'Trade expansion from a compressed range in the direction of established structure.', rules: ['15m range compression ratio below 0.70', '1h continuation trend aligned', 'Prison Break state must reach WATCH or ENTER', 'Breakout ENTER requires stronger relative volume'], defaults: ['Breakout volume: 1.55x', 'No RSI chasing', 'Retest confirmation preferred'] },
  { key: 'tabo', name: 'TABO', family: 'Intraday', timeframe: '4h / 1h / 15m', accent: '#ec8cff', summary: 'A trend-continuation setup combining momentum, nearby structure, and tradable RSI.', rules: ['1h MACD follows trade direction', '4h context does not oppose continuation', '15m RSI remains in tradable range', 'Nearby support or resistance defines structure'], defaults: ['Volume-confirmed ENTER', 'ATR stop', '1.5R and 2.5R targets'] },
  { key: 'alma_cci_scalp', name: 'ALMA / CCI Scalp', family: 'Scalper', timeframe: '15m / 5m / 3m', accent: '#ff8a68', summary: 'Fast continuation model with aligned bias, structure, and a fresh execution trigger.', rules: ['15m ALMA/EMA/CCI defines directional bias', '5m structure aligns with bias', '3m EMA9 crosses ALMA20 within three bars', 'CCI20 crosses through -100 long or +100 short'], defaults: ['ATR range: 0.12%-2.8%', 'Swing/ATR stop', '2R target', 'Paper/manual execution only'] },
  { key: 'ma_short', name: 'Validated MA Short', family: 'Intraday', timeframe: '15m', accent: '#2de1c2', summary: 'ETH short-only moving-average profile validated through the 60k / 100k candle backtest gate.', rules: ['20 MA remains below 50 MA', 'RSI is in the short trigger band', 'Candle body is at least 0.30 ATR', 'Close is in the lower 35% of the candle', 'Two bearish candles confirm the trigger'], defaults: ['ETH/USDT only', '0.18R target', '100% main and validation gates'] },
]

const now = new Date().toISOString()
export const demoSignals: NormalizedSignal[] = [
  { id: 'BTC:apex:long', symbol: 'BTC/USD', strategy: 'apex_squeeze', strategyLabel: 'Apex Squeeze', direction: 'long', lifecycle: 'ENTER', grade: 'A', confidence: .84, score: 89.4, entry: 118420, stopLoss: 117260, targets: [120160, 121320], riskReward: 2.5, source: 'Coinbase', scannedAt: now, timeframe: '15m', evidence: ['15m compression ratio is 0.58.', '1h and 4h trend filters are aligned up.', 'Relative volume confirms breakout at 1.72x.', '15m confirmation candle closed above the prison range.'], validationReasons: [], approved: true, freshness: 'live' },
  { id: 'ETH:transition:short', symbol: 'ETH/USD', strategy: 'transition_play', strategyLabel: 'Transition Play', direction: 'short', lifecycle: 'WATCH', grade: 'B+', confidence: .73, score: 76.1, entry: 3618, stopLoss: 3660, targets: [3555, 3513], riskReward: 2.5, source: 'Coinbase', scannedAt: now, timeframe: '15m', evidence: ['15m RSI is rolling over from 64.8.', '1h MACD momentum supports bearish reversal.', 'Price remains near the prison low; follow-through is pending.'], validationReasons: ['Volume confirmation remains below ENTER threshold.'], approved: true, freshness: 'live' },
  { id: 'ETH:ma-short:watch', symbol: 'ETH/USD', strategy: 'ma_short', strategyLabel: 'Validated MA Short', direction: 'short', lifecycle: 'WATCH', grade: 'A', confidence: .72, score: 72, source: 'Bitunix', scannedAt: now, timeframe: '15m', evidence: ['Validated MA short profile is monitored by the integrated scanner.', 'It enters only when the latest 15m candle matches the tuned confluences.'], validationReasons: ['Waiting for the full MA short trigger.'], approved: false, freshness: 'fresh', targets: [] },
  { id: 'SOL:scalp:long', symbol: 'SOL/USD', strategy: 'alma_cci_scalp', strategyLabel: 'ALMA / CCI Scalp', direction: 'long', lifecycle: 'WATCH', grade: 'B', confidence: .68, score: 71.5, entry: 164.2, stopLoss: 162.9, targets: [166.8], riskReward: 2, source: 'Coinbase', scannedAt: now, timeframe: '3m', evidence: ['15m bias and 5m structure are stacked long.', '3m EMA9 / ALMA20 trigger is forming.', 'CCI20 is rising toward the -100 trigger zone.'], validationReasons: ['Trigger candle has not closed.'], approved: false, freshness: 'fresh' },
  { id: 'XRP:bounce:long', symbol: 'XRP/USD', strategy: 'bounce', strategyLabel: 'Bounce', direction: 'long', lifecycle: 'WAIT', grade: 'B', confidence: .62, score: 66.8, entry: 2.24, stopLoss: 2.18, targets: [2.33, 2.39], riskReward: 2.5, source: 'Coinbase', scannedAt: now, timeframe: '15m', evidence: ['Support has four wick touches.', 'Latest candle rejected the lower zone.', 'Relative volume is 1.12x.'], validationReasons: ['Low volume: confirmation threshold not reached.'], approved: false, freshness: 'fresh' },
]

const month = startOfMonth(new Date())
export const marketEvents: MarketEvent[] = [
  { id: 'cpi', date: format(addDays(month, 13), 'yyyy-MM-dd'), time: '08:30 ET', code: 'CPI', title: 'Consumer Price Index', impact: 'high', note: 'Inflation release can materially change rate expectations and crypto volatility.' },
  { id: 'fomc', date: format(addDays(month, 8), 'yyyy-MM-dd'), time: '14:00 ET', code: 'FOMC', title: 'FOMC Meeting Minutes', impact: 'high', note: 'Review policy language and changes in the committee reaction function.' },
  { id: 'nfp', date: format(addDays(month, 2), 'yyyy-MM-dd'), time: '08:30 ET', code: 'NFP', title: 'Employment Situation', impact: 'high', note: 'Payrolls, unemployment, and wage growth often move dollar and risk markets.' },
  { id: 'pce', date: format(addDays(month, 24), 'yyyy-MM-dd'), time: '08:30 ET', code: 'PCE', title: 'Core PCE Price Index', impact: 'medium', note: 'The Federal Reserve\'s preferred inflation gauge.' },
]

export const equityCurve = [
  { day: 'Jul 1', equity: 10000 }, { day: 'Jul 3', equity: 10140 }, { day: 'Jul 5', equity: 10090 },
  { day: 'Jul 7', equity: 10310 }, { day: 'Jul 9', equity: 10235 }, { day: 'Jul 11', equity: 10540 },
  { day: 'Jul 13', equity: 10695 }, { day: 'Jul 15', equity: 10842 },
]

export const outcomeRows = [
  { strategy: 'Apex Squeeze', trades: 28, winRate: 64.3, avgR: 0.82, grade: 'A-' },
  { strategy: 'Bounce', trades: 34, winRate: 58.8, avgR: 0.54, grade: 'B+' },
  { strategy: 'Transition Play', trades: 21, winRate: 57.1, avgR: 0.43, grade: 'B' },
  { strategy: 'TABO', trades: 16, winRate: 56.3, avgR: 0.36, grade: 'B' },
  { strategy: 'ALMA / CCI Scalp', trades: 43, winRate: 53.5, avgR: 0.28, grade: 'B-' },
  { strategy: 'Validated MA Short', trades: 32, winRate: 100.0, avgR: 0.08, grade: 'A+' },
]
