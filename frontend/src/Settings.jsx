import { useEffect, useState } from 'react'
import { api } from './api.js'
import { saveSession } from './session.js'
import { PageHeader, Alert } from './ui.jsx'

export default function Settings({ session, onSessionChange }) {
  const [org, setOrg] = useState(null)
  const [name, setName] = useState('')
  const [catalog, setCatalog] = useState([])
  const [configured, setConfigured] = useState([])
  const [drafts, setDrafts] = useState({})
  const [busy, setBusy] = useState(false)
  const [pass, setPass] = useState({ current: '', next: '' })
  const [passMsg, setPassMsg] = useState('')
  const isAdmin = session.role === 'ADMIN'

  useEffect(() => {
    api('/api/settings')
      .then(o => { setOrg(o); setName(o.name) })
      .catch(err => alert(err.message))
    api('/api/providers').then(setCatalog).catch(err => alert(err.message))
    api('/api/settings/llm').then(setConfigured).catch(err => alert(err.message))
  }, [])

  async function rename(e) {
    e.preventDefault(); setBusy(true)
    try {
      const next = await api('/api/settings/org', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      })
      setOrg(next)
      const nextSession = { ...session, org: { ...session.org, name } }
      saveSession(nextSession)
      onSessionChange(nextSession)
    } catch (err) {
      alert(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function changePassword(e) {
    e.preventDefault(); setBusy(true); setPassMsg('')
    try {
      await api('/api/settings/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: pass.current, new_password: pass.next })
      })
      setPass({ current: '', next: '' })
      setPassMsg('Password changed. Other devices signed out. This one stays signed in.')
    } catch (err) {
      setPassMsg(err.message)
    } finally {
      setBusy(false)
    }
  }

  function setDraft(provider, field, value) {
    setDrafts(prev => ({ ...prev, [provider]: { ...prev[provider], [field]: value } }))
  }

  async function save(providerId, needsKey) {
    setBusy(true)
    const d = drafts[providerId] || {}
    try {
      setConfigured(await api('/api/settings/llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: providerId, api_key: needsKey ? d.key || '' : '', model: d.model || '' })
      }))
      alert(`Saved ${providerId} provider settings.`)
    } catch (err) {
      alert(err.message)
    } finally {
      setBusy(false)
    }
  }

  const known = Object.fromEntries(configured.map(c => [c.provider, c]))

  return (
    <div className="max-w-[1400px] mx-auto">
      <PageHeader eyebrow="Workspace Configuration" title="Settings"
        description={isAdmin
          ? 'Manage organization profile, password and bring-your-own-key provider credentials.'
          : 'Only admins can change organization and provider settings. Your own password can always be changed.'} />

      <div className="flex flex-col gap-6 max-w-3xl">
        <section className="bg-white border border-slate-200 rounded-xl p-5">
          <h2 className="text-[15px] font-semibold mb-4">Organization</h2>
          {org && (
            <div className="flex flex-col gap-4">
              {isAdmin && (
                <form onSubmit={rename} className="flex gap-3 items-end">
                  <label className="flex-1 block">
                    <span className="block text-xs font-semibold text-slate-600 mb-1">Organization name</span>
                    <input value={name} onChange={e => setName(e.target.value)} maxLength={80} required
                      className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm" />
                  </label>
                  <button className="btn-primary" disabled={busy}>Rename</button>
                </form>
              )}
              <p className="text-xs text-slate-500">
                Created {new Date(org.created_at).toLocaleDateString()} · {org.members} member{org.members === 1 ? '' : 's'} · your role: {org.role}
              </p>
            </div>
          )}
        </section>

        <section className="bg-white border border-slate-200 rounded-xl p-5">
          <h2 className="text-[15px] font-semibold mb-4">Password</h2>
          {passMsg && <Alert tone={passMsg.startsWith('Password changed') ? 'success' : 'error'}>{passMsg}</Alert>}
          <form onSubmit={changePassword} className="flex flex-col gap-3">
            <input type="password" placeholder="Current password" minLength={8} required
              value={pass.current} onChange={e => setPass({ ...pass, current: e.target.value })}
              className="px-3 py-2 border border-slate-300 rounded-md text-sm" />
            <input type="password" placeholder="New password (min 8 characters)" minLength={8} required
              value={pass.next} onChange={e => setPass({ ...pass, next: e.target.value })}
              className="px-3 py-2 border border-slate-300 rounded-md text-sm" />
            <div className="flex items-center gap-3">
              <button className="btn-primary" disabled={busy}>Change password</button>
            </div>
          </form>
        </section>

        <section className="bg-white border border-slate-200 rounded-xl p-5">
          <h2 className="text-[15px] font-semibold mb-4">AI Provider Keys</h2>
          <p className="text-xs text-slate-500 mb-4">
            Keys are masked after saving and never shown again. Two configured providers are used in order, so the second acts as a fallback when one fails.
          </p>
          <div className="flex flex-col gap-3">
            {catalog.map(spec => {
              const entry = known[spec.id]
              return (
                <div key={spec.id} className="border border-slate-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <strong className="text-sm text-slate-900">{spec.label}</strong>
                    {entry ? (
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700">
                        {spec.needs_key ? `Key saved (${entry.hint})` : 'No key needed'} · {entry.model || spec.default_model}
                      </span>
                    ) : (
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-500">Not configured</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mb-3">Default model: {spec.default_model}</p>
                  {isAdmin && (
                    <div className="flex gap-3 max-sm:flex-col">
                      <input
                        type="password"
                        placeholder={spec.needs_key ? 'API key' : 'No key needed (local model)'}
                        disabled={!spec.needs_key}
                        value={drafts[spec.id]?.key || ''}
                        onChange={e => setDraft(spec.id, 'key', e.target.value)}
                        className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-sm"
                      />
                      <input
                        placeholder="Model name (default if blank)"
                        value={drafts[spec.id]?.model || ''}
                        onChange={e => setDraft(spec.id, 'model', e.target.value)}
                        className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-sm"
                      />
                      <button className="btn-primary" disabled={busy || (spec.needs_key && !drafts[spec.id]?.key)}
                        onClick={() => save(spec.id, spec.needs_key)}>Save</button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      </div>
    </div>
  )
}