import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BookmarkPlus, ChevronRight, Clock3, FilePlus2, Play, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { db } from '../db'
import { fetchOpenInterest, runScan, type ApiStatus } from '../api'
import type { LinkedJournalTrade, NormalizedSignal, OpenInterestRow, ScanRunSummary } from '../types'
import { money, number, positionSize } from '../utils'
import { PageHeader, Panel, StatusBadge } from '../components/Ui'
import { TradingViewChart } from '../components/TradingViewChart'
import { recordSignalAlerts } from '../notifications'

const toneFor = (state: string) => state === 'ENTER' ? 'positive' : state === 'WATCH' ? 'warning' : state === 'REJECT' ? 'negative' : 'neutral'
const compactUsd = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(value)
const time = (value?: string) => value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short' }) : '—'
const metric = (value: number | null | undefined, digits = 2) => value == null ? '—' : value.toFixed(digits)

export default function Scanner({ initialSignals, onStatus }: { initialSignals: NormalizedSignal[]; onStatus: (status: ApiStatus) => void }) {
  const [mode, setMode] = useState<'intraday' | 'scalp'>('intraday')
  const [signals, setSignals] = useState(initialSignals.filter((item) => item.strategy !== 'alma_cci_scalp'))
  const [selected, setSelected] = useState<NormalizedSignal | null>(null)
  const [summary, setSummary] = useState<ScanRunSummary | null>(null)
  const [running, setRunning] = useState(false)
  const [warnings, setWarnings] = useState<string[]>([])
  const [demoFallback, setDemoFallback] = useState(false)
  const [query, setQuery] = useState('')
  const [grade, setGrade] = useState('All grades')
  const [planNotes, setPlanNotes] = useState('')
  const [feedback, setFeedback] = useState('')
  const [oiRows, setOiRows] = useState<OpenInterestRow[]>([])

  const loadOi = () => fetchOpenInterest().then((payload) => setOiRows(payload.rows)).catch(() => setOiRows([]))
  useEffect(() => { void loadOi() }, [])
  const oiFor = (symbol: string) => oiRows.find((row) => row.symbol === symbol)
  const shown = useMemo(() => signals.filter((item) => item.symbol.toLowerCase().includes(query.toLowerCase()) && (grade === 'All grades' || item.grade.startsWith(grade))), [signals, query, grade])

  const changeMode = (next: 'intraday' | 'scalp') => {
    setMode(next)
    setSignals(initialSignals.filter((item) => next === 'scalp' ? item.strategy === 'alma_cci_scalp' : item.strategy !== 'alma_cci_scalp'))
    setWarnings([])
    setSummary(null)
    setSelected(null)
  }
  const scan = async () => {
    setRunning(true)
    setWarnings([])
    setFeedback('')
    const result = await runScan(mode)
    setSignals(result.signals)
    setSummary(result.summary ?? null)
    setWarnings(result.warnings)
    setDemoFallback(!result.status.connected)
    if (result.status.connected) {
      recordSignalAlerts(result.signals)
      void loadOi()
    }
    if (mode === 'scalp') setSelected(result.signals.find((signal) => ['ENTER', 'WATCH'].includes(signal.lifecycle)) ?? result.signals[0] ?? null)
    onStatus(result.status)
    setRunning(false)
  }
  const openSignal = (signal: NormalizedSignal) => { setSelected(signal); setPlanNotes(''); setFeedback('') }
  const addWatch = async (signal: NormalizedSignal) => {
    try { await db.watchlist.add({ signalId: signal.id, addedAt: new Date().toISOString() }); setFeedback(`${signal.symbol} added to watchlist.`) }
    catch { setFeedback(`${signal.symbol} is already on your watchlist.`) }
  }
  const journal = async (signal: NormalizedSignal) => {
    if (!signal.entry) return
    const stored = JSON.parse(localStorage.getItem('edgeledger-defaults') || '{}') as { balance?: string; risk?: string }
    const quantity = signal.stopLoss ? positionSize(Number(stored.balance || 10000), Number(stored.risk || 1), signal.entry, signal.stopLoss) : 0
    const trade: LinkedJournalTrade = { externalId: signal.id, signalId: signal.id, openedAt: new Date().toISOString(), symbol: signal.symbol, exchange: signal.source, direction: signal.direction === 'short' ? 'short' : 'long', strategy: signal.strategy, entry: signal.entry, stopLoss: signal.stopLoss, target: signal.targets[0], quantity, leverage: 1, fees: 0, pnl: 0, session: 'Unassigned', emotion: 'Neutral', notes: [planNotes.trim(), `Created from ${signal.strategyLabel} ${signal.lifecycle} signal.`].filter(Boolean).join('\n') }
    try { await db.trades.add(trade); setFeedback(`${signal.symbol} trade plan added to the journal.`) }
    catch { setFeedback('This signal is already linked to a journal trade.') }
  }

  return <div className="page scanner-page">
    <PageHeader eyebrow="Integrated CMM engine · Paper research" title="Signal Desk" description="Coinbase market scans, CMM strategy diagnostics, and manual trade planning in one workspace." actions={<button className="btn primary scan-button" onClick={scan} disabled={running}>{running ? <RefreshCw className="spin" size={17} /> : <Play size={17} />}{running ? 'Scanning market...' : mode === 'scalp' ? 'Search scalpable setups' : 'Run intraday scan'}</button>} />
    <div className="scanner-toolbar">
      <div className="segmented"><button className={mode === 'intraday' ? 'active' : ''} onClick={() => changeMode('intraday')}>Intraday</button><button className={mode === 'scalp' ? 'active' : ''} onClick={() => changeMode('scalp')}>Scalper</button></div>
      <label className="field compact"><span className="sr-only">Search symbols</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search symbol" /></label>
      <label className="field compact"><span className="sr-only">Filter grade</span><select value={grade} onChange={(event) => setGrade(event.target.value)}><option>All grades</option><option>A</option><option>B</option><option>C</option><option>D</option></select></label>
      <div className="scanner-legend"><i className="live-dot" /> {signals.length} analyzed <span>·</span> {signals.filter((signal) => signal.lifecycle === 'ENTER').length} enter-ready</div>
    </div>
    {warnings.length > 0 && <div className="inline-alert"><AlertTriangle size={17} /><div><strong>{demoFallback ? 'Integrated engine unavailable' : 'Partial scan completed'}</strong><span>{warnings[0].replace(/[.]+$/, '')}.{demoFallback ? ' Restart EdgeLedger to restore the bundled scanner.' : ' Valid results are shown below.'}</span></div></div>}
    {mode === 'scalp' ? <ScalpWorkspace signals={shown} summary={summary} selected={selected} onSelect={openSignal} onWatch={addWatch} onJournal={journal} notes={planNotes} setNotes={setPlanNotes} feedback={feedback} /> : <IntradayTable signals={shown} oiFor={oiFor} onSelect={openSignal} />}
    <div className="research-note"><ShieldCheck size={16} /><span>CMM outputs are research context. EdgeLedger cannot place trades or access exchange credentials.</span></div>
    {mode === 'intraday' && selected && <TradeDrawer signal={selected} notes={planNotes} setNotes={setPlanNotes} feedback={feedback} onClose={() => setSelected(null)} onWatch={addWatch} onJournal={journal} />}
  </div>
}

