import { useMemo, useState } from 'react'
import { addMonths, eachDayOfInterval, endOfMonth, endOfWeek, format, isSameMonth, startOfMonth, startOfWeek, subMonths } from 'date-fns'
import { ChevronLeft, ChevronRight, Clock3, ExternalLink, X } from 'lucide-react'
import { marketEvents } from '../data'
import type { MarketEvent } from '../types'
import { PageHeader, StatusBadge } from '../components/Ui'

const sourceFor = (code: string) => code.includes('CPI') || code.includes('NFP')
  ? 'https://www.bls.gov/schedule/news_release/'
  : code.includes('FOMC')
    ? 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'
    : 'https://www.bea.gov/news/schedule'

export default function MarketCalendar() {
  const [month, setMonth] = useState(startOfMonth(new Date()))
  const [selected, setSelected] = useState<MarketEvent | null>(null)
  const days = useMemo(() => eachDayOfInterval({ start: startOfWeek(startOfMonth(month)), end: endOfWeek(endOfMonth(month)) }), [month])
  return <div className="page calendar-page"><PageHeader eyebrow="Macro awareness" title="Market Calendar" description="High-impact events in your local review calendar. Awareness, never prediction." actions={<div className="month-switcher"><button className="icon-btn" aria-label="Previous month" onClick={() => setMonth(subMonths(month, 1))}><ChevronLeft /></button><div><span>VIEWING</span><strong>{format(month, 'MMMM yyyy')}</strong></div><button className="icon-btn" aria-label="Next month" onClick={() => setMonth(addMonths(month, 1))}><ChevronRight /></button></div>} />
    <div className="calendar-shell"><div className="weekday-row">{['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map((day) => <span key={day}>{day}</span>)}</div><div className="calendar-grid">{days.map((day) => { const events = marketEvents.filter((event) => event.date === format(day, 'yyyy-MM-dd')); return <div className={`calendar-day ${!isSameMonth(day, month) ? 'outside' : ''} ${format(day, 'yyyy-MM-dd') === format(new Date(), 'yyyy-MM-dd') ? 'today' : ''}`} key={day.toISOString()}><span className="day-number">{format(day, 'd')}</span>{events.map((event) => <button className={`calendar-event ${event.impact}`} key={event.id} onClick={() => setSelected(event)}><span>{event.code}</span><strong>{event.time}</strong><small>{event.title}</small></button>)}</div> })}</div></div>
    <div className="calendar-legend"><span><i className="high" /> High impact</span><span><i className="medium" /> Medium impact</span><span><Clock3 size={14} /> Times shown in Eastern Time</span></div>
    {selected && <div className="dialog-backdrop" onMouseDown={() => setSelected(null)}><div className="event-modal" role="dialog" aria-modal="true" aria-label={`${selected.code} event details`} onMouseDown={(event) => event.stopPropagation()}><div className="modal-head"><div><span>MARKET EVENT</span><h2>{selected.code} · {selected.title}</h2></div><button className="icon-btn" aria-label="Close event" onClick={() => setSelected(null)}><X /></button></div><div className="event-meta"><strong>{new Date(`${selected.date}T12:00:00`).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</strong><span>{selected.time}</span><StatusBadge tone={selected.impact === 'high' ? 'negative' : 'warning'}>{selected.impact} impact</StatusBadge></div><p>{selected.note}</p><div className="event-safety">Reduce unnecessary exposure around high-impact releases and wait for your strategy confirmation after volatility settles.</div><a className="btn secondary" href={sourceFor(selected.code)} target="_blank" rel="noreferrer"><ExternalLink size={16} /> Official source</a></div></div>}
  </div>
}
