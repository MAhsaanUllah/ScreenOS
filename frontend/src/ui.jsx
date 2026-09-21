const TONE = {
  success: 'bg-emerald-50 border-emerald-200 text-emerald-700',
  error: 'bg-red-50 border-red-200 text-red-700',
  info: 'bg-brand-50 border-brand-200 text-brand-800',
}

export function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="mb-6 flex items-start justify-between gap-4 max-sm:flex-col">
      <div>
        {eyebrow && <p className="text-[11px] font-bold tracking-widest uppercase text-brand-600 mb-1">{eyebrow}</p>}
        <h1 className="text-2xl font-bold tracking-tight font-display text-slate-900">{title}</h1>
        {description && <p className="text-sm text-slate-500 mt-1 max-w-2xl">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function Alert({ tone = 'info', children }) {
  return (
    <div role="status" aria-live="polite" className={`px-4 py-3 rounded-md text-[13px] font-medium mb-6 flex items-center gap-2 border ${TONE[tone] || TONE.info}`}>
      {children}
    </div>
  )
}

export function EmptyState({ title, description, action }) {
  return (
    <div className="text-center py-16 text-slate-400 border border-dashed border-slate-300 rounded-lg bg-card">
      <p className="text-sm font-medium text-slate-500">{title}</p>
      {description && <p className="text-xs mt-2 max-w-[340px] mx-auto text-slate-400">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Badge({ className = '', children }) {
  return <span className={`text-[11px] font-semibold px-2 py-1 rounded inline-flex items-center ${className}`}>{children}</span>
}

export function HelpTip({ text }) {
  return (
    <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-slate-100 text-slate-500 text-[10px] font-bold ml-1 cursor-help shrink-0" title={text} aria-label={text}>?</span>
  )
}

export function GuideBanner({ onHelp }) {
  return (
    <div className="mb-6 flex items-center justify-between gap-4 bg-brand-50 border border-brand-200 rounded-lg px-4 py-3">
      <p className="text-sm text-brand-800"><strong>First time here?</strong> 3-minute guide for non-technical HR — no jargon.</p>
      <button onClick={onHelp} className="btn-primary px-3 py-1.5 text-xs whitespace-nowrap">Open guide</button>
    </div>
  )
}