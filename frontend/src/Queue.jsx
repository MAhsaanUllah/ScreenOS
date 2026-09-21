import { useEffect, useState } from 'react'
import { api } from './api.js'
import { Scorecard, VerdictBadge } from './Criterion.jsx'
import { PageHeader, EmptyState, Badge } from './ui.jsx'

const FILTERS = [
  { id: 'ALL', label: 'All' },
  { id: 'PENDING', label: 'Pending' },
  { id: 'SCORED', label: 'Scored' },
  { id: 'APPROVE', label: 'Approved' },
  { id: 'REJECT', label: 'Rejected' }
]

const STATUS_PILL = {
  PENDING: 'bg-slate-100 text-slate-600',
  SCORED: 'bg-blue-50 text-blue-700',
  APPROVE: 'bg-emerald-50 text-emerald-700',
  REJECT: 'bg-rose-50 text-rose-700'
}

export default function Queue() {
  const [reviews, setReviews] = useState([])
  const [filter, setFilter] = useState('ALL')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(null)
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    api('/api/reviews').then(setReviews).catch(err => alert(err.message))
  }, [])

  const shown = reviews.filter(r => filter === 'ALL' || r.status === filter)

  async function openReview(id) {
    setBusy(true); setDetail(null); setOpen(id)
    try {
      setDetail(await api(`/api/reviews/${id}`))
    } catch (err) {
      alert(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-[1400px] mx-auto">
      <PageHeader eyebrow="Team Screening" title="Candidate Queue"
        description="All candidate reviews in your organization. Candidates stay anonymous until a decision." />

      <div className="flex gap-2 mb-4">
        {FILTERS.map(f => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={`text-xs px-3 py-1.5 rounded-full border font-medium ${
              filter === f.id ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
            }`}
          >{f.label} {f.id === 'ALL' && `(${reviews.length})`}</button>
        ))}
      </div>

      {shown.length === 0 ? (
        <EmptyState icon="🗂️" title="No candidates here yet."
          description="Upload & screen your first CV to fill the queue." />
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-200">
                <th className="px-4 py-3 font-semibold">Candidate</th>
                <th className="px-4 py-3 font-semibold">Score</th>
                <th className="px-4 py-3 font-semibold">Verdict</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Uploaded</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {shown.map(r => (
                <tr key={r.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-700">{r.short}</td>
                  <td className="px-4 py-3 font-semibold">{r.score !== null ? <span className="font-mono">{r.score}<span className="text-slate-400">/100</span></span> : '—'}</td>
                  <td className="px-4 py-3">{r.verdict ? <VerdictBadge verdict={r.verdict} /> : <span className="text-slate-300">—</span>}</td>
                  <td className="px-4 py-3">
                    <Badge className={STATUS_PILL[r.status] || STATUS_PILL.PENDING}>{r.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{new Date(r.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => openReview(r.id)}
                      className="text-xs text-blue-600 font-medium hover:underline"
                    >{r.status === 'PENDING' ? 'View preview' : 'Open scorecard'}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {open && (
        <div className="fixed inset-0 bg-black/30 flex items-start justify-center p-6 z-50 overflow-y-auto" onClick={() => setOpen(null)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl max-w-3xl w-full mt-10" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 pt-5">
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-slate-500">{open}</span>
                {detail?.decision && <Badge className={STATUS_PILL[detail.decision]}>{detail.decision}</Badge>}
              </div>
              <button onClick={() => setOpen(null)} className="text-slate-400 hover:text-slate-700 text-lg leading-none" aria-label="Close">✕</button>
            </div>
            <div className="px-6 py-5">
              {busy ? (
                <p className="text-sm text-slate-500">Loading review...</p>
              ) : detail?.card ? (
                <div>
                  <Scorecard card={detail.card} />
                  {detail.reviewer_notes && (
                    <div className="mt-5 p-3.5 bg-slate-50 border border-slate-200 rounded-md">
                      <strong className="text-xs text-slate-500 uppercase block mb-1">Recruiter Notes</strong>
                      <p className="text-[13px] text-slate-900 whitespace-pre-wrap">{detail.reviewer_notes}</p>
                    </div>
                  )}
                  {detail.decided_at && <p className="text-xs text-slate-400 mt-3">Decided {new Date(detail.decided_at).toLocaleString()}</p>}
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Sanitized Candidate Text</label>
                  <pre className="text-xs leading-relaxed bg-slate-50 border border-slate-200 rounded-md p-4 whitespace-pre-wrap max-h-96 overflow-y-auto">{detail?.cleaned_text || 'Loading...'}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}