function IntradayTable({ signals, oiFor, onSelect }: { signals: NormalizedSignal[]; oiFor: (symbol: string) => OpenInterestRow | undefined; onSelect: (signal: NormalizedSignal) => void }) {
  return <Panel className="table-panel scanner-table-wrap"><table className="data-table scanner-table"><thead><tr><th>Market</th><th>Live price</th><th>Strategy</th><th>State</th><th>Grade</th><th>Confidence</th><th>Open interest</th><th>Entry / stop</th><th>Target</th><th>Freshness</th><th /></tr></thead><tbody>{signals.map((signal) => { const oi = oiFor(signal.symbol); return <tr key={signal.id}><td><div className="market-cell"><span className={`coin-mark ${signal.direction}`}>{signal.symbol[0]}</span><div><strong>{signal.symbol}</strong><small>{signal.source}</small></div></div></td><td><strong>{oi?.price != null ? money(oi.price, oi.price < 10 ? 4 : 2) : '—'}</strong><small>{oi?.price != null ? oi.source : 'Live quote unavailable'}</small></td><td><strong>{signal.strategyLabel}</strong><small>{signal.timeframe} execution</small></td><td><StatusBadge tone={toneFor(signal.lifecycle)}>{signal.lifecycle}</StatusBadge></td><td><span className="grade-cell">{signal.grade}</span></td><td><div className="confidence"><span>{Math.round(signal.confidence * 100)}%</span><div><i style={{ width: `${signal.confidence * 100}%` }} /></div></div></td><td><strong className={(oi?.open_interest_change_24h_pct ?? 0) >= 0 ? 'text-positive' : 'text-negative'}>{oi?.open_interest_change_24h_pct == null ? 'Current' : `${oi.open_interest_change_24h_pct >= 0 ? '+' : ''}${oi.open_interest_change_24h_pct.toFixed(1)}%`}</strong><small>{oi?.open_interest_usd != null ? `${compactUsd(oi.open_interest_usd)} · ${oi.source}` : 'OI unavailable'}</small></td><td><strong>{signal.entry ? number(signal.entry) : '—'}</strong><small>{signal.stopLoss ? number(signal.stopLoss) : 'No stop'}</small></td><td><strong>{signal.targets[0] ? number(signal.targets[0]) : '—'}</strong><small>{signal.riskReward ? `${signal.riskReward.toFixed(1)}R` : '—'}</small></td><td><span className={`freshness ${signal.freshness}`}><Clock3 size={13} /> {signal.freshness}</span></td><td><button className="icon-btn" onClick={() => onSelect(signal)} aria-label={`Open ${signal.symbol} plan`}><ChevronRight size={18} /></button></td></tr> })}</tbody></table>{!signals.length && <div className="table-empty">No signals match the current filters.</div>}</Panel>
}

