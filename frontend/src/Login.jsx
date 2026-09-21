import { useState } from 'react'
import { api } from './api.js'
import { saveSession } from './session.js'

export default function Login({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [orgName, setOrgName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const path = mode === 'login' ? '/api/auth/login' : '/api/auth/register'
      const body = mode === 'login'
        ? { email, password }
        : { org_name: orgName, email, password }
      const session = await api(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      saveSession(session)
      onLogin(session)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-2xl font-bold tracking-tight text-slate-900">SCREENOS</div>
          <p className="text-sm text-slate-500 mt-1">Fair & Evidence-Based Screening</p>
        </div>

        <form onSubmit={submit} className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          {mode === 'register' && (
            <label className="block text-sm font-semibold text-slate-900 mb-1.5">Organization name</label>
          )}
          {mode === 'register' && (
            <input
              value={orgName}
              onChange={e => setOrgName(e.target.value)}
              placeholder="Acme Corp"
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm mb-4 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            />
          )}

          <label className="block text-sm font-semibold text-slate-900 mb-1.5">Email</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm mb-4 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
          />

          <label className="block text-sm font-semibold text-slate-900 mb-1.5">Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
            className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm mb-4 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
          />

          {error && <p role="alert" className="text-sm text-red-600 mb-4">{error}</p>}

          <button type="submit" disabled={busy} className="w-full bg-blue-600 text-white text-sm font-semibold px-4 py-2.5 rounded-md hover:bg-blue-700 disabled:opacity-50">
            {busy ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create workspace'}
          </button>

          <button
            type="button"
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}
            className="w-full text-xs text-blue-600 underline mt-4"
          >
            {mode === 'login' ? 'New team? Create a workspace' : 'Already have an account? Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}