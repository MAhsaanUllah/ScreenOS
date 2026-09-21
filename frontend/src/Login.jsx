import { useState } from 'react'
import { api } from './api.js'
import { saveSession } from './session.js'
import { Alert } from './ui.jsx'

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
          <div className="inline-flex items-center justify-center w-11 h-11 rounded-lg bg-brand-600 text-white text-lg font-bold font-display mb-4">S</div>
          <div className="text-2xl font-bold tracking-tight text-slate-900 font-display">SCREENOS</div>
          <p className="text-sm text-slate-500 mt-1">Fair & Evidence-Based Screening</p>
        </div>

        <form onSubmit={submit} className="bg-white border border-slate-200 rounded-lg p-6">
          {mode === 'register' && (
            <div className="mb-4">
              <label htmlFor="org-name" className="label">Organization name</label>
              <input
                id="org-name"
                value={orgName}
                onChange={e => setOrgName(e.target.value)}
                placeholder="Acme Corp"
                maxLength={80}
                required
                className="input"
              />
            </div>
          )}

          <div className="mb-4">
            <label htmlFor="email" className="label">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              className="input"
            />
          </div>

          <div className="mb-4">
            <label htmlFor="password" className="label">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              minLength={8}
              required
              className="input"
            />
          </div>

          {error && <Alert tone="error">{error}</Alert>}

          <button type="submit" disabled={busy} className="btn-primary">
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