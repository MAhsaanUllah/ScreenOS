const TONE = {
  success: 'bg-emerald-50 border-emerald-200 text-emerald-700',
  error: 'bg-rose-50 border-rose-200 text-rose-700',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
}

export function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4 max-sm:flex-col">
      <div>
        {eyebrow && <p className="text-[11px] font-bold tracking-widest uppercase text-blue-600 mb-1">{eyebrow}</p>}
        <h1 className="text-2xl font-bold tracking-tight font-display">{title}</h1>
        {description && <p className="text-sm text-slate-600 mt-0.5 max-w-2xl">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function Alert({ tone = 'info', children }) {
  return (
    <div role="status" aria-live="polite" className={`px-4 py-3 rounded-md text-[13px] font-medium mb-5 flex items-center gap-2 border ${TONE[tone] || TONE.info}`}>
      {children}
    </div>
  )
}

export function EmptyState({ title, description, icon = '🗂️', action }) {
  return (
    <div className="text-center py-16 text-slate-400 border border-dashed border-slate-200 rounded-xl bg-white">
      <div className="text-3xl mb-3 text-slate-300">{icon}</div>
      <p className="text-sm font-medium text-slate-500">{title}</p>
      {description && <p className="text-xs mt-1.5 max-w-[340px] mx-auto text-slate-400">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Badge({ className = '', children }) {
  return <span className={`text-[11px] font-semibold px-2 py-0.5 rounded ${className}`}>{children}</span>
}