function ScalpWorkspace({ signals, summary, selected, onSelect, onWatch, onJournal, notes, setNotes, feedback }: { signals: NormalizedSignal[]; summary: ScanRunSummary | null; selected: NormalizedSignal | null; onSelect: (signal: NormalizedSignal) => void; onWatch: (signal: NormalizedSignal) => void; onJournal: (signal: NormalizedSignal) => void; notes: string; setNotes: (value: string) => void; feedback: string }) {
  const movers = [...signals].sort((a, b) => Math.abs(b.scalpDetails?.openInterestChange24hPct ?? 0) - Math.abs(a.scalpDetails?.openInterestChange24hPct ?? 0)).slice(0, 10)
  const actionable = signals.filter((signal) => ['WATCH', 'ENTER'].includes(signal.lifecycle))
  return <div className="scalp-workspace">
    {summary && <div className="scan-metrics">{[['Candidates', summary.candidates], ['Scanned', summary.scanned], ['Failed', summary.failed], ['Duration', `${summary.durationSeconds.toFixed(1)}s`], ['Workers', summary.workers]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>}
    {summary && <div className="scalp-counts"><div><span>Top OI movers</span><strong>{movers.length}</strong></div><div><span>ENTER setups</span><strong>{signals.filter((item) => item.lifecycle === 'ENTER').length}</strong></div><div><span>WATCH setups</span><strong>{signals.filter((item) => item.lifecycle === 'WATCH').length}</strong></div><div><span>Rejected / waiting</span><strong>{signals.filter((item) => ['REJECT', 'WAIT'].includes(item.lifecycle)).length}</strong></div></div>}
    {movers.length > 0 && <Panel className="scalp-oi-panel"><div className="panel-title"><div><span>Coinalyze context</span><h2>Top OI movers feeding the scalper</h2></div></div><div className="responsive-table"><table className="data-table compact-table"><thead><tr><th>Market</th><th>Signal candle</th><th>Age</th><th>OI 24H</th><th>24H volume</th><th>OI / price read</th><th>Grade</th><th>State</th></tr></thead><tbody>{movers.map((signal) => <tr key={signal.id}><td><strong>{signal.symbol}</strong></td><td>{time(signal.scalpDetails?.executionCandleTime)}</td><td>{metric(signal.scalpDetails?.setupAgeMinutes, 0)}m</td><td className={(signal.scalpDetails?.openInterestChange24hPct ?? 0) >= 0 ? 'text-positive' : 'text-negative'}>{signal.scalpDetails?.openInterestChange24hPct == null ? '—' : `${signal.scalpDetails.openInterestChange24hPct.toFixed(2)}%`}</td><td>{signal.scalpDetails?.volume24hUsd ? compactUsd(signal.scalpDetails.volume24hUsd) : '—'}</td><td>{signal.scalpDetails?.metrics.oiPriceRead ?? '—'}</td><td><span className="grade-cell">{signal.grade}</span></td><td><StatusBadge tone={toneFor(signal.lifecycle)}>{signal.lifecycle}</StatusBadge></td></tr>)}</tbody></table></div></Panel>}
    <Panel className="table-panel scalp-results"><div className="panel-title"><div><span>ALMA · EMA · CCI</span><h2>15m bias, 5m structure, 3m execution</h2></div><small>{signals.length} live results</small></div><div className="responsive-table"><table className="data-table compact-table"><thead><tr><th>Rank</th><th>Market</th><th>Grade</th><th>Scan</th><th>Signal candle</th><th>Age</th><th>State</th><th>Direction</th><th>Confidence</th><th>Score</th><th>OI read</th><th>Bias</th><th>Structure</th><th>3m ATR</th><th>Cross age</th><th>CCI slope</th><th>Entry</th><th>Stop</th><th>Target</th><th /></tr></thead><tbody>{signals.map((signal) => { const detail = signal.scalpDetails; return <tr key={signal.id} className={selected?.id === signal.id ? 'selected-row' : ''}><td>{detail?.rank ?? '—'}</td><td><strong>{signal.symbol}</strong><small>{signal.source}</small></td><td><span className="grade-cell">{signal.grade}</span></td><td>{time(signal.scannedAt)}</td><td>{time(detail?.executionCandleTime)}</td><td>{metric(detail?.setupAgeMinutes, 0)}m</td><td><StatusBadge tone={toneFor(signal.lifecycle)}>{signal.lifecycle}</StatusBadge></td><td>{signal.direction.toUpperCase()}</td><td>{Math.round(signal.confidence * 100)}%</td><td>{signal.score.toFixed(1)}</td><td>{detail?.metrics.oiPriceRead ?? '—'}</td><td>{detail?.metrics.biasStrength ?? '—'}</td><td>{detail?.metrics.structureStrength ?? '—'}</td><td>{detail?.metrics.atrPct == null ? '—' : `${detail.metrics.atrPct.toFixed(2)}%`}</td><td>{detail?.metrics.crossAgeBars ?? '—'}</td><td>{metric(detail?.metrics.cciSlope, 1)}</td><td>{signal.entry ? number(signal.entry) : '—'}</td><td>{signal.stopLoss ? number(signal.stopLoss) : '—'}</td><td>{signal.targets[0] ? number(signal.targets[0]) : '—'}</td><td><button className="icon-btn" onClick={() => onSelect(signal)} aria-label={`Inspect ${signal.symbol}`}><ChevronRight size={17} /></button></td></tr> })}</tbody></table></div>{!signals.length && <div className="table-empty">Run the integrated scalper to inspect live candidates.</div>}</Panel>
    {selected?.scalpDetails && <ScalpDetail signal={selected} onWatch={onWatch} onJournal={onJournal} notes={notes} setNotes={setNotes} feedback={feedback} />}
    {summary && actionable.length === 0 && <div className="inline-alert subdued"><AlertTriangle size={17} /><div><strong>No actionable scalp setup</strong><span>The scan completed normally; current candidates remain in WAIT or REJECT.</span></div></div>}
  </div>
}

function ScalpDetail({ signal, onWatch, onJournal, notes, setNotes, feedback }: { signal: NormalizedSignal; onWatch: (signal: NormalizedSignal) => void; onJournal: (signal: NormalizedSignal) => void; notes: string; setNotes: (value: string) => void; feedback: string }) {
  const detail = signal.scalpDetails!
  return <section className="scalp-detail" aria-label={`${signal.symbol} scalp analysis`}><div className="scalp-detail-head"><div><span>#{detail.rank} · {signal.strategyLabel}</span><h2>{signal.symbol} · {signal.lifecycle} {signal.direction.toUpperCase()}</h2></div><div><StatusBadge tone={toneFor(signal.lifecycle)}>{signal.lifecycle}</StatusBadge><span className="grade-cell">Grade {signal.grade}</span></div></div><TradingViewChart symbol={signal.symbol} /><div className="detail-metrics"><div><span>Signal</span><strong>{signal.lifecycle}</strong></div><div><span>Direction</span><strong>{signal.direction.toUpperCase()}</strong></div><div><span>Confidence</span><strong>{Math.round(signal.confidence * 100)}%</strong></div><div><span>Score</span><strong>{signal.score.toFixed(1)}</strong></div><div><span>Scan time</span><strong>{time(signal.scannedAt)}</strong></div><div><span>Signal candle</span><strong>{time(detail.executionCandleTime)}</strong></div><div><span>Setup age</span><strong>{metric(detail.setupAgeMinutes, 0)}m</strong></div><div><span>OI 24H</span><strong>{detail.openInterestChange24hPct == null ? '—' : `${detail.openInterestChange24hPct.toFixed(2)}%`}</strong></div></div><div className="scalp-detail-grid"><section><h3>Quality</h3>{detail.quality.map((item) => <p key={item}><i />{item}</p>)}</section><section><h3>Trade plan</h3><div className="plan-prices"><div><span>ENTRY</span><strong>{signal.entry ? number(signal.entry) : '—'}</strong></div><div><span>STOP</span><strong>{signal.stopLoss ? number(signal.stopLoss) : '—'}</strong></div><div><span>TARGET</span><strong>{signal.targets[0] ? number(signal.targets[0]) : '—'}</strong></div><div><span>RRR</span><strong>{signal.riskReward?.toFixed(1) ?? '—'}R</strong></div></div><h3>Evidence</h3>{[...detail.prefilterReasons, ...signal.evidence].map((item, index) => <p key={`${index}-${item}`}><i />{item}</p>)}</section></div>{(detail.invalidationReason || signal.validationReasons.length > 0) && <div className="validation scalp-validation"><h3>Validation</h3>{detail.invalidationReason && <p><AlertTriangle size={15} />{detail.invalidationReason}</p>}{signal.validationReasons.map((item) => <p key={item}><AlertTriangle size={15} />{item}</p>)}</div>}<div className="scalp-actions"><label>Personal plan notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="What must happen before you act?" /></label><div>{feedback && <p className="form-message" role="status">{feedback}</p>}<button className="btn secondary" onClick={() => onWatch(signal)}><BookmarkPlus size={17} /> Watchlist</button><button className="btn primary" onClick={() => onJournal(signal)} disabled={!signal.entry}><FilePlus2 size={17} /> Journal this trade</button></div></div></section>
}

function TradeDrawer({ signal, notes, setNotes, feedback, onClose, onWatch, onJournal }: { signal: NormalizedSignal; notes: string; setNotes: (value: string) => void; feedback: string; onClose: () => void; onWatch: (signal: NormalizedSignal) => void; onJournal: (signal: NormalizedSignal) => void }) {
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="trade-drawer" onMouseDown={(event) => event.stopPropagation()} aria-label="Trade plan"><div className="drawer-head"><div><span>{signal.strategyLabel}</span><h2>{signal.symbol} · {signal.direction.toUpperCase()}</h2></div><button className="icon-btn" aria-label="Close trade plan" onClick={onClose}><X /></button></div><div className="drawer-status"><StatusBadge tone={toneFor(signal.lifecycle)}>{signal.lifecycle}</StatusBadge><span className="grade-cell">Grade {signal.grade}</span><span>{Math.round(signal.confidence * 100)}% confidence</span></div><div className="plan-prices"><div><span>ENTRY</span><strong>{signal.entry ? number(signal.entry) : '—'}</strong></div><div><span>STOP</span><strong>{signal.stopLoss ? number(signal.stopLoss) : '—'}</strong></div><div><span>TARGET</span><strong>{signal.targets[0] ? number(signal.targets[0]) : '—'}</strong></div><div><span>RRR</span><strong>{signal.riskReward?.toFixed(1) ?? '—'}R</strong></div></div>{signal.entry && signal.stopLoss && <div className="sizing-callout"><span>At 1% risk on $10,000</span><strong>{number(positionSize(10000, 1, signal.entry, signal.stopLoss), 4)} {signal.symbol.split('/')[0]}</strong></div>}<section className="evidence"><h3>Why CMM surfaced this</h3>{signal.evidence.map((line) => <p key={line}><i />{line}</p>)}</section>{signal.validationReasons.length > 0 && <section className="validation"><h3>Validation notes</h3>{signal.validationReasons.map((line) => <p key={line}><AlertTriangle size={15} />{line}</p>)}</section>}<div className="drawer-notes"><label>Personal plan notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="What must happen before you act?" /></label>{feedback && <p className="form-message" role="status">{feedback}</p>}</div><footer><button className="btn secondary" onClick={() => onWatch(signal)}><BookmarkPlus size={17} /> Watchlist</button><button className="btn primary" onClick={() => onJournal(signal)} disabled={!signal.entry}><FilePlus2 size={17} /> Journal this trade</button></footer></aside></div>
}
