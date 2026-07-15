import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { Activity, BarChart3, Bell, BookOpen, CalendarDays, ChevronLeft, CircleDollarSign, CircleGauge, FlaskConical, LayoutDashboard, Menu, Radar, Search, Settings, ShieldCheck, TableProperties, Target, X } from 'lucide-react'
import type { ApiStatus } from '../api'
import { markAlertsRead, readAlerts, type EdgeAlert } from '../notifications'

const nav = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/scanner', label: 'CMM Scanner', icon: Radar },
  { to: '/trades', label: 'Trades', icon: Activity },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/risk-lab', label: 'Risk Lab', icon: ShieldCheck },
  { to: '/market-calendar', label: 'Market Calendar', icon: CalendarDays },
  { to: '/market-screener', label: 'Market Screener', icon: TableProperties },
  { to: '/open-interest', label: 'Open Interest', icon: CircleDollarSign },
  { to: '/playbook', label: 'Playbook', icon: BookOpen },
  { to: '/goals', label: 'Goals', icon: Target },
]

export default function Shell({ children, apiStatus }: { children: ReactNode; apiStatus: ApiStatus }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [alerts, setAlerts] = useState<EdgeAlert[]>(readAlerts)
  const navigate = useNavigate()
  const location = useLocation()
  useEffect(() => setMobileOpen(false), [location.pathname])
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setPaletteOpen((value) => !value) }
      if (event.key === 'Escape') setPaletteOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  useEffect(() => { const update = (event: Event) => setAlerts((event as CustomEvent<EdgeAlert[]>).detail); window.addEventListener('edgeledger-alerts', update); return () => window.removeEventListener('edgeledger-alerts', update) }, [])
  const filtered = useMemo(() => nav.filter((item) => item.label.toLowerCase().includes(query.toLowerCase())), [query])
  const go = (path: string) => { navigate(path); setPaletteOpen(false); setQuery('') }

  return <div className={`app-shell ${collapsed ? 'nav-collapsed' : ''}`}>
    <a className="skip-link" href="#main">Skip to workspace</a>
    <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
      <div className="brand-row"><NavLink to="/dashboard" className="brand"><span className="brand-mark">E</span><span className="brand-name">Edge<span>Ledger</span></span></NavLink><button className="icon-btn collapse-btn" onClick={() => setCollapsed(!collapsed)} aria-label="Collapse navigation"><ChevronLeft size={17} /></button></div>
      <div className="profile-block"><span>Good morning,</span><strong>Trader Andre</strong><small><i className="online-dot" /> Paper workspace</small></div>
      <nav aria-label="Main navigation">{nav.map((item) => <NavLink key={item.to} to={item.to} title={collapsed ? item.label : undefined}><item.icon size={18} /><span>{item.label}</span>{item.to === '/scanner' && <em>LIVE</em>}</NavLink>)}</nav>
      <div className="sidebar-foot"><NavLink to="/settings"><Settings size={18} /><span>Settings</span></NavLink><div className="safety-note"><FlaskConical size={16} /><span>Research only<br />No live execution</span></div></div>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <button className="icon-btn mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu /></button>
        <button className="search-trigger" onClick={() => setPaletteOpen(true)}><Search size={17} /><span>Search workspace...</span><kbd>Ctrl K</kbd></button>
        <div className="topbar-right"><div className={`api-state ${apiStatus.connected ? 'connected' : ''}`}><i /> <span>{apiStatus.message}</span></div><div className="notification-wrap"><button className="icon-btn" title="Notifications" aria-label="Notifications" aria-expanded={notificationsOpen} onClick={() => { setNotificationsOpen((value) => !value); if (!notificationsOpen) markAlertsRead() }}><Bell size={18} />{alerts.some((alert) => !alert.read) && <b>{alerts.filter((alert) => !alert.read).length}</b>}</button>{notificationsOpen && <div className="notification-menu" role="dialog" aria-label="Notifications"><strong>Signal alerts</strong>{alerts.slice(0, 6).map((alert) => <button key={alert.id} onClick={() => { navigate('/scanner'); setNotificationsOpen(false) }}><span>{alert.symbol} · {alert.lifecycle}</span><small>{alert.strategy} · Grade {alert.grade} · {Math.round(alert.confidence * 100)}% confidence</small></button>)}{!alerts.length && <p>No CMM alerts yet. Run a scan to populate this inbox.</p>}</div>}</div><div className="avatar">AI</div></div>
      </header>
      <main id="main">{children}</main>
    </div>
    {mobileOpen && <button className="mobile-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
    {paletteOpen && <div className="dialog-backdrop" role="presentation" onMouseDown={() => setPaletteOpen(false)}><div className="command-palette" role="dialog" aria-modal="true" aria-label="Workspace search" onMouseDown={(event) => event.stopPropagation()}><div className="command-input"><Search /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search pages and tools" /><button className="icon-btn" onClick={() => setPaletteOpen(false)}><X size={17} /></button></div><div className="command-results"><small>NAVIGATE</small>{filtered.map((item) => <button key={item.to} onClick={() => go(item.to)}><item.icon size={18} /><span>{item.label}</span><kbd>Open</kbd></button>)}{!filtered.length && <p>No matching workspace tools.</p>}</div><footer><span><CircleGauge size={14} /> EdgeLedger command center</span><span>Esc to close</span></footer></div></div>}
  </div>
}
