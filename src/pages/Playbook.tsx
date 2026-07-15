import { useEffect, useState } from 'react'
import { BookOpenCheck, Check, CheckCircle2, ChevronRight, LockKeyhole, SlidersHorizontal } from 'lucide-react'
import { strategies } from '../data'
import type { StrategyTemplate } from '../types'
import { PageHeader, Panel, StatusBadge } from '../components/Ui'

type PlaybookPrefs = Record<string, { notes: string; checks: boolean[] }>
const readPrefs = (): PlaybookPrefs => { try { return JSON.parse(localStorage.getItem('edgeledger-playbook') || '{}') } catch { return {} } }

export default function Playbook() {
  const [family, setFamily] = useState<'All' | 'Intraday' | 'Scalper'>('All')
  const [selected, setSelected] = useState<StrategyTemplate>(strategies[0])
  const [prefs, setPrefs] = useState<PlaybookPrefs>(readPrefs)
  const [saved, setSaved] = useState(false)
  const shown = strategies.filter((item) => family === 'All' || item.family === family)
  const personal = prefs[selected.key] ?? { notes: '', checks: selected.rules.map(() => false) }
  useEffect(() => { if (!shown.some((item) => item.key === selected.key)) setSelected(shown[0]) }, [family, selected.key, shown])
  const updatePersonal = (next: { notes: string; checks: boolean[] }) => setPrefs((current) => ({ ...current, [selected.key]: next }))
  const save = () => { localStorage.setItem('edgeledger-playbook', JSON.stringify(prefs)); setSaved(true); window.setTimeout(() => setSaved(false), 1600) }

  return <div className="page playbook-page"><PageHeader eyebrow="Canonical CMM rules" title="Strategy Playbook" description="Know what a valid setup looks like before the chart starts negotiating with you." actions={<div className="segmented">{(['All','Intraday','Scalper'] as const).map((item) => <button key={item} onClick={() => setFamily(item)} className={family === item ? 'active' : ''}>{item}</button>)}</div>} />
    <div className="playbook-layout"><div className="strategy-library">{shown.map((strategy, index) => <button key={strategy.key} className={selected.key === strategy.key ? 'active' : ''} onClick={() => setSelected(strategy)} style={{ '--strategy-accent': strategy.accent } as React.CSSProperties}><div className="strategy-index">{String(index + 1).padStart(2, '0')}</div><div><span>{strategy.family} · {strategy.timeframe}</span><strong>{strategy.name}</strong><p>{strategy.summary}</p></div><ChevronRight /></button>)}</div>
      <Panel className="strategy-detail"><div className="strategy-detail-head" style={{ '--strategy-accent': selected.accent } as React.CSSProperties}><div><span>{selected.family.toUpperCase()} SYSTEM TEMPLATE</span><h2>{selected.name}</h2><p>{selected.summary}</p></div><div className="template-lock"><LockKeyhole size={16} /><span>Canonical rules<br /><strong>Read only</strong></span></div></div><div className="strategy-section"><h3><BookOpenCheck size={17} /> Entry checklist</h3>{selected.rules.map((rule, index) => <label className="check-row" key={rule}><input type="checkbox" checked={personal.checks[index] ?? false} onChange={(event) => { const checks = [...personal.checks]; checks[index] = event.target.checked; updatePersonal({ ...personal, checks }) }} /><span><Check size={13} /></span>{rule}</label>)}</div><div className="strategy-section"><h3><SlidersHorizontal size={17} /> CMM defaults</h3><div className="default-grid">{selected.defaults.map((item) => <div key={item}><span>{item}</span></div>)}</div></div>{selected.key !== 'alma_cci_scalp' && <div className="prison-state"><div><span>CONFIRMATION COMPONENT</span><strong>Prison Break</strong></div><p>A timing state that moves a setup through WAIT, WATCH, ENTER, or REJECT. It is not a standalone strategy.</p><StatusBadge tone="warning">WATCH → ENTER</StatusBadge></div>}<div className="personal-notes"><label>Personal notes<textarea value={personal.notes} onChange={(event) => updatePersonal({ ...personal, notes: event.target.value })} placeholder="Add observations without changing the canonical CMM template..." /></label><button className="btn secondary" onClick={save}>{saved ? <CheckCircle2 size={16} /> : null}{saved ? 'Saved' : 'Save personal notes'}</button></div></Panel>
    </div></div>
}
