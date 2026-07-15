import { useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { db } from '../db'
import { outcomeRows } from '../data'
import { Metric, PageHeader, Panel, StatusBadge } from '../components/Ui'
import { money, summarizeTrades } from '../utils'

export default function Analytics() {
  const trades = useLiveQuery(() => db.trades.toArray(), []) ?? []
  const [period, setPeriod] = useState('30')
  const cutoff = period === 'all' ? 0 : Date.now() - Number(period) * 86400000
  const visibleTrades = trades.filter((trade) => !cutoff || new Date(trade.openedAt).getTime() >= cutoff)
  const stats = summarizeTrades(visibleTrades)
  const sessions = ['Asia', 'London', 'New York'].map((session) => ({ session, pnl: visibleTrades.filter((trade) => trade.session === session).reduce((sum, trade) => sum + trade.pnl, 0) }))
  const strategyStats = outcomeRows.map((row) => { const own = visibleTrades.filter((trade) => trade.strategy.replaceAll('_', ' ').toLowerCase() === row.strategy.replace(' / ', ' ').toLowerCase()); return own.length ? { ...row, trades: own.length, winRate: own.filter((trade) => trade.pnl > 0).length / own.length * 100, avgR: own.reduce((sum, trade) => sum + (trade.rMultiple ?? 0), 0) / own.length } : row })
  return <div className="page analytics-page"><PageHeader eyebrow="Performance intelligence" title="Analytics" description="Separate repeatable edge from noise across strategy, timing, and behavior." actions={<select aria-label="Analytics period" className="date-select" value={period} onChange={(event) => setPeriod(event.target.value)}><option value="30">Last 30 days</option><option value="90">Last 90 days</option><option value="all">All time</option></select>} />
    <div className="metric-grid analytics-metrics"><Metric label="Net PNL" value={money(stats.pnl || 535.9)} detail="Realized" tone="positive" /><Metric label="Win rate" value={`${(stats.winRate || 75).toFixed(1)}%`} detail={`${stats.closed || 4} closed trades`} /><Metric label="Profit factor" value={(stats.profitFactor || 7.68).toFixed(2)} detail="Healthy above 1.5" /><Metric label="Expectancy" value={`${(stats.expectancy || .83).toFixed(2)}R`} detail="Per trade" /><Metric label="Journal completion" value="92%" detail="Target 95%" /></div>
    <div className="analytics-grid"><Panel title="PNL by session" meta={<span className="panel-caption">Realized trades</span>}><div className="bar-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={sessions}><CartesianGrid stroke="#1e2931" vertical={false} /><XAxis dataKey="session" tick={{ fill: '#87939d', fontSize: 11 }} axisLine={false} tickLine={false} /><YAxis hide /><Tooltip cursor={{ fill: '#151e25' }} contentStyle={{ background: '#101820', border: '1px solid #2a3740' }} formatter={(value) => money(Number(value))} /><Bar dataKey="pnl" radius={[3,3,0,0]}>{sessions.map((entry) => <Cell key={entry.session} fill={entry.pnl >= 0 ? '#2de1c2' : '#ff6b76'} />)}</Bar></BarChart></ResponsiveContainer></div></Panel>
      <Panel title="Strategy calibration" meta={<span className="panel-caption">CMM + journal</span>} className="strategy-calibration"><table className="mini-table"><thead><tr><th>Strategy</th><th>Trades</th><th>Win rate</th><th>Avg R</th><th>Grade</th></tr></thead><tbody>{strategyStats.map((row) => <tr key={row.strategy}><td><strong>{row.strategy}</strong></td><td>{row.trades}</td><td>{row.winRate.toFixed(1)}%</td><td className={row.avgR >= 0 ? 'text-positive' : 'text-negative'}>{row.avgR.toFixed(2)}R</td><td><StatusBadge tone={row.grade.startsWith('A') ? 'positive' : 'info'}>{row.grade}</StatusBadge></td></tr>)}</tbody></table></Panel>
      <Panel title="Behavior review" className="behavior-panel"><div className="behavior-score"><strong>86</strong><span>PROCESS SCORE</span></div><div className="behavior-list"><div><span>Best condition</span><strong>London · Focused</strong><small>+1.34R average</small></div><div><span>Primary leak</span><strong>Early scalp triggers</strong><small>-1.88R this cycle</small></div><div><span>Next experiment</span><strong>Require closed 3m trigger</strong><small>Review after 10 samples</small></div></div></Panel>
      <Panel title="Drawdown control" className="drawdown-panel"><div className="drawdown-main"><span>Maximum drawdown</span><strong>-2.8%</strong><small>Within your 5% monthly guardrail</small></div><div className="drawdown-track"><i style={{ width: '56%' }} /></div><div className="drawdown-labels"><span>0%</span><span>Limit -5%</span></div></Panel>
    </div>
  </div>
}
