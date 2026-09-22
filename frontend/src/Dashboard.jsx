import { useEffect, useState } from 'react'
import { api } from './api.js'
import BlobMascot from './BlobMascot.jsx'

function LiveClock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t) }, [])
  const time = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })
  const date = now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
  return (
    <div className="text-right whitespace-nowrap">
      <div className="text-sm font-semibold text-slate-800 font-mono">{time}</div>
      <div className="text-[11px] text-slate-400">{date}</div>
    </div>
  )
}

function StatTile({ label, value, color, icon }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 flex items-center gap-4">
      <div className={`w-11 h-11 rounded-lg flex items-center justify-center text-lg ${color}`}>{icon}</div>
      <div>
        <div className="text-2xl font-bold font-mono tracking-tight text-slate-900">{value}</div>
        <div className="text-xs text-slate-500 font-medium mt-0.5">{label}</div>
      </div>
    </div>
  )
}

function QuickAction({ label, description, onClick, accent }) {
  return (
    <button onClick={onClick} className="text-left bg-white border border-slate-200 rounded-lg p-5 hover:border-brand-300 hover:bg-brand-50 transition-colors group">
      <div className={`w-9 h-9 rounded-md flex items-center justify-center text-sm font-bold mb-3 ${accent}`}>{label.charAt(0)}</div>
      <div className="text-sm font-semibold text-slate-800 group-hover:text-brand-700">{label}</div>
      <div className="text-xs text-slate-400 mt-1">{description}</div>
    </button>
  )
}

export default function Dashboard({ session, onNavigate }) {
  const [reviews, setReviews] = useState([])
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api('/api/reviews')
      .then(setReviews)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    api('/api/jobs').then(setJobs).catch(() => {})
  }, [])

  const total = reviews.length
  const scored = reviews.filter(r => r.score !== null)
  const avg = scored.length ? (scored.reduce((s, r) => s + r.score, 0) / scored.length).toFixed(1) : '—'
  const pending = reviews.filter(r => r.status === 'PENDING').length
  const approved = reviews.filter(r => r.decision === 'APPROVE').length
  const rejected = reviews.filter(r => r.decision === 'REJECT').length
  const openJobs = jobs.filter(j => j.status === 'OPEN').length
  const recent = [...reviews].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 5)

  const VERDICT_DOT = { STRONG_MATCH: 'bg-emerald-500', POSSIBLE_MATCH: 'bg-amber-500', WEAK_MATCH: 'bg-slate-300' }

  return (
    <div className="max-w-[1400px] mx-auto space-y-6">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-xl border border-slate-200 p-8" style={{ background: 'linear-gradient(135deg, #f0f5ff 0%, #ffffff 40%, #f8fafc 100%)' }}>
        {/* Colored blobs */}
        <div className="absolute -top-16 -right-16 w-[300px] h-[300px] bg-brand-400 rounded-full opacity-20" style={{ filter: 'blur(70px)' }} />
        <div className="absolute -bottom-24 -left-10 w-[280px] h-[280px] bg-emerald-400 rounded-full opacity-20" style={{ filter: 'blur(70px)' }} />
        <div className="absolute top-1/4 left-1/3 w-[220px] h-[220px] bg-amber-300 rounded-full opacity-20" style={{ filter: 'blur(60px)' }} />
        <div className="absolute -bottom-8 right-1/3 w-[200px] h-[200px] bg-brand-300 rounded-full opacity-20" style={{ filter: 'blur(60px)' }} />

        <div className="relative flex items-start justify-between">
          <div>
            <p className="text-[11px] font-bold tracking-widest uppercase text-brand-600 mb-2">High-trust recruiter workspace</p>
            <h1 className="text-3xl font-bold tracking-tight font-display text-slate-900 mb-2">
              {session.user.email.split('@')[0] ? `Welcome back, ${session.user.email.split('@')[0].replace(/\./g, ' ').replace(/\b\w/g, c => c.toUpperCase())}` : 'Welcome back'}
            </h1>
            <p className="text-sm text-slate-500 max-w-xl">
              Evidence first. Human decision. Screen CVs against verifiable requirements with verbatim quotes.
            </p>
          </div>
          <div className="flex items-center gap-5 shrink-0 relative z-10">
            <BlobMascot size={150} />
            <LiveClock />
          </div>
        </div>
        <div className="relative z-10 flex items-center gap-3 mt-6">
          <button onClick={() => onNavigate('upload')} className="btn-primary">Start screening</button>
          <button onClick={() => onNavigate('queue')} className="btn-ghost">View queue</button>
          <button onClick={() => onNavigate('analytics')} className="btn-ghost">Analytics</button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2 max-sm:grid-cols-1">
        <StatTile label="Total screened" value={loading ? '...' : total} color="bg-brand-50 text-brand-600" icon="#" />
        <StatTile label="Pending decision" value={loading ? '...' : pending} color="bg-amber-50 text-amber-600" icon="?" />
        <StatTile label="Approved" value={loading ? '...' : approved} color="bg-emerald-50 text-emerald-600" icon="+" />
        <StatTile label="Avg score" value={loading ? '...' : avg} color="bg-slate-100 text-slate-600" icon="/" />
      </div>

      <div className="grid grid-cols-[1fr_380px] gap-6 items-start max-lg:grid-cols-1">
        {/* Recent activity */}
        <section className="panel">
          <h2 className="panel-title">Recent activity</h2>
          {loading ? (
            <p className="text-sm text-slate-400 py-8 text-center">Loading...</p>
          ) : recent.length === 0 ? (
            <p className="text-sm text-slate-400 py-8 text-center">No reviews yet. Upload your first CV to get started.</p>
          ) : (
            <div className="space-y-3">
              {recent.map(r => (
                <div key={r.id} className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${VERDICT_DOT[r.verdict] || 'bg-slate-200'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-slate-700">{r.short}</span>
                      {r.verdict && <span className="text-[10px] uppercase font-semibold text-slate-400">{r.verdict.replace('_', ' ')}</span>}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {r.score !== null ? `Scored ${r.score}/100` : 'Pending'}
                      {r.decision && ` — ${r.decision === 'APPROVE' ? 'Approved' : 'Rejected'}`}
                    </div>
                  </div>
                  <span className="text-[11px] text-slate-400 shrink-0">{new Date(r.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Quick actions */}
        <div className="space-y-4">
          <h2 className="panel-title">Quick actions</h2>
          <QuickAction label="Screen CV" description="Upload one or more CVs for evidence-based scoring" onClick={() => onNavigate('upload')} accent="bg-brand-50 text-brand-600" />
          <QuickAction label="Candidate Queue" description="View all candidates, filter by status, open scorecards" onClick={() => onNavigate('queue')} accent="bg-emerald-50 text-emerald-600" />
          <QuickAction label="Analytics" description="Team metrics, verdict breakdowns, AI vs human discrepancies" onClick={() => onNavigate('analytics')} accent="bg-amber-50 text-amber-600" />
          <QuickAction label="Job Openings" description="Create jobs, manage rubrics, approve for screening" onClick={() => onNavigate('hrcontrols')} accent="bg-brand-50 text-brand-600" />
        </div>
      </div>
    </div>
  )
}
