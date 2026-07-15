import type { ReactNode } from 'react'

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description: string; actions?: ReactNode }) {
  return <header className="page-header">
    <div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>
    {actions && <div className="page-actions">{actions}</div>}
  </header>
}

export function Panel({ title, meta, children, className = '' }: { title?: string; meta?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>
    {(title || meta) && <div className="panel-head"><h2>{title}</h2><div>{meta}</div></div>}
    {children}
  </section>
}

export function StatusBadge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'positive' | 'negative' | 'warning' | 'info' | 'neutral' }) {
  return <span className={`status-badge ${tone}`}>{children}</span>
}

export function Metric({ label, value, detail, tone = '' }: { label: string; value: string; detail?: string; tone?: string }) {
  return <div className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>
}

export function EmptyState({ icon, title, text, action }: { icon: ReactNode; title: string; text: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon">{icon}</div><h3>{title}</h3><p>{text}</p>{action}</div>
}
