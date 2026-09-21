import { useEffect, useState } from 'react'
import { api } from './api.js'
import { PageHeader, EmptyState } from './ui.jsx'

const VERDICT_BAR = {
  STRONG_MATCH: 'bg-emerald-500',
  POSSIBLE_MATCH: 'bg-amber-500',
  WEAK_MATCH: 'bg-slate-300'
}

function StatCard({ label, value, accent }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <div className={`text-3xl font-bold font-mono ${accent || 'text-slate-900'}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-1 font-medium">{label}</div>
    </div>
  )
}

export default function Analytics() {
  const [reviews, setReviews] = useState([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api('/api/reviews').then(setReviews).catch(err => alert(err.message))
  }, [])

  async function exportCompliance() {
    setBusy(true)
    try {
      const data = await api('/api/compliance')
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `screenos-compliance-${data.generated_at ? data.generated_at.slice(0, 10) : 'report'}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert(err.message)
    } finally {
      setBusy(false)
    }
  }

  const scored = reviews.filter(r => r.score !== null)
  const avg = scored.length ? (scored.reduce((sum, r) => sum + r.score, 0) / scored.length).toFixed(1) : '—'
  const byVerdict = v => scored.filter(r => r.verdict === v).length
  const byStatus = s => reviews.filter(r => r.status === s).length
  const decided = reviews.filter(r => r.decision).length
  const pipeline = [
    { label: 'Total Screened', value: reviews.length, bar: 'bg-blue-500' },
    { label: 'Scored', value: scored.length, bar: 'bg-indigo-500' },
    { label: 'Decided', value: decided, bar: 'bg-violet-500' },
    { label: 'Approved', value: byStatus('APPROVE'), bar: 'bg-emerald-500' },
    { label: 'Rejected', value: byStatus('REJECT'), bar: 'bg-rose-500' }
  ]

  return (
    <div className="max-w-[1400px] mx-auto">
      <PageHeader
        eyebrow="Team Insights"
        title="Analytics"
        description="Live queue metrics computed from your organization's reviews."
        action={
          <button onClick={exportCompliance} disabled={busy} className="btn-approve">
            {busy ? 'Preparing…' : '⬇ Export compliance report'}
          </button>
        }
      />

      {reviews.length === 0 ? (
        <EmptyState icon="📈" title="Screen candidates to start seeing metrics."
          description="Queue numbers, verdicts and approval rates appear here once you run your first review." />
      ) : (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2">
            <StatCard label="Reviews" value={reviews.length} />
            <StatCard label="Scored (avg)" value={avg} accent="text-blue-600" />
            <StatCard label="Approved" value={byStatus('APPROVE')} accent="text-emerald-600" />
            <StatCard label="Rejected" value={byStatus('REJECT')} accent="text-rose-600" />
          </div>

          <div className="grid grid-cols-2 gap-6 max-lg:grid-cols-1">
            <div className="bg-white border border-slate-200 rounded-xl p-5">
              <h3 className="text-[13px] font-semibold mb-4">Pipeline Overview</h3>
              <div className="flex flex-col gap-3">
                {pipeline.map((s, i) => s.value === 0 ? null : (
                  <div key={s.label}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-600 font-medium">{s.label}</span>
                      <span className="font-mono text-slate-700">{s.value}</span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                      <div className={`h-full ${s.bar} rounded-full`}
                           style={{ width: `${Math.max(4, (s.value / reviews.length) * 100)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-5">
              <h3 className="text-[13px] font-semibold mb-4">Scores by Verdict</h3>
              {scored.length === 0 ? (
                <p className="text-xs text-slate-400">No scored candidates yet.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {Object.keys(VERDICT_BAR).map(v => {
                    const n = byVerdict(v)
                    return n === 0 ? null : (
                      <div key={v}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-slate-600 font-medium">{v.replaceAll('_', ' ')}</span>
                          <span className="font-mono text-slate-700">{n} · {Math.round((n / scored.length) * 100)}%</span>
                        </div>
                        <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                          <div className={`h-full ${VERDICT_BAR[v]} rounded-full`}
                               style={{ width: `${Math.max(4, (n / scored.length) * 100)}%` }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}