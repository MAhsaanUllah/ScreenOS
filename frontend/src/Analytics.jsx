import { useEffect, useState } from 'react'
import { api } from './api.js'
import { PageHeader, EmptyState, Badge, Alert } from './ui.jsx'
import { VerdictBadge } from './Criterion.jsx'

const VERDICT_BAR = {
  STRONG_MATCH: 'bg-emerald-500',
  POSSIBLE_MATCH: 'bg-amber-500',
  WEAK_MATCH: 'bg-slate-300'
}

function StatCard({ label, value, accent }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5">
      <div className={`text-3xl font-bold font-mono tracking-tight ${accent || 'text-slate-900'}`}>{value}</div>
      <div className="text-xs text-slate-500 mt-1 font-medium">{label}</div>
    </div>
  )
}

export default function Analytics() {
  const [reviews, setReviews] = useState([])
  const [jobs, setJobs] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [csvDecision, setCsvDecision] = useState('')
  const [csvVerdict, setCsvVerdict] = useState('')
  const [jobFilter, setJobFilter] = useState('')

  useEffect(() => {
    api('/api/reviews').then(setReviews).catch(err => setError(err.message))
    api('/api/jobs').then(setJobs).catch(() => {})
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
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  async function exportCsv() {
    setBusy(true)
    try {
      const q = new URLSearchParams()
      if (csvDecision) q.set('decision', csvDecision)
      if (csvVerdict) q.set('verdict', csvVerdict)
      const suffix = q.toString() ? `?${q}` : ''
      const res = await api(`/api/compliance.csv${suffix}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `screenos-${csvDecision || 'all'}-${csvVerdict || 'all'}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  const filteredReviews = reviews.filter(r => !jobFilter || r.job_id === jobFilter)
  const scored = filteredReviews.filter(r => r.score !== null)
  const avg = scored.length ? (scored.reduce((sum, r) => sum + r.score, 0) / scored.length).toFixed(1) : '—'
  const byVerdict = v => scored.filter(r => r.verdict === v).length
  const byStatus = s => filteredReviews.filter(r => r.status === s).length
  const decided = filteredReviews.filter(r => r.decision).length
  const pipeline = [
    { label: 'Total Screened', value: filteredReviews.length, bar: 'bg-brand-400' },
    { label: 'Scored', value: scored.length, bar: 'bg-brand-500' },
    { label: 'Decided', value: decided, bar: 'bg-brand-600' },
    { label: 'Approved', value: byStatus('APPROVE'), bar: 'bg-emerald-500' },
    { label: 'Rejected', value: byStatus('REJECT'), bar: 'bg-red-500' }
  ]

  const discrepancies = filteredReviews.filter(r =>
    r.decision && r.verdict && (
      (r.verdict === 'STRONG_MATCH' && r.decision === 'REJECT') ||
      (r.verdict === 'WEAK_MATCH' && r.decision === 'APPROVE')
    )
  )
  const discrepancyNote = (r) =>
    r.verdict === 'STRONG_MATCH' && r.decision === 'REJECT'
      ? 'Recruiter overruled a strong AI match'
      : r.verdict === 'WEAK_MATCH' && r.decision === 'APPROVE'
        ? 'Recruiter approved despite a weak match'
        : ''

  return (
    <div className="max-w-[1400px] mx-auto">
      <PageHeader
        eyebrow="Team metrics"
        title="Analytics"
        description="Live queue metrics computed from your organization's reviews."
        action={
          <div className="flex items-center gap-2 flex-wrap">
            <select value={jobFilter} onChange={e => setJobFilter(e.target.value)} className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white">
              <option value="">All Jobs</option>
              {jobs.map(j => <option key={j.id} value={j.id}>{j.title} — {j.status} {j.rubric_approved ? '(Approved 100)' : j.rubric ? '(Draft)' : '(No rubric)'}</option>)}
            </select>
            <select value={csvDecision} onChange={e => setCsvDecision(e.target.value)} className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white">
              <option value="">All decisions</option><option value="APPROVE">Approved</option><option value="REJECT">Rejected</option>
            </select>
            <select value={csvVerdict} onChange={e => setCsvVerdict(e.target.value)} className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white">
              <option value="">All verdicts</option><option value="STRONG_MATCH">Strong</option><option value="POSSIBLE_MATCH">Possible</option><option value="WEAK_MATCH">Weak</option>
            </select>
            <button onClick={exportCsv} disabled={busy} className="btn-ghost">CSV</button>
            <button onClick={exportCompliance} disabled={busy} className="btn-ghost">
              {busy ? 'Preparing...' : 'JSON'}
            </button>
          </div>
        }
      />

      {error && <Alert tone="error">{error}</Alert>}

      {reviews.length === 0 ? (
        <EmptyState title="Screen candidates to start seeing metrics."
          description="Queue numbers, verdicts and approval rates appear here once you run your first review." />
      ) : (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2">
            <StatCard label="Reviews" value={reviews.length} />
            <StatCard label="Scored (avg)" value={avg} accent="text-brand-600" />
            <StatCard label="Approved" value={byStatus('APPROVE')} accent="text-emerald-600" />
            <StatCard label="Rejected" value={byStatus('REJECT')} accent="text-red-600" />
          </div>

          <section className="bg-white border border-slate-200 rounded-lg">
            <div className="px-5 pt-5 pb-3 flex items-baseline justify-between border-b border-slate-200">
              <h2 className="text-[15px] font-semibold">Recruiter vs AI differences</h2>
              <span className="text-xs text-slate-400">{discrepancies.length} of {decided} decided</span>
            </div>
            {discrepancies.length === 0 ? (
              <p className="px-5 py-5 text-xs text-slate-400">No human decisions overrode the AI verdict. Differences appear here for review.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-200">
                      <th className="px-5 py-3 font-semibold">Candidate</th>
                      <th className="px-5 py-3 font-semibold">AI verdict</th>
                      <th className="px-5 py-3 font-semibold">Score</th>
                      <th className="px-5 py-3 font-semibold">Human decision</th>
                      <th className="px-5 py-3 font-semibold">Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {discrepancies.map(r => (
                      <tr key={r.id} className="border-b border-slate-100 last:border-0">
                        <td className="px-5 py-4 font-mono text-xs text-slate-700">{r.short}</td>
                        <td className="px-5 py-4"><VerdictBadge verdict={r.verdict} /></td>
                        <td className="px-5 py-4 font-mono text-slate-700">{r.score}</td>
                        <td className="px-5 py-4">
                          <Badge className={r.decision === 'APPROVE' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'}>
                            {r.decision}
                          </Badge>
                        </td>
                        <td className="px-5 py-4 text-xs text-slate-500">{discrepancyNote(r)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <div className="grid grid-cols-2 gap-6 max-lg:grid-cols-1">
            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <h3 className="text-[13px] font-semibold mb-4">Pipeline overview</h3>
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

            <div className="bg-white border border-slate-200 rounded-lg p-5">
              <h3 className="text-[13px] font-semibold mb-4">Scores by verdict</h3>
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