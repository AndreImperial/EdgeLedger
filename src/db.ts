import Dexie, { type EntityTable } from 'dexie'
import type { LinkedJournalTrade } from './types'

class EdgeLedgerDB extends Dexie {
  trades!: EntityTable<LinkedJournalTrade, 'id'>
  watchlist!: EntityTable<{ id?: number; signalId: string; addedAt: string }, 'id'>

  constructor() {
    super('edgeledger')
    this.version(1).stores({ trades: '++id, &externalId, signalId, openedAt, symbol, strategy', watchlist: '++id, &signalId, addedAt' })
  }
}

export const db = new EdgeLedgerDB()

export async function seedDemoTrades() {
  if (await db.trades.count()) return
  await db.trades.bulkAdd([
    { externalId: 'demo-1', openedAt: '2026-07-12T08:10:00Z', closedAt: '2026-07-12T12:40:00Z', symbol: 'BTC/USD', exchange: 'Coinbase', direction: 'long', strategy: 'apex_squeeze', entry: 117420, exit: 119080, stopLoss: 116540, target: 119180, quantity: 0.18, leverage: 2, fees: 21.4, pnl: 277.4, rMultiple: 1.89, session: 'London', emotion: 'Focused', notes: 'Waited for the 15m close and volume expansion.' },
    { externalId: 'demo-2', openedAt: '2026-07-10T14:20:00Z', closedAt: '2026-07-10T16:05:00Z', symbol: 'ETH/USD', exchange: 'Coinbase', direction: 'short', strategy: 'transition_play', entry: 3548, exit: 3487, stopLoss: 3582, target: 3480, quantity: 4.1, leverage: 3, fees: 17.8, pnl: 232.3, rMultiple: 1.79, session: 'New York', emotion: 'Calm', notes: 'Clean rollover; reduced at first target.' },
    { externalId: 'demo-3', openedAt: '2026-07-08T03:05:00Z', closedAt: '2026-07-08T03:44:00Z', symbol: 'SOL/USD', exchange: 'Coinbase', direction: 'long', strategy: 'alma_cci_scalp', entry: 162.4, exit: 160.9, stopLoss: 161.6, target: 164, quantity: 48, leverage: 4, fees: 8.2, pnl: -80.2, rMultiple: -1.88, session: 'Asia', emotion: 'Impatient', notes: 'Cross was already old. Checklist would have prevented this.' },
    { externalId: 'demo-4', openedAt: '2026-07-04T09:12:00Z', closedAt: '2026-07-04T13:10:00Z', symbol: 'XRP/USD', exchange: 'Coinbase', direction: 'long', strategy: 'bounce', entry: 2.18, exit: 2.24, stopLoss: 2.14, target: 2.26, quantity: 1900, leverage: 2, fees: 7.6, pnl: 106.4, rMultiple: 1.5, session: 'London', emotion: 'Focused', notes: 'Support held on third test; managed conservatively.' },
  ])
}
