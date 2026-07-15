import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowDown, ArrowUp, RefreshCw, Search, Wifi } from 'lucide-react'
import { fetchMarketScreener } from '../api'
import { PageHeader, Panel, StatusBadge } from '../components/Ui'
import type { ScreenerRow } from '../types'
import { money } from '../utils'

type SortKey = 'symbol' | 'change24h' | 'rsi4h'

const rsiLabel = (value: number | null) => {
  if (value == null) return 'Unavailable'
  if (value >= 70) return `Overbought ${value.toFixed(1)}`
  if (value <= 30) return `Oversold ${value.toFixed(1)}`
  return `Neutral ${value.toFixed(1)}`
}

const freshness = (timestamp: string) => {
  const seconds = Math.max(0, Math.round((Date.now() - new Date(timestamp).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

export default function Screener() {
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<SortKey>('change24h')
  const [descending, setDescending] = useState(true)
  const [rows, setRows] = useState<ScreenerRow[]>([])
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const [source, setSource] = useState('')
  const [message, setMessage] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setMessage('')
    try {
      const payload = await fetchMarketScreener()
      setRows(payload.rows)
      setUpdatedAt(payload.updatedAt)
      setSource(payload.source)
      setMessage(payload.warnings.length ? `${payload.warnings.length} market${payload.warnings.length === 1 ? '' : 's'} could not be refreshed.` : '')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to reach the integrated scanner.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const shown = useMemo(() => rows
    .filter((row) => row.symbol.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => {
      const av = a[sort]
      const bv = b[sort]
      const result = typeof av === 'string' ? av.localeCompare(String(bv)) : Number(av ?? -Infinity) - Number(bv ?? -Infinity)
      return descending ? -result : result
    }), [rows, query, sort, descending])

  const sortBy = (key: SortKey) => {
    if (sort === key) setDescending((value) => !value)
    else { setSort(key); setDescending(true) }
  }
  const macdTone = (value: string) => value.includes('Bull Zone') && value.includes('Bull Cross') ? 'positive' : value.includes('Bear Cross') ? 'negative' : 'info'

  return <div className="page screener-page">
    <PageHeader eyebrow="Live technical context" title="Market Screener" description="Current Coinbase prices and strategy indicators, calculated from public market candles by EdgeLedger's integrated engine." actions={<button className="btn secondary" onClick={() => void refresh()} disabled={loading}><RefreshCw className={loading ? 'spin' : ''} size={16} /> {loading ? 'Loading live data...' : 'Refresh data'}</button>} />
    {message && <div className="inline-alert"><AlertTriangle size={17} /><div><strong>{rows.length ? 'Partial live refresh' : 'Live screener unavailable'}</strong><span>{message}</span></div></div>}
    <div className="screener-summary">
      <label className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search coin" /></label>
      <span>Showing {shown.length} of {rows.length}</span>
      <div className="fresh-pill"><Wifi size={13} /><i /> {source ? `Live · ${source}` : 'Connecting'}{updatedAt ? ` · ${new Date(updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}` : ''}</div>
    </div>
    <Panel className="table-panel"><div className="responsive-table"><table className="data-table market-table"><thead><tr><th><button onClick={() => sortBy('symbol')}>Coin {sort === 'symbol' && (descending ? <ArrowDown /> : <ArrowUp />)}</button></th><th>Live price</th><th><button onClick={() => sortBy('change24h')}>24H % {sort === 'change24h' && (descending ? <ArrowDown /> : <ArrowUp />)}</button></th><th><button onClick={() => sortBy('rsi4h')}>RSI 4H {sort === 'rsi4h' && (descending ? <ArrowDown /> : <ArrowUp />)}</button></th><th>RSI 1H</th><th>MACD 1D</th><th>MACD 4H</th><th>MACD 1H</th><th>Fresh</th></tr></thead><tbody>{shown.map((row) => <tr key={row.market}><td><div className="market-cell"><span className="coin-mark neutral">{row.symbol[0]}</span><div><strong>{row.symbol}</strong><small>{row.source}</small></div></div></td><td><strong>{money(row.price, row.price < 10 ? 4 : 2)}</strong></td><td><strong className={(row.change24h ?? 0) >= 0 ? 'text-positive' : 'text-negative'}>{row.change24h == null ? '—' : `${row.change24h >= 0 ? '+' : ''}${row.change24h.toFixed(2)}%`}</strong></td><td><span className="rsi-pill">{rsiLabel(row.rsi4h)}</span></td><td><span className="rsi-pill">{rsiLabel(row.rsi1h)}</span></td><td><StatusBadge tone={macdTone(row.macd1d)}>{row.macd1d}</StatusBadge></td><td><StatusBadge tone={macdTone(row.macd4h)}>{row.macd4h}</StatusBadge></td><td><StatusBadge tone={macdTone(row.macd1h)}>{row.macd1h}</StatusBadge></td><td><span className="freshness fresh">{freshness(row.updatedAt)}</span></td></tr>)}</tbody></table></div>{!loading && !shown.length && <div className="table-empty">No live markets are available for the current filter.</div>}</Panel>
    <p className="research-note">Prices and indicators come from EdgeLedger's integrated Coinbase feed. They are research context, not an order or outcome forecast.</p>
  </div>
}
