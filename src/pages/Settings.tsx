import { useEffect, useState } from 'react'
import { CheckCircle2, Database, Link2, RotateCcw, ShieldCheck, X } from 'lucide-react'
import { API_URL, checkHealth, type ApiStatus } from '../api'
import { db, seedDemoTrades } from '../db'
import { PageHeader, Panel, StatusBadge } from '../components/Ui'

type Tab = 'Workspace' | 'Risk defaults' | 'Data & privacy'
const defaults = { balance: '10000', risk: '1.0', exchange: 'Coinbase', timezone: 'Asia/Taipei' }
const readDefaults = () => { try { return { ...defaults, ...JSON.parse(localStorage.getItem('edgeledger-defaults') || '{}') } } catch { return defaults } }

export default function Settings({ apiStatus }: { apiStatus: ApiStatus }) {
  const stored = readDefaults()
  const [tab, setTab] = useState<Tab>('Workspace')
  const [risk, setRisk] = useState(stored.risk)
  const [balance, setBalance] = useState(stored.balance)
  const [exchange, setExchange] = useState(stored.exchange)
  const [timezone, setTimezone] = useState(stored.timezone)
  const [saved, setSaved] = useState(false)
  const [connection, setConnection] = useState(apiStatus)
  const [testing, setTesting] = useState(false)
  const [resetOpen, setResetOpen] = useState(false)
  const [demoMessage, setDemoMessage] = useState('')
  useEffect(() => setConnection(apiStatus), [apiStatus])
  const save = () => { localStorage.setItem('edgeledger-defaults', JSON.stringify({ balance, risk, exchange, timezone })); setSaved(true); window.setTimeout(() => setSaved(false), 1800) }
  const reset = async () => { await db.delete(); localStorage.removeItem('edgeledger-playbook'); localStorage.removeItem('edgeledger-goals'); window.location.reload() }

  return <div className="page settings-page"><PageHeader eyebrow="Workspace controls" title="Settings" description="Manage your local journal, integrated scanner, and default risk guardrails." /><div className="settings-layout"><nav className="settings-nav" aria-label="Settings sections">{(['Workspace', 'Risk defaults', 'Data & privacy'] as const).map((item) => <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>)}</nav><div className="settings-content">
    {tab === 'Workspace' && <Panel title="Integrated scanner" meta={<StatusBadge tone={connection.connected ? 'positive' : 'warning'}>{connection.connected ? 'Connected' : 'Demo mode'}</StatusBadge>}><div className="connection-row"><div className="connection-icon"><Link2 /></div><div><strong>{API_URL || 'Same-origin /api'}</strong><span>{connection.connected ? 'Authoritative strategy responses are available.' : 'Restart EdgeLedger to restore the bundled scanner.'}</span></div><button className="btn secondary" disabled={testing} onClick={async () => { setTesting(true); setConnection(await checkHealth()); setTesting(false) }}>{testing ? 'Testing...' : 'Test scanner'}</button></div><div className="safety-callout"><ShieldCheck size={18} /><p><strong>Paper and manual mode only</strong><span>EdgeLedger does not accept exchange secrets or place orders.</span></p></div></Panel>}
    {tab === 'Risk defaults' && <Panel title="Trading defaults"><div className="form-grid"><label>Account balance<div className="input-prefix"><span>$</span><input type="number" min="1" value={balance} onChange={(event) => setBalance(event.target.value)} /></div></label><label>Risk per trade<div className="input-prefix suffix"><input type="number" min="0.1" max="10" step="0.1" value={risk} onChange={(event) => setRisk(event.target.value)} /><span>%</span></div></label><label>Default exchange<select value={exchange} onChange={(event) => setExchange(event.target.value)}><option>Coinbase</option><option>Manual</option></select></label><label>Timezone<select value={timezone} onChange={(event) => setTimezone(event.target.value)}><option>Asia/Taipei</option><option>UTC</option><option>America/New_York</option></select></label></div><button className="btn primary" disabled={Number(balance) <= 0 || Number(risk) <= 0 || Number(risk) > 10} onClick={save}>{saved ? <CheckCircle2 size={16} /> : null}{saved ? 'Saved' : 'Save defaults'}</button></Panel>}
    {tab === 'Data & privacy' && <Panel title="Local data"><div className="data-actions"><div><Database /><span><strong>Browser journal</strong>Trades stay in IndexedDB on this device.</span></div><button className="btn secondary" onClick={async () => { const before = await db.trades.count(); await seedDemoTrades(); const after = await db.trades.count(); setDemoMessage(after > before ? 'Demo trades loaded.' : 'Demo trades are already present.') }}>Load demo set</button><button className="btn danger-btn" onClick={() => setResetOpen(true)}><RotateCcw size={16} /> Reset workspace</button></div>{demoMessage && <p className="form-message">{demoMessage}</p>}</Panel>}
  </div></div>
  {resetOpen && <div className="dialog-backdrop" onMouseDown={() => setResetOpen(false)}><div className="confirm-modal" role="alertdialog" aria-modal="true" aria-label="Reset workspace" onMouseDown={(event) => event.stopPropagation()}><div className="modal-head"><div><span>DESTRUCTIVE ACTION</span><h2>Reset local workspace?</h2></div><button className="icon-btn" aria-label="Close reset confirmation" onClick={() => setResetOpen(false)}><X /></button></div><p>This permanently removes local trades, watchlist items, goals, and playbook notes from this browser.</p><footer><button className="btn secondary" onClick={() => setResetOpen(false)}>Cancel</button><button className="btn danger-btn" onClick={reset}>Reset workspace</button></footer></div></div>}
  </div>
}
