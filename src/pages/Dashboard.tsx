import { useMemo, useState } from 'react'
import { ArrowRight, BookOpenCheck, CalendarClock, Radar, TrendingUp } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useNavigate } from 'react-router-dom'
import { useLiveQuery } from 'dexie-react-hooks'
import { db } from '../db'
import { demoSignals, equityCurve, marketEvents } from '../data'
import { Metric, PageHeader, Panel, StatusBadge } from '../components/Ui'
import { money, summarizeTrades } from '../utils'

export default function Dashboard() {
  const navigate = useNavigate()
  const [range, setRange] = useState<'30D' | '90D' | 'ALL'>('30D')
  const trades = useLiveQuery(() => db.trades.orderBy('openedAt').reverse().toArray(), []) ?? []
  const stats = summarizeTrades(trades)
  const chartData = useMemo(() => range === '30D' ? equityCurve.slice(-8) : range === '90D' ? equityCurve.slice(-14) : equityCurve, [range])
  return <div className="page dashboard-page">
    <PageHeader eyebrow="Personal trading OS · 15 July 2026" title="Good morning, Andre." description="Your process is improving. Keep the next decision as clean as the last one." actions={<><button className="btn secondary" onClick={() => navigate('/trades')}>Journal trade</button><button className="btn primary" onClick={() => navigate('/scanner')}><Radar size={17} /> Run scanner</button></>} />
    <div className="metric-grid">
      <Metric label="Trading balance" value={money(10842)} detail="+$842 this cycle" />
      <Metric label="Net PNL" value={money(stats.pnl || 535.9)} detail="+5.36% realized" tone="positive" />
      <Metric label="Win rate" value={`${(stats.winRate || 75).toFixed(1)}%`} detail={`${stats.closed || 4} reviewed trades`} />
      <Metric label="Profit factor" value={(stats.profitFactor || 7.68).toFixed(2)} detail="Target > 1.50" />
      <Metric label="Expectancy" value={`${(stats.expectancy || .83).toFixed(2)}R`} detail="Per closed trade" tone="positive" />
    </div>
    <div className="dashboard-grid">
      <Panel title="Equity curve" meta={<div className="range-tabs">{(['30D', '90D', 'ALL'] as const).map((item) => <button key={item} className={range === item ? 'active' : ''} onClick={() => setRange(item)}>{item}</button>)}</div>} className="equity-panel">
        <div className="chart-summary"><strong>+$842.00</strong><span><TrendingUp size={14} /> 8.42% return</span></div>
        <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData}><defs><linearGradient id="equity" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2de1c2" stopOpacity={.28} /><stop offset="100%" stopColor="#2de1c2" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#1e2931" vertical={false} /><XAxis dataKey="day" tick={{ fill: '#77838e', fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis domain={['dataMin - 150', 'dataMax + 100']} hide /><Tooltip contentStyle={{ background: '#101820', border: '1px solid #2a3740', borderRadius: 4 }} formatter={(value) => money(Number(value))} /><Area type="monotone" dataKey="equity" stroke="#2de1c2" strokeWidth={2} fill="url(#equity)" /></AreaChart></ResponsiveContainer></div>
      </Panel>
      <Panel title="Process score" meta={<StatusBadge tone="positive">A-</StatusBadge>} className="process-panel">
        <div className="score-ring"><strong>86</strong><span>/100</span></div>
        {[['Journal completion', 92], ['Rule adherence', 84], ['Risk consistency', 88], ['Patience', 77]].map(([label, value]) => <div className="progress-row" key={label as string}><span>{label}</span><b>{value}%</b><div><i style={{ width: `${value}%` }} /></div></div>)}
        <button className="text-btn" onClick={() => navigate('/analytics')}>View full review <ArrowRight size={15} /></button>
      </Panel>
      <Panel title="CMM signal desk" meta={<button className="text-btn" onClick={() => navigate('/scanner')}>View scanner <ArrowRight size={15} /></button>} className="signal-desk">
        <div className="signal-list">{demoSignals.slice(0, 3).map((signal) => <button key={signal.id} onClick={() => navigate('/scanner')}><div className={`coin-mark ${signal.direction}`}>{signal.symbol.slice(0, 1)}</div><div><strong>{signal.symbol}</strong><span>{signal.strategyLabel}</span></div><StatusBadge tone={signal.lifecycle === 'ENTER' ? 'positive' : signal.lifecycle === 'WATCH' ? 'warning' : 'neutral'}>{signal.lifecycle}</StatusBadge><div className="signal-score"><strong>{signal.grade}</strong><span>{Math.round(signal.confidence * 100)}%</span></div></button>)}</div>
      </Panel>
      <Panel title="Upcoming market risk" meta={<CalendarClock size={17} />} className="events-panel">
        {marketEvents.slice(0, 3).map((event) => <div className="event-row" key={event.id}><div className="event-date"><strong>{new Date(`${event.date}T12:00:00`).getDate()}</strong><span>{new Date(`${event.date}T12:00:00`).toLocaleString('en', { month: 'short' })}</span></div><div><strong>{event.code}</strong><span>{event.title}</span></div><StatusBadge tone={event.impact === 'high' ? 'negative' : 'warning'}>{event.impact}</StatusBadge></div>)}
      </Panel>
      <Panel className="review-strip"><div className="review-callout"><BookOpenCheck /><div><span>WEEKLY REVIEW</span><strong>Your best trades waited for confirmation.</strong><p>Three of four reviewed entries followed the planned trigger. The SOL scalp remains the exception worth studying.</p></div><button className="btn secondary" onClick={() => navigate('/trades')}>Review journal</button></div></Panel>
    </div>
  </div>
}
