import { useMemo, useRef, useState } from 'react'
import { Download, FileUp, Plus, Search, Trash2, X } from 'lucide-react'
import Papa from 'papaparse'
import { useLiveQuery } from 'dexie-react-hooks'
import { db, seedDemoTrades } from '../db'
import type { LinkedJournalTrade } from '../types'
import { calculateR, calculateTrade, money, number } from '../utils'
import { EmptyState, PageHeader, Panel, StatusBadge } from '../components/Ui'

const blank = { symbol: 'BTC/USD', exchange: 'Manual', direction: 'long', strategy: 'manual', entry: '', exit: '', stopLoss: '', target: '', quantity: '', leverage: '1', fees: '0', session: 'London', emotion: 'Focused', notes: '' }

export default function Trades() {
  const trades = useLiveQuery(() => db.trades.orderBy('openedAt').reverse().toArray(), []) ?? []
  const [query, setQuery] = useState('')
  const [direction, setDirection] = useState('All')
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(blank)
  const [importMessage, setImportMessage] = useState('')
  const [formError, setFormError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const filtered = useMemo(() => trades.filter((trade) => trade.symbol.toLowerCase().includes(query.toLowerCase()) && (direction === 'All' || trade.direction === direction.toLowerCase())), [trades, query, direction])
  const save = async () => {
    const entry = Number(form.entry); const exit = form.exit ? Number(form.exit) : undefined; const stop = form.stopLoss ? Number(form.stopLoss) : undefined; const quantity = Number(form.quantity); const fees = Number(form.fees)
    if (!form.symbol.trim()) { setFormError('Symbol is required.'); return }
    if (!Number.isFinite(entry) || entry <= 0) { setFormError('Enter a valid entry price.'); return }
    if (!Number.isFinite(quantity) || quantity <= 0) { setFormError('Quantity must be greater than zero.'); return }
    if (exit != null && exit <= 0) { setFormError('Exit price must be greater than zero.'); return }
    const pnl = exit ? calculateTrade(entry, exit, quantity, form.direction as 'long' | 'short', fees) : 0
    const trade: LinkedJournalTrade = { openedAt: new Date().toISOString(), closedAt: exit ? new Date().toISOString() : undefined, symbol: form.symbol.toUpperCase(), exchange: form.exchange, direction: form.direction as 'long' | 'short', strategy: form.strategy as LinkedJournalTrade['strategy'], entry, exit, stopLoss: stop, target: form.target ? Number(form.target) : undefined, quantity, leverage: Number(form.leverage), fees, pnl, rMultiple: exit && stop ? calculateR(entry, exit, stop, form.direction as 'long' | 'short') : undefined, session: form.session, emotion: form.emotion, notes: form.notes }
    await db.trades.add(trade); setForm(blank); setFormError(''); setOpen(false)
  }
  const importCsv = (file?: File) => {
    if (!file) return
    Papa.parse<Record<string, string>>(file, { header: true, skipEmptyLines: true, complete: async ({ data }) => {
      const valid = data.filter((row) => row.symbol && row.entry && row.quantity).map((row, index) => {
        const side = row.direction?.toLowerCase() === 'short' ? 'short' : 'long'; const entry = Number(row.entry); const exit = row.exit ? Number(row.exit) : undefined; const stop = row.stopLoss ? Number(row.stopLoss) : undefined; const fees = Number(row.fees || 0); const quantity = Number(row.quantity)
        return { externalId: row.id || `csv-${file.name}-${index}`, openedAt: row.openedAt || new Date().toISOString(), closedAt: row.closedAt || (exit ? new Date().toISOString() : undefined), symbol: row.symbol.toUpperCase(), exchange: row.exchange || 'CSV import', direction: side, strategy: (row.strategy || 'manual') as LinkedJournalTrade['strategy'], entry, exit, stopLoss: stop, target: row.target ? Number(row.target) : undefined, quantity, leverage: Number(row.leverage || 1), fees, pnl: exit ? calculateTrade(entry, exit, quantity, side, fees) : 0, rMultiple: exit && stop ? calculateR(entry, exit, stop, side) : undefined, session: row.session || 'Unassigned', emotion: row.emotion || 'Neutral', notes: row.notes || '' } satisfies LinkedJournalTrade
      })
      let imported = 0
      for (const trade of valid) { try { await db.trades.add(trade); imported++ } catch { /* duplicate */ } }
      setImportMessage(`${imported} trades imported; ${data.length - valid.length} rows skipped.`)
      if (fileRef.current) fileRef.current.value = ''
    } })
  }
  const exportJson = () => { const blob = new Blob([JSON.stringify(trades, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `edgeledger-trades-${new Date().toISOString().slice(0, 10)}.json`; link.click(); URL.revokeObjectURL(url) }

  return <div className="page trades-page">
    <PageHeader eyebrow="Execution journal" title="Trades" description="Turn executions into useful evidence. Honest notes beat perfect hindsight." actions={<><input ref={fileRef} className="sr-only" type="file" accept=".csv" onChange={(event) => importCsv(event.target.files?.[0])} /><button className="btn secondary" onClick={() => fileRef.current?.click()}><FileUp size={17} /> Import CSV</button><button className="btn primary" onClick={() => setOpen(true)}><Plus size={17} /> Add trade</button></>} />
    <div className="filters-row"><label className="search-field"><Search size={16} /><input placeholder="Search symbol" value={query} onChange={(event) => setQuery(event.target.value)} /></label><div className="segmented small">{['All', 'Long', 'Short'].map((item) => <button key={item} className={direction === item ? 'active' : ''} onClick={() => setDirection(item)}>{item}</button>)}</div><button className="icon-btn export-btn" title="Export JSON backup" onClick={exportJson}><Download size={17} /></button><span className="result-count">{filtered.length} records</span></div>
    {importMessage && <div className="toast-line">{importMessage}<button onClick={() => setImportMessage('')}><X size={14} /></button></div>}
    <Panel className="table-panel"><div className="responsive-table"><table className="data-table trades-table"><thead><tr><th>Opened</th><th>Market</th><th>Direction</th><th>Strategy</th><th>Entry / exit</th><th>Size</th><th>PNL</th><th>R</th><th>Review</th><th /></tr></thead><tbody>{filtered.map((trade) => <tr key={trade.id}><td><strong>{new Date(trade.openedAt).toLocaleDateString()}</strong><small>{new Date(trade.openedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</small></td><td><strong>{trade.symbol}</strong><small>{trade.exchange}</small></td><td><StatusBadge tone={trade.direction === 'long' ? 'positive' : 'negative'}>{trade.direction.toUpperCase()}</StatusBadge></td><td><span className="strategy-name">{trade.strategy.replaceAll('_', ' ')}</span></td><td><strong>{number(trade.entry)}</strong><small>{trade.exit ? number(trade.exit) : 'Open'}</small></td><td><strong>{number(trade.quantity, 4)}</strong><small>{trade.leverage}x leverage</small></td><td><strong className={trade.pnl >= 0 ? 'text-positive' : 'text-negative'}>{money(trade.pnl)}</strong><small>fees {money(trade.fees)}</small></td><td><strong className={(trade.rMultiple ?? 0) >= 0 ? 'text-positive' : 'text-negative'}>{trade.rMultiple?.toFixed(2) ?? '—'}R</strong></td><td><span className={`review-dot ${trade.notes ? 'done' : ''}`} />{trade.notes ? 'Reviewed' : 'Needs notes'}</td><td><button className="icon-btn danger" onClick={() => trade.id && window.confirm(`Delete ${trade.symbol} from the journal?`) && db.trades.delete(trade.id)} aria-label={`Delete ${trade.symbol}`}><Trash2 size={15} /></button></td></tr>)}</tbody></table></div>{!filtered.length && <EmptyState icon={<FileUp />} title="Your journal is ready" text="Add a trade, import an exchange CSV, or load a small demo set to explore the analytics." action={<button className="btn secondary" onClick={seedDemoTrades}>Load demo trades</button>} />}</Panel>
    {open && <div className="dialog-backdrop" onMouseDown={() => setOpen(false)}><div className="trade-form-modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}><div className="modal-head"><div><span>MANUAL JOURNAL ENTRY</span><h2>Add a trade</h2></div><button className="icon-btn" onClick={() => setOpen(false)}><X /></button></div><div className="form-grid">
      <label>Symbol<input value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })} /></label><label>Direction<select value={form.direction} onChange={(e) => setForm({ ...form, direction: e.target.value })}><option value="long">Long</option><option value="short">Short</option></select></label><label>Strategy<select value={form.strategy} onChange={(e) => setForm({ ...form, strategy: e.target.value })}><option value="manual">Manual</option><option value="bounce">Bounce</option><option value="apex_squeeze">Apex Squeeze</option><option value="transition_play">Transition Play</option><option value="tabo">TABO</option><option value="alma_cci_scalp">ALMA / CCI Scalp</option></select></label><label>Exchange<input value={form.exchange} onChange={(e) => setForm({ ...form, exchange: e.target.value })} /></label>
      <label>Entry<input type="number" value={form.entry} onChange={(e) => setForm({ ...form, entry: e.target.value })} /></label><label>Exit <small>optional</small><input type="number" value={form.exit} onChange={(e) => setForm({ ...form, exit: e.target.value })} /></label><label>Stop loss<input type="number" value={form.stopLoss} onChange={(e) => setForm({ ...form, stopLoss: e.target.value })} /></label><label>Target<input type="number" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} /></label>
      <label>Quantity<input type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></label><label>Leverage<input type="number" value={form.leverage} onChange={(e) => setForm({ ...form, leverage: e.target.value })} /></label><label>Fees<input type="number" value={form.fees} onChange={(e) => setForm({ ...form, fees: e.target.value })} /></label><label>Session<select value={form.session} onChange={(e) => setForm({ ...form, session: e.target.value })}><option>Asia</option><option>London</option><option>New York</option><option>Unassigned</option></select></label>
      <label className="full">Review notes<textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Why did you enter, what happened, and what did you learn?" /></label>
    </div>{formError && <p className="form-message error" role="alert">{formError}</p>}<footer><button className="btn secondary" onClick={() => { setOpen(false); setFormError('') }}>Cancel</button><button className="btn primary" onClick={save}>Save trade</button></footer></div></div>}
  </div>
}
