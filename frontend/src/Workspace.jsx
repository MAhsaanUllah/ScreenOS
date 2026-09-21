import { useState } from 'react'
import Screening from './Screening.jsx'
import Queue from './Queue.jsx'
import Analytics from './Analytics.jsx'
import Rubrics from './Rubrics.jsx'
import Team from './Team.jsx'
import Settings from './Settings.jsx'
import { saveSession } from './session.js'
import { api } from './api.js'

const NAV = [
  { id: 'upload', label: 'Upload & Screening', ready: true },
  { id: 'queue', label: 'Candidate Queue', ready: true },
  { id: 'analytics', label: 'Analytics', ready: true },
  { id: 'rubrics', label: 'Rubrics', ready: true },
  { id: 'team', label: 'Team & Roles', ready: true },
  { id: 'settings', label: 'Settings', ready: true }
]

export default function Workspace({ session, onSwitch, onSessionChange }) {
  const [view, setView] = useState('upload')
  const [error, setError] = useState('')

  async function switchOrg(orgId) {
    if (orgId === session.org.id || error) return
    try {
      const next = await api('/api/auth/switch-org', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ org_id: orgId })
      })
      saveSession(next)
      onSessionChange(next)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <div className="h-1 bg-brand-600" />
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <strong className="text-[15px] font-bold tracking-tight font-display">SCREENOS</strong>
          <span className="text-[13px] text-slate-400">/ {session.org.name}</span>
        </div>

        <div className="flex items-center gap-3">
          {session.orgs.length > 1 && (
            <select
              value={session.org.id}
              onChange={e => switchOrg(e.target.value)}
              className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-slate-50 focus:outline-none focus:border-brand-500"
              title="Switch organization"
            >
              {session.orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          )}
          {error && <span className="text-xs text-red-600">{error}</span>}
          <div className="flex items-center gap-2">
            <span className="w-7 h-7 rounded-full bg-brand-600 text-white text-xs font-semibold flex items-center justify-center">
              {session.user.email.charAt(0).toUpperCase()}
            </span>
            <button onClick={onSwitch} className="text-xs text-slate-500 hover:text-slate-900">Sign out</button>
          </div>
        </div>
      </header>

      <div className="flex flex-1">
        <nav className="w-52 border-r border-slate-200 bg-white p-3 flex flex-col gap-1 shrink-0">
          {NAV.map(item => item.ready ? (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={`text-left text-sm px-3 py-2 rounded-md font-medium ${
                view === item.id ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >{item.label}</button>
          ) : (
            <div
              key={item.id}
              className="text-left text-sm px-3 py-2 rounded-md text-slate-400 flex items-center justify-between cursor-not-allowed"
            >
              <span>{item.label}</span>
              <span className="text-[10px] uppercase text-slate-300">Phase {item.phase}</span>
            </div>
          ))}
        </nav>

        <main className="flex-1 p-6 overflow-auto">
          {view === 'upload' && <Screening key={session.org.id} onNavigate={setView} />}
          {view === 'queue' && <Queue key={session.org.id} />}
          {view === 'analytics' && <Analytics key={session.org.id} />}
          {view === 'rubrics' && <Rubrics />}
          {view === 'team' && <Team key={session.org.id} session={session} />}
          {view === 'settings' && <Settings key={session.org.id} session={session} onSessionChange={onSessionChange} />}
        </main>
      </div>
    </div>
  )
}