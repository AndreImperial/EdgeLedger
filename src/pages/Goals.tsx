import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Plus, Target, X } from 'lucide-react'
import { PageHeader, Panel } from '../components/Ui'

type Goal = { title: string; progress: number; target: string; done: boolean }
const initial: Goal[] = [
  { title: 'Journal every closed trade', progress: 92, target: '12 / 13 trades', done: false },
  { title: 'Wait for candle confirmation', progress: 80, target: '8 / 10 samples', done: false },
  { title: 'Complete weekly review', progress: 100, target: '4 / 4 weeks', done: true },
]
const readGoals = (): Goal[] => { try { return JSON.parse(localStorage.getItem('edgeledger-goals') || 'null') || initial } catch { return initial } }

export default function Goals() {
  const [goals, setGoals] = useState<Goal[]>(readGoals)
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [target, setTarget] = useState('10 samples')
  useEffect(() => localStorage.setItem('edgeledger-goals', JSON.stringify(goals)), [goals])
  const addGoal = () => { if (!title.trim()) return; setGoals([...goals, { title: title.trim(), progress: 0, target: `0 / ${target}`, done: false }]); setTitle(''); setTarget('10 samples'); setOpen(false) }
  const toggle = (index: number) => setGoals(goals.map((item, i) => i === index ? { ...item, done: !item.done, progress: !item.done ? 100 : 0 } : item))
  return <div className="page goals-page">
    <PageHeader eyebrow="Process over outcome" title="Goals" description="Track behaviors you can control, especially when the market refuses to cooperate." actions={<button className="btn primary" onClick={() => setOpen(true)}><Plus size={17} /> New goal</button>} />
    <div className="goals-layout"><Panel title="July discipline cycle"><div className="goal-list">{goals.map((goal, index) => <button key={`${goal.title}-${index}`} onClick={() => toggle(index)}><div className="goal-check">{goal.done ? <CheckCircle2 /> : <Circle />}</div><div><strong>{goal.title}</strong><span>{goal.target}</span><div className="goal-track"><i style={{ width: `${goal.progress}%` }} /></div></div><b>{goal.progress}%</b></button>)}</div></Panel><Panel className="goal-focus"><Target /><span>CURRENT FOCUS</span><h2>Confirmation before conviction.</h2><p>Every skipped early entry protects both capital and confidence. Review again after ten clean samples.</p><div className="focus-stats"><div><strong>8</strong><span>clean samples</span></div><div><strong>2</strong><span>remaining</span></div></div></Panel></div>
    {open && <div className="dialog-backdrop" onMouseDown={() => setOpen(false)}><div className="confirm-modal goal-modal" role="dialog" aria-modal="true" aria-label="Create goal" onMouseDown={(event) => event.stopPropagation()}><div className="modal-head"><div><span>PROCESS TARGET</span><h2>Create a goal</h2></div><button className="icon-btn" aria-label="Close goal form" onClick={() => setOpen(false)}><X /></button></div><div className="form-grid"><label className="full">Goal<input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Example: Respect every stop" /></label><label className="full">Target<input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="10 samples" /></label></div><footer><button className="btn secondary" onClick={() => setOpen(false)}>Cancel</button><button className="btn primary" disabled={!title.trim()} onClick={addGoal}>Create goal</button></footer></div></div>}
  </div>
}
