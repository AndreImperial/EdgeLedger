import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, RefreshCw, Search } from 'lucide-react'
import { fetchOpenInterest } from '../api'
import type { OpenInterestRow } from '../types'
import { Metric, PageHeader, Panel, StatusBadge } from '../components/Ui'
import { money, number } from '../utils'

const compactUsd = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(value)

export default function OpenInterest() {
  const [rows, setRows] = useState<OpenInterestRow[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = async () => { setLoading(true); setError(''); try { const payload = await fetchOpenInterest(); setRows(payload.rows); setWarnings(payload.warnings) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Open interest data is unavailable.') } finally { setLoading(false) } }
  useEffect(() => { void load() }, [])
  const shown = useMemo(() => rows.filter((row) => row.symbol.toLowerCase().includes(query.toLowerCase())).sort((a, b) => (b.open_interest_usd ?? 0) - (a.open_interest_usd ?? 0)), [query, rows])
  const total = rows.reduce((sum, row) => sum + (row.open_interest_usd ?? 0), 0)
  const changes = rows.map((row) => row.open_interest_change_24h_pct).filter((value): value is number => value != null)
  const averageChange = changes.length ? changes.reduce((sum, value) => sum + value, 0) / changes.length : null
  const updatedAt = rows[0]?.updated_at ? new Date(rows[0].updated_at) : null
  const isFixture = rows[0]?.source === 'Fixture'

  return <div className="page oi-page"><PageHeader eyebrow="Derivatives context" title="Open Interest" description="Track outstanding derivatives exposure alongside price and volume. Context only, never a standalone entry signal." actions={<button className="btn secondary" onClick={load} disabled={loading}><RefreshCw className={loading ? 'spin' : ''} size={16} /> {loading ? 'Refreshing...' : 'Refresh OI'}</button>} />
    <div className="metric-grid"><Metric label="Tracked OI" value={compactUsd(total)} detail={`${rows.length} markets`} /><Metric label="Average 24H change" value={averageChange == null ? 'Unavailable' : `${averageChange >= 0 ? '+' : ''}${averageChange.toFixed(1)}%`} detail={averageChange == null ? 'Add Coinalyze for historical change' : 'Across tracked markets'} tone={averageChange != null && averageChange >= 0 ? 'positive' : undefined} /><Metric label="Largest market" value={shown[0]?.symbol ?? '—'} detail={shown[0]?.open_interest_usd != null ? compactUsd(shown[0].open_interest_usd) : 'Waiting for data'} /><Metric label="Last update" value={updatedAt ? updatedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'} detail={rows[0]?.source ?? 'No source'} /></div>
    {warnings.length > 0 && <div className="inline-alert info-alert"><AlertTriangle size={17} /><div><strong>{isFixture ? 'Synthetic fixture data' : 'Live OI with limited history'}</strong><span>{isFixture ? 'Fixture OI data is synthetic and offline.' : 'Current OI values are live. Configure Coinalyze only if you also need 24-hour OI percentage change.'}</span></div></div>}
    {error && <div className="inline-alert"><AlertTriangle size={17} /><div><strong>Open interest unavailable</strong><span>{error}</span></div></div>}
    <div className="screener-summary"><label className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search OI market" /></label><span>Showing {shown.length} of {rows.length}</span></div>
    <Panel className="table-panel"><div className="responsive-table"><table className="data-table oi-table"><thead><tr><th>Market</th><th>Open interest</th><th>OI USD</th><th>24H change</th><th>24H volume</th><th>Price</th><th>Source</th><th>Freshness</th></tr></thead><tbody>{shown.map((row) => <tr key={row.symbol}><td><div className="market-cell"><span className="coin-mark neutral">{row.symbol[0]}</span><strong>{row.symbol}</strong></div></td><td>{row.open_interest == null ? '—' : number(row.open_interest, 2)}</td><td><strong>{row.open_interest_usd == null ? '—' : compactUsd(row.open_interest_usd)}</strong></td><td><strong className={(row.open_interest_change_24h_pct ?? 0) >= 0 ? 'text-positive' : 'text-negative'}>{row.open_interest_change_24h_pct == null ? 'Requires Coinalyze' : `${row.open_interest_change_24h_pct >= 0 ? '+' : ''}${row.open_interest_change_24h_pct.toFixed(1)}%`}</strong></td><td>{row.volume_24h_usd == null ? '—' : compactUsd(row.volume_24h_usd)}</td><td>{row.price == null ? '—' : money(row.price, row.price < 10 ? 4 : 2)}</td><td><StatusBadge tone={isFixture ? 'warning' : 'positive'}>{row.source}</StatusBadge></td><td><span className="freshness fresh">{row.status}</span></td></tr>)}</tbody></table></div>{!loading && !shown.length && <div className="table-empty">No open interest markets match this search.</div>}</Panel>
    <p className="research-note">Rising OI can reflect new long or short exposure. Confirm direction with price, funding, volume, and the canonical CMM setup.</p>
  </div>
}
